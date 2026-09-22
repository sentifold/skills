"""Behavioral regression tests; all provider CLIs are local fakes, never models."""
from __future__ import annotations

import json
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('provider_runtime_fixture', ROOT / 'lib/provider_runtime.py')
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)
FAKE = r'''
import json, os, pathlib, signal, subprocess, sys, time
args = sys.argv[1:]
mode = os.environ.get('FAKE_MODE', 'success')
record = pathlib.Path(os.environ['FAKE_RECORD'])
with record.open('a') as stream:
    stream.write(json.dumps({'argv': args}) + '\n')
if args == ['--version']:
    if mode == 'version-timeout':
        time.sleep(60)
    if mode == 'broken-version':
        sys.exit(19)
    print('fixture-cli 1.0')
    sys.exit(0)
if args in (['--help'], ['exec', '--help']):
    if mode == 'old-version':
        print('--model')
    else:
        print('--ephemeral --sandbox --model --output-last-message --no-session-persistence '
              '--output-format --max-turns --permission-mode --allowedTools --tools --effort '
              '--strict-mcp-config --mcp-config --disable-slash-commands --no-chrome')
    sys.exit(0)
if args == ['auth', 'status', '--json']:
    print(json.dumps({'loggedIn': True}))
    sys.exit(0)
if mode in ('hang', 'orphan'):
    if mode == 'orphan':
        child = subprocess.Popen([sys.executable, '-c',
            'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'])
        pathlib.Path(os.environ['FAKE_DESCENDANT']).write_text(str(child.pid))
    pathlib.Path(os.environ['FAKE_STARTED']).write_text(str(os.getpid()))
    time.sleep(60)
if mode == 'fail':
    print('OLD_EXIT CODEX_RUN_EXIT rc=0')
    sys.exit(42)
if mode == 'missing':
    if '-p' in args:
        print(json.dumps({'subtype': 'success'}))
    sys.exit(0)
stdin = sys.stdin.read()
payload = {'argv': args, 'cwd': os.getcwd(), 'stdin': stdin,
           'key_vars': {k: k in os.environ for k in ('OPENAI_API_KEY', 'CODEX_API_KEY',
               'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL')},
           'codex_home': os.environ.get('CODEX_HOME')}
if '-p' in args:
    envelope = {'subtype': 'success', 'result': json.dumps(payload),
                'usage': {'input_tokens': 10, 'output_tokens': 20}}
    if mode == 'denied':
        envelope['permission_denials'] = [{'tool_name': 'Bash', 'tool_input': {'command': 'SECRET'}}]
    if mode == 'envelope-fail':
        envelope['subtype'] = 'error_max_turns'
    print(json.dumps(envelope))
else:
    output = pathlib.Path(args[args.index('-o') + 1])
    output.write_text(json.dumps(payload))
    print('provider progress only')
'''


@unittest.skipUnless(os.name == 'posix', 'requires POSIX process groups')
class CrossProviderHelpersTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='provider tests ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.caller = self.root / 'caller repo'
        self.target = self.root / 'target repo'
        self.bin = self.root / 'fake cli'
        for path in (self.caller, self.target, self.bin):
            path.mkdir()
        self.links = self.root / 'global skills'
        self.links.mkdir()
        for provider in ('codex', 'claude'):
            (self.links / provider).symlink_to(ROOT / 'skills' / provider, target_is_directory=True)
            path = self.bin / provider
            path.write_text(f'#!{sys.executable}\n' + FAKE)
            path.chmod(0o755)
        (self.bin / 'python3').symlink_to(sys.executable)
        self.record = self.root / 'calls.jsonl'
        self.config = self.root / 'config.toml'
        self.config.write_text('service_tier = "fast"\nweb_search = "live"\n[features]\nfast_mode = false\n')
        # A regression in executable selection must never fall through to a real
        # developer model CLI. System paths supply only shell/process utilities.
        self.env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.defpath,
                    'TMPDIR': str(self.root), 'FAKE_RECORD': str(self.record),
                    'FAKE_STARTED': str(self.root / 'started'),
                    'FAKE_DESCENDANT': str(self.root / 'descendant'), 'CODEX_HOME': str(self.root),
                    'OPENAI_API_KEY': 'test-only', 'CODEX_API_KEY': 'test-only',
                    'ANTHROPIC_API_KEY': 'test-only', 'ANTHROPIC_AUTH_TOKEN': 'test-only',
                    'ANTHROPIC_BASE_URL': 'test-only'}
        self.env.pop('CODEX_BIN', None)
        self.env.pop('CLAUDE_BIN', None)

    def command(self, provider, *options, model='explicit-model', prompt=True):
        return ['bash', str(self.links / provider / 'scripts' / f'{provider}-ephemeral.sh'),
                *(['--model', model] if model else []), *options,
                *(['--', 'task with spaces and $literal'] if prompt else [])]

    def run_helper(self, provider, *options, mode='success', stdin=None, model='explicit-model'):
        return subprocess.run(self.command(provider, *options, model=model, prompt=stdin is None),
                              input=stdin or '', cwd=self.caller, env={**self.env, 'FAKE_MODE': mode},
                              capture_output=True, text=True, timeout=12)

    def receipt(self, result):
        start = next(json.loads(line.split(' ', 1)[1]) for line in result.stdout.splitlines()
                     if '_RUN_START ' in line)
        return json.loads(Path(start['receipt']).read_text())

    def payload(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(Path(self.receipt(result)['output']).read_text())

    def watch(self, provider, path, *args):
        return subprocess.run(['bash', str(self.links / provider / 'scripts' / f'{provider}-watch.sh'),
                               str(path), *args], capture_output=True, text=True, timeout=5)

    def test_model_effort_cwd_symlinks_and_key_environment(self):
        for provider in ('codex', 'claude'):
            for target in (None, self.target):
                for effort in (None, 'xhigh'):
                    with self.subTest(provider=provider, target=target, effort=effort):
                        flags = ['--cd', str(target)] if target else []
                        if effort:
                            flags += ['--effort', effort]
                        result = self.run_helper(provider, *flags)
                        payload = self.payload(result)
                        args = payload['argv']
                        self.assertEqual(args[args.index('--model') + 1], 'explicit-model')
                        self.assertEqual(payload['cwd'], str(target if provider == 'claude' and target else self.caller))
                        self.assertEqual(payload['stdin'], '')
                        self.assertEqual(args[-1], 'task with spaces and $literal')
                        self.assertEqual(payload['codex_home'], str(self.root))
                        if provider == 'codex':
                            self.assertIn('--ephemeral', args)
                            self.assertEqual('model_reasoning_effort=xhigh' in args, bool(effort))
                            self.assertIn('mcp_servers.node_repl.enabled=false', args)
                            self.assertIn('sandbox_workspace_write.network_access=false', args)
                            self.assertEqual(args[args.index('--sandbox') + 1], 'read-only')
                            for key in ('OPENAI_API_KEY', 'CODEX_API_KEY'):
                                self.assertFalse(payload['key_vars'][key])
                            if target:
                                self.assertEqual(args[args.index('--cd') + 1], str(target))
                        else:
                            self.assertIn('--no-session-persistence', args)
                            self.assertEqual('--effort' in args, bool(effort))
                            self.assertEqual(args[args.index('--permission-mode') + 1], 'dontAsk')
                            for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL'):
                                self.assertFalse(payload['key_vars'][key])

    def test_explicit_model_required_for_both(self):
        for provider in ('codex', 'claude'):
            result = self.run_helper(provider, model=None)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('_RUN_START', result.stdout)
        self.assertFalse(self.record.exists())

    def test_speed_options_do_not_mutate_config_and_keep_review_write_contract(self):
        original = self.config.read_bytes()
        for speed, expected in (([], None), (['--fast'], 'fast'), (['--no-fast'], 'default'), (['--nofast'], 'default')):
            for mode in ([], ['--review'], ['--sandbox', 'workspace-write', '--network', '--json']):
                with self.subTest(speed=speed, mode=mode):
                    args = self.payload(self.run_helper('codex', *speed, *mode, '--effort', 'max'))['argv']
                    config = dict(args[i + 1].split('=', 1) for i, value in enumerate(args) if value == '-c')
                    self.assertEqual(config.get('service_tier'), expected)
                    self.assertEqual(config.get('features.fast_mode'), 'true' if expected == 'fast' else None)
                    self.assertEqual(config['model_reasoning_effort'], 'max')
                    self.assertEqual(config['sandbox_workspace_write.network_access'], str('--network' in mode).lower())
                    if '--review' in mode:
                        self.assertEqual(args[-2], 'review')
                    self.assertEqual(self.config.read_bytes(), original)
        for flags in (('--fast', '--no-fast'), ('--nofast', '--fast')):
            result = self.run_helper('codex', *flags)
            self.assertEqual(result.returncode, 2)
            self.assertIn('mutually exclusive', result.stderr)
            self.assertNotIn('_RUN_START', result.stdout)

    def test_stdin_and_explicit_search_overrides(self):
        for provider in ('codex', 'claude'):
            flags = ['--no-fast', '--nofast'] if provider == 'codex' else []
            payload = self.payload(self.run_helper(provider, *flags, '--no-search', stdin='stdin prompt\n'))
            self.assertEqual(payload['stdin'], 'stdin prompt\n')
            if provider == 'codex':
                self.assertIn('web_search="disabled"', payload['argv'])
                self.assertNotIn('--search', payload['argv'])
                self.assertEqual(payload['argv'].count('service_tier=default'), 1)
            else:
                self.assertNotIn('WebSearch', payload['argv'])
                self.assertNotIn('WebFetch', payload['argv'])
        opted = self.payload(self.run_helper('codex', '--browser-mcp'))['argv']
        self.assertNotIn('mcp_servers.node_repl.enabled=false', opted)
        inherited = self.payload(self.run_helper('claude', '--auth', 'inherit'))
        self.assertTrue(inherited['key_vars']['ANTHROPIC_API_KEY'])

    def test_selected_cli_never_skips_broken_wrapper_and_reports_capabilities(self):
        for provider in ('codex', 'claude'):
            selected = self.bin / provider
            for mode, code in (('broken-version', 19), ('old-version', 2)):
                result = self.run_helper(provider, '--cli', str(selected), mode=mode)
                self.assertEqual(result.returncode, code)
                self.assertEqual(self.receipt(result)['cli'], str(selected))
                self.assertNotEqual(self.receipt(result)['status'], 'DONE')
                self.assertIn('Selected', result.stderr)
            self.env[f'{provider.upper()}_BIN'] = str(selected)
            self.assertEqual(self.receipt(self.run_helper(provider))['cli'], str(selected))
        missing = self.run_helper('codex', '--companion', str(self.root / 'missing host'))
        self.assertEqual(missing.returncode, 2)
        self.assertIn('companion', missing.stderr)

    def test_unique_run_results_stale_output_and_exit_cannot_pass(self):
        for provider in ('codex', 'claude'):
            old = self.run_helper(provider)
            old_receipt = self.receipt(old)
            stale = self.root / f'{provider} old success.txt'
            stale.write_text('OLD SUCCESS')
            refused = self.run_helper(provider, '--out', str(stale))
            self.assertEqual(refused.returncode, 2)
            self.assertEqual(stale.read_text(), 'OLD SUCCESS')
            new = self.run_helper(provider, mode='fail')
            self.assertEqual(new.returncode, 42)
            self.assertNotEqual(old_receipt['run_id'], self.receipt(new)['run_id'])
            self.assertNotEqual(old_receipt['result'], self.receipt(new)['result'])
            log = self.root / f'{provider}.log'
            log.write_text(old.stdout + new.stdout)
            verdict = self.watch(provider, log)
            self.assertNotEqual(verdict.returncode, 0)
            self.assertTrue(verdict.stdout.startswith('FAILED '), verdict.stdout)
            self.assertIn('rc=42', verdict.stdout)
            self.assertEqual(self.watch(provider, log, '--run-id', old_receipt['run_id']).returncode, 0)

    def test_success_requires_complete_intact_output_and_clean_claude_envelope(self):
        for provider in ('codex', 'claude'):
            target = self.root / f'{provider} export.md'
            result = self.run_helper(provider, '--out', str(target))
            receipt = self.receipt(result)
            self.assertEqual(self.watch(provider, receipt['receipt']).returncode, 0)
            target.write_text('modified after completion')
            verdict = self.watch(provider, receipt['receipt'])
            self.assertEqual(verdict.returncode, 1)
            self.assertTrue(verdict.stdout.startswith('MISSING '))
            missing = self.run_helper(provider, mode='missing')
            self.assertEqual(missing.returncode, 4)
            self.assertEqual(self.receipt(missing)['status'], 'MISSING')
        for mode in ('denied', 'envelope-fail'):
            result = self.run_helper('claude', mode=mode)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn('SECRET', result.stderr)

    def wait_path(self, path):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            if path.exists():
                return int(path.read_text())
            time.sleep(.03)
        self.fail(f'fixture did not start: {path}')

    def assert_stopped(self, pid):
        result = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True)
        self.assertTrue(not result.stdout.strip() or result.stdout.strip().startswith('Z'),
                        f'process {pid} remains running: {result.stdout}')

    def test_timeout_cleans_descendants_and_bounded_preflight(self):
        for provider in ('codex', 'claude'):
            descendant = Path(self.env['FAKE_DESCENDANT'])
            descendant.unlink(missing_ok=True)
            result = self.run_helper(provider, '--timeout', '0.6', mode='orphan')
            self.assertEqual(result.returncode, 124, result.stderr)
            self.assertEqual(self.receipt(result)['status'], 'TIMEOUT')
            self.assert_stopped(self.wait_path(descendant))
            probe = self.run_helper(provider, '--preflight-timeout', '0.2', mode='version-timeout')
            self.assertEqual(probe.returncode, 124)
            self.assertEqual(self.receipt(probe)['phase'], 'version')

    def test_term_int_terminate_owned_process_group_and_watch_running_is_not_success(self):
        for provider in ('codex', 'claude'):
            for sig in (signal.SIGTERM, signal.SIGINT):
                with self.subTest(provider=provider, sig=sig):
                    for key in ('FAKE_STARTED', 'FAKE_DESCENDANT'):
                        Path(self.env[key]).unlink(missing_ok=True)
                    log = self.root / f'{provider}-{sig}.log'
                    with log.open('w') as output:
                        process = subprocess.Popen(self.command(provider, '--timeout', '10'), cwd=self.caller,
                                                   env={**self.env, 'FAKE_MODE': 'orphan'},
                                                   stdout=output, stderr=subprocess.PIPE, text=True,
                                                   start_new_session=True)
                        try:
                            leader = self.wait_path(Path(self.env['FAKE_STARTED']))
                            descendant = self.wait_path(Path(self.env['FAKE_DESCENDANT']))
                            running = self.watch(provider, log)
                            self.assertEqual(running.returncode, 10, running.stdout)
                            process.send_signal(sig)
                            _, stderr = process.communicate(timeout=6)
                            self.assertEqual(process.returncode, 128 + sig, stderr)
                        finally:
                            if process.poll() is None:
                                process.kill()
                                process.wait()
                        self.assert_stopped(leader)
                        self.assert_stopped(descendant)
                    stopped = self.watch(provider, log)
                    self.assertEqual(stopped.returncode, 1)
                    self.assertTrue(stopped.stdout.startswith('CANCELLED '), stopped.stdout)

    def test_open_stdin_is_bounded_by_overall_deadline(self):
        for provider in ('codex', 'claude'):
            process = subprocess.Popen(self.command(provider, '--timeout', '0.5', prompt=False),
                                       cwd=self.caller, env=self.env, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                # Keep the input pipe open without writing; communicate() would
                # close it and miss the original background-stdin failure mode.
                process.wait(timeout=5)
                stdout = process.stdout.read()
                stderr = process.stderr.read()
                self.assertEqual(process.returncode, 124, stderr)
                start = json.loads(stdout.splitlines()[0].split(' ', 1)[1])
                receipt = json.loads(Path(start['receipt']).read_text())
                self.assertEqual(receipt['status'], 'TIMEOUT')
                self.assert_stopped(receipt['child_pid'])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close()

    def test_supervisor_heartbeat_and_legacy_exit_do_not_count_as_provider_progress(self):
        for provider in ('codex', 'claude'):
            result = self.run_helper(provider)
            receipt = self.receipt(result)
            receipt.update(status='RUNNING', exit_code=None, pid=os.getpid(), deadline_at=time.time() + 10)
            for field in ('stdout', 'stderr'):
                os.utime(receipt[field], (time.time() - 120, time.time() - 120))
            Path(receipt['receipt']).write_text(json.dumps(receipt))
            log = self.root / f'{provider}-heartbeat.log'
            log.write_text(result.stdout + f'WATCHDOG: heartbeat\n{provider.upper()}_RUN_EXIT rc=0\n')
            verdict = self.watch(provider, log, '1')
            self.assertEqual(verdict.returncode, 10)
            self.assertTrue(verdict.stdout.startswith('QUIET '), verdict.stdout)

    def lifecycle_fixture(self):
        root = self.root / 'lifecycle'
        root.mkdir()
        args = RUNTIME.parser('codex').parse_args(['--model', 'fixture-model'])
        with mock.patch.object(RUNTIME.tempfile, 'mkdtemp', return_value=str(root)):
            return RUNTIME.Run('codex', args)

    def test_leader_exit_is_detected_without_waitid_and_leaves_it_unreaped(self):
        # macOS interpreters before 3.13 have no os.waitid; the ps path must agree.
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        try:
            with mock.patch.object(RUNTIME, 'LEADER_WAITID', None):
                self.assertFalse(RUNTIME.Run.child_exited(child))
                child.terminate()
                until = time.monotonic() + 3
                while not RUNTIME.Run.child_exited(child) and time.monotonic() < until:
                    time.sleep(.01)
                self.assertTrue(RUNTIME.Run.child_exited(child))
                self.assertIsNone(child.returncode)
                child.wait(timeout=3)
                self.assertTrue(RUNTIME.Run.child_exited(child))
        finally:
            child.kill()
            child.wait(timeout=3)

    def test_darwin_zombie_only_group_eperm_is_verified_before_reaping(self):
        run = self.lifecycle_fixture()
        child = subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True)
        run.child = child
        try:
            until = time.monotonic() + 3
            while not RUNTIME.Run.child_exited(child) and time.monotonic() < until:
                time.sleep(.01)
            self.assertTrue(RUNTIME.Run.child_exited(child))
            # Darwin really returns EPERM here; force that result on Linux too.
            with mock.patch.object(RUNTIME.os, 'killpg', side_effect=PermissionError(1, 'Operation not permitted')):
                run.cleanup()
            self.assertIsNone(run.child)
            self.assertEqual(child.returncode, 0)
        finally:
            child.wait(timeout=3)

    def test_live_group_permission_failure_is_terminal_not_silently_successful(self):
        run = self.lifecycle_fixture()
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        run.child = child
        try:
            with mock.patch.object(run, 'perform', return_value=None), \
                 mock.patch.object(RUNTIME.os, 'killpg', side_effect=PermissionError(1, 'Operation not permitted')), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = run.run()
            self.assertEqual(code, 125)
            receipt = json.loads(run.receipt.read_text())
            self.assertEqual(receipt['status'], 'CLEANUP_FAILED')
            self.assertIn(child.pid, receipt['cleanup_live_pids'])
            self.assertIsNone(child.poll())
        finally:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()

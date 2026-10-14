"""Behavioral regression tests; all provider CLIs are local fakes, never models."""
from __future__ import annotations

import json
import contextlib
import importlib.util
import io
import os
from pathlib import Path
if os.name == 'posix':
    import pty
import shutil
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
if mode == 'null-result':
    print(json.dumps({'subtype': 'success', 'result': None, 'usage': {}}))
    sys.exit(0)
if mode.startswith('leftover'):
    child = subprocess.Popen([sys.executable, '-c',
        'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'])
    pathlib.Path(os.environ['FAKE_DESCENDANT']).write_text(str(child.pid))
    if mode == 'leftover-fail':
        sys.exit(42)
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
            if os.name == 'nt':
                import _winapi
                _winapi.CreateJunction(str(ROOT / 'skills' / provider), str(self.links / provider))
                (self.bin / f'{provider}.py').write_text(FAKE)
                (self.bin / f'{provider}.cmd').write_text(
                    f'@"{sys.executable}" "%~dp0{provider}.py" %*\n')
            else:
                (self.links / provider).symlink_to(ROOT / 'skills' / provider, target_is_directory=True)
                path = self.bin / provider
                path.write_text(f'#!{sys.executable}\n' + FAKE)
                path.chmod(0o755)
        if os.name == 'nt':
            (self.bin / 'python3').write_text(
                '#!/bin/sh\nexec "' + Path(sys.executable).as_posix() + '" "$@"\n')
        else:
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
        if os.name == 'nt':
            self.env['PATH'] += os.pathsep + str(Path(shutil.which('bash')).parent)
            self.env.update(TEMP=str(self.root), TMP=str(self.root))
        self.env.pop('CODEX_BIN', None)
        self.env.pop('CLAUDE_BIN', None)

    def command(self, provider, *options, model='explicit-model', prompt=True):
        return [shutil.which('bash'), str(self.links / provider / 'scripts' / f'{provider}-ephemeral.sh'),
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
        return subprocess.run([shutil.which('bash'), str(self.links / provider / 'scripts' / f'{provider}-watch.sh'),
                               str(path), *args], env=self.env, capture_output=True, text=True, timeout=5)

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
                        if os.name == 'nt':
                            self.assertEqual(payload['stdin'], 'task with spaces and $literal')
                            self.assertNotIn('task with spaces and $literal', args)
                        else:
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
                self.assertIn("web_search='disabled'" if os.name == 'nt' else 'web_search="disabled"', payload['argv'])
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
            selected = self.bin / (f'{provider}.cmd' if os.name == 'nt' else provider)
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
                value = path.read_text()
                if value:
                    return int(value)
            time.sleep(.03)
        self.fail(f'fixture did not start: {path}')

    def assert_stopped(self, pid):
        if os.name == 'nt':
            self.assertFalse(RUNTIME.alive(pid), f'process {pid} remains running')
            return
        result = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True)
        self.assertTrue(not result.stdout.strip() or result.stdout.strip().startswith('Z'),
                        f'process {pid} remains running: {result.stdout}')

    def test_timeout_cleans_descendants_and_bounded_preflight(self):
        for provider in ('codex', 'claude'):
            descendant = Path(self.env['FAKE_DESCENDANT'])
            descendant.unlink(missing_ok=True)
            # Native Windows must start two .cmd/Python probes before the orphan fixture.
            timeout = '4' if os.name == 'nt' else '0.6'
            result = self.run_helper(provider, '--timeout', timeout, mode='orphan')
            self.assertEqual(result.returncode, 124, result.stderr)
            self.assertEqual(self.receipt(result)['status'], 'TIMEOUT')
            self.assert_stopped(self.wait_path(descendant))
            probe = self.run_helper(provider, '--preflight-timeout', '0.2', mode='version-timeout')
            self.assertEqual(probe.returncode, 124)
            self.assertEqual(self.receipt(probe)['phase'], 'version')

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX signals, ps or pty')
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
        args = RUNTIME.parser('codex').parse_args(['--model', 'fixture-model', '--', 'fixture prompt'])
        return RUNTIME.Run('codex', args)

    def run_quietly(self, run):
        root = self.root / f'lifecycle-{run.run_id}'
        root.mkdir()
        with mock.patch.object(RUNTIME.tempfile, 'mkdtemp', return_value=str(root)), \
             contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()):
            code = run.run()
        return code, stdout.getvalue()

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX signals, ps or pty')
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

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX signals, ps or pty')
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

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX signals, ps or pty')
    def test_live_group_permission_failure_is_terminal_not_silently_successful(self):
        run = self.lifecycle_fixture()
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        run.child = child
        try:
            with mock.patch.object(run, 'perform', return_value=None), \
                 mock.patch.object(RUNTIME.os, 'killpg', side_effect=PermissionError(1, 'Operation not permitted')):
                code, _ = self.run_quietly(run)
            self.assertEqual(code, 125)
            receipt = json.loads(run.receipt.read_text())
            self.assertEqual(receipt['status'], 'CLEANUP_FAILED')
            self.assertIn(child.pid, receipt['cleanup_live_pids'])
            self.assertIsNone(child.poll())
        finally:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=3)

    def test_null_claude_result_is_missing_not_a_crash(self):
        result = self.run_helper('claude', mode='null-result')
        self.assertEqual(result.returncode, 4, result.stderr)
        receipt = self.receipt(result)
        self.assertEqual(receipt['status'], 'MISSING')
        self.assertNotIn('AttributeError', receipt['diagnostic'])
        self.assertNotIn('Traceback', result.stderr)

    def test_leftover_descendant_after_leader_exit_keeps_child_rc(self):
        descendant = Path(self.env['FAKE_DESCENDANT'])
        for provider in ('codex', 'claude'):
            for mode, code in (('leftover', 0), ('leftover-fail', 42)):
                with self.subTest(provider=provider, mode=mode):
                    descendant.unlink(missing_ok=True)
                    result = self.run_helper(provider, mode=mode)
                    self.assertEqual(result.returncode, code, result.stderr)
                    receipt = self.receipt(result)
                    self.assertEqual(receipt['status'], 'DONE' if code == 0 else 'FAILED')
                    self.assertNotIn('cleanup_warning', receipt)
                    self.assert_stopped(self.wait_path(descendant))

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX signals, ps or pty')
    def test_unverifiable_cleanup_after_successful_exit_is_a_warning(self):
        real_ps = shutil.which('ps', path=os.defpath)
        fake_ps = self.bin / 'ps'
        # Group listing fails as if procps were missing; the leader-state probe still works.
        fake_ps.write_text('#!/bin/sh\ncase "$*" in *-axo*) exit 1;; esac\nexec ' + real_ps + ' "$@"\n')
        fake_ps.chmod(0o755)
        self.addCleanup(fake_ps.unlink)
        descendant = Path(self.env['FAKE_DESCENDANT'])
        descendant.unlink(missing_ok=True)
        result = self.run_helper('codex', mode='leftover')
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = self.receipt(result)
        self.assertEqual(receipt['status'], 'DONE')
        self.assertIn('Cannot verify cleanup', receipt['cleanup_warning'])
        self.assert_stopped(self.wait_path(descendant))
        self.assertEqual(self.watch('codex', receipt['receipt']).returncode, 0)

    def stale_run_dir(self, provider, status, age_days, **fields):
        run_id = os.urandom(8).hex()
        root = self.root / f'{provider}-{run_id}-stale'
        root.mkdir()
        finished = time.time() - age_days * 86400
        receipt = dict(schema=1, provider=provider, run_id=run_id, status=status,
                       finished_at=finished, **fields)
        (root / 'receipt.json').write_text(json.dumps(receipt))
        (root / 'provider.stdout').write_text('transcript')
        return root

    def test_finished_run_dirs_older_than_retention_are_collected(self):
        old_done = self.stale_run_dir('codex', 'DONE', 8)
        old_failed = self.stale_run_dir('codex', 'FAILED', 8)
        recent_done = self.stale_run_dir('codex', 'DONE', 6)
        old_running = self.stale_run_dir('codex', 'RUNNING', 8)
        old_kept = self.stale_run_dir('codex', 'DONE', 8, keep=True)
        other_provider = self.stale_run_dir('claude', 'DONE', 8)
        foreign = self.root / 'codex-not-a-run'
        foreign.mkdir()
        (foreign / 'receipt.json').write_text(json.dumps(dict(schema=1, provider='codex', run_id='x',
                                                              status='DONE', finished_at=0)))
        result = self.run_helper('codex', '--keep')
        receipt = self.receipt(result)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(receipt['collected_run_dirs'], 2)
        self.assertTrue(receipt['keep'])
        for path in (old_done, old_failed):
            self.assertFalse(path.exists(), path)
        for path in (recent_done, old_running, old_kept, other_provider, foreign, Path(receipt['receipt']).parent):
            self.assertTrue(path.exists(), path)

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX signals, ps or pty')
    def test_empty_prompt_argument_falls_back_to_stdin_unless_stdin_is_a_terminal(self):
        for provider in ('codex', 'claude'):
            with self.subTest(provider=provider):
                command = self.command(provider, prompt=False) + ['--', '']
                piped = subprocess.run(command, input='piped prompt\n', cwd=self.caller,
                                       env={**self.env, 'FAKE_MODE': 'success'},
                                       capture_output=True, text=True, timeout=12)
                self.assertEqual(piped.returncode, 0, piped.stderr)
                self.assertEqual(json.loads(Path(self.receipt(piped)['output']).read_text())['stdin'],
                                 'piped prompt\n')
                leader, follower = pty.openpty()
                try:
                    terminal = subprocess.run(command, stdin=follower, cwd=self.caller,
                                              env={**self.env, 'FAKE_MODE': 'success'},
                                              capture_output=True, text=True, timeout=12)
                finally:
                    os.close(leader)
                    os.close(follower)
                self.assertEqual(terminal.returncode, 2)
                self.assertIn('Provide a prompt', terminal.stderr)
                self.assertNotIn('_RUN_START', terminal.stdout)

    def test_usage_failures_create_no_run_directory(self):
        before = set(self.root.iterdir())
        taken = self.root / 'taken.md'
        taken.write_text('taken')
        for provider in ('codex', 'claude'):
            self.assertEqual(self.run_helper(provider, '--out', str(taken)).returncode, 2)
        self.assertEqual(self.run_helper('claude', '--output-schema', str(self.root / 'absent.json')).returncode, 2)
        self.assertEqual(set(self.root.iterdir()), before | {taken})
        self.assertEqual(taken.read_text(), 'taken')

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows')
    def test_windows_watch_never_kills_a_live_process_and_reports_died(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            with mock.patch.object(RUNTIME.os, 'kill', side_effect=AssertionError('unsafe Windows liveness probe')):
                self.assertTrue(RUNTIME.alive(child.pid))
            self.assertIsNone(child.poll())
            for provider in ('codex', 'claude'):
                result = self.run_helper(provider)
                receipt = self.receipt(result)
                self.assertEqual(receipt['status'], 'DONE')
                self.assertEqual(self.watch(provider, receipt['receipt']).returncode, 0)
                receipt.update(status='RUNNING', exit_code=None, pid=child.pid, started_at=time.time())
                Path(receipt['receipt']).write_text(json.dumps(receipt))
                watching = self.watch(provider, receipt['receipt'])
                self.assertEqual(watching.returncode, 10, watching.stdout)
                self.assertTrue(watching.stdout.startswith('RUNNING '), watching.stdout)
                self.assertIsNone(child.poll())
            child.terminate()
            child.wait(timeout=3)
            self.assertFalse(RUNTIME.alive(child.pid))
            died = self.watch('claude', receipt['receipt'])
            self.assertEqual(died.returncode, 1)
            self.assertTrue(died.stdout.startswith('DIED '), died.stdout)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows')
    def test_windows_alive_handles_access_errors_and_closes_query_handles(self):
        for error, expected in ((5, True), (87, False), (1168, False)):
            with self.subTest(error=error), \
                 mock.patch.object(RUNTIME._kernel32, 'OpenProcess', return_value=0), \
                 mock.patch.object(RUNTIME.ctypes, 'get_last_error', return_value=error):
                self.assertEqual(RUNTIME.alive(123), expected)
        with mock.patch.object(RUNTIME._kernel32, 'OpenProcess', return_value=123), \
             mock.patch.object(RUNTIME._kernel32, 'GetExitCodeProcess', return_value=0), \
             mock.patch.object(RUNTIME._kernel32, 'CloseHandle') as close:
            with self.assertRaises(OSError):
                RUNTIME.alive(123)
            close.assert_called_once_with(123)

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows')
    def test_windows_cmd_argument_guard_and_stdin_prompt(self):
        for suffix in ('.cmd', '.BAT'):
            for character in '"%^&|<>!\r\n':
                with self.subTest(suffix=suffix, character=repr(character)):
                    with self.assertRaises(RUNTIME.RunError) as caught:
                        RUNTIME._WindowsJobOwnership.command_line(['cli' + suffix, 'SECRET' + character])
                    self.assertIn('index 1', str(caught.exception))
                    self.assertNotIn('SECRET', str(caught.exception))
        for provider in ('codex', 'claude'):
            result = self.run_helper(provider, model='secret-model&echo')
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(self.receipt(result)['status'], 'FAILED')
            self.assertIn('argument at index', result.stderr)
            self.assertNotIn('secret-model', result.stderr)
            calls = [json.loads(line)['argv'] for line in self.record.read_text().splitlines()]
            self.assertTrue(all('--version' in args or '--help' in args for args in calls))
            self.record.unlink()
            prompt = 'quotes " and %PATH% ^ & | < > !\r\nnext line'
            command = self.command(provider, prompt=False) + ['--', prompt]
            result = subprocess.run(command, input='', cwd=self.caller, env=self.env,
                                    capture_output=True, text=True, timeout=12)
            self.assertEqual(self.payload(result)['stdin'], prompt.replace('\r\n', '\n'))
            self.record.unlink()

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows')
    def test_windows_empty_prompt_falls_back_to_stdin(self):
        for provider in ('codex', 'claude'):
            result = subprocess.run(self.command(provider, prompt=False) + ['--', ''],
                                    input='piped prompt\n', cwd=self.caller, env=self.env,
                                    capture_output=True, text=True, timeout=12)
            self.assertEqual(self.payload(result)['stdin'], 'piped prompt\n')

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows')
    def test_windows_hung_cli_is_dead_after_timeout(self):
        for provider in ('codex', 'claude'):
            started = Path(self.env['FAKE_STARTED'])
            started.unlink(missing_ok=True)
            result = self.run_helper(provider, '--timeout', '2', mode='hang')
            self.assertEqual(result.returncode, 124, result.stderr)
            self.assertEqual(self.receipt(result)['status'], 'TIMEOUT')
            self.assert_stopped(self.wait_path(started))

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows')
    def test_windows_spawn_failures_kill_suspended_child(self):
        real_popen = subprocess.Popen
        for dll, function, failure in (
                (RUNTIME._kernel32, 'CreateJobObjectW', 0),
                (RUNTIME._kernel32, 'SetInformationJobObject', 0),
                (RUNTIME._kernel32, 'AssignProcessToJobObject', 0),
                (RUNTIME._ntdll, 'NtResumeProcess', -1)):
            with self.subTest(function=function):
                run = self.lifecycle_fixture()
                started = self.root / 'must-not-run'
                children = []
                def spawn(*args, **kwargs):
                    child = real_popen(*args, **kwargs)
                    children.append(child)
                    return child
                with mock.patch.object(RUNTIME.subprocess, 'Popen', side_effect=spawn), \
                     mock.patch.object(dll, function, return_value=failure):
                    with self.assertRaises(RUNTIME.RunError):
                        run.ownership.spawn(run, [sys.executable, '-c',
                            f'from pathlib import Path; Path({str(started)!r}).touch()'])
                self.assertEqual(len(children), 1)
                self.assertIsNotNone(children[0].poll())
                self.assertFalse(started.exists())
                self.assertIsNone(run.ownership.job)
                self.assertIsNone(run.child)

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows')
    def test_windows_job_close_kills_orphan_even_without_cleanup(self):
        run = self.lifecycle_fixture()
        descendant = self.root / 'job-descendant'
        code = ('import pathlib,subprocess,sys; '
                'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
                f'pathlib.Path({str(descendant)!r}).write_text(str(p.pid))')
        try:
            run.ownership.spawn(run, [sys.executable, '-c', code])
            pid = self.wait_path(descendant)
            run.child.wait(timeout=3)
            self.assertTrue(RUNTIME.alive(pid))
            self.assertEqual(run.ownership.active_processes(), 1)
            self.assertEqual(run.ownership.live_pids(), [pid])
            run.ownership.close()
            until = time.monotonic() + 3
            while RUNTIME.alive(pid) and time.monotonic() < until:
                time.sleep(.02)
            self.assert_stopped(pid)
        finally:
            run.ownership.close()

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows')
    def test_windows_cleanup_failure_records_live_pids_and_closes_job(self):
        run = self.lifecycle_fixture()
        try:
            run.ownership.spawn(run, [sys.executable, '-c', 'import time; time.sleep(60)'])
            pid = run.child.pid
            with mock.patch.object(RUNTIME._kernel32, 'GenerateConsoleCtrlEvent', return_value=0), \
                 mock.patch.object(RUNTIME._kernel32, 'TerminateJobObject', return_value=0):
                with self.assertRaises(RUNTIME.RunError) as caught:
                    run.cleanup(strict=False)
            self.assertEqual(caught.exception.code, 125)
            self.assertEqual(caught.exception.status, 'CLEANUP_FAILED')
            self.assertEqual(run.data['cleanup_live_pids'], [pid])
            self.assertIsNone(run.ownership.job)
            run.child.wait(timeout=3)
            self.assert_stopped(pid)
        finally:
            run.ownership.close()

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows')
    def test_windows_ctrl_break_cancels_supervisor_and_cleans_job(self):
        for provider in ('codex', 'claude'):
            for key in ('FAKE_STARTED', 'FAKE_DESCENDANT'):
                Path(self.env[key]).unlink(missing_ok=True)
            command = [sys.executable, str(ROOT / 'lib/provider_runtime.py'), provider, 'run',
                       '--model', 'fixture-model', '--timeout', '15', '--', 'fixture prompt']
            process = subprocess.Popen(command, cwd=self.caller, env={**self.env, 'FAKE_MODE': 'orphan'},
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            try:
                leader = self.wait_path(Path(self.env['FAKE_STARTED']))
                descendant = self.wait_path(Path(self.env['FAKE_DESCENDANT']))
                process.send_signal(signal.CTRL_BREAK_EVENT)
                stdout, stderr = process.communicate(timeout=6)
                self.assertEqual(process.returncode, 128 + signal.SIGBREAK, stderr)
                start = json.loads(stdout.splitlines()[0].split(' ', 1)[1])
                receipt = json.loads(Path(start['receipt']).read_text())
                self.assertEqual(receipt['status'], 'CANCELLED')
                self.assert_stopped(leader)
                self.assert_stopped(descendant)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=3)

    def test_exit_marker_is_printed_when_the_receipt_cannot_be_saved(self):
        run = self.lifecycle_fixture()
        def vanish():
            shutil.rmtree(run.root)
        with mock.patch.object(run, 'perform', side_effect=vanish):
            code, stdout = self.run_quietly(run)
        self.assertEqual(code, 2)
        lines = stdout.splitlines()
        self.assertTrue(lines[0].startswith('CODEX_RUN_START '), stdout)
        exit_line = json.loads(lines[-1].split(' ', 1)[1])
        self.assertTrue(lines[-1].startswith('CODEX_RUN_EXIT '), stdout)
        self.assertEqual(exit_line['rc'], 2)
        self.assertEqual(exit_line['receipt_error'], 'FileNotFoundError')

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX signals, ps or pty')
    def test_signal_during_timeout_cleanup_keeps_the_timeout_cause(self):
        for key in ('FAKE_STARTED', 'FAKE_DESCENDANT'):
            Path(self.env[key]).unlink(missing_ok=True)
        process = subprocess.Popen(self.command('codex', '--timeout', '1.5'), cwd=self.caller,
                                   env={**self.env, 'FAKE_MODE': 'orphan'},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   start_new_session=True)
        try:
            self.wait_path(Path(self.env['FAKE_DESCENDANT']))
            start = json.loads(process.stdout.readline().split(' ', 1)[1])
            deadline = json.loads(Path(start['receipt']).read_text())['deadline_at']
            # The descendant ignores TERM, so the timeout cleanup spends a full grace
            # second before KILL; a TERM inside that window must be deferred.
            time.sleep(max(0, deadline + .4 - time.time()))
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=6)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        self.assertEqual(process.returncode, 124, stderr)
        receipt = json.loads(Path(start['receipt']).read_text())
        self.assertEqual(receipt['status'], 'TIMEOUT')
        self.assertEqual(receipt['deferred_signals'], [int(signal.SIGTERM)])
        self.assertTrue(stdout.strip().startswith('CODEX_RUN_EXIT '), stdout)


if __name__ == '__main__':
    unittest.main()

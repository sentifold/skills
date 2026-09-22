#!/usr/bin/env python3
"""Bounded POSIX lifecycle for the portable Codex and Claude shell helpers.

Copyright (c) 2026 Theta Games. Derived from gamejam f4dbd06ec.
Internal use only; see LICENSE.txt at the repository root.
Provider configuration/authentication is inherited; this is not a security sandbox.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid


TERMINAL_STATUSES = frozenset(("DONE", "FAILED", "MISSING", "TIMEOUT", "CANCELLED", "CLEANUP_FAILED"))
RUN_DIR_RETENTION_SECONDS = 7 * 86400


class RunError(Exception):
    def __init__(self, message, code=2, status="FAILED"):
        super().__init__(message)
        self.code, self.status = code, status


class Cancelled(BaseException):
    def __init__(self, signum):
        self.signum = signum


def positive(value):
    number = float(value)
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("must be finite and positive")
    return number


def parser(provider):
    p = argparse.ArgumentParser(prog=f"{provider}-ephemeral.sh")
    p.add_argument("--model", required=True, help="exact model; never substituted")
    p.add_argument("--effort")
    p.add_argument("--cli", help=f"exact executable; otherwise {provider.upper()}_BIN or PATH")
    p.add_argument("--cd")
    p.add_argument("--out", help="unused destination; existing files are rejected")
    p.add_argument("--timeout", type=positive, default=1800)
    p.add_argument("--preflight-timeout", type=positive, default=10)
    p.add_argument("--keep", action="store_true", help="exempt this run directory from the retention sweep")
    p.add_argument("--no-watchdog", action="store_true", help="compatibility no-op; no watchdog is spawned")
    p.add_argument("--search", dest="search", action="store_true", default=True)
    p.add_argument("--no-search", dest="search", action="store_false")
    if provider == "codex":
        p.add_argument("--sandbox", choices=("read-only", "workspace-write", "danger-full-access"), default="read-only")
        p.add_argument("--network", action="store_true")
        p.add_argument("--browser-mcp", action="store_true")
        p.add_argument("--review", action="store_true")
        p.add_argument("--json", action="store_true")
        p.add_argument("--fast", action="store_true")
        p.add_argument("--no-fast", "--nofast", action="store_true")
        p.add_argument("--companion", help="check an expected codex-code-mode-host executable; does not change CLI resolution")
    else:
        p.add_argument("--mode", choices=("read-only", "workspace-write"), default="read-only")
        p.add_argument("--agent")
        p.add_argument("--max-turns", type=int, default=32)
        p.add_argument("--output-schema")
        p.add_argument("--auth", choices=("sanitized", "inherit", "subscription"), default="sanitized")
        p.add_argument("--allow-bash", action="append", default=[])
    p.add_argument("prompt", nargs=argparse.REMAINDER)
    return p


def atomic_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


# CPython exposes os.waitid on macOS only from 3.13; older interpreters read the
# leader's state from ps, and that fork is why their polling backs off.
LEADER_WAITID = getattr(os, "waitid", None)
EXIT_POLL_START = .03
EXIT_POLL_LIMIT = .03 if LEADER_WAITID else .25


def leader_state(pid):
    try:
        snapshot = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, timeout=2, start_new_session=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RunError(f"Cannot verify owned child {pid}: {type(exc).__name__}",
                       125, "CLEANUP_FAILED") from exc
    return snapshot.stdout.strip()[:1]


def collect_finished_run_dirs(provider, own_root):
    removed = 0
    now = time.time()
    for entry in Path(tempfile.gettempdir()).glob(f"{provider}-*"):
        receipt = entry / "receipt.json"
        try:
            if entry == own_root or not entry.is_dir() or not receipt.is_file():
                continue
            data = json.loads(receipt.read_text(encoding="utf-8"))
            owned = (data.get("schema") == 1 and data.get("provider") == provider
                     and entry.name.startswith(f"{provider}-{data.get('run_id')}-"))
            if not owned or data.get("keep") or data.get("status") not in TERMINAL_STATUSES:
                continue
            finished = data.get("finished_at") or receipt.stat().st_mtime
            if now - float(finished) < RUN_DIR_RETENTION_SECONDS:
                continue
            shutil.rmtree(entry)
            removed += 1
        except (OSError, ValueError, TypeError):
            continue
    return removed


class Run:
    def __init__(self, provider, args):
        self.provider, self.args = provider, args
        self.run_id = uuid.uuid4().hex
        self.root = self.receipt = self.result = None
        self.child = None
        self.deadline = time.monotonic() + args.timeout
        self.export = Path(args.out).absolute() if args.out else None
        self.reservation = None
        self.schema = None
        self.prompt_text = None
        self.shield = False
        self.data = dict(schema=1, provider=provider, run_id=self.run_id, pid=os.getpid(),
                         status="STARTING", started_at=time.time(), deadline_at=time.time() + args.timeout,
                         keep=bool(args.keep))
        self.env = os.environ.copy()
        keys = ("OPENAI_API_KEY", "CODEX_API_KEY") if provider == "codex" else (
            "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
            "ANTHROPIC_CUSTOM_HEADERS", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
        if provider == "codex" or args.auth != "inherit":
            for key in keys:
                self.env.pop(key, None)

    def save(self, **fields):
        self.data.update(fields)
        self.data["deadline_remaining"] = round(max(0.0, self.deadline - time.monotonic()), 3)
        atomic_json(self.receipt, self.data)

    def marker(self, kind, **fields):
        # Only this supervisor writes lifecycle stdout. Provider text stays in files.
        print(f"{self.provider.upper()}_RUN_{kind} " + json.dumps(
            dict(run_id=self.run_id, **fields), separators=(",", ":")), flush=True)

    def on_signal(self, signum, _frame):
        if self.shield:
            self.data.setdefault("deferred_signals", []).append(signum)
            return
        raise Cancelled(signum)

    @staticmethod
    def child_exited(process):
        # Keep the leader unreaped until its group is cleaned. This retains its
        # PID and prevents group-id reuse while we still own descendant cleanup.
        if LEADER_WAITID is not None:
            return LEADER_WAITID(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
        return leader_state(process.pid) in ("", "Z")

    def live_group_members(self, pgid):
        try:
            snapshot = subprocess.run(["ps", "-axo", "pid=,pgid=,stat="],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, timeout=2, check=True, start_new_session=True)
            return [int(pid) for line in snapshot.stdout.splitlines()
                    for pid, group, state in [line.split()]
                    if int(group) == pgid and not state.startswith(("Z", "X"))]
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise RunError(f"Cannot verify cleanup of owned group {pgid}: {type(exc).__name__}",
                           125, "CLEANUP_FAILED") from exc

    def signal_group(self, pgid, signum):
        try:
            os.killpg(pgid, signum)
            return True
        except ProcessLookupError:
            return False
        except PermissionError as exc:
            # Darwin returns EPERM for a group containing only zombies. An exited
            # leader is not enough: an orphan descendant can still be alive.
            live = self.live_group_members(pgid)
            if live:
                self.data["cleanup_live_pids"] = live
                raise RunError(f"Cannot signal owned group {pgid}; live members remain: {live}",
                               125, "CLEANUP_FAILED") from exc
            return False

    def stop_group(self, process):
        # A new session owns this group, including normal descendants even if the
        # leader has exited. Never terminate by executable name or caller's group.
        group_exists = self.signal_group(process.pid, signal.SIGTERM)
        until = time.monotonic() + 1
        while group_exists and time.monotonic() < until:
            if self.child_exited(process) and not self.live_group_members(process.pid):
                group_exists = False
                break
            group_exists = self.signal_group(process.pid, 0)
            time.sleep(.02)
        if group_exists:
            self.signal_group(process.pid, signal.SIGKILL)
            until = time.monotonic() + 1
            remaining = self.live_group_members(process.pid)
            while remaining and time.monotonic() < until:
                time.sleep(.02)
                remaining = self.live_group_members(process.pid)
            if remaining:
                self.data["cleanup_live_pids"] = remaining
                raise RunError(f"Owned group {process.pid} still has live members after KILL: {remaining}",
                               125, "CLEANUP_FAILED")
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired as exc:
            raise RunError(f"Owned child {process.pid} did not stop after KILL", 125, "CLEANUP_FAILED") from exc

    def cleanup(self, strict=True):
        if self.child is None:
            return
        process = self.child
        self.shield = True
        try:
            self.stop_group(process)
        except RunError as exc:
            if strict:
                raise
            self.data["cleanup_warning"] = str(exc)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        finally:
            self.shield = False
        self.child = None

    def execute(self, argv, label, *, stdin=None, cwd=None, limit=None):
        out, err = self.root / f"{label}.stdout", self.root / f"{label}.stderr"
        with out.open("wb") as stdout, err.open("wb") as stderr:
            # Record ownership before a pending TERM/INT can be delivered. Otherwise
            # a signal between fork and assignment could leave an unrecorded child.
            blocked = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
            def child_signals():
                # This supervisor is single-threaded. Restore the inherited mask
                # before exec so the child can receive graceful termination.
                signal.signal(signal.SIGINT, signal.SIG_DFL)
                signal.signal(signal.SIGTERM, signal.SIG_DFL)
                signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
            try:
                self.child = subprocess.Popen(argv, stdin=stdin if stdin is not None else subprocess.DEVNULL,
                                              stdout=stdout, stderr=stderr, cwd=cwd,
                                              env=self.env, start_new_session=True, preexec_fn=child_signals)
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
            self.save(child_pid=self.child.pid, phase=label,
                      stdout=str(out), stderr=str(err))
            process = self.child
            end = min(self.deadline, time.monotonic() + limit) if limit else self.deadline
            interval = EXIT_POLL_START
            try:
                while not self.child_exited(process):
                    if time.monotonic() >= end:
                        raise RunError(f"{label} exceeded its deadline; inspect {err}", 124, "TIMEOUT")
                    time.sleep(interval)
                    interval = min(interval * 1.5, EXIT_POLL_LIMIT)
            except BaseException:
                # The first cause stays; signals during cleanup are only recorded.
                self.cleanup()
                raise
            self.cleanup(strict=False)
            deferred = self.data.get("deferred_signals")
            if deferred:
                raise Cancelled(deferred[0])
        return process.returncode, out, err

    def probe(self, cli, flags, label):
        rc, out, err = self.execute([cli, *flags], label, limit=self.args.preflight_timeout)
        if rc:
            raise RunError(f"Selected executable {cli} failed {label} (rc={rc}); inspect {err}. "
                           "No alternate installation was tried.", rc if 0 < rc < 126 else 2)
        return out.read_text(encoding="utf-8", errors="replace")[:131072]

    def resolve_cli(self):
        selected = self.args.cli or self.env.get(f"{self.provider.upper()}_BIN") or self.provider
        cli = shutil.which(selected)
        if not cli:
            raise RunError(f"Selected executable not found or not executable: {selected}", 127)
        # Keep the selected wrapper/symlink path; resolving to another installation
        # could bypass account/egress behavior. Absolute only, not realpath.
        cli = os.path.abspath(cli)
        self.save(cli=cli)
        version = self.probe(cli, ["--version"], "version").strip().splitlines()
        if not version:
            raise RunError(f"Selected executable {cli} returned no version", 2)
        self.save(cli_version=version[0][:160])
        flags = ["exec", "--help"] if self.provider == "codex" else ["--help"]
        help_text = self.probe(cli, flags, "capabilities")
        required = ("--ephemeral", "--sandbox", "--model", "--output-last-message") if self.provider == "codex" else (
            "--no-session-persistence", "--output-format", "--max-turns", "--permission-mode",
            "--allowedTools", "--tools", "--strict-mcp-config", "--mcp-config", "--model",
            "--disable-slash-commands", "--no-chrome")
        if self.args.effort and self.provider == "claude":
            required += ("--effort",)
        missing = [flag for flag in required if flag not in help_text]
        if missing:
            raise RunError(f"Selected {self.provider} ({version[0][:80]}) lacks capabilities: {', '.join(missing)}. "
                           "Update this installation through its wrapper; keep CLI and any companion (such as "
                           "codex-code-mode-host) from the same distribution. No fallback was attempted.")
        if self.provider == "codex" and self.args.companion:
            companion = Path(self.args.companion).absolute()
            if not companion.is_file() or not os.access(companion, os.X_OK):
                raise RunError(f"Expected code-mode companion is missing or not executable: {companion}. "
                               "Repair the selected CLI installation and its matching resources.")
            self.save(companion=str(companion), companion_check="executable-only; version compatibility unverified")
        return cli

    def command(self, cli):
        a = self.args
        if self.provider == "codex":
            argv = [cli, *(["--search"] if a.search else []), "exec", "--ephemeral",
                    "--skip-git-repo-check", "--color", "never", "--sandbox", a.sandbox,
                    "--model", a.model, "-o", str(self.result)]
            if a.cd:
                argv += ["--cd", str(Path(a.cd).absolute())]
            if a.effort:
                argv += ["-c", f"model_reasoning_effort={a.effort}"]
            if a.fast or a.no_fast:
                argv += ["-c", "service_tier=fast" if a.fast else "service_tier=default"]
            if a.fast:
                argv += ["-c", "features.fast_mode=true"]
            # Explicitly overrides inherited workspace-write network/search config.
            argv += ["-c", f"sandbox_workspace_write.network_access={str(a.network).lower()}"]
            if not a.search:
                argv += ["-c", 'web_search="disabled"']
            if not a.browser_mcp:
                argv += ["-c", "mcp_servers.node_repl.enabled=false"]
            if a.json:
                argv += ["--json"]
            if a.review:
                argv += ["review"]
            return argv, None
        tools = ["Read", "Grep", "Glob", "Bash"]
        allowed = ["Read", "Grep", "Glob", *[f"Bash(git {verb} *)" for verb in (
            "diff", "status", "show", "log", "rev-parse", "merge-base", "grep")], "Bash(rg *)"]
        if a.search and a.mode == "read-only":
            tools += ["WebSearch", "WebFetch"]
            allowed += ["WebSearch", "WebFetch"]
        if a.mode == "workspace-write":
            tools += ["Edit", "Write"]
            allowed += ["Edit", "Write"]
        if a.agent:
            tools += ["Agent"]
            allowed += ["Agent"]
        allowed += [f"Bash({pattern})" for pattern in a.allow_bash]
        argv = [cli, "-p", "--output-format", "json", "--no-session-persistence",
                "--max-turns", str(a.max_turns), "--permission-mode",
                "dontAsk" if a.mode == "read-only" else "acceptEdits",
                "--allowedTools", *allowed, "--tools", ",".join(tools),
                "--disable-slash-commands", "--no-chrome", "--strict-mcp-config",
                "--mcp-config", '{"mcpServers":{}}', "--model", a.model]
        if a.effort:
            argv += ["--effort", a.effort]
        if a.agent:
            argv += ["--agent", a.agent]
        if self.schema is not None:
            argv += ["--json-schema", json.dumps(self.schema)]
        return argv, a.cd

    def claude_result(self, stdout):
        try:
            envelope = json.loads(stdout.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise RunError("Claude returned an invalid JSON envelope; inspect the run stdout", 4, "MISSING") from exc
        if not isinstance(envelope, dict):
            raise RunError("Claude envelope is not an object", 4, "MISSING")
        subtype = envelope.get("subtype")
        if envelope.get("is_error") or subtype not in (None, "success"):
            raise RunError(f"Claude envelope reports failure (subtype={subtype!r}); inspect run stdout", 1)
        if envelope.get("permission_denials"):
            raise RunError("Claude reported denied tool calls; result is incomplete (see run stdout)", 1)
        usage = envelope.get("usage") or {}
        self.save(usage={key: usage.get(key) for key in (
            "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")})
        payload = envelope.get("structured_output") if self.args.output_schema else envelope.get("result")
        if payload is None and self.args.output_schema:
            raw = (envelope.get("result") or "").strip()
            if raw.startswith("```") and raw.endswith("```"):
                raw = "\n".join(raw.splitlines()[1:-1])
            try:
                payload = json.loads(raw)
            except ValueError as exc:
                raise RunError("Claude returned no structured result", 4, "MISSING") from exc
        if payload is None:
            raise RunError("Claude returned no result", 4, "MISSING")
        rendered = payload if isinstance(payload, str) else json.dumps(payload, indent=2, sort_keys=True)
        self.result.write_text(rendered + "\n", encoding="utf-8")

    def release_export(self):
        if self.reservation and self.export:
            try:
                if self.export.stat().st_ino == self.reservation:
                    self.export.unlink()
            except FileNotFoundError:
                pass
        self.reservation = None

    def prepare(self):
        prompt = list(self.args.prompt)
        if prompt and prompt[0] == "--":
            prompt = prompt[1:]
        if prompt and prompt[0]:
            self.prompt_text = " ".join(prompt)
        elif sys.stdin.isatty():
            raise RunError("Provide a prompt argument after -- or pipe it on stdin")
        if self.provider == "claude" and self.args.output_schema:
            try:
                self.schema = json.loads(Path(self.args.output_schema).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise RunError(f"--output-schema is not a readable JSON file: {self.args.output_schema}") from exc
        if self.export:
            # Reserve exclusively before launch. Never expose a previous run's file
            # under an expected new output path or overwrite an existing artifact.
            try:
                fd = os.open(self.export, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError as exc:
                raise RunError(f"--out already exists: {self.export}; choose an unused path") from exc
            with os.fdopen(fd, "wb") as handle:
                self.reservation = os.fstat(handle.fileno()).st_ino

    def open_run_dir(self):
        self.root = Path(tempfile.mkdtemp(prefix=f"{self.provider}-{self.run_id}-")).resolve()
        self.receipt = self.root / "receipt.json"
        self.result = self.root / "result.txt"
        self.data.update(result=str(self.result), receipt=str(self.receipt))
        collected = collect_finished_run_dirs(self.provider, self.root)
        if collected:
            self.data["collected_run_dirs"] = collected

    def perform(self):
        cli = self.resolve_cli()
        if self.provider == "claude" and self.args.auth == "subscription":
            # Compatibility spelling: loggedIn is not a billing/provider attestation.
            status = json.loads(self.probe(cli, ["auth", "status", "--json"], "auth"))
            if status.get("loggedIn") is not True:
                raise RunError("Claude reports no login; use its supported login flow", 3)
        argv, cwd = self.command(cli)
        stdin = None
        if self.prompt_text is not None:
            argv.append(self.prompt_text)
        else:
            stdin = sys.stdin
            if self.provider == "codex":
                argv.append("-")
        self.save(status="RUNNING")
        rc, stdout, stderr = self.execute(argv, "provider", stdin=stdin, cwd=cwd)
        self.save(child_exit_code=rc)
        if rc:
            raise RunError(f"Selected {self.provider} failed (rc={rc}); inspect {stderr} and {stdout}. "
                           "Model/effort and executable were not substituted; check selected CLI capabilities, "
                           "authentication and matching companion resources if required.", rc if rc > 0 else 128 - rc)
        if self.provider == "claude":
            self.claude_result(stdout)
        if not self.result.is_file() or not self.result.read_bytes().strip():
            raise RunError("Provider exited successfully without a nonempty final result", 4, "MISSING")
        digest = hashlib.sha256(self.result.read_bytes()).hexdigest()
        if self.export:
            if self.export.stat().st_ino != self.reservation:
                raise RunError("Reserved output was replaced by another process; refusing publication")
            # Atomic publication on the destination filesystem, including cross-volume --out.
            fd, temp = tempfile.mkstemp(prefix=f".{self.export.name}-{self.run_id}-", dir=self.export.parent)
            try:
                with os.fdopen(fd, "wb") as target:
                    target.write(self.result.read_bytes())
                os.replace(temp, self.export)
            finally:
                Path(temp).unlink(missing_ok=True)
            self.reservation = None
        self.save(result_sha256=digest, output=str(self.export or self.result))

    def run(self):
        try:
            self.prepare()
            self.open_run_dir()
            self.save()
        except (RunError, OSError) as exc:
            self.release_export()
            print(exc, file=sys.stderr)
            return exc.code if isinstance(exc, RunError) else 2
        self.marker("START", pid=os.getpid(), receipt=str(self.receipt))
        old_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        for sig in old_handlers:
            signal.signal(sig, self.on_signal)
        rc, status = 0, "DONE"
        try:
            self.perform()
        except Cancelled as exc:
            rc, status = 128 + exc.signum, "CANCELLED"
            self.data["diagnostic"] = f"Received signal {exc.signum}"
        except RunError as exc:
            rc, status = exc.code, exc.status
            self.data["diagnostic"] = str(exc)
        except (OSError, ValueError) as exc:
            rc, status = 2, "FAILED"
            self.data["diagnostic"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            rc, status = 2, "FAILED"
            self.data["diagnostic"] = f"Unexpected {type(exc).__name__}; inspect the run files"
        finally:
            # Repeated TERM/INT must not interrupt descendant cleanup.
            for sig in old_handlers:
                signal.signal(sig, signal.SIG_IGN)
            try:
                self.cleanup()
            except RunError as exc:
                rc, status = exc.code, exc.status
                self.data["diagnostic"] = str(exc)
            except OSError as exc:
                rc, status = 125, "CLEANUP_FAILED"
                self.data["diagnostic"] = f"Could not complete process cleanup: {type(exc).__name__}"
            self.release_export()
            exit_fields = dict(rc=rc, status=status, receipt=str(self.receipt), output=self.data.get("output"))
            try:
                self.save(status=status, exit_code=rc, finished_at=time.time())
            except OSError as exc:
                if not rc:
                    rc, status = 2, "FAILED"
                self.data["diagnostic"] = f"Could not write the receipt: {type(exc).__name__}: {exc}"
                exit_fields.update(rc=rc, status=status, receipt_error=type(exc).__name__)
            self.marker("EXIT", **exit_fields)
            for sig, old in old_handlers.items():
                signal.signal(sig, old)
        if rc:
            print(self.data.get("diagnostic", status), file=sys.stderr)
        return rc


def watch(provider, argv):
    p = argparse.ArgumentParser(prog=f"{provider}-watch.sh")
    p.add_argument("path", help="receipt.json or captured lifecycle log")
    p.add_argument("stall_minutes", nargs="?", type=positive, default=10)
    p.add_argument("--run-id", help="require a specific run; use when following an appended log")
    args = p.parse_args(argv)
    try:
        path = Path(args.path)
        expected = args.run_id
        if path.name != "receipt.json":
            starts = []
            for line in path.read_text(encoding="utf-8").splitlines():
                prefix = f"{provider.upper()}_RUN_START "
                if line.startswith(prefix):
                    try:
                        item = json.loads(line[len(prefix):])
                        if not expected or item.get("run_id") == expected:
                            starts.append(item)
                    except ValueError:
                        pass
            if not starts:
                raise ValueError("no run-specific START receipt; legacy markers are not accepted")
            start = starts[-1]
            expected = start["run_id"]
            path = Path(start["receipt"])
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != 1 or data.get("provider") != provider or (expected and data.get("run_id") != expected):
            raise ValueError("receipt identity mismatch")
        status = data["status"]
        if status == "DONE":
            result = Path(data["output"])
            if data.get("exit_code") != 0 or not result.is_file() or not result.read_bytes().strip():
                status = "MISSING"
            elif hashlib.sha256(result.read_bytes()).hexdigest() != data.get("result_sha256"):
                status = "MISSING"
        elif status in ("RUNNING", "STARTING"):
            # The supervisor alone decides TIMEOUT, on its monotonic clock. A live
            # supervisor past deadline_at is still running its cleanup.
            if not alive(data["pid"]):
                status = "DIED"
            else:
                # Supervisor status changes and heartbeat messages are not workload
                # progress. Silence may be healthy; QUIET is never proof of a stall.
                stamps = [Path(data[key]).stat().st_mtime for key in ("stdout", "stderr")
                          if key in data and Path(data[key]).exists()]
                latest = max(stamps, default=data["started_at"])
                status = "QUIET" if time.time() - latest >= args.stall_minutes * 60 else "RUNNING"
        print(f"{status} run_id={data['run_id']} rc={data.get('exit_code', 'pending')} receipt={path}")
        return 0 if status == "DONE" else 10 if status in ("RUNNING", "QUIET") else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"UNKNOWN {exc}")
        return 1


def main():
    provider, operation, *argv = sys.argv[1:]
    if operation == "watch":
        return watch(provider, argv)
    p = parser(provider)
    args = p.parse_args(argv)
    if os.name != "posix":
        p.error("requires POSIX process groups; use macOS, Linux, or WSL (not native Git Bash)")
    if not args.model.strip():
        p.error("--model must not be empty")
    if provider == "codex" and args.fast and args.no_fast:
        p.error("--fast and --no-fast/--nofast are mutually exclusive")
    if provider == "claude" and args.max_turns < 1:
        p.error("--max-turns must be positive")
    return Run(provider, args).run()


if __name__ == "__main__":
    raise SystemExit(main())

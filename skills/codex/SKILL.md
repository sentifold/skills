---
name: codex
description: >-
  Run Codex CLI headlessly for an explicitly requested second opinion,
  cross-provider review, or implementation handoff. Requires an explicit model,
  defaults to read-only, and records a bounded run with a verified result receipt.
  Do not invoke merely because another model might be helpful.
license: Internal
metadata:
  author: Theta Games
  version: "2.0.0"
  repository: https://github.com/sentifold/skills
---

# Codex

Use the selected Codex installation and account wrapper. Resolve this skill's
absolute directory from the loaded `SKILL.md`; a global symlink is supported.
Keep the target repository as the working directory. The installed release must
include its shared `lib/provider_runtime.py`; copying this skill folder alone is
not a supported installation.

```bash
CODEX_SKILL_DIR="/absolute/path/to/loaded/codex"
bash "$CODEX_SKILL_DIR/scripts/codex-ephemeral.sh" \
  --model <requested-model> --cd /absolute/repository \
  --out /absolute/unused-answer.md -- "Review the current diff for correctness."
```

`--model` is required and never substituted. Pass a reasoning effort only when
chosen by the user or applicable project workflow; otherwise the CLI's setting
is inherited. Read the target project's `AGENTS.md` for checks, review scope and
publication policy. This skill does not supply game/build/repository policy.

Read [references/runtime-findings.md](references/runtime-findings.md) before
delegating real work: it carries the field notes behind this helper — the
Linux bubblewrap silent-success trap, the write-mode delegation contract, the
marker extraction contract for structured output, batching, the Claude Code
background-launch rule, model gating on ChatGPT accounts and the known benign
noise lines.

## Execution

- Default: `--sandbox read-only`. Use `workspace-write` only for an authorized
  implementation handoff. `danger-full-access` is accepted only when the caller
  explicitly chooses it; no automatic escalation or retry changes sandbox/model.
  The one legitimate reason to choose it for an analysis run is a Linux host
  that denies bubblewrap user namespaces (the sandboxed run reads nothing and
  still answers; see runtime-findings). Pair it with a hard read-only line in
  the prompt and a `git status --porcelain` check afterwards.
- Implementation handoffs routinely outlive the 1800 s default deadline; pass
  `--timeout 3600` for a write run and resume an interrupted one with a second
  run that continues the same working tree.
- Choose `--cli /exact/executable` or `CODEX_BIN`; otherwise use the first PATH
  `codex`. A broken wrapper fails with a diagnostic; the helper never skips it
  for another installation or a binary inside an app bundle.
- Version and required flag probes have a bounded timeout. They do not prove
  that an account accepts a model. Model/effort/provider failures remain failures.
  If the selected installation requires `codex-code-mode-host`, preserve its
  matching resources. `--companion /expected/path` checks that file is executable,
  not that its version matches; it does not change the CLI's resource resolution.
- `--cd` names the target repo without changing the caller directory.
- Pass the prompt after `--`, or pipe it on stdin. Argument prompts close the
  child's stdin on POSIX; Windows feeds them through stdin. A pipe that never
  closes is bounded by the run deadline. An empty prompt argument (`-- ""`)
  falls back to stdin when stdin is not a terminal; on a terminal it is a usage
  error.
- `--review` selects `codex exec review`. `--json` retains provider JSONL in the
  run's stdout file. The final message remains the result file in either mode.
- `--fast` sets `service_tier=fast` and `features.fast_mode=true`.
  `--no-fast` / `--nofast` selects `service_tier=default`. These are mutually
  exclusive; omitting both inherits the configured tier. Config files are never
  rewritten.

## Result and lifecycle

Each invocation creates a private, unique run directory
`$TMPDIR/codex-<run_id>-*` (the interpreter's temporary directory) containing
`receipt.json`, the provider stdout/stderr (`provider.stdout`,
`provider.stderr`), preflight evidence and `result.txt`. Only the supervisor
writes lifecycle stdout: `CODEX_RUN_START` and `CODEX_RUN_EXIT` followed by JSON
with `run_id` and `receipt`. Model text cannot supply control records. The
receipt records the selected executable/version, status, exit code, output
path, result digest, the child PID, `deadline_at` (wall clock, informational)
and `deadline_remaining` (the supervisor's monotonic clock, which alone decides
a timeout).

`--out` must name an unused file. The helper reserves it exclusively, publishes
only a nonempty final result after successful CLI exit, and removes its empty
reservation on failure. An existing output is never reused or overwritten.
Without `--out`, read the receipt's unique `output` path. A successful receipt
proves process/result completion, not the truth or completeness of the review;
apply the caller's expected report/schema/coverage checks too.

Run directories are retained for inspection. Every run sweeps its siblings:
a run directory of this provider whose receipt is terminal (`DONE`, `FAILED`,
`MISSING`, `TIMEOUT`, `CANCELLED`, `CLEANUP_FAILED`) and finished more than
seven days ago is deleted; `--keep` exempts the new run from that sweep. Copy
evidence you must retain longer out of the run directory.

The default overall deadline is 1800 seconds; `--timeout <seconds>` changes it.
Version/help probes are limited to 10 seconds each (`--preflight-timeout`).
On POSIX, TERM/INT and deadline expiry terminate the owned child process group,
wait briefly, then kill remaining group members. A signal that arrives during that
cleanup is recorded in the receipt (`deferred_signals`) and does not replace
the first cause. After the leader exits on its own, leftover descendants are
still terminated and killed, but a member that cannot be verified or stopped
is recorded as `cleanup_warning` and the child's exit code stands; `125` is
reserved for timeout/cancel paths where live members remain. No detached
watchdog is started; `--no-watchdog` is retained as a no-op. SIGKILL of the
POSIX supervisor and descendants that deliberately create independent sessions
cannot be cleaned by a signal handler. Inspect the receipt/processes before
retrying an interrupted write run.

For a background run, capture lifecycle stdout in a fresh log and use a bounded
wait loop owned by the caller. The watcher itself runs once:

```bash
bash "$CODEX_SKILL_DIR/scripts/codex-watch.sh" /absolute/run.log
# Or inspect receipt.json directly; pin --run-id when following an appended log.
```

Watch statuses: `DONE` (exit 0); `RUNNING`/`QUIET` (exit 10, incomplete);
`FAILED`, `MISSING`, `TIMEOUT`, `CANCELLED`, `CLEANUP_FAILED`, `DIED`, `UNKNOWN` (exit 1).
`QUIET` means no recent provider output, not a proven stall. It ignores
supervisor activity. The watcher never declares `TIMEOUT` from the wall clock:
a live supervisor is `RUNNING`/`QUIET` until its own receipt says otherwise,
and `DIED` means the recorded supervisor PID is gone without a terminal
receipt. The latest run-specific START selects the receipt; an old EXIT line is
never completion evidence. A missing or changed result fails. Legacy
marker-only logs must be inspected manually, never accepted as a gate.

Helper exit codes: 0 success, 2 usage/preflight failure, 4 missing result,
124 timeout, 125 incomplete process cleanup, 127 missing executable,
130/143 cancellation (149 for Windows Ctrl+Break), otherwise the child failure
code; a child killed by a signal reports 128+signal. These codes are ambiguous on their own: a child that
itself exits 2, 4, 124, 125 or 127 is passed through unchanged, and a preflight
probe that dies by signal or exits 126+ is reported as 2. Always read the
receipt's `status`, `diagnostic` and `child_exit_code` to distinguish causes.

## Configuration and access

The helper clears `OPENAI_API_KEY` and `CODEX_API_KEY`, but inherits `CODEX_HOME`,
saved authentication, provider configuration and the selected wrapper's routing.
It **does not guarantee subscription billing or a particular provider**.
Never print keys, auth files or complete configuration to diagnose it.

Search is on by default. `--no-search` explicitly sets `web_search="disabled"`,
overriding inherited provider-search configuration. Local workspace-write network
access is explicitly false unless `--network` enables it. These controls do not
block the provider connection, other sandbox profiles or external MCP tools.
The default disables only the `node_repl` MCP entry; `--browser-mcp` leaves its
inherited setting in place. Other MCP servers, writable roots, hooks and config
may remain inherited: `read-only` is the selected CLI sandbox mode, not a claim
that every external integration is incapable of mutation. Match those settings
to the authorized task before delegating work.

The helper runs Codex with its own `--ephemeral`, which avoids saved
session rollouts; the helper itself takes no such flag (a run passed one
fails at parse time). Ephemeral does not erase caches, wrapper/service logs
or this helper's explicit run files. Read-only Git queries
are valid; writes to linked worktree Git metadata may need separate permissions.
macOS, Linux and WSL with Python 3.10+ and a working `ps` (procps) are
supported: the runtime lists the owned process group through `ps`, and
interpreters without `os.waitid` (CPython before 3.13 on macOS) also poll the
leader through it. Native Windows (Git Bash + Python 3.10+) uses a kill-on-close
Job Object: spawn suspended, assign before resume, then Ctrl+Break and bounded
job termination on cancellation, timeout or leftover descendants. Job membership
also covers orphaned descendants. Cleanup failure is terminal (`125`,
`CLEANUP_FAILED`). `.cmd`/`.bat` arguments containing cmd metacharacters are
rejected; Windows prompts travel on stdin. `python3` must resolve to a real
interpreter, not the Microsoft Store alias.

A write run (`--sandbox workspace-write`) must keep caches out of the repository
(`PRE_COMMIT_HOME`, virtualenvs, Playwright reports in `%TEMP%`): directories it
creates inside a worktree are owned by the sandbox and can break the next
native build there.

Known limits of the preflight and polling: the capability probe matches
literal flag names in `codex exec --help`, so a wrapper that pages or
localizes help text, or an older CLI missing a probed flag, fails the run
(deliberately, with no fallback). POSIX interpreters without `os.waitid` fork `ps`
on every poll tick (up to four times a second for the whole run); prefer
CPython 3.13+ for long runs. The supervisor is single-threaded and installs
signal handlers (plus a POSIX `preexec_fn`); `Run` is not safe to drive from a
threaded harness.

## Callers of the earlier Bash helpers

Code written against the earlier repo-local Bash `codex-ephemeral.sh`/`codex-watch.sh`
(stdout log parsing, `rc=` lines, reused `-o` outputs) needs the breaks listed in
[references/migration-from-bash-helpers.md](references/migration-from-bash-helpers.md).

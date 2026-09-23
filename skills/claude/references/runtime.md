# Runtime contract

## Selected executable and inherited state

Use `--cli`, then `CLAUDE_BIN`, then the first PATH executable. Version/help
probes are bounded and record the selected path/version. A wrapper is preserved;
failure never switches account/egress routing to a later binary. Capability
checks do not prove model availability. Unsupported models/efforts and provider
errors fail without fallback.

Print mode passes `--no-session-persistence`, an explicit permission mode and
tool/approval allowlists. `--disable-slash-commands`, `--no-chrome` and an empty
`--strict-mcp-config` remove those CLI surfaces. Local/project settings, hooks,
plugins and saved authentication may still be inherited. The helper is not an
OS sandbox and does not claim isolation from all configuration or external
services. `--agent` permits a separately installed agent with its own behavior.

`--no-search` removes WebSearch/WebFetch from available and approved tools.
It does not deny provider network access or make permitted shell commands offline.
The surrounding OS/harness determines local network access. There is no blanket
claim that a read-only tool policy prevents every possible shell/Git side effect.

## Network

The child needs outbound network to reach the model API. When the caller is
itself sandboxed (e.g. a `codex exec` under `workspace-write`), grant network
to the sandbox (`--network` on codex-ephemeral) or the run dies on connect —
verified: works under `codex exec --sandbox workspace-write` with network on.

## Authentication

Default `sanitized` mode removes `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`,
`ANTHROPIC_BASE_URL`, `ANTHROPIC_CUSTOM_HEADERS`, `CLAUDE_CODE_OAUTH_TOKEN`,
`CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX` and
`CLAUDE_CODE_USE_FOUNDRY` from both probes and the model child. `inherit` keeps
these variables. Both retain saved CLI/provider configuration and wrapper behavior.
Neither attests subscription billing. The legacy `subscription` spelling also
requires `claude auth status --json` to report `loggedIn: true`; a login boolean
alone does not attest the billing route. No credentials or entire config dumps
are printed. Diagnose provider/login failures using the selected installation's
supported tools, under the caller's authorization.

Watch item: official docs say `--bare` is recommended for scripted calls and
may become the `-p` default. `--bare` skips OAuth/keychain and needs an API
key, which conflicts with subscription enforcement here — if a CLI update
flips that default, the wrapper must opt back out explicitly (the helper
never passes `--bare` today).

## Results and process ownership

Each run owns a private unique directory `$TMPDIR/claude-<run_id>-*` with an
atomic `receipt.json`, raw provider stdout/stderr (`provider.stdout`,
`provider.stderr`), preflight evidence and `result.txt`. Only the supervisor
writes lifecycle stdout. Receipts record run ID, selected executable/version,
phase, timestamps, `deadline_at` (wall clock, informational) and
`deadline_remaining` (monotonic; the supervisor's own clock decides a timeout),
child PID, exit status, output path and SHA-256. Usage errors (`--out` exists,
unreadable `--output-schema`, terminal stdin with no prompt) exit 2 before any
run directory or lifecycle line exists.
Existing `--out` files are rejected. A new destination is exclusively reserved;
failure removes that empty reservation, and success atomically publishes the
validated result. Old output cannot become a new run's result.

The CLI must exit zero and return a valid JSON result envelope without
`is_error`, error subtype or permission denials. With an output schema, extract
`structured_output` or parse JSON `result` after one optional outer fence.
Missing/blank payload fails. Usage fields are retained in the receipt; no model
text is interpreted as lifecycle control. A completed process may still give an
incomplete review: the caller checks required sections/scope/coverage itself.

The default 1800-second deadline includes preflight and stdin consumption.
Every subprocess gets its own POSIX session/group. TERM/INT or timeout sends TERM
to that owned group, then KILL after a bounded grace period; a signal arriving
during that cleanup is recorded as `deferred_signals` and never replaces the
first cause. Normal descendants are also stopped if their leader exits early:
after a leader exit, a descendant that cannot be verified (no `ps`) or stopped
is a `cleanup_warning` in the receipt and the child's exit code stands; exit
125 `CLEANUP_FAILED` is reserved for timeout/cancel paths with live members
remaining. No detached watcher is launched.
SIGKILL of the supervisor and deliberate independent-session daemonization are
outside this cleanup guarantee. A `DIED` receipt requires inspecting the owned
processes/workspace before restarting writes; never kill by executable name.

Watcher selection uses the latest run-specific START (or supplied receipt),
optionally pinned by `--run-id`. It validates the result hash for `DONE`.
`RUNNING` and `QUIET` are incomplete (exit 10); `QUIET` only describes silence
in provider stdout/stderr, ignoring supervisor activity. The watcher never
derives `TIMEOUT` from the wall clock: while the recorded supervisor PID is
alive the run is `RUNNING`/`QUIET`, and `DIED` means that PID is gone without
a terminal receipt. Failed, missing,
timeout, cancelled, cleanup-failed, died and unknown runs exit 1. Legacy marker-only logs do not
qualify. The watcher does not cancel work or spawn another watcher; the helper
owns the deadline.

Helper codes: 0 success; 2 usage/preflight; 3 missing login under legacy auth
check; 4 missing result; 124 timeout; 125 incomplete process cleanup;
127 missing executable; 130/143 cancellation; otherwise the child's failure
code (128+signal for a signal death). The codes are ambiguous on their own: a
child exiting 2, 3, 4, 124, 125 or 127 passes through unchanged and a probe
that dies by signal or exits 126+ is reported as 2. Read the receipt's
`status`, `diagnostic` and `child_exit_code` for the cause.

Run files remain for inspection. Every run sweeps sibling run directories of
this provider whose receipt is terminal and finished more than seven days
ago; `--keep` exempts a run from that sweep. Delete only the run directories
you own after collecting required evidence. `--no-session-persistence` does
not suppress these files, caches, wrapper/service logs or logs caused by
inherited settings. macOS/Linux/WSL require Python 3.10+, POSIX process groups
and a working `ps` (the runtime lists the owned group through it; interpreters
without `os.waitid`, CPython before 3.13 on macOS, also poll the leader with
it). Native Windows Python/Git Bash is rejected rather than pretending to
terminate a process tree.

Known limits: the capability probe matches literal flag names in
`claude --help` (including `--no-chrome` and, with `--effort`, `--effort`), so
paged or localized help and older CLIs fail the run without fallback.
`--max-turns` is the one exception: Claude Code stopped listing it in
`--help` while still honoring it (observed on 2.1.280, 2026-09-23 -- neither
`claude --help` nor `claude -p --help` mentions it, but `claude -p --max-turns
1 ...` still runs a real, single-turn-bounded session). A missing `--max-turns`
in the help text therefore falls back to a functional probe -- a closed-stdin,
promptless `-p` invocation that fails locally before any network/model call
either way, distinguishing "unknown option" (truly unsupported) from any other
local failure (supported but undocumented) -- instead of failing the run on
text absence alone. Interpreters without `os.waitid` fork `ps` on every poll
tick for the whole run; prefer CPython 3.13+ for long runs. The supervisor is
single-threaded (signal handlers plus a `preexec_fn`); `Run` is not safe to
drive from a threaded harness.

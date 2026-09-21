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

## Results and process ownership

Each run owns a private unique directory with an atomic `receipt.json`, raw
provider stdout/stderr, preflight evidence and `result.txt`. Only the supervisor
writes lifecycle stdout. Receipts record run ID, selected executable/version,
phase, timestamps, deadline, child PID, exit status, output path and SHA-256.
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
to that owned group, then KILL after a bounded grace period. Normal descendants
are also stopped if their leader exits early. No detached watcher is launched.
SIGKILL of the supervisor and deliberate independent-session daemonization are
outside this cleanup guarantee. A `DIED` receipt requires inspecting the owned
processes/workspace before restarting writes; never kill by executable name.

Watcher selection uses the latest run-specific START (or supplied receipt),
optionally pinned by `--run-id`. It validates the result hash for `DONE`.
`RUNNING` and `QUIET` are incomplete (exit 10); `QUIET` only describes silence
in provider stdout/stderr, ignoring supervisor activity. Failed, missing,
timeout, cancelled, cleanup-failed, died and unknown runs exit 1. Legacy marker-only logs do not
qualify. The watcher does not cancel work or spawn another watcher; the helper
owns the deadline.

Helper codes: 0 success; 2 usage/preflight; 3 missing login under legacy auth
check; 4 missing result; 124 timeout; 125 incomplete process cleanup;
127 missing executable; 130/143 cancellation;
otherwise the child's failure code. Read receipt status/diagnostic for context.

Run files remain for inspection; delete only the run directories you own after
collecting required evidence. `--no-session-persistence` does not suppress these
files, caches, wrapper/service logs or logs caused by inherited settings.
macOS/Linux/WSL require Python 3.10+ and POSIX process groups. Native Windows
Python/Git Bash is rejected rather than pretending to terminate a process tree.

---
name: codex
description: >-
  Run Codex CLI headlessly for an explicitly requested second opinion,
  cross-provider review, or implementation handoff. Requires an explicit model,
  defaults to read-only, and records a bounded run with a verified result receipt.
  Do not invoke merely because another model might be helpful.
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

## Execution

- Default: `--sandbox read-only`. Use `workspace-write` only for an authorized
  implementation handoff. `danger-full-access` is accepted only when the caller
  explicitly chooses it; no automatic escalation or retry changes sandbox/model.
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
  child's stdin; a pipe that never closes is bounded by the run deadline.
- `--review` selects `codex exec review`. `--json` retains provider JSONL in the
  run's stdout file. The final message remains the result file in either mode.
- `--fast` sets `service_tier=fast` and `features.fast_mode=true`.
  `--no-fast` / `--nofast` selects `service_tier=default`. These are mutually
  exclusive; omitting both inherits the configured tier. Config files are never
  rewritten.

## Result and lifecycle

Each invocation creates a private, unique temporary run directory containing
`receipt.json`, the provider stdout/stderr, preflight evidence and `result.txt`.
Only the supervisor writes lifecycle stdout: `CODEX_RUN_START` and
`CODEX_RUN_EXIT` followed by JSON with `run_id` and `receipt`. Model text cannot
supply control records. The receipt records the selected executable/version,
status, exit code, output path and result digest.

`--out` must name an unused file. The helper reserves it exclusively, publishes
only a nonempty final result after successful CLI exit, and removes its empty
reservation on failure. An existing output is never reused or overwritten.
Without `--out`, read the receipt's unique `output` path. A successful receipt
proves process/result completion, not the truth or completeness of the review;
apply the caller's expected report/schema/coverage checks too.

The default overall deadline is 1800 seconds; `--timeout <seconds>` changes it.
Version/help probes are limited to 10 seconds each (`--preflight-timeout`).
TERM/INT and deadline expiry terminate the owned child process group, wait
briefly, then kill remaining group members. No detached watchdog is started;
`--no-watchdog` is retained as a no-op. SIGKILL of the supervisor and descendants
that deliberately create independent sessions cannot be cleaned by a signal
handler. Inspect the receipt/processes before retrying an interrupted write run.

For a background run, capture lifecycle stdout in a fresh log and use a bounded
wait loop owned by the caller. The watcher itself runs once:

```bash
bash "$CODEX_SKILL_DIR/scripts/codex-watch.sh" /absolute/run.log
# Or inspect receipt.json directly; pin --run-id when following an appended log.
```

Watch statuses: `DONE` (exit 0); `RUNNING`/`QUIET` (exit 10, incomplete);
`FAILED`, `MISSING`, `TIMEOUT`, `CANCELLED`, `CLEANUP_FAILED`, `DIED`, `UNKNOWN` (exit 1).
`QUIET` means no recent provider output, not a proven stall. It ignores
supervisor activity. The latest run-specific START selects the receipt; an old
EXIT line is never completion evidence. A missing or changed result fails.
Legacy marker-only logs must be inspected manually, never accepted as a gate.

Helper exit codes: 0 success, 2 usage/preflight failure, 4 missing result,
124 timeout, 125 incomplete process cleanup, 127 missing executable,
130/143 cancellation, otherwise the child
failure code. Inspect the recorded diagnostic and logs to distinguish causes.

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

`--ephemeral` avoids saved Codex session rollouts; it does not erase caches,
wrapper/service logs or this helper's explicit run files. Read-only Git queries
are valid; writes to linked worktree Git metadata may need separate permissions.
macOS, Linux and WSL with Python 3.10+ are supported. Native Windows/Git Bash is
rejected because this helper requires POSIX process-group ownership.

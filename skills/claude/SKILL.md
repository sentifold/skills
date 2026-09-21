---
name: claude
description: >-
  Run Claude Code headlessly for an explicitly requested second opinion,
  cross-provider review, or implementation handoff. Requires an explicit model,
  defaults to read-only tools, and records a bounded run with a result receipt.
  Do not use merely because another model might be helpful.
---

# Claude

Resolve this skill's absolute directory from the loaded `SKILL.md`; a global
symlink is supported. Keep the target repository as the working directory.
The installed release must include its shared `lib/provider_runtime.py`.

```bash
CLAUDE_SKILL_DIR="/absolute/path/to/loaded/claude"
bash "$CLAUDE_SKILL_DIR/scripts/claude-ephemeral.sh" \
  --model <requested-model> --cd /absolute/repository \
  --out /absolute/unused-answer.md -- "Review the current diff for correctness."
```

`--model` is required, never substituted. Set `--effort` only when selected by
the user or target project's workflow; otherwise inherit the CLI setting. Read
that project's `AGENTS.md` for checks and review/publication policy. There are no
engine/build rules in this shared skill.

The prompt follows `--` or arrives on stdin. An argument prompt closes the
child's stdin. The helper runs print mode without a PTY or saved session;
provider output is retained separately from supervisor lifecycle records.
Read [references/runtime.md](references/runtime.md) before using authorization,
configuration, process or result assumptions in an automated gate.

## Modes and options

- Default `--mode read-only`: `dontAsk`, `Read,Grep,Glob,Bash`, plus
  `WebSearch,WebFetch` unless `--no-search`. Shell pre-approvals cover only plain
  `git diff/status/show/log/rev-parse/merge-base/grep` and `rg` commands.
  Use the repo as cwd; a `git -C ...` form does not match those grants.
- `--mode workspace-write`: `acceptEdits` and adds `Edit,Write`. Use only for an
  authorized implementation handoff. This is a permission policy, **not an OS
  filesystem sandbox**. Inspect the diff and validate the reported work.
- Repeat `--allow-bash '<specific command pattern>'` for explicitly needed test
  commands. Avoid blanket Bash grants. Shell/Git behavior and inherited hooks
  remain part of the selected CLI's trust boundary.
- `--cli /exact/executable` or `CLAUDE_BIN`; otherwise first PATH `claude`.
  Failed version/capability probes stop; no alternate executable is tried.
- `--timeout <seconds>` defaults to 1800; `--preflight-timeout` defaults to 10;
  `--max-turns` defaults to 32. All are finite limits.
- `--out <unused-file>` publishes a final result only after a clean CLI exit and
  successful JSON envelope. Existing files are rejected. Otherwise use the unique
  result path in the run receipt.
- `--output-schema <file>` forwards a JSON Schema. The CLI enforces it; the helper
  extracts `structured_output` or parses JSON from `result`. The caller still
  checks task-specific report coverage.
- `--agent <name>` uses a named agent and permits `Agent` tool calls. The named
  definition must be installed separately; it is not bundled into this skill.
- `--auth sanitized` (default) removes obvious API/provider env overrides while
  inheriting saved configuration/login. `--auth inherit` keeps those variables.
  Legacy `--auth subscription` additionally checks `loggedIn`; this is **not**
  a guarantee of subscription billing or authentication provider.
- `--no-watchdog` is a compatibility no-op: no detached watcher is started.

The helper prints `CLAUDE_RUN_START` and `CLAUDE_RUN_EXIT` with a unique `run_id`
and receipt path. Model text, raw JSON envelope and errors stay in the private
run directory. Follow a background log with a bounded caller-owned loop using:

```bash
bash "$CLAUDE_SKILL_DIR/scripts/claude-watch.sh" /absolute/run.log
```

The watcher runs once: `DONE` exits 0; `RUNNING`/`QUIET` exit 10; failure,
missing/changed result, timeout, cancellation, death or unknown state exit 1.
Pass a receipt path directly or `--run-id` to pin an appended log. Silence is
not proof of a stall, and old EXIT lines are not successful completion evidence.

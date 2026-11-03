# Codex runtime findings

Field notes on the `codex` CLI and the Claude Code harness, not any one
machine. The helper's own contract (receipt, result file, exit codes) is in
[SKILL.md](../SKILL.md).

## Helper invocation rules

**This helper is the ONE tested way to drive Codex from Claude Code.** Do not invoke
`codex` directly from tool shells: in interactive shells `codex` is often a user
function adding proxy env + bypass flags via a private helper that does NOT exist
in non-interactive shells — the call dies with `command not found` (exit 127). The
helper calls the PATH binary, which needs no proxy (verified 2026-06-06: runs fine
without it).

This applies at every agent depth: **subagents reach Codex the same way** — the
helper is a plain Bash script, so any subagent with the Bash tool can run it
(e.g. a profiler agent getting a second opinion on findings). There is no
`codex` subagent type; never try to spawn Codex through the Agent tool.

**Take the model from `~/.codex/config.toml`; do not guess it from the family name.** Which
models a login may use is gated by the account type, and a wrong pick burns the whole run at
the first request. A guessed model ID can fail even with a valid ChatGPT login:
`400 invalid_request_error: The 'gpt-5.6-codex' model is not supported when using Codex with a
ChatGPT account.` (observed 2026-07-30, codex-cli 0.144.5). The `model = "..."` line in
`~/.codex/config.toml` is the model that login is known to accept, and `model_reasoning_effort`
next to it is an effort tier it is known to allow — read both before overriding `--model`. Two
lines print *before* the rejection and are noise, not the cause: `failed to load models cache:
missing field supports_reasoning_summaries` and `Model metadata for <m> not found. Defaulting
to fallback metadata`.

`gpt-6-astra` supports `low`, `medium`, `high`, `xhigh`, and `max`, but not `none`;
check a different model's supported efforts before overriding them. See the
[official Astra guide](https://developers.openai.com/api/docs/guides/latest-model).

**New sibling models (added 2026-09):** `gpt-6-sol` is the mid-tier model --
"built to power complex coding and agentic workflows," cheaper/faster than
`gpt-6-astra` -- and `gpt-6-luna` is the cheapest/fastest tier, for
high-volume/low-depth tasks; both list `none` as a supported effort alongside
`low`, `medium`, `high`, `xhigh`, `max` (Astra does not support `none`). Source:
the [models reference](https://developers.openai.com/api/docs/models). `gpt-6-sol`
is a reasonable default for an implementation/bulk leg that does not need
Astra-grade judgment. Directly verified through this helper: `--model gpt-6-sol
--effort low` is accepted by this login and completes (2026-09-23); its other
listed efforts were not each individually re-verified here, only sourced from
the reference above -- same caveat for every `gpt-6-luna` effort. As always,
take the model from `~/.codex/config.toml` rather than guessing account access
from the family name.

## Speed is per invocation

Map a requested `fast` run to `--fast`, and `nofast` / Standard to `--no-fast`.
Keep the chosen model and reasoning effort: Fast changes the requested service
tier, not reasoning depth.

| Helper option | This new Codex run |
| --- | --- |
| `--fast` | Override `service_tier=fast` and `features.fast_mode=true`; CLI sends `priority`. |
| `--no-fast` / `--nofast` | Override `service_tier=default` (Standard), even if config prefers Fast. |
| Neither | Use the effective Codex config, including the caller's `CODEX_HOME` and project configuration. |

The helper starts a new ephemeral CLI process. It does **not** inherit a parent
Claude/Codex chat's per-task speed. When delegating or retrying with a desired
speed, pass the same explicit flag to each helper invocation, at every agent
depth. These overrides apply only to the child run; they do not edit config or
change the parent's speed. Contradictory flags fail before Codex starts. The
provider must support and honor the requested tier; `--fast` alone is not proof
of delivered acceleration. Ultrafast is outside this helper's explicit options.

## Modes

**1. Analyze / verify / second-opinion (read-only)** — the safe default.
```
bash "$CODEX_HELPER" --model <m> --sandbox read-only -- "<question + what to read>"
```

**2. Implement / fix (write)** — Codex edits files in place inside the repo.
```
bash "$CODEX_HELPER" --model <m> --sandbox workspace-write --cd /abs/repo -- "<task>"
# then review what it changed:  git -C /abs/repo diff
```
Writes are confined to `--cd` **plus the system temp dirs** (`$TMPDIR`, `/tmp` —
verified writable 2026-06-06, so `mktemp`-based test fixtures work). Outbound
network is DENIED under workspace-write (verified: `curl` fails) — pass `--network`
when the task needs downloads; a `git fetch` into the repository fails even then
(`.git/` is read-only), so fetch before the handoff.

The battle-tested delegation contract (used for real fixes on a large PR):
1. Write the task spec to a file (full context: defect, exact files, required
   tests, how to verify). Pass it as `"$(cat /tmp/task.md)"`.
2. In the spec, demand: surgical edits only, **DO NOT commit** (leave the working
   tree dirty), run the named tests, print a short summary of changes at the end.
3. Run with `--sandbox workspace-write --cd <repo>`, in the background, with its
   own log file; `--out <file>` for the final summary.
4. Caller (you) independently re-runs the tests, reviews `git diff`, and commits
   with proper attribution. Never trust "tests passed" claims without re-running.
5. Parallel sessions are fine on DISJOINT file sets in the same worktree (verified:
   two concurrent write sessions, zero interference); tell each session which
   paths the other owns so it keeps off them.

**3. Code review** — ephemeral review of the current repo/diff.
```
bash "$CODEX_HELPER" --model <m> --review --cd /abs/repo -- "focus: <area>"
```

**4. Bulk / batched** — many items without exhausting one turn or flooding the app.
Keep each run focused (~10–15 items, read only the cited locations); run in parallel,
one output file each:
```bash
for b in batch_1 batch_2 batch_3; do
  PROMPT=$(cat <<EOF
Read items from /abs/path/$b.json. For EACH, open ONLY the cited file/lines under
/abs/worktree/<file> (don't read unrelated files). Decide <verdict...>. Output ONLY
a JSON array wrapped between <<<RESULT_BEGIN>>> and <<<RESULT_END>>>. No prose outside.
EOF
)
  bash "$CODEX_HELPER" --model "$MODEL" --sandbox read-only \
    --out "/abs/path/result_$b.txt" -- "$PROMPT" > "/abs/path/run_$b.log" 2>&1 &
done
wait
```
This pattern turned a single 75-item run (8.8M tokens, 36-min stall) into five
parallel ~2-minute batches. This `&`/`wait` form is safe only inside one shell
invocation that owns every child process. In Claude Code tool calls, use the
harness background-call pattern below instead of splitting launch and wait
across separate calls.

## Output contract: markers, not arbitrary files

The sandbox blocks out-of-workspace writes, so do NOT ask Codex to write an output
file. Read the final message (`--out <file>` or the receipt's `result.txt`), not the
transcript and `tokens used` footer in `<run>/provider.stdout`. Tell Codex to wrap the
payload in unique markers and extract the **last** pair caller-side (an earlier
truncated preview can also contain the opener).

```python
e = txt.rfind('<<<RESULT_END>>>'); b = txt.rfind('<<<RESULT_BEGIN>>>', 0, e)
blob = txt[b+len('<<<RESULT_BEGIN>>>'):e]
blob = blob[blob.index('['):blob.rindex(']')+1]
data = json.loads(blob, strict=False)   # strict=False: reasoning strings may hold raw newlines
```

## Runtime findings baked in (why this skill exists)

These are the failure modes we hit driving Codex; the skill is shaped to avoid them:

- **Sandbox boundaries (verified 2026-06-06):** `read-only` = no writes anywhere.
  `workspace-write` = writes inside `--cd` **and** the system temp dirs (`$TMPDIR`,
  `/tmp` both writable — mktemp test fixtures work), but **no outbound network**
  (`curl`/downloads fail; pass `--network` to allow). Other absolute paths are
  blocked — capture results via `--out`/the result file, not via files at arbitrary paths.
- **`workspace-write` keeps `.git/`, `.agents/` and `.codex/` at the top of `--cd`
  read-only (verified 2026-11-03 on macOS, codex-cli 0.162.1, standalone clone).**
  There `apply_patch` answers `writing outside of the project; rejected by user
  approval settings` and the shell `operation not permitted`, even for a `.codex/`
  that does not exist yet; so git mutations fail (`.git/index.lock`) in a standalone
  clone too, not only in a linked worktree (below). Other dot-directories
  (`.github/`, `.claude/`) and the same names deeper down (`docs/.agents/`) stay
  writable. A handoff that edits a repo's own skills learns it only from the final
  message: in sentifold/sleash#1069 every target was under `.agents/skills/`, and
  Codex tested its patch on temporary copies and left the repository unchanged.
  Pattern that works: for files under `.agents/` or `.codex/`, have the spec ask for
  a unified diff in the final message, between markers, and `git apply` it from the
  caller; or run `--sandbox danger-full-access` with a hard constraint line in the
  prompt (the files it may write; no git mutations, builds or setup commands).
- **Linux: `read-only` can fail to run ANY command where bubblewrap cannot create
  namespaces (verified 2026-09-11).** Codex's Linux sandbox is bubblewrap; on a host
  that denies it (container, hardened kernel, restricted user namespaces) every
  command in the session dies with `bwrap: loopback: Failed RTM_NEWADDR: Operation
  not permitted` **before** it runs, and the model silently falls back to reviewing
  the prompt instead of the code — it answers fluently, so the run looks successful
  until you notice it cites no file. Tell-tale line in the output:
  `warning: Codex's Linux sandbox uses bubblewrap and needs access to create user
  namespaces`. Check any read-only verdict for real file citations; if there are
  none, re-run with `--sandbox danger-full-access` and a HARD CONSTRAINT line in the
  prompt ("read-only reviewer — no file writes, no git mutations, no builds"), which
  restores file access without Codex's own sandbox. (Real cost: three design
  validations and one review leg wasted before the pattern was spotted.)
- **A sandboxed run on a Linux host that forbids user namespaces reads NOTHING and still
  exits 0 with a confident answer.** With `kernel.apparmor_restrict_unprivileged_userns=1`
  (the default on current Ubuntu), every `--sandbox read-only` / `workspace-write` run dies
  inside bubblewrap with `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`
  *before* it executes a single command, and Codex then answers from the prompt alone. The
  run looks healthy — exit 0, a structured verdict, plausible file-by-file discussion — and
  the only tells are that one line and a suspiciously small output (10 KB rather than
  hundreds). Observed 2026-09-12: three design validations came back polished and worthless;
  the diagnosis was one sentence, "Repository reads are blocked", buried mid-answer.
  Detect with `bwrap --dev-bind / / --unshare-net true`. Where that fails, pass
  `--sandbox danger-full-access` — which such a host's own `~/.codex/config.toml` may already
  declare as its `sandbox_mode` — put an explicit read-only instruction in the prompt for an
  analysis run, and confirm afterwards with `git status --porcelain` that nothing was
  written. On a Linux host, grep any finished run's `<run>/provider.stdout` and
  `<run>/provider.stderr` (paths in the receipt) for lines that begin with
  `bwrap: ` (`^bwrap: `, the sandbox's own diagnostics, whatever follows the
  prefix) and confirm in the transcript that the run's commands failed, before
  trusting a word of it. A match inside a line is no evidence: this note and
  the review-agent skill quote the word, and a run that reads them echoes it
  (observed on macOS, whose sandbox is not bubblewrap at all).
- **Git worktrees: Codex cannot run git AT ALL under `workspace-write` (verified
  2026-07-28).** A linked worktree's git metadata lives in the MAIN clone
  (`<main>/.git/worktrees/<name>/index.lock`, plus shared `objects`/`refs`) —
  outside any `--cd` you'd sanely grant, so `git add/commit/merge/checkout` die
  with `Unable to create ...index.lock: Permission denied`. (Real cost: a
  7-branch integration merge stalled mid-conflict.) Pattern that works:
  **driver-git + file-only resolution** — the caller runs every git command
  (merge, add, commit); Codex's task spec says "FILES ONLY — NO git commands"
  and it only edits/resolves conflict markers in the working tree. Also budget
  for npm installs: the sandbox blocks the registry, so new deps added to
  package.json must be `npm install`ed by the caller afterward.
- **Web search is a provider-side tool, not a sandbox network toggle (verified
  codex-cli 0.142.5).** `--search` is a **top-level** flag — `codex exec --search`
  fails with `error: unexpected argument '--search' found`, so the helper injects it
  *before* the `exec` subcommand. It enables the native Responses `web_search` tool,
  which runs on the provider side; it therefore needs no local network and works
  under `--sandbox read-only`, and is orthogonal to `--network` (the local outbound
  toggle). The helper turns it **on by default** because the verify/second-opinion
  path is exactly where web-grounded claims must be checked — leaving it off is what
  made Codex return UNVERIFIED for trivially checkable public facts and forced manual
  cross-checks. Use `--no-search` only for an intentionally hermetic/offline run.
- **One turn is finite.** A single run handed dozens of items exhausts the turn before
  producing output. Batch (mode 4).
- **Reasoning effort drives latency.** An omitted `--effort` inherits the Codex
  config; the helper does not force `max`. Astra supports `max`, but deep reasoning
  can make even trivial prompts take minutes. Pass `--effort low` (or `medium`)
  for verification/bulk passes only when the task permits less depth. Preserve
  the existing effort for a model migration when the target supports it.
- **Launch each run as ONE `Bash(run_in_background: true)` call — never `&` + a separate
  poller.** In the Claude Code harness, shell state (and thus `wait`) does NOT survive a
  tool-call boundary, and a `cmd &` child started inside a *foreground* Bash is left
  untracked/orphaned — so the only "wait" you can build is a brittle second `kill -0 $pid`
  poller that can fire early or miss the real exit. Instead run the helper itself as a
  single backgrounded Bash command:
  `Bash(run_in_background: true): bash <helper> ...args... > out.txt 2>&1`. The harness then
  owns the process, keeps it alive across turns, and re-invokes you with a real completion
  notification when it actually exits — then read the result file named in `out.txt`'s
  `CODEX_RUN_EXIT` line (`out.txt` itself holds only the START/EXIT lifecycle lines). For
  parallelism, issue several such background calls, each with its own output file. This is
  a genuine push notification with no polling — unlike the plugin's detached, poll-only
  `task --background` (where you must poll `/codex:status`).
- **`Reading additional input from stdin...` in the provider output is harmless.** The
  helper closes stdin for argument prompts, so the run proceeds.
- **Output is buffered; silence ≠ hang.** `codex exec` does not stream — the
  transcript, final message, and `tokens used` footer appear only when it finishes
  (minutes at `high`/`xhigh`). Don't kill a quiet run. To tell "working" from
  "stuck", check that the receipt's `child_pid` is burning CPU (`ps -o
  pid,%cpu,etime -p <child_pid>`) or that `<run>/provider.stdout` is growing — not the
  absence of output. `codex-watch.sh` reports such a run as `QUIET`, never as a stall.
- **Judge a run by its lifecycle records, not by notifications.** The helper prints
  `CODEX_RUN_START` first and `CODEX_RUN_EXIT` last; a run with no `CODEX_RUN_EXIT` is
  not done, whatever a notification says. Check a run one-shot with
  `bash "$CODEX_SKILL_DIR/scripts/codex-watch.sh" <out.txt>`: it derives `DIED` from the
  receipt plus pid liveness and exits 10 while the run is live.
- **Relaunching an interrupted run: write a RESUME NOTE, verify remote state first.**
  When a run dies mid-task (kill, session stop), do not re-issue the original spec
  blindly: (1) check what it completed (its output file tail + the workspace/remote
  state it mutated — checkouts, warm build dirs, half-written files); (2) append a
  RESUME NOTE to the spec stating what is already done and where to continue
  (e.g. "checkout already at <sha>, buck-out warm — skip fetch, start at STEP 2");
  (3) clean leftovers that would poison the rerun (stale locks, partial sandbox
  homes) before relaunching. Resumed runs are dramatically cheaper — never restart
  cold what can resume warm.
- **`read-only` cannot RUN tools that write a daemon/cache/lock.** Under
  `--sandbox read-only` Codex can't run e.g. `buck2` (needs a daemon + `buck-out`
  writes), so it reports it "could not execute" them and falls back to **static**
  review. If the task must actually *run* a build/test/lint tool, use `--sandbox
  workspace-write --cd <repo>`; with `read-only`, expect static-analysis-only findings
  (verify the runnable parts yourself).
- **Track your run by its output file and receipt, not `pgrep`.** Parallel batches and
  other worktrees' Codex jobs make `pgrep codex` ambiguous. Give each run its own output
  file and identify it by the receipt's supervisor `pid` and `child_pid`, rather than
  guessing which `codex` process is yours.
- **A routed provider hides the built-in `image_gen` tool (verified 2026-09-18,
  codex-cli 0.154.0).** Where the CLI reaches the model through an account-rotation
  proxy — a custom `model_providers.<name>` entry whose backend forwards only
  `/responses`, `/models` and `/alpha/search` — the image tool has nowhere to post:
  it wants `{backend}/codex/images/generations`. Codex then never offers it and says
  "built-in image_gen is unavailable in this session" even though `codex features list`
  reports `image_generation stable true`. This helper cannot fix it, because the
  provider is the caller's configuration, not the helper's.
  For an image, run the official CLI binary from inside the npm package
  (`@openai/codex-<platform>/vendor/<triple>/bin/codex`) against the primary login,
  bypassing the routing wrapper, with the API-key variables unset so the subscription
  is used: `env -u OPENAI_API_KEY -u CODEX_API_KEY <binary> exec --ephemeral
  --skip-git-repo-check --sandbox workspace-write -C <dir> -m <model>
  -c mcp_servers.node_repl.enabled=false "<prompt>" </dev/null`. That bills the primary
  account rather than the pool. Ask for the PNG to be copied out of
  `$CODEX_HOME/generated_images/` into the workspace and its path printed. One image per
  run, several runs in parallel; a prompt that fails three times with
  `error sending request for url (.../images/generations)` while its siblings succeed is
  prompt-specific, so rephrase it rather than retry.
- **Headless runs cannot use browser MCPs — the helper disables `node_repl` (cua_repl).**
  `codex exec` runs with `approval: never`; the browser MCP asks approval per
  navigation, is refused every time, and the model then reports "web access was
  denied" instead of falling back to the provider-side `web_search` (observed
  2026-09-15, a whole review delivered with unverified prices). The helper now
  passes `-c mcp_servers.node_repl.enabled=false`; `--browser-mcp` re-enables it.
  In the prompt, say "use the built-in web_search tool for web facts".
- **MCP auth noise in stderr is benign.** Startup may log
  `ERROR rmcp::transport::worker: ... AuthRequired ... invalid_token` for MCP servers
  configured in `~/.codex` (e.g. Linear) whose tokens expired. The run proceeds
  normally — don't treat it as a failure or wait for it to clear.
- **Never use an interactive `codex` shell function from scripts** (exit 127 on a
  missing private helper; see the rules above). Also skip ad-hoc proxy wrappers:
  the plain binary authenticates fine via `~/.codex` (verified).

## Checklist

- [ ] ALWAYS go through the helper script — never the bare/interactive `codex` from a tool shell.
- [ ] Default to `--sandbox read-only`; only `workspace-write --cd <repo>` when edits are required.
- [ ] Task needs downloads / any network? Add `--network` (workspace-write denies it by default). A `git fetch` into the repo fails even with it: fetch before the handoff.
- [ ] Web search is ON by default so verify/second-opinion runs can cite public facts; pass `--no-search` only for a deliberately hermetic/offline run. (`--search`/`--network` are unrelated — provider tool vs local sandbox net.)
- [ ] Linux host? Grep the finished run's `provider.stdout`/`provider.stderr` for lines beginning `bwrap: ` and confirm its commands failed before trusting a verdict that cites no file. Elsewhere skip the grep: a quoted `bwrap:` inside a line is skill text the run read.
- [ ] Write-mode spec: surgical edits, DO NOT commit, run named tests, print summary; then re-verify and commit yourself.
- [ ] Bulk → batch in parallel; never one run over dozens of items. Parallel write sessions only on disjoint file sets.
- [ ] Structured output via markers in the final message; single-run prose verdict via `--out <file>`. Never a file at an arbitrary absolute path.
- [ ] Read `model` / `model_reasoning_effort` from `~/.codex/config.toml` before choosing `--model`; do not invent IDs or infer account access from a model-family name.
- [ ] Pass `--fast` or `--no-fast` for an explicit speed choice; repeat it on each delegation/retry. Omission uses Codex config, not the parent chat speed.
- [ ] Omitted `--effort` inherits config. Astra supports `low|medium|high|xhigh|max`, not `none`; preserve the configured effort unless the task calls for a different tier.
- [ ] Need Codex to actually RUN a daemon-backed tool (a build system, a test runner)? Use `workspace-write --cd <repo>`, not `read-only` (which can only review statically).
- [ ] Quiet run? Don't assume a hang — check the `child_pid`'s CPU / growing `provider.stdout`.
- [ ] Ignore startup `rmcp ... AuthRequired` stderr noise from expired MCP tokens.

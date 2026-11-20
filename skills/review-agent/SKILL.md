---
name: review-agent
disable-model-invocation: true
argument-hint: "[scope]"
description: "Second-order layered review of a change scope — assumes a first-order pass (orchestrate's Code Review gate, /code-review, or codex review) already ran; an orchestrator subagent picks the relevant lenses, inspects them itself, runs a cross-provider leg, validates findings, and reports exact coverage. Use only when the user invokes review-agent or an explicitly invoked workflow names this gate."
---

# Review Agent

Layered, cross-validated review of a change scope, built on native subagents —
no external runner. This is the **second-order** pass: it assumes the
first-order pass — orchestrate's Code Review gate, `/code-review`, `codex review`,
or `/simplify` — already ran on this scope. It does not re-hunt what those
passes own (local correctness bugs, hygiene, readability, generic
simplification); its value is the project-encoded, cross-cutting judgment
they structurally lack: contracts, lifecycle, architecture, platform behavior,
and follow-through. For an
explicitly requested standalone review, include the first-order fallback below.
Review source without editing it.

The person invokes it explicitly (`/review-agent` in Claude Code,
`$review-agent` in Codex). The model must not launch it from ambient review
intent. One chained entry is sanctioned: an explicitly user-invoked workflow
whose contract names this pass (the Final Review gate of `orchestrate` or
`delegate`) carries the user's consent, and its driver runs it by spawning the
`review-orchestrator` subagent directly — never through the Skill tool, which
refuses `disable-model-invocation` skills by design. That refusal is expected,
not a consent failure and not a reason to stop.

## Establish the two roots

`SKILL_DIR` is the real installed directory containing this file; `SKILLS_ROOT`
is its parent. Resolve symlinks. Package references and provider helpers live
under these roots, independently of the repository being reviewed.
`PROJECT_ROOT` is the target checkout, supplied by the caller or resolved with
`git rev-parse --show-toplevel` from the user's working directory.

Read target root and applicable nested `AGENTS.md`/`CLAUDE.md`, its CI and
architecture documentation, and optional `.agents/project-workflow.md`. Follow
[the project contract](references/project-contract.md). A profile path is relative
to PROJECT_ROOT; a link in this package is relative to the linking file.

## Topology

The **calling agent** does exactly one thing: spawn a single
**`review-orchestrator`** subagent with the change scope, then relay the
orchestrator's report. Both runtimes install the def from this package
(`agents/claude/review-orchestrator.md` and
`agents/codex/review-orchestrator.toml`). The def is deliberately thin: it Reads
this file and executes the orchestrator role below. Keep the user's session
clean — no lens work in the caller.

The orchestrator applies every selected lens itself, in one pass while the
cross-provider leg runs, and spawns no lens or verifier children.

Wait for it synchronously where the runtime lets the caller wait on a child
(`claude -p`, the Agent SDK, Codex). Claude Code's interactive clients — the
terminal, and since 2.1.302 the desktop app and VS Code — run every subagent
the main conversation spawns in the background: the report arrives as a
completion notification in a later turn, so advance other ready work or end
the turn, and never poll. Neither shape transfers the obligation: the caller
is done only once it holds a result that opens with the completion line
below. **A completion notification is not a result.** An orchestrator that stops with "the legs are
running" produces a notification indistinguishable from a finished run — if
what comes back is not the report shape, resume it (see "Resuming an
interrupted run") and never relay a progress note as the review.

Follow [the bounded lifecycle](references/lifecycle.md). Record every child/job
handle, assigned lenses, immutable scope, status, and result. A child that ends
with “the legs are running” has returned progress, not a review. If a supported
resume/message tool exists, use it once with the missing work; otherwise collect
its available job results and finish in the parent. If their handles or
results are inaccessible, report that coverage as missing. Never loop forever,
relaunch a completed leg, or report COMPLETE on the basis of a notification.

## Orchestrator procedure

The **orchestrator** owns the whole run:

1. **Resolve the scope.** Preserve an explicit PR, commit range, branch, or
   `uncommitted` scope exactly. Otherwise use a known stack parent,
   `branch.<name>.gh-merge-base`, then the selected remote's default branch
   (`refs/remotes/origin/HEAD` for origin). Do not assume a branch name or use
   `HEAD~1` to guess the scope. If there is no authoritative base, collect the
   available refs and ask for the missing target. Resolve a bare branch name
   against its remote-tracking ref (`origin/<branch>`) when that ref exists — a
   linked worktree's local branch is often frozen behind the remote.

   Run the read-only [scope helper](scripts/resolve_scope.py) to record the
   scope; it applies the base order and the remote-tracking rule above, refuses
   an unmerged index or an in-progress merge/rebase/cherry-pick, pins its diff
   settings so the digest is machine-independent, and reports `base_upstream`
   plus a `warnings` entry when the local base branch is behind its remote. Run
   it from any directory, with quoted absolute paths:

   ```bash
   python3 "$SKILL_DIR/scripts/resolve_scope.py" --repo "$PROJECT_ROOT"
   python3 "$SKILL_DIR/scripts/resolve_scope.py" --repo "$PROJECT_ROOT" --base "$BASE"
   python3 "$SKILL_DIR/scripts/resolve_scope.py" --repo "$PROJECT_ROOT" --mode uncommitted
   ```

   Use `--base <left> --head <right> --exact-base` for an exact two-commit
   range (no upstream substitution); `--head <branch>` alone derives the stack
   parent from that branch; `--include-worktree` adds current tracked and
   untracked changes to a branch scope. Default branch mode reports excluded
   dirty paths explicitly. Record the resolved commit IDs, `base_upstream`,
   warnings, snapshot digest, and `changed_count`; hand the same IDs to every
   reviewer. Quote `changed_count` — the length of `changed_paths`, a rename
   counting both its paths — wherever a prompt or report states the scope's
   size, never a hand count (observed: a Final Review told its cross-provider
   leg 72 paths for a range of 73). The
   helper excludes Git-ignored files; review those separately if explicitly in
   scope. Dirty submodules require their own snapshots because a parent gitlink
   does not fingerprint their contents. Do not fetch or mutate Git merely to
   resolve a scope; if remote refs may be stale, report that limitation or
   refresh within the user's authorized workflow. When the helper reports a
   missing `refs/remotes/origin/HEAD`, its message names the repair (`git remote
   set-head origin -a`), which contacts the remote — run it only under that same
   authorization. For PRs, verify the actual base/head from GitHub, then resolve
   those refs locally. Never silently substitute another diff.

   Skim the diff and the touched files enough to know what the change is.
   While skimming, hold the four approach questions — what is the goal; is
   this the right placement; does an existing mechanism already do this; is
   there a meaningfully simpler design? Doubt on any of them engages
   `review/design-architecture.md` regardless of archetype.
2. **Run deterministic checks** for the touched file types — the applicable
   rows of the target project's CI documentation, scripts, and profile.
   Cheap, local, no model cost. Reuse fresh results for this snapshot when
   available. Run only applicable authorized checks. Failures become
   findings; do not fix anything. Report their real result: missing tools or
   environment are unavailable checks, not code defects or passes. Some tests
   write build output: keep source review read-only and use an isolated
   checkout/output directory when needed.
3. **Select lenses** from the archetype map below;
   `review/correctness-runtime-safety.md` is always one of them. Engage the
   first-order fallback only when the user says no first-order pass ran on
   this scope, or asks for a full standalone
   review; its narrower form covers the ranges the caller names as read by no
   first-order pass. Do not auto-escalate when relevance is unclear; note the
   skipped borderline lens in the report instead. Select every lens the
   diff's surfaces call for, all five when all apply.
4. **Run both legs in parallel.** You own this run to completion: **do not end
   your turn while a provider job is still working**. Wait in the bounded
   calls the lifecycle allows, retaining every handle, and spend the gaps
   collecting finished results — not writing status notes. Once your own pass
   is finished you will have no other pending action; **that is the cue to emit
   the wait call, not to write a status note.**
   - **Own-engine leg**: your own pass, made after launching the cross-provider
     leg in the background and before waiting on it. Read the family's common
     doc first
     ([review-common](references/review-common.md) for `review/*` lenses,
     [linter-common](references/linter-common.md) for `linter/*`), then each
     lens doc, the applicable project overrides, and any project-provided
     escape weights. Investigate with tools and return findings in that common
     doc's output format.
   - **Cross-provider leg**: one holistic session on the other engine, given
     the same scope, the same selected lens doc paths plus the project
     overrides, and the same instruction to read the common doc first and
     resolve the diff itself. Hand it the change's stated limitations, each
     PR description's included (observed: given only the design's, a leg
     reported a limitation a PR had stated as a finding). Tell it to run
     plain `git diff` / `git show` /
     `git log` forms from the repo root — where a project's wrappers
     pre-approve only those exact forms, variants like `git -C <path> diff`
     fail closed and waste the run. See "Cross-provider leg" below for the
     helper contract.
5. **Validate.** Merge and dedupe findings from both legs. Every finding that
   survives must be verified against the actual code by you. Drop what
   does not survive; mark provenance (`corroborated` when both legs found it,
   `single-leg` otherwise). Distinguish introduced regressions from existing
   causes exposed by this change. "No issues found" is a valid outcome. Do not
   invent findings to fill a quota.
6. **Recheck scope.** Compare the reviewed commit IDs and worktree digest to the
   current target (rerun the scope helper). If it changed, the report covers
   the old snapshot only. Re-review affected coverage when authorized; do not
   certify the newer tree with stale results.
7. **Report.** Return the whole report directly to the caller: finding
   counts by severity, every verified finding, lens selection with one-line
   rationale, and legs status (effective model, effort, duration, failures).
   Write no report file: where the user or the target project contract asks
   for one, the caller saves the returned report verbatim at a local path it
   selects, because the desktop app refuses a subagent's report file in any
   location ("Subagents should return findings as text, not write report
   files"; observed in every pass of two orchestrate runs). Publishing a
   report is a separate action.
   If any leg ran on a fast/cheap tier, flag the run as degraded —
   judgment work belongs on strong models.

   **Open the summary with one of exactly two lines**, so a caller can tell a
   finished run from an abandoned one without reading it (see "Result
   contract"). Anything else the caller receives — a progress note, a plan, an
   apology — means the run did not finish, whatever the notification said.

The orchestrator is read-only with respect to the source tree: findings are
reported, never auto-fixed, and the caller saves any report file. For a very
large diff (more than a leg reads within a chunk's
[budget](references/lifecycle.md)), split it into subsystem-aligned chunks,
repeat steps 3–5 per chunk, and state chunk coverage in the report instead of
doing one shallow pass. A scope whose ranges end at different heads is chunked
by head, since a leg's `--cd` holds one (observed: two lanes at different
heads, then a stack with two tops, had no single checkout for the leg).

### Resuming an interrupted run

Where the runtime supports messaging or resume, an orchestrator that stopped
early is **resumable from its own transcript** — send it a message and it picks
up with its context. Try that before paying for a fresh run: a re-spawn
re-reads the whole diff and re-runs the cross-provider leg from zero, while a
resume usually costs one message. Do **not** assume its provider jobs survived
the gap — that the resume keeps them alive is unverified, so make re-checking
them the first instruction. Tell it plainly what to do: re-check every job it
launched, collect the finished ones, nudge or relaunch any that stopped
mid-investigation rather than returning findings, launch whatever work is still
owed, and deliver the report — without ending its turn again.

Without that capability, the parent collects the accessible job results and
finishes the remaining work itself. Re-run from scratch only when the
transcript itself is gone (the session that owned it died), and say so in the
report along with the leg or lenses that were lost.

## Cross-provider leg

Read the sibling provider skill before invoking its helper. From Codex use
`$SKILLS_ROOT/claude/SKILL.md` and
`$SKILLS_ROOT/claude/scripts/claude-ephemeral.sh`; from Claude use
`$SKILLS_ROOT/codex/SKILL.md` and
`$SKILLS_ROOT/codex/scripts/codex-ephemeral.sh`. Do not look for those files in
the target repository. Use `--cd` naming a checkout whose working tree is the
reviewed snapshot, because the leg opens the files it reads there:
`PROJECT_ROOT` when its tree is that snapshot, else a clean checkout of the
scope's head — a worktree the caller handed in that holds it and that no
session works in, or a temporary
`git worktree add --detach <dir> <head>` in a private temporary directory,
removed after the leg (observed: the three passes of one run each moved the
leg to a lane's clean worktree on their own, because the root they were given
was a driver's worktree on another branch; later a lane still at work switched
one to another branch before the launch). A plain copy of the snapshot's
files is not such a checkout: `git` run in it reads the enclosing repository
(observed: a Final Review handed its leg copies under the driver's worktree,
whose HEAD was `main`). Use an absolute, unused `--out`
path in a fresh private temporary directory. Judge whether the leg
landed from the helper's receipt (`status`, `diagnostic`, the result file), not
from the exit code alone. Pass prompt text without shell interpolation hazards;
follow the selected helper's supported arguments. Ask the leg open questions,
never a hypothesis to confirm (observed: a leading check produced a finding
the orchestrator then dropped).

On a narrow pass — a re-run after fixes or the first-order fallback over
caller-named ranges — the prompt names the files and line regions the leg reads:
the delta's hunks, their enclosing functions, the call sites the change reaches,
and any wider read it may make. An open prompt over a small delta sends a strong
model through unrelated whole files until its budget or provider capacity ends
the run (observed: 278 tool calls and a capacity failure on a 44-line delta; 31
calls with a region list, the same verdict). Retry a leg failed by a provider's
transient refusal (the receipt's `provider_error`) using the narrower,
region-naming prompt as the changed, evidence-based recovery step, on the same
model and effort, within the original budget; record both attempts.

For review, request read-only permissions and the minimum required tools. Do
not broaden permissions, switch to metered credentials, or grant implementation
access to recover a failed review. A helper's intended permissions are not
proof of enforcement: use its preflight/result metadata and report limitations.

One host condition is the exception, because there the sandbox itself is the
failure: on Linux hosts that deny unprivileged user namespaces (containers,
`kernel.apparmor_restrict_unprivileged_userns=1`, hardened kernels) Codex's
bubblewrap sandbox kills every command before it runs, and the model answers
from the prompt alone — exit 0, a fluent verdict, no file citations. See the
codex skill's `references/runtime-findings.md` (bubblewrap silent-success
trap). Detect it before the leg with `bwrap --dev-bind / / --unshare-net true`
and after it, on a Linux host only, by grepping the run's
`provider.stdout`/`provider.stderr` for lines that begin with `bwrap: `
(`^bwrap: `, the sandbox's own diagnostics, whatever follows the prefix) and
confirming in the transcript that the run's commands failed — a quotation of
the word inside a line is this file or the codex skill's notes, which the run
read. On such a host run the Codex leg with `--sandbox danger-full-access`
**only if** the target profile's `## Provider policy` declares
`Codex sandbox: danger-full-access (bubblewrap denied)` or the user says so for
this run; put a HARD CONSTRAINT line in the prompt ("read-only reviewer — no
file writes, no git mutations, no builds"), snapshot `git status --porcelain`
before and confirm it is unchanged after, and state in the report that the
sandbox was prompt-enforced, not kernel-enforced. Without that authorization
the leg is INCOMPLETE with the `bwrap:` line as the specific failure; never
escalate silently, and never treat a fluent verdict with no file citations as
coverage.

Track start/timeout/completion using the provider's runner/watch contract.
Successful process exit alone is not a completed review: require a valid final
answer for the assigned scope. If the provider cannot start, authenticate, or
finish within its budget, collect the other leg and report INCOMPLETE with the
specific failure and available coverage. Preserve enough local evidence to
resume; do not disclose credentials, prompts containing secrets, or raw private
transcripts in external reports.

## Provider policy

Judgment work runs on strong tiers only — a review you cannot trust is worse
than no review. The orchestrator inherits the session's model and effort;
the defs deliberately pin none. The cross-provider leg needs an explicit model:
**both ephemeral helpers refuse to run without `--model`** (exit 2, no `--out`
file written) and neither reads a provider config file as a fallback, so a run
that leaves the model implicit is not a run at all. Provider names are not
interchangeable.

Never hardcode a model in this skill or an agent def. Resolve the model and
effort for each provider leg from, in order:

1. The target profile's `## Provider policy` section (see
   [the project contract](references/project-contract.md)): per leg (`codex`,
   `claude`), the exact model, the effort, and optionally the CLI selection
   the helper's `--cli` accepts. Pass those values verbatim as `--model` and
   `--effort`.
2. The user's explicit instruction for this run, which overrides the profile.
3. Otherwise ask; a missing policy is a blocking question, not a license to
   guess or silently downgrade.

Do not pass a cheaper model or lower effort to save tokens unless the user
explicitly asks; if any leg ran on a fast/cheap tier, the report says so and the
run is flagged degraded.

## Lens map

Built-in common guidance: [review](references/review-common.md) and
[linter](references/linter-common.md). The lens docs under
`references/review/` (five folded lenses) and `references/linter/` are the
library; this table is the index. Read a lens doc in full only after selecting it. Project profiles may
replace or supplement lenses, with explicit project-relative paths and reasons,
and may supply measured escape statistics for lens selection. Do not import
another project's domain assumptions or escape weights.

`review/correctness-runtime-safety.md` is always one of them; add the rest by
the diff's archetype — the smallest set that covers the diff's actual
surfaces. Name the skipped borderline lens in the report. When all five
archetypes apply, all five are selected.

| Diff archetype | Add |
|----------------|-----|
| any (always on) | [`review/correctness-runtime-safety.md`](references/review/correctness-runtime-safety.md) |
| feature / port / gameplay / UI / multi-step workflow | [`review/port-fidelity-followthrough.md`](references/review/port-fidelity-followthrough.md) (+ `review/contracts-standards.md` when schemas, bindings, or API shape also change) |
| schemas / serialization / module APIs / language or process crossings / third-party usage / re-platforming | [`review/contracts-standards.md`](references/review/contracts-standards.md) |
| auth / secrets / network / file-system boundaries | `review/contracts-standards.md` — mandatory |
| new module / cross-module redesign / structural re-platforming / wrapper architecture | [`review/design-architecture.md`](references/review/design-architecture.md) + `review/contracts-standards.md` |
| build system / wrappers / scripts / platform code / hot paths / process lifecycle | [`review/platform-performance.md`](references/review/platform-performance.md) |
| docs, comments, or the API surface docs describe | [`linter/documentation-consistency.md`](references/linter/documentation-consistency.md) |
| trivial code diff | correctness lens alone |

### First-order fallback

`/code-review`, `codex review`, and `/simplify` own local correctness,
hygiene, and readability. When the user says no first-order pass ran on this
scope — or asks for a full standalone review — extend the
`correctness-runtime-safety` lens to also own local single-path logic
defects (suspend its first-order deference), and engage the linter lenses:
[`linter/code-hygiene.md`](references/linter/code-hygiene.md) +
[`linter/readability.md`](references/linter/readability.md), plus
[`linter/speculative-complexity-cleanup.md`](references/linter/speculative-complexity-cleanup.md)
when new abstractions, fallbacks, or indirection appear.
When the caller names ranges no first-order pass read (fixes made after a
lane's last review), both legs own local single-path logic defects within
those ranges, without the linter lenses.

## Runtime notes

- **Claude Code**: the caller launches the `review-orchestrator` subagent
  with the Agent tool. The subagent inherits the session model; the def
  deliberately pins none.
- **Codex**: subagents are named-only, so the package installs the
  `review-orchestrator` def. The caller spawns it with the scope in the prompt.
  The def pins no model — it inherits the session's.

## If a leg cannot run

A missing CLI, a failed login, or a timeout on either leg never silently
degrades the run. Finish the other leg, but head the report and the summary
with `REVIEW INCOMPLETE — <leg>: <reason>`, and the caller must surface that
to the user. A single-engine result is not a clean review pass — it stays
INCOMPLETE until the run is repeated with both legs; a user may accept
proceeding on that partial coverage, and the report records that acceptance
separately without upgrading the status.

## Result contract

Start the final result with one of:

```text
REVIEW COMPLETE — <n> verified findings (<h> high, <m> medium, <l> low)
REVIEW INCOMPLETE — <missing coverage or failed leg>
```

COMPLETE means all required selected coverage has final results on the recorded
snapshot, both provider legs completed, applicable required checks are accounted
for, and surviving findings were verified. It does not mean the change has no
findings. Missing required coverage stays INCOMPLETE even if a user accepts
proceeding; record that acceptance separately. Scope drift cannot certify the
current tree. Sequential native inspection — reported in the legs status as
`own-engine: orchestrator pass` — is disclosed and counts only when independent
native reviewers were not a project requirement.

Include: repository and exact scope (commit IDs, digest); system model;
selected/skipped lenses and why; check results; each leg's status and the
model and effort it actually ran on, as the runtime reports them — an
inherited value is named as inherited, never as what the profile names;
findings with file:line, evidence, concrete failure,
severity and fix; coverage limits, outstanding jobs and their disposition;
any local artifact path. A plan, progress note, notification, or empty provider
output cannot satisfy this contract.

## Review standard

Prefer findings that are non-local or cross-cutting, that survive
re-checking the actual diff, and that the team would either fix now or
explicitly waive. Down-rank cosmetic style comments, purely local cleanup,
and speculative concerns without a concrete failure path. The shared method,
suppression list, and output format live in
[review-common](references/review-common.md) and
[linter-common](references/linter-common.md) — the lens docs point to the
right one.

## Self-Improvement Policy

If this skill, the lens docs, or the helpers it drives create avoidable
friction — a dead link, a stale step, a broken command, or user pushback —
capture it and return it as skill feedback in your summary, separately from
the findings. Do not modify skill sources or open a PR during a read-only
review; the package maintainers fold verified corrections back at closure.

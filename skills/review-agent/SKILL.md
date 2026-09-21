---
name: review-agent
disable-model-invocation: true
description: "Explicit layered review of a code change: select relevant lenses, run native and cross-provider legs, verify findings, and report exact coverage. Use only when the user invokes review-agent or an explicitly invoked workflow names this gate."
---

# Layered review

This is the second-order pass after a first-order correctness and simplification
review. It targets cross-cutting contracts, lifecycle, architecture, platform
behavior, and follow-through. For an explicitly requested standalone review,
include the first-order fallback below. Review source without editing it.

Activation is explicit: `/review-agent`, `$review-agent`, or an explicitly
user-invoked workflow that names this pass, such as orchestrate's Final Review.
Ambient review intent does not activate it. Where a runtime refuses to invoke
an explicit-only skill through a Skill tool, the authorized workflow may read
this file and dispatch the role directly; this does not widen authorization.

## Establish the two roots and the scope

`SKILL_DIR` is the real installed directory containing this file; `SKILLS_ROOT`
is its parent. Resolve symlinks. Package references and provider helpers live
under these roots, independently of the repository being reviewed.
`PROJECT_ROOT` is the target checkout, supplied by the caller or resolved with
`git rev-parse --show-toplevel` from the user's working directory.

Read target root and applicable nested `AGENTS.md`/`CLAUDE.md`, its CI and
architecture documentation, and optional `.agents/project-workflow.md`. Follow
[the project contract](references/project-contract.md). A profile path is relative
to PROJECT_ROOT; a link in this package is relative to the linking file.

Resolve the requested PR, commit range, branch, or uncommitted scope before
launching reviewers. Preserve an explicit scope exactly. Otherwise use a known
stack parent, `branch.<name>.gh-merge-base`, then the selected remote's default
branch (`refs/remotes/origin/HEAD` for origin). Do not assume a branch name or use
`HEAD~1` to guess the scope. If there is no authoritative base, collect the
available refs and ask for the missing target.

The read-only [scope helper](scripts/resolve_scope.py) can record local Git
scopes. For example, run from any directory, with quoted absolute paths:

```bash
python3 "$SKILL_DIR/scripts/resolve_scope.py" --repo "$PROJECT_ROOT"
python3 "$SKILL_DIR/scripts/resolve_scope.py" --repo "$PROJECT_ROOT" --base "$BASE"
python3 "$SKILL_DIR/scripts/resolve_scope.py" --repo "$PROJECT_ROOT" --mode uncommitted
```

Use `--base <left> --head <right> --exact-base` for an exact two-commit range;
`--include-worktree` adds current tracked and untracked changes to a branch
scope. Default branch mode reports excluded dirty paths explicitly. Record the
resolved commit IDs and snapshot digest. The helper excludes Git-ignored files;
review those separately if explicitly in scope. Dirty submodules require their
own snapshots because a parent gitlink does not fingerprint their contents.
Do not fetch or mutate Git merely to
resolve a scope; if remote refs may be stale, report that limitation or refresh
within the user's authorized workflow. For PRs, verify the actual base/head from
GitHub, then resolve those refs locally. Never silently substitute another diff.

## Assign ownership before launching work

Prefer one `review-orchestrator` child when it can own nested reviewers and
return their results. Check the tools actually exposed in this session before
choosing that topology; installed role definitions do not prove nested spawn,
message, or resume support.

When nested spawning is unavailable, the calling agent owns orchestration and
fans out `review-lens` children itself. If a delegated orchestrator discovers
that limit later, it returns `NEEDS_PARENT_FANOUT` with the resolved scope,
selected lenses, completed results, and outstanding tasks. The parent continues
that run rather than starting it over. With no agent capability, perform the
lenses sequentially and disclose the reduced independence. Do not invent tools
such as `SendMessage` or configuration fields to enable a missing capability.

Follow [the bounded lifecycle](references/lifecycle.md). Record every child/job
handle, assigned lenses, immutable scope, status, and result. A child that ends
with “waiting for children” has returned progress, not a review. If a supported
resume/message tool exists, use it once with the missing work; otherwise collect
its available children/results and finish in the parent. If their handles or
results are inaccessible, report that coverage as missing. Never loop forever,
relaunch a completed leg, or report COMPLETE on the basis of a notification.

## Orchestrator procedure

1. **Understand.** Read the diff and surrounding system. State the intended
   behavior, ownership, existing mechanisms, and plausible simpler alternatives.
   Doubt about placement or the approach selects design-architecture.
2. **Check.** Discover applicable deterministic checks from target CI, scripts,
   and project policy. Reuse fresh results for this snapshot when available.
   Run only applicable authorized checks. Report their real result; missing
   tools or environment are unavailable checks, not code defects or passes.
   Some tests write build output: keep source review read-only, use an isolated
   checkout/output directory when needed, and do not auto-fix failures.
3. **Select.** Choose the smallest lens set covering actual surfaces, with at
   most five native lens children. Correctness-runtime-safety always applies.
   Group related lenses when necessary; name skipped borderline coverage.
   “Full review” may select all five review lenses, but is not the default.
4. **Dispatch both legs.** Each native lens receives PROJECT_ROOT, exact scope,
   its lens paths, family common guidance, applicable project overrides, and
   any project-provided escape weights. Read the common guidance first. Run
   one holistic cross-provider session on the same scope and lens set. Use
   bounded waves fitting the observed runtime capacity; do not assume a fixed
   nesting depth or concurrent-child limit.
5. **Validate.** Collect every result, merge duplicates, and re-check surviving
   findings against actual code. Use a bounded verifier for contested findings
   if needed. Mark provenance as corroborated or single-leg. Distinguish
   introduced regressions from existing causes exposed by this change.
   “No issues found” is a valid result. Do not invent findings to fill a quota.
6. **Recheck scope.** Compare the reviewed commit IDs and worktree digest to the
   current target. If it changed, the report covers the old snapshot only.
   Re-review affected coverage when authorized; do not certify the newer tree
   with stale results.
7. **Report.** Return findings and coverage directly to the caller. Write a
   report file only when requested by the user or target project contract,
   using a caller-selected local path. Publishing a report is a separate action.

## Cross-provider leg

Read the sibling provider skill before invoking its helper. From Codex use
`$SKILLS_ROOT/claude/SKILL.md` and
`$SKILLS_ROOT/claude/scripts/claude-ephemeral.sh`; from Claude use
`$SKILLS_ROOT/codex/SKILL.md` and
`$SKILLS_ROOT/codex/scripts/codex-ephemeral.sh`. Do not look for those files in
the target repository. Use `--cd "$PROJECT_ROOT"` and an absolute native output
path in a fresh private temporary directory. Pass prompt text without shell
interpolation hazards; follow the selected helper's supported arguments.

Native children inherit the user's current model and effort. Cross-provider
model and effort must follow the user's choice or the target project's explicit
provider policy; provider names are not interchangeable. Both provider runners
require an explicit `--model`; obtain a supported model from that policy or
ask if it is missing. Do not insert a hardcoded model or silently downgrade.
For review, request read-only permissions and the minimum required tools. Do
not broaden permissions, switch to metered credentials, or grant implementation
access to recover a failed review. A helper's intended permissions are not
proof of enforcement: use its preflight/result metadata and report limitations.

Track start/timeout/completion using the provider's runner/watch contract.
Successful process exit alone is not a completed review: require a valid final
answer for the assigned scope. If the provider cannot start, authenticate, or
finish within its budget, collect the other leg and report INCOMPLETE with the
specific failure and available coverage. Preserve enough local evidence to
resume; do not disclose credentials, prompts containing secrets, or raw private
transcripts in external reports.

## Lens map

Built-in common guidance: [review](references/review-common.md) and
[linter](references/linter-common.md). Project profiles may replace or supplement
lenses, with explicit project-relative paths and reasons. Do not import another
project's domain assumptions or measured escape statistics.

| Actual change surface | Lens |
| --- | --- |
| Every scope | [Correctness and runtime safety](references/review/correctness-runtime-safety.md) |
| Feature, port, UI or multi-step workflow | [Port fidelity and follow-through](references/review/port-fidelity-followthrough.md) |
| Schemas, serialization, APIs, third-party use; mandatory for auth, secrets, network and filesystem boundaries | [Contracts and standards](references/review/contracts-standards.md) |
| New module, cross-module redesign, structural doubts, wrapper architecture | [Design and architecture](references/review/design-architecture.md), plus contracts when boundaries change |
| Build, scripts, platform branches, process lifecycle or hot paths | [Platform and performance](references/review/platform-performance.md) |
| Documentation or documented behavior changes | [Documentation consistency](references/linter/documentation-consistency.md) |

For an explicitly requested standalone review or when the user says no
first-order pass ran, assign local single-path logic to correctness too. Group
[code hygiene](references/linter/code-hygiene.md) and
[readability](references/linter/readability.md); add
[speculative complexity](references/linter/speculative-complexity-cleanup.md)
when new abstractions, fallbacks, or indirection appear. The five-child cap
still holds; group lenses rather than dropping relevant coverage silently.

## Result contract

Start the final result with one of:

```text
REVIEW COMPLETE — <n> verified findings (<severity counts>)
REVIEW INCOMPLETE — <missing coverage or failed leg>
```

COMPLETE means all required selected coverage has final results on the recorded
snapshot, both provider legs completed, applicable required checks are accounted
for, and surviving findings were verified. It does not mean the change has no
findings. Missing required coverage stays INCOMPLETE even if a user accepts
proceeding; record that acceptance separately. Scope drift cannot certify the
current tree. Sequential native inspection is disclosed and counts only when
independent native reviewers were not a project requirement.

Include: repository and exact scope; system model; selected/skipped lenses and
why; check results; each leg's status and effective model/effort when known;
findings with file:line, evidence, concrete failure, severity and fix; coverage
limits, outstanding children and their disposition; any local artifact path.
A plan, progress note, notification, or empty provider output cannot satisfy
this contract. Return skill feedback separately; do not automatically open a
PR or modify skill sources during a read-only review.

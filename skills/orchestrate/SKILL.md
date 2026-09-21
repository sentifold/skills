---
name: orchestrate
disable-model-invocation: true
description: "Explicit end-to-end engineering orchestration: define scope, validate design, implement owned lanes, run evidence-based test and review gates, and prepare the authorized delivery. Activate only when the user invokes orchestrate."
---

# Orchestrate

Run this workflow only when the user explicitly invokes it. Ordinary coding,
planning, or performance requests do not activate it. Preserve the user's scope,
model choices, delivery intent, and prior authorization throughout the run.

The pipeline is: scope → design validation → owned implementation lanes →
first-order review and cleanup → appropriate tests → conditional project gates
→ whole-scope layered review → authorized delivery. Make each gate observable;
a status label without evidence does not pass it.

## Read the target project before planning

Resolve the real installed directory containing this skill and its parent
`SKILLS_ROOT`, separately from the target checkout `PROJECT_ROOT`. Package
skills are siblings under SKILLS_ROOT. All commands that inspect or change the
product run with an explicit target working directory, never the package root.

Read root and applicable nested `AGENTS.md`/`CLAUDE.md`, the project's architecture
map and relevant CI documentation, plus optional `.agents/project-workflow.md`.
Use the shared [project contract](../review-agent/references/project-contract.md).
The project supplies build commands, supported platforms, compatibility policy,
resource coordination, runtime-test routes, profiling permissions, review lens
overrides, PR conventions, and any readiness floor. Without a profile, derive
those facts from existing project instructions and CI; do not import another
repository's commands, environment variables, branch names, or report paths.

Identify task-triggered skills before implementation and again when the scope
changes. Read and use applicable project/domain skills when the actual task
matches their trigger. Prefer a designated tester for hands-on verification
when one is available. A mention of a technology alone does not activate an
explicit-only skill; invoking orchestrate does not bypass another skill's
separate consent boundary. Record the chosen routes in the gate plan.

## 1. Scope and gate plan

Record a compact scope agreement in working context, or the project's normal
local planning file when required:

- Original request, intended outcome, and explicit exclusions.
- Concrete completion evidence (`done_proof`), including relevant user flows.
- Repositories, candidate lanes, owned paths, dependencies, and delivery target.
- Applicable gates, exact planned checks, and justified non-applicable gates.
- Known user decisions, model/effort choices, and unresolved constraints.

Infer routine implementation details from the repository and user context.
Clarify only consequential ambiguity, missing authority, or a scope decision
that blocks dependent work. Continue independent authorized work while waiting.
Append material scope amendments so late discoveries do not silently change the
contract. Distinguish a newly required capability from a fix within agreed scope.

If a diff already exists, label it adopted work: reconstruct its intent and run
the same applicable design, review and test gates honestly. Do not claim it was
created or reviewed during this run merely because it is present.

For multiple repositories, write their shared API/data contract first, then
plan one independently reviewable change and evidence set per repository. Track
consumer/provider version dependencies explicitly. Do not create a cross-repo
Git stack or edit another lane's repo through an implicit working directory.

## 2. Design validation

Inspect existing mechanisms and architecture before proposing new ones. Explain
the intended behavior, why the change belongs at that boundary, the smallest
complete implementation, and its test strategy. Consider a simpler alternative
and justify the choice using the code and current requirements.

Have an independent reviewer challenge the plan before implementation. Use the
other provider when available and authorized by this explicit workflow, reading
its sibling `claude` or `codex` skill first. Give it the goal, constraints,
relevant source paths, proposed contract and tests. Native children inherit the
session's model/effort; cross-provider choices follow user/project policy. Both
provider runners require an explicitly selected supported model. Do not substitute
a fixed model, downgrade effort, or widen permissions to make a gate run.

Resolve concrete design findings. A routine correction is already authorized;
a material scope change needs the user's decision. If a required independent
leg cannot run, retain the useful work and mark the gate incomplete. Ask for a
waiver only when needed to advance delivery; never silently count a missing leg
as a pass.

## 3. Implementation lanes and integration

Split only where ownership and interfaces are clear. Prefer a small number of
independently shippable lanes over parallel edits to the same files. Each worker
receives: absolute checkout path, task contract, owned paths, dependency/base
commit, relevant instructions, test expectations, and the warning that other
agents are working concurrently and their changes must be preserved.

Use an isolated worktree when the task needs an independent branch or runtime
state. Follow the target project's worktree/setup hooks and shared-machine
rules. Record the base SHA; never assume a branch name or let sibling worktrees
share mutable test state accidentally. Coordinate scarce devices, build caches,
dependency writers, and live UI executors according to actual project policy.

Keep lane outputs small enough to review and integrate. Reconcile interfaces
before merging lane work. For dependent branches, record the old parent tip and
restack onto the new parent explicitly; after a squash or rewritten parent,
verify that the child diff contains only its own work. Do not blindly rebase or
force-push unrelated user work; use lease protection for authorized rewrites.

Update the target project's required architecture maps and docs with behavior
changes. Avoid generated plans, compatibility shims, or abstraction layers that
are unsupported by the task and project contract.

## 4. Per-lane first-order review and cleanup

Review an immutable snapshot of each meaningful lane before claiming it ready.
Give every reviewer the same exact base/head and any explicitly included dirty
files. The shared [scope helper](../review-agent/scripts/resolve_scope.py) can
record these. Do not edit a tree while another agent reviews or live-tests it.

Use a native generalist correctness review plus the other provider's independent
review. In Claude, the shared
[claude-stock-code-review](../claude-stock-code-review/SKILL.md) is the first-order
copy; in Codex use its native review capability or an equivalent independent
code-review child. Follow target policy on counterpart review scope. Reviewers
receive the intended behavior, exact diff and relevant project constraints,
without being steered to rubber-stamp an implementation.

Include simplification, reuse, readability and unnecessary complexity. For a
small bounded diff, those angles can be folded into the generalist pass; use a
separate simplification pass when structural complexity warrants it. Record
which form covered them. Cleanup that changes behavior or the reviewed design
invalidates affected review/test receipts; re-check the final tree.

Adjudicate findings with concrete code evidence. Fix actionable in-scope defects,
then repeat only affected checks/coverage. Disputed design or scope choices go
to the user with the evidence. Do not repeat successful unaffected checks just
to accumulate more receipts.

## 5. Risk-sized verification and conditional gates

Select tests from the changed behavior and target CI. Distinguish source checks,
build success, launch success, exercised behavior, screenshots actually inspected,
and measured performance; one does not prove the others.

| Changed surface and evidence | Verification |
| --- | --- |
| Documentation or tooling with no runtime product impact | Applicable docs/tooling checks; runtime N/A unless project readiness policy requires it |
| Runtime behavior primarily pinned by focused automated tests | Focused tests plus the project's required clean-state startup smoke |
| UI, state transitions, integrations, or behavior not pinned by tests | Drive the actual flow from clean state and verify explicit assertions |
| Platform-specific or cross-platform behavior | Validate affected supported hosts; use project policy for build-only versus live/device evidence |
| Performance-sensitive work | Follow the project's measurement/profiling route and its separate authorization requirements |

For runtime tests, identify the exact product, runtime, build, revision, and
state namespace. Follow the project tester's cleanup/ownership protocol. Do not
edit or rebuild its live checkout while it is exercising the product. Distinguish
passed assertions, untested flows, failures and needs-human observations.

A simulator cannot stand in for device performance; a desktop run cannot prove
a different platform's behavior. Conditional profiling or publication is not
automatically authorized by orchestrate when the project requires separate
consent. Gather available non-dependent evidence while that decision is pending.

A failed required check keeps its gate open. Diagnose and repair in-scope failures
without repeatedly asking permission. For unavailable environments, record the
specific missing evidence and seek an explicit waiver only if required for the
requested delivery. Do not relabel unavailable as N/A or pass.

## 6. Whole-scope layered review

After lane integration and applicable verification, run
[review-agent](../review-agent/SKILL.md) once over the complete final scope per
repository. This explicit invocation authorizes the workflow's named review
gate. Pass the scope, first-order receipts, relevant project profile, and
outstanding limitations. Include the final integrated tree, not an old pre-fix
snapshot or just the last commit.

Use its capability-based topology and
[bounded lifecycle](../review-agent/references/lifecycle.md): the parent owns
completion, child IDs and results are tracked, and missing nested spawn or
SendMessage is handled by parent fanout/collection. Never finish with “children
are running” as though that were the report. Native sequential fallback must
state its reduced independence. Required cross-provider coverage remains
incomplete until it actually returns. Delivery may proceed with explicit user
acceptance, while coverage stays INCOMPLETE.

Resolve verified findings within scope, then re-review affected coverage on the
new snapshot. Preserve unaffected results with their provenance. COMPLETE is a
coverage statement, not a claim of zero findings; INCOMPLETE must remain visible
at delivery even when the user accepts that limitation.

## 7. Delivery and gate receipts

Prepare the user's requested output: local changes, a branch, or a PR. Use the
shared [github-create-pr](../github-create-pr/SKILL.md) when creating/updating a
PR is within scope. Select the target base from explicit scope/stack policy,
branch gh-merge-base, or the repository default. No branch name is universal.
A review or implementation request alone does not imply merge, deployment,
external report publication, or messages to teammates. Follow existing explicit
authorization and the target project's delivery rules.

Each gate receipt names the repository, revision/snapshot, actual command or
review assignment, result, evidence location if any, and unresolved limitations.
Keep receipts compact and local; no report service or directory is mandatory.
For stacks, validate every PR against its own parent and the total change against
the final target. For cross-repo work, link the dependency order and validation
of compatible versions without claiming atomic publication.

End with the concrete delivered result, meaningful validation, review coverage,
and any open decisions or risks. Do not call the task complete while required
work or children remain outstanding. If a blocking decision prevents further
progress, report the completed work and precise gap without inventing a pass.

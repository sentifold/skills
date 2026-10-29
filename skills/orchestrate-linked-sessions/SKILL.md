---
name: orchestrate-linked-sessions
disable-model-invocation: true
argument-hint: "[light|heavy] <task>"
description: "Opt-in orchestration workflow for Claude Code in the Claude desktop app that turns a scope into right-sized, cross-provider-validated, reviewed, clean-state-tested draft PRs landing directly on the target project's base branch, with every lane built by a linked session of its own. The invoking session drives the work, each lane session runs its gates and its reviewer subagents, and Codex is the other engine through the installed codex skill. Use ONLY when the caller explicitly names `orchestrate-linked-sessions` or invokes `/orchestrate-linked-sessions`, or explicitly asks for this plan -> validate -> lanes as linked sessions -> review -> test workflow. It chains github-create-pr, the live-test executor the project profile names for the surface under change, the project's profiling route, review-agent, and the project's cross-platform tooling. Do NOT auto-trigger from ordinary 'plan and implement' / feature / bugfix requests — those follow the project's AGENTS.md default behavior; this is the heavyweight gated pipeline, opt-in only. Explicit invocation in any language counts (e.g. 'прогони задачу через orchestrate-linked-sessions'); a generic 'implement this' does not. Outside the desktop app it stops and names `/orchestrate`."
---

# Orchestrate linked sessions

Turn a scope into a set of **right-sized, validated, reviewed,
clean-state-tested draft PRs** that land directly on the project's base branch — **fast**. The gates set the
quality bar; everything between them is scheduled to get work through as
quickly as possible: independent sub-tasks execute as **concurrent lanes**,
questions batch into single round-trips, and PRs go ready the moment their
gates clear. This is an orchestrator: it owns the planning, scheduling, gates, and
delivery coordination while driving the installed shared skills and the target
project's own skills. It is `orchestrate` for Claude Code in the Claude
desktop app, which can start **linked sessions**: the session the person
invoked it in is the **driver** — intake, the Design gate, the whole-scope
gates and landing — and every lane is a **linked session** of its own, in its
own worktree, that implements, reviews and tests its slice and reports back;
its reviewers and executors are its subagents. Codex is the other engine for
independent validation and review, through the installed `codex` skill.

**What this file optimizes.** Time to a landed, verified PR at constant
rigor, and the return on every token spent: a token goes where it buys
proof, speed or an unbiased read, and is never saved by stopping, throttling
or thinning a gate. The file itself stays small: a rule enters it only when it
removes friction a run actually met, and names that friction.

## Runtime

The driver needs the desktop app's session tools: the one that starts a
linked session (`mcp__ccd_session__start_session`, with
`mcp__ccd_session__list_start_targets` for the places it may start in),
messaging between
sessions (`SendMessage`, addressed by a session's `local_…` id: a lane's from
`start_session`'s result, the driver's own from `get_session` with `self`; a
lane's `name` is not an address, and a send to it is refused), and the
listing and stopping of linked sessions (`mcp__ccd_session_mgmt__list_sessions`
with `linked`, `mcp__ccd_session_mgmt__stop_session`). Check they are exposed
before intake. Where they are not — the terminal, VS Code, Codex — stop and
name `/orchestrate`, which runs the same loop with the driver scheduling the
lanes itself; this skill never falls back to that shape on its own, because a
run that mixed the two could not say which session owns a lane. A start is
refused in a turn that another session's message or an automated event began,
so lanes start only in turns the person began.

**One scope per driver session.** The session the person invoked the skill in
drives this scope and no other: the run ends at closure, and a follow-up, a
new scope or a redesign the person asks for afterwards is a new invocation in
a new session, given the previous run's notes ref and its open PRs as input;
the old run's lanes stay reachable by id for a restack, and such a request
names the new driver's session id as the address of the lane's state lines
from then on, the lane entering the new ledger. A scope change inside
the run is an amendment to the scope record, as the loop says. Starting
another scope's lanes from a closed run's driver mixes two families in the
sidebar and keeps every lane's traffic in one context (observed: one driver
carried a scope, its redesign and three follow-ups for 38 hours and 1,300
turns, through a compaction).

## Roots and the project profile

`SKILL_DIR` is the real installed directory containing this file; `SKILLS_ROOT`
is its parent. Resolve symlinks. The sibling shared packages this workflow
chains — `review-agent`, `github-create-pr`, `codex`, `claude`,
`claude-stock-code-review` — live under `SKILLS_ROOT`, independently of the
repository being changed. Do not look for them in the target repository.

`PROJECT_ROOT` is the target checkout: supplied by the caller, else resolved
with `git rev-parse --show-toplevel` from the user's working directory. Every
command that inspects or changes the product runs with an explicit target
working directory (`git -C`, `--cd`), never the package root. Resolve
`PROJECT_ROOT` **per lane worktree** — a lane session's worktree is its own
root and working directory, and it reads the profile checked out there — and
**per repository** in a cross-repo
scope; a lane never edits another lane's repo through an implicit working
directory.

The project profile is `PROJECT_ROOT/.agents/project-workflow.md`, read
together with the root and applicable nested `AGENTS.md`/`CLAUDE.md`, the
project's architecture map and its CI documentation, under the shared
[project contract](../review-agent/references/project-contract.md). The
profile supplies what this file deliberately does not: the base branch and
branch-naming policy, build and check commands, the live-test executor per
changed surface, clean-state rules, shared-machine resources to serialize,
conditional platform and performance gates with their consent rules, the
readiness floor, provider model policy, review lens overrides, PR conventions,
and where evidence and reports belong. Wherever this file says "the project
profile names …", that is the lookup.

**Without a profile**, derive those facts from the project's existing
instructions — `AGENTS.md`/`CLAUDE.md`, README, CI configuration, Makefile or
package scripts — and record what you derived in the scope record. Never
import another repository's commands, environment variables, branch names,
executors, or report paths. A required check the project defines but the
environment cannot run is a visible `blocked:` gate, never a pass.

Identify task-triggered project skills before implementation and again when
the scope changes; read and use the ones whose trigger the actual task matches.
Prefer a designated tester or executor for hands-on verification when the
profile names one. A mention of a technology alone does not activate an
explicit-only skill, and invoking `orchestrate-linked-sessions` does not bypass another
skill's separate consent boundary. Record the chosen routes in the gate plan.

## Trigger (opt-in)

Use this skill only when:
- the user explicitly names `orchestrate-linked-sessions` or invokes
  `/orchestrate-linked-sessions`, in Claude Code in the Claude desktop app
- the user asks for this plan -> validate -> lanes as linked sessions ->
  review -> test workflow by description

Do not auto-trigger from generic repo work, a language, file paths, or task
intent alone. A project's `AGENTS.md` keeps this workflow opt-in; ordinary
tasks follow the default "smallest direct change" behavior, not this ceremony.

## Operating principles

- **Smallest honest scope.** Use this loop for multi-step scopes that are worth
  the ceremony. A one-line fix does not need it — say so and just do it.
- **Ship fast at constant rigor.** Time-to-landed-PR is a first-class
  objective, second only to the gates themselves. Never skip or thin a gate to
  save time; make the time up between the gates instead — overlap work in
  lanes, batch questions into one round-trip, budget long-running steps, size
  tests to the actual risk, and flip PRs ready the moment gates clear (merging
  stays the user's call). Ceremony between gates is waste.
- **Plan before code, code before commit, review before land.** Every phase has
  a gate (below). Never skip a gate to save time.
- **Adopt existing work honestly.** If the skill is invoked after a diff already
  exists, freeze further edits and run the Design gate against the existing approach before
  continuing. Record that validation happened after the initial implementation;
  never claim it was pre-code.
- **Lanes, not phases.** After the Design gate, each independent sub-task runs as its own
  **lane** — a linked session in its own worktree: set up → implement → Code
  Review → Live Test — and lanes advance concurrently (2–3 at a time on a
  shared machine), on their own turns. The driver starts lanes, answers them
  and evaluates the whole-scope gates; it does not walk one phase across the
  whole scope, and it writes no lane's code. See
  [Parallelization](#parallelization) and [Lanes as sessions](#lanes-as-sessions).
- **Never wait idle.** If the only thing running is a single background op and
  any lane has ready work, start that work before waiting. Before any
  stop-and-ask, bring every other lane to a running state so the wait overlaps
  machine work instead of freezing it. A lane is never waited on: the driver
  ends its turn and the app continues it when the lanes report, and a lane
  that needs an answer sooner messages it.
- **Delegate for isolation, not lower quality.** A lane is a session, not a
  subagent: it keeps a context of its own across turns, asks the person
  itself, and hands the driver a line, not its transcript. Inside a session,
  the main agent holds the big-picture context and hands off well-scoped work
  to native subagents that return compact results. Live app driving / UI
  verification → the tester executor the project profile names for the
  surface. Performance captures → the profiler executor the profile names.
  The driver and its children, the Final Review among them, run on the
  model and effort the person chose for its session. A lane runs on
  `claude-opus-5-5` at effort `medium` by default, and its children inherit
  the lane's pair. The person may name another pair for a lane, at its start
  or later: the driver passes it to `start_session`, or sets it with
  `set_session_model` and `set_session_effort` on a running lane and for a
  pair above its own, which `start_session` cannot start. Every session and
  child inherits the person's permission mode. Never pin a delegated role to
  another model or effort on your own. The profile's Claude leg is the
  cross-provider helper's setting for a Codex driver, not these children's.
- **Stop and ask whenever a decision is ambiguous or a gate fails.** A silent
  guess at a fork is worse than a one-line question. See [Stop conditions](#stop-conditions).
- **Bounded waits only.** Never wait unbounded on a remote, a background Codex
  or Claude run, or a log. Every wait has a deadline AND
  unreachable-detection and ends with an explicit verdict — follow the
  [bounded lifecycle](../review-agent/references/lifecycle.md) (bounded calls
  of at most 60 seconds, retained handles, a fixed overall deadline) and the
  bounded-wait tooling the project profile names, not a hand-rolled `until`
  loop. Probe an ephemeral cross-provider run through the `codex` skill's
  watcher, never a blind poll. Before calling a slow producer stalled,
  check its actual progress (the profile records platform-specific probes for
  its own artifacts); a failed probe proves neither progress nor a stall, and
  a healthy producer is never stopped on directory metadata alone.

## Weight

The person picks the weight in the invocation: `heavy` runs the full review
fan-out (`/orchestrate-linked-sessions heavy <task>`); `light`,
or no weight named, runs light. Both weights run every gate with the same
cross-provider legs, stop conditions and readiness floor, and neither pins a
weaker model; they differ only in how much own-engine review the two review
gates spend:

- **Light** (default): the Code Review gate's native leg is three grouped
  reviewers whose candidates the lane verifies itself, with simplification
  folded into the quality reviewer, and one reviewer over the fix delta; the
  Final Review's orchestrator inspects the selected lenses itself.
- **Heavy**: the native leg is `/claude-stock-code-review` (ten angles, a
  verifier per candidate, a sweep) plus `/simplify` sized to the diff; the
  Final Review spawns one lens child per selected lens.

Record the weight in the scope record, in every lane brief and at closure;
only the person changes it.

## Runtime mapping

| Need | Who | How |
|------|-----|-----|
| Cross-provider design validation / review | the driver / the lane | `codex` skill, read-only/review |
| Implementation | the lane | itself, or a `codex` write handoff into its own worktree |
| First-order review | the lane | light: three grouped reviewer subagents; heavy: `/claude-stock-code-review` (copy of the stock `/code-review`) |
| Simplification | the lane | light: folded into the quality reviewer; heavy: `/simplify` (model-invocable) |
| Final layered review | the driver | `review-orchestrator` subagent, given the weight |

The counterpart is the `codex` skill; `claude` is Codex-only and never used
here. Read its `SKILL.md` under `SKILLS_ROOT` before the first run — the
driver before the Design gate, each lane before its first handoff; its helper
requires `--cd` naming the checkout the run works in and an absolute, unused
output path.

**Model selection.** Both provider helpers require an explicit model and never
substitute one. Take it, in order, from the project profile's "Provider policy"
section, then from the user's instruction, else **ask** — do not insert a
hardcoded model, downgrade effort, or widen permissions to make a gate run. A
cross-provider leg that ran on a cheaper tier than the profile names, or that
cannot report its effective model, is `degraded:`, not a pass.

**An auth or proxy failure from a provider helper is not a permanent verdict.**
A proxy or account can start refusing every key mid-session and recover on its
own hours later, taking the cross-provider leg away only for as long as nobody
retries. **Re-probe before declaring a run single-engine**, and again before
closure: one throwaway call is enough (`--effort low --no-search "Reply with
exactly: AUTH_OK"` through the counterpart helper). A run that reported
single-engine at 12:00 and never retried spent the whole afternoon degraded
for nothing. The counterpart helper's own platform traps are documented in its
skill; the project profile records any proxy-specific symptom.

When the counterpart is genuinely unreachable, the Design gate has the same
problem the Final Review gate does, and the same answer: an own-engine
substitute is a **degraded** pass, not a pass. Record it as
`blocked: cross-provider unavailable — <reason>`, say so in the PR body, and
carry the gap into closure rather than letting a second same-engine agent
quietly stand in for a second engine.

## The loop

### 0 — Intake & decompose

State the scope in 1-2 sentences: **outcome, explicitly excluded work, and the
proof that means done.** **Trust the project's load-bearing docs** — the maps
its `AGENTS.md` or profile declares authoritative (README, architecture
overview); start from them instead of re-deriving structure by grepping the
tree. Inspect code for the behavioral details docs do not pin, and before
trusting memory. If a trusted map disagrees with the code, that is a bug in
the map — fix it in the same change, never silently work around it. Ask the
user clarifying questions *before committing to an approach*, **batched into
one round** — front-load every decision you can foresee (scope cuts, risk
tolerance, profiling consent when a performance-critical surface is plausibly in
scope, model choice when the profile names none) so later phases do not stall
on a human round-trip.

Write the scope down as a **scope record** before any Design validation
launches — the Final Review gate will hold the delivered work against it, so
it must not live only in the driver's evolving memory:

```md
Scope record
- initial_ask: <the user's request, verbatim or tightly quoted>
- weight: <light, or heavy when the person named it>
- outcome: <what exists when done>
- excluded: <deliberately out of scope>
- done_proof: <the checks that mean done>
- project_facts: <profile read, or the derived base/checks/executors when there is none>
- sub_tasks: <appended once decomposition settles>
```

The record is **append-only**: a scope change is an amendment carrying the
user's approval, never a silent rewrite. Distinguish a newly required
capability (an amendment) from a fix within the agreed scope (not one).

Decompose the scope into **independently shippable, right-sized** sub-tasks.
Small is not the goal — every slice boundary needs a reason (independence,
risk isolation, a unit that reviews and reverts as one thing), and each extra
PR pays its own Code Review passes, Live Test run, and landing mechanics, so a
split must earn its overhead. A slice that cannot ship alone is not a slice.
**Slice for independence first**: every dependency serializes a lane, so prefer
vertical slices that ship as parallel PRs. A **stacked chain**
(`<base> <- PR1 <- PR2 <- PR3`) is the fallback for genuinely ordered work —
record a one-line justification when you choose it. Mark dependencies either
way. Keep architecture-heavy decomposition inline here — reason about owners,
module boundaries, and contract deltas as part of the design you validate at
the Design gate.

**A scope can span repositories**, and the loop still holds — two repositories
that meet at a wire format (a client and its backend, a provider and its
consumer) make a delivery or API change one scope in two repos. What changes
is bookkeeping, and only these four things:

- **Write the shared contract down before the lanes start**, in one file both
  sides implement against, and hand it to every Design validation and every
  implementation handoff. A lane that infers the other side's format from its
  own tests will agree with itself and nothing else.
- **A stack cannot cross repositories.** PRs in different repos are
  independent whatever their real order; record the rollout order in each PR
  body instead, and say which side must deploy first, and track
  consumer/provider version dependencies explicitly.
- **Every per-repo gate runs per repo**, with that repo's own checks and its
  own conventions — each repo's profile or CI instructions name them; the
  other repo's `AGENTS.md` and profile do not apply to it. A lane in the
  other repository is a session started in that repository's folder (`cwd`,
  a place `list_start_targets` names), with its own worktree there.
- **The Final Review gate runs once per repo**, not once per scope. Hand each
  run the other repo's worktree as read-only context so the lens that owns
  contracts can read both sides of the wire.

Two traps a cross-repo scope hits early: run every command for the other repo
with an explicit `-C <path>` (a bare `cd` in one tool call does not survive to
the next), and expect a repo with submodules to need them initialised in a
fresh worktree — a shallow local clone cannot serve as `--reference`, so
`git submodule update --init --depth 1 <path>` is the form that works.

### 1 — Plan & validate each sub-task — **Design gate**

For each sub-task, design the approach: owner/surface, files to touch, contract
delta, and how it will be verified. Inspect existing mechanisms before
proposing new ones, consider a simpler alternative, and justify the choice
from the code. Then **validate the design before writing any
code** with the cross-provider counterpart in read-only mode: the driver uses
the **`codex` skill**. Hand it the approach and the files to read, and ask it to flag wrong owners, missed contracts,
simpler alternatives, and risks.

Design gate validations are read-only and independent of each other, so **launch them as
one batch** — one backgrounded cross-provider run per sub-task, each with its
own output file, probed through the counterpart skill's watcher. Do not hold
sub-task B's validation until sub-task A's comes back.

**Do not start coding until the approach is clear AND cross-provider-validated.**
If the counterpart returns only minor refinements, fold them in and proceed. If
it flags the approach as wrong, or the right call is ambiguous, that is a **Design gate
failure — stop and ask** before writing any code (see [Stop conditions](#stop-conditions)).

When adopting an existing diff, validate the current design and implementation
before any further edit or commit. A clean result passes the Design gate as
`ran: adopted-existing-work`; a material design defect fails the gate normally. This
exception makes an already-started task usable without falsifying gate order.

A lane is never started before its design passes; its brief carries the
design as validated, refinements folded in. Adopted work reaches its lane as
commits: the driver commits the existing diff on its own branch (a WIP commit
the lane may rewrite), the lane is cut from that branch with the original
base recorded as its base, and the driver writes no more into it; work that
cannot be committed stops the run before any lane starts.

### 2 — Slice into right-sized draft PRs

Split the validated work into draft PRs **sized by justification, not by a
smallness aesthetic**: each PR lands directly on the base branch, reviews as one
coherent unit, and reverts cleanly — and no finer than that. The base is the
one the project profile names, or an explicit user/stack base; absent both,
resolve it the way the **`github-create-pr` skill** does (stack parent,
`branch.<name>.gh-merge-base`, then the verified remote default) — no branch
name is universal. Stack them as a chain when there are dependencies (each PR
targets the previous branch in the chain — see the **`github-create-pr`
skill**, "PR Chains"). Follow the project profile's branch-naming
policy: the app names a lane's branch from the slug the driver passes, under
the person's branch prefix and with a suffix of its own, so pass the slug
that gives the name the policy wants, and take the final name from the lane's
first report.

Each PR gets a clear description. Add a diagram only when it materially shortens
the explanation, following the **`github-create-pr` skill**: use a minimal
plain-text schematic in a fenced `text` block, with one reading direction and a
handful of steps. Do not use Mermaid, diagram subagents, rendered assets, or a
mandatory diagram-per-PR template. Place an optional schematic next to the
paragraph it clarifies.

**Open each PR as a draft early** — as soon as its branch has a first commit
(from phase 3) — via the **`github-create-pr` skill**, with the base set to
the project base (or the previous branch in a stacked chain), so the review and
test gates attach to a real PR. The lane opens it from its worktree, and the
app's PR monitor follows the session that opened it.

### 3 — Implement in a lane session

Give each validated task **its own linked session** in **its own worktree**:
the driver starts it — `start_session` with `initiation: user_asked` (the
person's invocation and their answers at intake are the ask), `context:
fresh`, `use_worktree: true`, `source_branch` the lane's base, `branch_name`
the slice's slug, `name` a short lane handle, `wake_when_done: true`, and
the lane's `model` and `effort` (by default `claude-opus-5-5` and `medium`)
— and the app cuts the worktree from the base. The lane
provisions it with whatever the project profile names (env seeding, LFS or
submodule hydration, dependency installs, the project's worktree setup
command). If that automation misfires, fix the hook installation rather than
hand-seeding files; the profile points at the project's worktree guide.

**The brief is the lane's whole world.** A fresh session has seen nothing of
this conversation: the `prompt` carries [the lane brief](#the-lane-brief)
below and `background` the scope in a few lines. Keep the same text in the
run's folder (`.local/orchestrate/<run>/lanes/<lane>/task.md`, pushed to the
run's notes ref — see [Evidence outlives the worktree](#parallelization)):
the Final Review reads it, and a lane whose session is lost is restarted from
it.

**Reverting one file in a lane means checking it out from the lane's base, not from HEAD.**
`git checkout -- <file>` restores the index/HEAD version, which already contains the
lane's own committed change, so nothing is reverted and the review keeps finding it. Use
`git checkout <base-sha> -- <file>` and
confirm with `git diff <base-sha> -- <file>` being empty.

**Restacking stacked lanes uses `git rebase --onto <new-base> <old-base>`.** A
plain `rebase <new-base>` on a lane that CONTAINS its old base's commits
replays those base commits too and conflicts against their own rewritten
versions. Record each lane's base SHA when you fork it, and re-record it
after a restack or a merge from the base — the `--onto` target, or the base
commit the merge brought in: the review ranges are `<lane-base>...HEAD`, and
against the stale SHA they contain every base commit since. Restack after a
base gains fix commits with `--onto`, then re-verify and
`push --force-with-lease`.
After a squash or rewritten parent, verify that the child diff contains only
its own work; never force-push unrelated user work. A lane restacks its own
branch; the driver asks for it by message and waits for the new head. A lane
stacked on another does not follow its predecessor commit by commit: it
restacks at `go`, onto the predecessor's implementation head; when the
predecessor's per-lane gates close, onto that head; and after that only when
a Final Review fix or a merge below moves its base. A restack rewrites the
reviewed head: the lane records which new commit it became, and the fix-delta
range starts there.

**One session, one worktree.** The driver never writes into a lane's worktree
and never runs git there; a lane never writes into another lane's or the
driver's — the Write and Edit tools refuse such paths anyway ("belongs to a
different worktree"). A fix another lane needs, a restack, a revert, a re-run:
all travel as a message to the session that owns the worktree, which does it
and reports the new head.

**Check work in flight on the same surface before the Design gate.** Another session may already own
part of the scope (observed: a sibling PR adding the same asset surfaced only in a live-test
screenshot, after both designs were implemented). `gh pr list --search` over the touched paths, the
runtime's agent listing (`ListAgents`) and the app's session list are cheap; an overlap found early is a
scope question, found late it is a restack.

**Start lanes in turns the person began, within the cap.** A start is refused
in a turn that another session's message or an automated event began — a
background validation's completion notification begins such a turn — so the
driver watches its Design validations inside the person's turn, in the
bounded watcher calls the counterpart skill gives it, and starts the lanes in
that same turn, or in the one after a Hard Stop's answer: every lane of the
scope at once, the ones beyond the concurrent-lane cap too. A lane within the
cap whose base already holds what it builds on starts at once. Every other
lane provisions its worktree, reports `ready` and parks: its warm build, its
tests and its code wait for the driver's `go` (SendMessage, by the lane's
session id), sent as a slot frees — and to a lane stacked on another lane, sent
only once the predecessor's branch holds the implementation the design names,
with `restack onto <that head>` first. Nothing is lost in the wait: the brief
already carries the design as validated.

The lane may implement directly or hand the work to a `codex` write run into
its own worktree (`--cd` its worktree path). Any implementation handoff gets
the same contract: **surgical edits only, DO
NOT commit** (leave the tree dirty), run the named tests, print a short summary.
Each worker receives the absolute checkout path, the task contract, its owned
paths, the base SHA, the relevant project instructions, the test expectations,
and the warning that other agents are working concurrently and their changes
must be preserved.
Then **the lane re-runs the tests itself, reviews `git diff`, and commits**
with proper attribution — never trust a "tests passed" claim without re-running.
Parallel writers are safe only on **disjoint file sets**; the brief tells each
lane which paths the other lanes own, and the lane tells its workers.

Building happens as part of running the named tests. When a change needs the
product actually launched to be exercised, go through the live-test executor
the project profile names for that surface (it builds a fresh instance and
launches it under agent control). Update the project's required architecture
maps and docs with behavior changes in the same lane.

### 4 — Per-step review — **Code Review gate**

A first-order review on every sub-task, before it can advance. Review an
immutable snapshot: give every leg the same exact base/head (the shared
[scope helper](../review-agent/scripts/resolve_scope.py) can record it) and do
not edit the tree while a leg reads it. Run all three
legs — the third folds into the first in light and may in heavy:

1. A native correctness review, by [weight](#weight), run by the lane.
   - **Light**: the lane launches three reviewer subagents (Agent tool,
     `general-purpose`, told to review and never edit) over its exact
     range (`<lane-base>...HEAD`, the base SHA recorded at lane fork), each
     given the lane's intended behavior and the paths other lanes own. Each
     reads only the Phase 1 angles of
     [`claude-stock-code-review`](../claude-stock-code-review/SKILL.md),
     runs none of its other phases, performs its angles itself in its own
     context — never through the Agent tool — and owns one group: **inside
     the diff** — Angles A, B, D and E, plus a doc comment deleted or
     rewritten without its content carried over; **outside it** — Angle C
     and Conventions, plus the local review docs the project profile names;
     **quality** — Reuse, Simplification, Efficiency and Altitude, plus
     unreachable branches and fallbacks for states that cannot occur. Each
     returns, as text and never through ReportFindings, every candidate it
     can tie to a quoted line and a concrete failure or cost, with no count
     limit, ranked most severe first and
     deduped across its angles, each with `file`, `line`, `summary`,
     `failure_scenario` and `category`. The lane dedupes them and verifies each
     against the code before fixing, with that skill's Phase 2 verdicts
     (CONFIRMED / PLAUSIBLE / REFUTED); no verifier agents and no sweep.
   - **Heavy**: the lane invokes **`/claude-stock-code-review`** — the
     shared model-invocable copy of Claude Code's stock `/code-review` (it
     runs as a forked background subagent). **Pass the lane's exact range as
     the argument** (`<lane-base>...HEAD`): with no argument its diff
     defaults to `@{upstream}...HEAD`, which reviews nothing once the lane's
     draft-PR branch is pushed. If the copy is unavailable in the session,
     spawn a fresh review subagent (Agent tool, `general-purpose`) over the
     exact diff with a first-order mandate instead. Give either a generous
     deadline, ~60 minutes of agent time; past it send one wrap-up message
     if the runtime can reach the run, otherwise treat it as the silent
     death below — never a silent wait.
2. An independent cross-provider review focused on the area of risk: the
   lane uses the **`codex` skill** in review mode. Reviewers receive the
   intended behavior, the exact diff and the relevant project constraints,
   without being steered to rubber-stamp
   an implementation.
3. A simplification pass, **sized to the diff** in heavy: on a substantial diff,
   the lane invokes the **`/simplify`** skill (it is model-invocable) — fix
   what it surfaces. On a small or low-risk diff, skip the separate
   pass: the native review's cleanup angles already surface reuse /
   simplification / efficiency / altitude findings — apply the worthwhile
   ones and record `simplify: folded-into-review`. Light always folds it in,
   into the quality reviewer.

**In light, scope and budget every reviewer subagent** — the three above and
the fix-delta one below. Hand it the exact range and short notes — the
intended behavior in a few lines and, for the fix-delta one, the verified
list as one line per finding (`file:line`, `summary`, `failure_scenario`) —
never the implementation briefs, earlier review reports or PR threads they
came from. It opens code by line range — the function or type enclosing each
hunk, the call sites and helpers its greps turn up — never a whole source
file, and batches its reads: one command prints several hunks, not one per
turn. Give it a budget of ~40 tool calls or ~15 minutes of agent time; one
that cannot finish within budget returns what it has, ranked as usual, with
unfinished leads marked unverified and the hunks it never reached named,
instead of exploring open-endedly. Those hunks go to a fresh reviewer with
the same brief and budget — the lifecycle's waves — until every hunk has
had a reader; the gate never passes on an unread hunk. The budget is the fixed
deadline the [bounded lifecycle](../review-agent/references/lifecycle.md)
requires of every wait: past it the lane sends one wrap-up message
(SendMessage), never a silent wait (observed: a fix-delta reviewer handed two
implementation briefs, three review reports and the PR thread read whole
files and traced code one command per turn: 183 turns, a ~485k-token context,
36 minutes of which its tools took 31 seconds, until the driver told it to
wrap up).

**In heavy, the forked native review can die silently.** `/claude-stock-code-review` forks
finder subagents and a verifier; on a session model rate limit (`You've reached
your ... limit`, HTTP 429) the finders' raw angle reports still arrive as task
notifications but the consolidated, verified report never does (observed: nine
forks across three lanes, zero consolidated reports). Treat the raw angles as
unverified candidates — reconcile them yourself against the code — record the
native leg as `degraded: no verified report`, and re-run the skill once on the
final range when the limit has reset instead of re-forking per fix round.

If a named surface is not model-invocable in the lane's session, run that
leg in the lane's own form (a spawned subagent or the lane's own pass over the
exact diff) and record the substitution — availability never cancels a leg,
and no leg satisfies another; only the weight and the sizing rule above may
fold the simplification pass into the native review.

**Launch every leg that runs together, in one message, as background runs** — they
are independent reads of the same diff; running them back-to-back is a
scheduling bug. In heavy, because the simplification pass edits the code, reconcile at
the gate against the **post-simplify** tree: confirm each correctness finding
still applies, and if simplification rewrote the reviewed code beyond
mechanical cleanups, re-run the cheap native review on the final diff before
calling the gate.

**Proceed only when the native and cross-provider reviews agree the solution is
sound.** Reconcile every finding with concrete code evidence; fix actionable
in-scope defects, then repeat only the affected checks. In light that is one
fix-delta check once the fixes change behavior: commit the fixes, then a fresh
reviewer subagent, scoped and budgeted as above, over
`<reviewed-head>..HEAD` and the enclosing functions, given the verified list
and the remit of `claude-stock-code-review`'s Phase 3 — what the fixes broke
or missed, not re-confirmation — reporting every candidate on the same terms,
plus one cross-provider pass over the same delta. The delta is what the lane
itself wrote since the reviewed head: its own commits
(`git log -p --first-parent --no-merges <reviewed-head>..HEAD`) and, for a
merge made in between, that merge's conflict resolution alone
(`git show --remerge-diff <merge>`) — never the base commits a merge or
restack carried in, which `git diff <reviewed-head>..HEAD` would hand the
reviewer as if they were fixes. The lane verifies what
they find; fixing it starts no further round, and those last fixes reach the
Final Review as a range no first-order pass read.
If a pass comes back `blocked`, the two reviews
conflict on a material point, or fixing a finding needs a broader redesign than
the finding names, that is a **Code Review gate failure — stop and ask**.

The layered cross-validated review (`review-agent`) does **not** run here —
it is deferred to the single whole-scope **final pass (the Final Review gate)** below, because it
is expensive.

### 5 — Test under a clean state — **Live Test gate**

**Size the test to the risk, with a stated reason** — record the tier and why
in the Live Test record. Distinguish source checks, build success, launch
success, exercised behavior, screenshots actually inspected, and measured
performance; one does not prove the others.

- **No runtime surface touched** (docs, CI/build tooling with its own tests)
  → record `not-applicable:` with the reason; no live run at this gate (the
  readiness floor in phase 8 still applies before ready).
- **Covered risk** (the default) — the changed behavior is reliably pinned by
  the unit/module tests that already ran in phase 3 → one clean-state **boot
  smoke**: build, boot, load the touched area, decisive verdict.
- **Real risk** — behavior automated tests cannot reliably pin (UI flows, live
  scripting/AI, physics feel, persistence/restore, cross-system interactions)
  or a wide blast radius → a **full surface exercise** per the rules below.

A smoke that surfaces anything doubtful escalates to the full exercise — never
to a shrug. Do not stretch a low tier over a risky change to save time; the
tier claim is part of the gate evidence.

**Pick the live-test executor by product surface** from the project profile's
"Verification by changed surface" table (learned the hard way: an executor
built for one runtime cannot drive another — native tooling cannot drive a
browser game, a desktop run says nothing about a mobile host). A browser or
device executor that differs in mechanics still carries the same tiering, time
budgets, and Reporting Contract.

The lane delegates the live run to the chosen executor, **reproducing a
clean-state scenario** so stale data cannot mask or fake a pass:

- Clear only the persisted state the profile lists as relevant to the changed
  area before the run (session/scenario/editor state, run artifacts), unless
  the test is specifically about restore/restart. **Never clear or namespace
  away a shared authentication session for an ordinary run.** For auth-flow
  tests, use the dedicated isolation the profile describes and clean only
  that isolation afterward. Identify the exact product, runtime, build,
  revision, and state namespace of the run.
- For stale build output, rely on the executor's own build step to produce a
  fresh binary (its managed launch rebuilds) rather than reusing stale output.
  Do not edit or rebuild the executor's live checkout while it is exercising
  the product.
- **In the full-exercise tier, exercise every product surface the change
  touches — the success AND the failure path of each affected
  command/behavior — not one representative case.**
  Enumerate the affected cases from the diff and drive each: a single happy-path
  (or single-failure) smoke misses a regression in a branch that only *looks*
  untouched and leaves new behavior (e.g. a rollback / transactional path)
  unproven. Treat any affected surface you did not exercise as a coverage gap to
  close, or to call out explicitly in the Live Test record rather than imply it passed.

Run live tests for different lanes **in parallel by default** — lanes in separate
worktrees are isolated by design when the project's managed launch gives each
worktree its own instance registry, ephemeral ports, a no-focus background
window, and process-local input (the profile says whether it does). Serialize only
when runs contend for a genuinely machine-wide resource: GPU-heavy captures, a
test that deliberately needs real foreground focus or native input, a paired
physical device, or a run that mutates a shared auth session. Within a single
instance, an executor's agent commands still run sequentially. The profile
records agent-mode facts that otherwise cost a baseline run (input encodings,
pre-existing behavior on the base branch that must not be classified as the
lane's regression without a baseline).

Give each Live Test handoff a **time budget matched to its tier** (boot smoke ~10–15
minutes of agent time; full exercise 30–45; longer only with a named reason
such as a long scenario or many affected surfaces). A run that cannot reach its verdict
within budget returns `blocked` with what it did prove instead of exploring
open-endedly — the multi-hour live-test runs on record were agents deliberating, not the
product being slow.

**Record exactly what state was cleared** so the result is reproducible. The
executor returns only its **Reporting Contract** (Verify shape:
verdict / checked / evidence / repro / state). Any `fail`, `blocked`, or
`ambiguous` verdict is a **Live Test gate failure — stop and ask**, surfacing the evidence
and the proposed fix before iterating. A central `needs-human` assertion also
stops the gate for a human verdict; secondary `Needs human eyes` items stay explicit
coverage gaps and cannot be silently counted as automated passes.

### 5a — Platform host verification (conditional) — **Platform gate**

The driver runs this per scope, after every lane's Live Test gate, **only when the change reaches a
platform host surface the project profile defines** (a mobile host, a handheld,
a console target — each with its own compiler, sysroot, dependency root and
GPU backend). The Live Test gate exercises the primary product; nothing it
does says anything about another host. The profile names, per host: the
surface (paths and link closure), the executor, and the verdict rules.

Decide:

- **No such surface touched** → record **`not-applicable:`** and skip.
- **Touched** → the profile's **emulator/simulator run**, delegated to the named
  executor: build for the target, clean-install, launch with the log captured, and
  decide from **logs and pixels**. Know what the default launch renders — a host
  whose default bundle draws nothing by design needs the profile's artifact-loading
  flag before any rendering claim can be made. Verdict rules and the evidence contract
  live in the executor's skill; a `fail`, `blocked` or `ambiguous` verdict fails this gate.
- **Hardware-only question** → **real-device run**, additionally. A simulator pass never
  substitutes for these, because the simulator is not the device: it runs on the host
  machine's CPU and GPU (so CPU work is *faster* and frame times are *slower* and
  unrepresentative), exposes a different graphics feature set, and enforces no memory
  limits or thermal throttling. Anything about performance, memory ceilings, GPU
  feature parity, thermals or real touch input is a device question.

Two honest limits to plan around on real devices:

- Where the device tooling streams stdout/stderr but offers **no screenshot
  command**, log evidence works and visual confirmation on hardware is a **human
  step** — record it as `needs-human` rather than claiming a pixel check you did not make.
- A paired device is a genuinely **machine-wide resource**: device runs serialize across
  lanes and across agents, like GPU-heavy captures. Simulator runs do not.

Any gate failure is a **stop and ask**, with the log evidence and the screenshot (or the
explicit note that no screenshot was possible). Where a simulator control panel
grants device access per session, or a synthetic-input hook cannot fire the host's
native gesture recognizers, the profile says which checks a subagent-only run can
decide and which must be driven from the main session.

### 5b — Performance capture (conditional) — **Performance gate**

The driver runs this per scope, after every lane's Live Test gate and before the Final Review gate, **only when the change touches a
performance-critical surface** — anything on a per-frame, per-request or
per-step hot path. The authoritative list lives in the project profile
("Conditional gates and consent") and the profiling skill it names.

Decide:
- **No performance-critical surface touched** → record **`not-applicable:`**
  and skip.
- **Touched** → stop and ask the user to explicitly approve the profiling
  route for the named scope and scenario; invoking `orchestrate-linked-sessions` alone is not
  profiling consent. After confirmation, capture a before/after pair via the
  profiler executor the profile names, on the affected scenario (baseline
  from the base branch or a stored baseline; after-capture on the candidate).
  Same scenario, same capture length, comparable activity — the profiling
  skill's comparison discipline is binding.
  Attach the numbers (frame or latency p50/p95/p99, hitch count) to the PR body.
- A regression beyond noise (worse p95/p99 or more hitches across two runs)
  that the PR does not explicitly justify is a **Performance gate failure — stop and ask**
  with the two captures as evidence.

Gather available non-dependent evidence while the consent decision is pending;
make no measured performance claim without the captures.

### 6 — Final review & lint (whole scope) — **Final Review gate**

The driver runs this **once**, after **every** lane has reported its per-lane gates passed and before any PR is
marked ready. It is the expensive pass, so it is deferred to the end and run over
the **whole change scope** rather than per PR — and once per repository in a
cross-repo scope.

**Every lane's work is committed and reported before this pass.** `review-agent`
resolves a committed range, and a lane's commits are on its branch in the
shared repository, readable from the driver's worktree by ref; its uncommitted
edits are not. A lane whose receipt is missing, or whose branch is behind what
it reported, is not done: ask it to commit and report, never read its worktree
for it. A lane whose code is final and whose only open item waits on the
person — a sign-in only they may approve, a device, a decision — counts as
reported: name that item in the pass's scope, and flip its PR ready once the
person acts, with no new pass unless its code changes.

1. **Fidelity to the scope record.** Re-read the intake scope record and hold
   the delivered set against it: every promised outcome shipped or covered by
   an approved amendment, the done-proof actually holds, and nothing material
   added beyond the ask — unrequested scope is drift too. Any unexplained gap
   is a **Final Review gate failure — stop and ask** before paying for the
   expensive review pass.
2. **Model/engine checkpoint.** Explicitly invoking `orchestrate-linked-sessions` authorizes its
   named final `review-agent` pass; do not add a second consent prompt or an
   external review wrapper. Run the current `review-agent` topology and
   follow its model policy (the profile's "Provider policy", else the user's
   choice). If either leg reports a cheap/fast tier or cannot report its
   effective model, treat the result as degraded rather than inventing a
   fast-mode checkpoint.
3. **The `review-agent` pass** — the second-order layered, cross-validated
   review across the full scope: project-encoded, cross-cutting, and
   architectural risk on top of the first-order reviews the Code Review gate already ran per
   step — the skill's default lens set assumes exactly that. Pass it
   every lane's base and branch — a lane's range is `<lane-base>...<lane-branch>`,
   which the skill's scope helper resolves with `--head <lane-branch>`, and a
   stacked chain's whole scope is `<base>...<top branch>` — each lane's
   worktree path as read-only context, the weight, the first-order receipts
   with any ranges no first-order pass read (fixes made after a lane's last
   review), the project profile, and the outstanding limitations. For
   independent lanes the scope is the set of their ranges, the deterministic
   checks of each lane's snapshot are those its receipt holds for the reviewed
   head, and the report states coverage per lane. Run it by
   spawning the **`review-orchestrator` subagent** with the scope (both
   runtimes ship the def; the skill's topology is its contract), with no
   `model` or `effort` of its own — it inherits the session's, and its report
   names what it ran on —
   never through the Skill tool: `review-agent` is explicit-only
   (`disable-model-invocation`), skill authorization does not chain, and the
   Skill call is refused by design. The checkpoint above already carries the
   user's consent, so the refusal is expected — neither a blocker nor a stop-and-ask.
   The subagent runs in the driver's worktree and writes its report there,
   under the run's evidence path; the lane worktrees it is handed are read,
   never written — a refused write into one of them is the wrong location,
   not a failed pass.
   Follow the skill's capability-based topology and
   [bounded lifecycle](../review-agent/references/lifecycle.md): the parent
   owns completion, child handles and results are tracked, and in heavy a
   missing nested-spawn or resume capability is handled by parent fan-out and
   collection (`NEEDS_PARENT_FANOUT`). Never finish with "children are
   running" as though that were the report. A sequential native fallback
   must state its reduced independence.

Reconcile every finding. Any blocking finding, or a review verdict of `blocked`,
is a **Final Review gate failure — stop and ask**, then fix and re-run the affected pass
on the new snapshot, preserving unaffected results with their provenance. A
**`REVIEW INCOMPLETE` report also fails the Final Review gate**: if a review leg couldn't finish
(a backend not logged in, a rate limit, a timeout), do **not** treat the
degraded result as a pass — **stop and ask** the user how to proceed (accept
the single-engine result, fix the cause and re-run, or abort). `REVIEW
COMPLETE` is a coverage statement, not a claim of zero findings; an accepted
`INCOMPLETE` stays visible in the PR body and at closure.

### 7 — Cross-platform verification (whole scope) — **Cross-Platform gate** (conditional)

Run this once, after the Final Review gate and before landing, **only when both conditions hold**:

1. **The change scope carries cross-platform risk** — it touches the build
   system, toolchain, platform-specific code or `#ifdef`s, filesystem/path or
   process handling, OS wrappers/launchers, or anything whose behavior can
   differ across the platforms the project supports.
2. **A remote target (container, sandbox, or reachable host) is
   reachable** for the platforms the change puts at risk.

Decide:
- **No cross-platform risk** → record **`not-applicable:`** and skip.
- **Risk, but no reachable target** for a platform at risk → do **not** silently
  pass: record **`waived:`** with the reason, surface it in closure, and **stop
  and ask** when the risk is material.
- **Risk and a target is reachable** → use the cross-platform tooling the
  project profile names to build and run on each at-risk OS through its
  remote/sandbox tooling, keep exact-revision evidence, and
  reconcile parity failures. Any build or runtime parity failure is a
  **Cross-Platform gate failure — stop and ask**, then fix and re-run.

### 8 — Mark ready & land

The draft PRs already exist from phase 2. Once **Code Review and Live Test pass for each PR, the
whole-scope Final Review pass is clean, and Cross-Platform has passed or been recorded
`not-applicable:` / `waived:`**, the driver flips each out of draft via the
**`github-create-pr` skill** (`gh` needs no worktree) — **the moment the gate
set completes**, not in an end-of-run batch; a passed gate sitting in draft is
pure latency.

**The readiness floor is unconditional; the profile defines what it is.**
Before a PR flips ready, its **final commit state** must have passed the floor
the project profile names — by default a green build, a passing clean-state
boot smoke, and the applicable CI checks for the touched files. The profile
may declare a component of the floor not applicable for a class of change (a
docs- or tooling-only change with no runtime product impact may carry
`not-applicable:` for the runtime smoke, with the reason recorded); that is a
recorded status, never a silently skipped floor. Earlier gate runs count
only if no commit landed after them — a fix commit for Code Review, Final Review,
or Cross-Platform findings that never
re-built, re-booted, or re-ran checks is untested code about to land. The Live
Test risk tier does not waive this floor. The lane runs the floor's checks in
its worktree and its receipt names the head they passed on; the driver flips
nothing it has not read there.

**Never
auto-merge**: readying PRs is the orchestrator's job, merging is the user's.
A review or implementation request alone never implies merge, deployment,
external report publication, or messages to teammates.
Report the ready PRs and merge only on explicit instruction, then follow the
chain mechanics below. Confirm the body still reflects the whole branch, in the
`github-create-pr` body shape, with `## Testing` naming the actual clean-state
commands and verdict. When a
stacked chain merges, retarget each downstream PR onto its new base **before**
merging the one below it (the driver, with `gh`); once that merge has landed,
have the downstream lane restack onto the updated base with a lease-guarded
force-push and re-run its floor (see github-create-pr "PR Chains"), and merge
it only on that new head. Never merge a PR before retargeting the PR stacked
above it.

## Gates summary

| Gate | Scope | Condition to pass | On failure |
|------|-------|-------------------|------------|
| **Design** | per sub-task | Design cross-provider-validated before code, or honestly recorded as `adopted-existing-work` | **stop & ask**, then revise the plan |
| **Code Review** | per sub-task | Native + cross-provider reviews agree; simplification applied or recorded `folded-into-review` | **stop & ask**, then iterate on the code |
| **Live Test** | per PR | Risk-sized (`not-applicable:` / boot smoke / full exercise, reason recorded); clean-state executor returns a decisive `pass`; no central assertion is `needs-human` | **stop & ask**, then fix & retest |
| **Platform** | per scope, conditional | Simulator/emulator boot/render via the profile's host executor when the change reaches a profile-defined host surface, plus a real-device run for hardware-only questions (performance, memory, GPU features, touch); otherwise `not-applicable:` | **stop & ask**, then fix & re-run |
| **Performance** | per scope, conditional | Before/after capture via the profile's profiling route when the change touches a performance-critical surface; no unjustified p95/p99/hitch regression | **stop & ask** with both captures |
| **Final Review** | whole scope, once per repo | Delivered work matches the intake scope record; `review-agent` returns `REVIEW COMPLETE` with both strong-model legs complete | **stop & ask**, then fix & re-run |
| **Cross-Platform** | whole scope, conditional | Cross-platform parity via the profile's tooling when the change has cross-platform risk *and* a remote target is reachable; otherwise `not-applicable:` / `waived:` | **stop & ask**, then fix & re-run |

New output always uses the gate names. A project profile may record legacy gate
IDs that older runs, PRs, and transcripts of that project reference.

A per-sub-task gate failure (Design / Code Review / Live Test) parks **its lane**; other lanes keep
running (see [Stop conditions](#stop-conditions)). Whole-scope failures
(Platform / Performance / Final Review / Cross-Platform) stop the scope. Independent of every tier decision, the
**unconditional readiness floor** (phase 8) gates each PR before it flips
ready, on the final commit state.

## Parallelization

Concurrency is the default shape of this loop, not an optimization. The driver
is a **scheduler**: it keeps lanes moving and evaluates gates. Any moment where
the driver idles on a single background op while another lane has ready work is
a scheduling bug.

**The lane model.** After the Design gate, each independent sub-task is a lane —
a linked session in its own worktree: set up → implement → Code Review → Live
Test — advancing on its own turns, independently of the other lanes and of
the driver. Aim for **2–3 concurrent lanes** on a shared machine — CPU, the
build cache, and product instances contend beyond that; further lanes are
started with the rest and wait for `go` behind the first free slot.

**The lane ledger.** The driver keeps, in working context and under the run's
evidence path (`.local/orchestrate/<run>/lanes.md` by default), one row per
lane: name, session, worktree path, base SHA, branch, PR, the last state line,
and what the lane waits for. A lane's end-of-turn note reaches the driver only
once every lane is quiet, so a lane sends its state line to the driver itself
(SendMessage to the driver's session id, which its brief carries) whenever
anything the ledger holds changed — its phase or status, its head or base,
its PR, what it waits for — or a request of the driver's is done; a freed
slot, a new head or a finished lane must not wait for the others; a turn that
changed none of that sends none, the app's note is enough, and every message
starts a turn of the driver's — and the driver answers by the lane's session
id. Anything in a lane's worktree — a restack, a revert, a re-run — the
driver asks of the lane by message and never does there.

**Evidence outlives the worktree.** The app hands an archived session's
worktree folder to a new session, so `.local/` is scratch and a path into it
is not a record (observed: two later lanes landed in the folders of two
closed ones, whose receipts the PR bodies still pointed at). A receipt is
therefore self-contained: the decisive lines of a log, a measurement, a
verdict are quoted in it, and what it must link lives in a durable place — a
PR, a ref — never under a worktree path. Two durable copies: a lane posts its
receipt as a comment on its PR at closure and names that comment in its final
state line (a lane that closed before it had a PR sends the receipt in that
message instead); the driver pushes the run's folder — the scope record, the
design and its validations, the lane briefs, the ledger, every lane's
receipt, the Final Review report, the closure — to
`refs/orchestrate/<run>/notes` in the repository, as a commit of that folder
alone: fetch the ref first (`git fetch origin
+refs/orchestrate/<run>/notes:refs/orchestrate/<run>/notes`, which fails
harmlessly before the first push), `git add -f` the folder into a temporary
`GIT_INDEX_FILE`, `write-tree`, `commit-tree` with the fetched tip as the
parent when there is one, `update-ref` the local ref, `push origin
refs/orchestrate/<run>/notes` (a fast-forward: a rejected push means a newer
tip to fetch and build on, never a force) — when the Design gate passes, at
each lane's closure and at the run's closure; every PR body links the ref. A
run whose driver is gone resumes in a new driver session from the ref and
the PRs. The profile may name another durable place; a repository with no
remote keeps the ref locally and the closure says so; a worktree is never
one.

**Stopping.** The person's stop in the driver stops nothing in the lanes: list
the linked sessions and stop each one (`list_sessions` with `linked`, then
`stop_session`), and report what was stopped. A lane is finished when its PR
has merged and the driver has pushed that lane's closure to the notes ref: the
driver archives it then, by its id with the PR as the reason
(`mcp__ccd_session_mgmt__archive_session`), and the person's invocation is the
word for that (observed: merged lanes stayed open in the sidebar until the
person asked to archive them). Every other lane stays for the person to open,
at closure too; archive one of those only on the person's word.

Machine-wide build resources are easy to forget: a build-cache writer lease or
a dependency-root lock that two lanes of the **same** session contend for
exactly as sibling agents do, where every retry costs the whole build. The
project profile ("Lanes and resources") names them, how to see who holds
them, and how a dead holder is recognised and cleared. Serialize builds per
session where the profile says so and let the review, live-test and
cross-provider legs overlap the one build that is running instead. Before
retrying a lock timeout, check whether the holder is alive — a stale lease
from an aborted sibling can block a lane for hours behind a message that looks
like a lane-specific problem.

Runs concurrently:

- **Design validations** — one backgrounded cross-provider run per sub-task,
  launched as a single batch.
- **Lanes** — one linked session each, on disjoint file sets; every brief
  names the paths the other lanes own.
- **The review legs** — native review (in light, its three reviewers),
  cross-provider review, and the
  simplification pass (when it runs) launch together inside each lane; reconcile
  against the post-simplify diff at the gate.
- **Live-test runs** — per-lane worktrees isolate managed instances by design
  where the profile says so (worktree-local registry, ephemeral ports,
  background window); nothing to
  configure. Serialize only for genuinely machine-wide resources (GPU-heavy
  captures, real-focus tests, paired devices, shared-auth mutation). Within one instance,
  an executor's agent commands run sequentially.
  **Exception for live runs served from the lane's own source tree:** when the
  live run is driven off a dev server with hot reload serving that same
  worktree, any source write during it triggers a reload and destroys the run
  — the same holds for a browser-test lane whose web server is that dev
  server: an edit mid-run shows up as
  `Execution context was destroyed` failures that look like product bugs. In heavy, the simplification leg of the
  Code Review gate edits code, so it and such a live test cannot overlap in
  one lane — run the two read-only review legs alongside the live test and the
  simplification pass after it, or finish the review legs first. Ordering the
  live test before the review legs also costs a re-run whenever review changes
  the code, which the readiness floor then requires anyway.
- **Warm-up builds, PR prep, and background cross-provider runs** — overlap
  any of the above.

Stays serial, deliberately:

- **Final Review and Cross-Platform** run **once** over the whole scope, after
  every lane has passed its per-lane gates — do not parallelize them across
  sub-tasks. Cross-Platform runs only
  when it applies (cross-platform risk *and* a reachable target).
- **Landing mechanics** — retarget/restack/merge order for stacked chains.
- **A lane's own verification** — re-running the named tests and reviewing
  `git diff` before each commit stays with the lane; keep it targeted so no
  lane becomes the long pole.

Launch each background cross-provider run as one backgrounded call with its
own output file and probe it through that counterpart skill's watcher rather
than polling blindly.

## Stop conditions

Checkpoint and ask the user when:
- the scope, owner, or "done" proof is ambiguous
- a lane session cannot be started, ends a turn without its state line, stops
  answering messages, or its worktree or branch is gone
- the project profile names no provider model and the user has not chosen one
- any gate fails or a review pass is `blocked`
- a performance-critical surface was touched but a comparable before/after
  capture cannot be produced (no scenario reproduces the load) and the gap is
  not waived
- a performance-critical surface was touched but the user has not explicitly
  approved the profiling route for the scope
- the two per-step reviews conflict on a material point
- the work needs materially more PRs (or wider surface) than planned
- the delivered work drifts from the scope record (a missing outcome or an
  unrequested surface) with no approved amendment
- a clean-state test cannot run and the gap is not waived
- the change reaches a profile-defined platform host surface but no simulator is available, or the question is
  hardware-only and no paired device is reachable
- the cross-provider validator flags the design as wrong rather than just refinable
- the Final Review pass reports a cheap/fast tier, cannot identify the effective model, or returns `REVIEW INCOMPLETE`
- the change has cross-platform risk you cannot verify (no reachable remote target) and the gap is not waived

A gate failure or ambiguity stops **its lane, not the world**, and is asked in
the session that owns it: a lane posts the checkpoint in its own thread, where
the person answers it, and tells the driver in one line; the driver never
re-asks a lane's question, and the other lanes keep running. A decision that
could invalidate other lanes too — a scope-wide ambiguity, a shared-contract
change, a defect the other lanes build on — is the driver's: it halts the
lanes whose work in flight the answer could invalidate (`stop_session`; a
message reaches a busy lane only when its turn ends), sends `pause` to the
rest and waits for their `paused` state lines, then asks. Batch every
decision pending at the driver into that one checkpoint — one round-trip, not
one ask per lane.

Checkpoint shape:

```md
Hard Stop
- triggered_gate_or_rule:
- current_proof:
- smallest_safe_next_step:
- other_lanes: <running | parked — and why>
- decision_needed:
```

## Closure

Report the smallest honest summary:
- the PRs opened (links), and how they stack on the base branch
- the run's notes ref (`refs/orchestrate/<run>/notes`) at its final commit,
  and each lane's receipt comment
- the lane sessions, by name and link, each with its final state and whether
  it still waits on the person
- the scope-record verdict: each recorded outcome shipped / amended /
  descoped, naming the user decision behind every amendment
- the weight the run used (`light` or `heavy`)
- per-sub-task/PR gate status using tagged statuses: `ran:`, `not-applicable:`,
  `blocked:`, `waived:`, or `degraded:` for Design / Code Review / Live Test, the per-scope
  Platform result (simulator verdict, and whether a device run was needed and made), the
  per-scope Performance result (with the
  before/after numbers when it ran), and the whole-scope Final Review
  (`REVIEW COMPLETE` / `REVIEW INCOMPLETE`, with the effective model of each leg) /
  Cross-Platform results
  (record Platform / Performance / Cross-Platform as `not-applicable:` or `waived:` when
  they did not run)
- each gate receipt names the repository, revision, the actual command or
  review assignment, the result, the evidence location the profile designates,
  and unresolved limitations — kept compact and local; no report service is mandatory
- what was actually tested and at which Live Test tier, and which persisted state was
  cleared for it
- how the lanes actually ran: max concurrent lanes, and anything planned
  parallel that serialized (with the reason)
- elapsed wall clock from invocation to the last PR going ready, and the
  longest single wait with what it was waiting on
- any open decisions or risks, and any follow-up PR opened for workflow or
  profile friction (see below)

Never claim a gate passed without the evidence that proves it. Do not call the
task complete while required work or children remain outstanding; if a blocking
decision prevents further progress, report the completed work and the precise
gap without inventing a pass.

## Handoffs (skills & docs)

Every shared skill named here is installed under `SKILLS_ROOT`; a runtime's
skill root links to it. If `Skill(<name>)` answers `Unknown skill` in a session
(the link is missing, or the runtime cannot follow it), read
`$SKILLS_ROOT/<name>/SKILL.md` directly and follow it; for a skill whose
topology is "spawn an orchestrator subagent" (`review-agent`), hand that
subagent the path and let it read the file itself. Project skills the profile
names live under `PROJECT_ROOT`.

- PRs & chains: **`github-create-pr` skill**
- cross-provider design validation / second review: the **`codex` skill**
- implementation: the lane session, itself or through a `codex` write
  handoff, in its own worktree
- per-step native review / simplification: in the lane — three grouped
  reviewer subagents in light, **`/claude-stock-code-review`**
  (copy of the stock `/code-review`) + **`/simplify`** sized to the diff in
  heavy
- final review & lint (whole scope, once): **`review-agent` skill** via its
  **`review-orchestrator`** subagent, given the weight
- build / run / clean-state test: the executor the project profile names per
  changed surface (it builds a fresh instance and launches under agent
  control; a browser or device executor carries the same tiers and Reporting Contract)
- platform host build / launch / verification (Platform gate, conditional): the profile's host executor
- performance before/after captures (Performance gate, conditional): the profile's profiling route and executor
- bounded waits + cross-platform parity (Cross-Platform gate, conditional): the profile's cross-platform tooling
- worktrees & env: the app cuts a lane's worktree; the lane provisions it per
  the worktree guide the profile names

## Lanes as sessions

### The lane brief

A lane starts with a fresh context and has seen nothing of this conversation,
so the brief is its whole world. `prompt` is the brief; `background` is the
scope record in a few lines (outcome, excluded, done proof, the other lanes).
The brief, in this order:

```md
Lane brief
- run: <the scope record's initial_ask in a line>; weight: <light|heavy>
- lane: <name>; slice: <what this PR delivers, and why it is one PR>
- base: <branch> at <sha>; PR target: <the base, or the predecessor lane's branch>
- start: <now | wait for `go`>
- design: <the validated design — owner/surface, files, contract delta, verification — with the counterpart's refinements folded in>
- owned paths: <this lane's>; other lanes: <lane: paths>
- done proof: <the tests to run, the Live Test tier with its reason and executor, the readiness floor>
- codex: <model, effort and sandbox from the profile's Provider policy; `--network` when the tests need it>
- driver: <this session's id (`get_session` with `self`), where every changed state line goes; its PROJECT_ROOT, for the run's evidence paths>
- rules: read `<SKILL_DIR>/SKILL.md`, "Running a lane", before anything else; then the profile, AGENTS.md and the laws from your own worktree
```

### Running a lane

A lane is a full session, with the person, the tools and the project's
instructions; this file is its contract. Its order:

1. **Set up.** Provision the worktree the app cut, as the profile's worktree
   guide says; write the brief's spec to your own
   `.local/orchestrate/<lane>/task.md`; read the profile, `AGENTS.md` and the
   laws the slice touches; record the base SHA. If the brief says wait, end
   the turn on the state line `ready` and write no code until `go`.
2. **Implement** per phase 3 — yourself, or through a `codex` write handoff
   into this worktree — then run the named tests, review `git diff`, commit,
   push, and open the draft PR against the brief's target (the
   `github-create-pr` skill); the app's PR monitor follows this session.
3. **Gates**: the Code Review gate per phase 4, the Live Test gate per phase
   5, then the readiness floor the profile names, on the final head.
4. **Report.** Every turn ends with one state line first, then the rest;
   the same state line goes to the driver's session id by message when
   anything in it changed since the last one sent — phase, status, head, PR,
   what it waits for — or a request of the driver's is done, and otherwise
   not at all:
   `<lane>: <phase> — <ran:|blocked:|degraded:|not-applicable:> …; head <sha>; PR <url|none>; waits for <nothing|person|driver|lane X>`.
   The receipt lives at `.local/orchestrate/<lane>/receipt.md` in this
   worktree, in the closure's tagged form, with the ranges no first-order
   pass read and the Live Test record, self-contained: the decisive lines
   quoted, links only to durable places. At closure the lane posts it as a
   comment on its PR (`gh pr comment`) and its final state line names that
   comment, or carries the receipt itself when the lane has no PR, because
   the worktree folder is not kept for it (see
   [Evidence outlives the worktree](#parallelization)).

**Keep the context lean.** A lane runs for hours and pays for its whole
context on every turn (observed on the first run: two lanes of ~800 turns
each re-reading ~600k tokens a turn). The output of a Codex run, a test, a
build, a release or `verify-local` goes to a file under
`.local/orchestrate/<lane>/` and is read by line range, or by a subagent that
returns the lines that matter; several checks run in one command; a whole
source file or log never goes into the conversation. The long hands-on jobs
leave the lane's own transcript altogether: a live test driven through a
browser or a scripted call, a log or test run read for its verdict, a Codex
run watched to its end go to a subagent that returns the receipt lines (the
Agent tool; a subagent keeps the browser and shell tools), and the lane's own
turns are for decisions, the verification of review candidates, commits and
reports (observed: lanes that drove their live tests themselves ran to a
thousand turns, their reviewers' candidates buried among browser probes).

A lane never edits outside its worktree; never changes its slice — a scope
question goes to the driver by message, and the lane parks; never merges,
deploys or publishes; never starts sessions of its own; and never asks the
person what the driver owns (scope, models, the merge). It does ask the person
about its own gate failures, in the checkpoint shape, in its own thread, after
telling the driver in one line.

Messages it answers: `go` (start the warm build, then the code; when it
names a head, restack onto it first); `pause` (finish the step in flight,
commit nothing new, report the state line `paused`, wait for `go`);
`restack onto <ref>` (rebase `--onto`,
re-record the base, re-run the floor, force-push with lease, report the new
head); `revert <path>` (to the base, per phase 3); `re-run <check>`; `stop`
(end the turn where the tree stands, and say where that is). Marking the PR
ready is the driver's, never the lane's.

## Self-Improvement Policy

This workflow should get better every time it is used. While running it, watch for
friction — the list is not exhaustive: a dead link, a stale instruction, a step
that fought you, a skill that has moved or been renamed, a clearly better ordering,
or **user pushback/disappointment** when they corrected you or were let down.
Capture what you hit.

At **closure**, if you captured a clear, verified fix, route it by what it
touches — a **small, separate follow-up PR** (via the `github-create-pr` skill)
with the observed friction as its `## Why`, independent from the task's PRs:

- generic workflow friction (this file, a sibling shared skill, its scripts)
  → a PR to `sentifold/skills`;
- project policy friction (a wrong base, executor, check, resource rule, or
  report path) → a PR to the target project's `.agents/project-workflow.md`
  or the project instruction it belongs in.

For fuzzier "could be better" ideas, flag them for the user instead of forcing a PR.
Either way, **tell the user** what you hit and link any PR; never auto-merge.

- **Never edit the installed release mid-run** — it is shared by every
  session on the machine — and do **not** block the task on
  the improvement; the follow-up PR is fire-and-forget cleanup.
- One tight PR per destination per run at most; fold multiple observations into it.

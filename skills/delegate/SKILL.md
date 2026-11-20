---
name: delegate
disable-model-invocation: true
argument-hint: "<task>"
description: "Opt-in workflow for Claude Code that takes one medium task — one PR in one repository — to a validated, reviewed, tested draft PR in two layers: the invoking session, on whatever model the person started it on, designs, writes the spec, judges the diff and lands; Codex, through the installed codex skill, reads the code, writes it, fixes it and gives the diff its second read. No lanes, no linked sessions, no reviewer fan-out. Use ONLY when the caller explicitly names `delegate` or invokes `/delegate`, or explicitly asks for this spec -> Codex writes -> the session reviews loop by description. It chains github-create-pr, review-agent's pass as its final gate, and the live-test executor the project profile names for the surface under change. Do NOT auto-trigger from ordinary 'plan and implement' / feature / bugfix requests — those follow the project's AGENTS.md default behavior. Explicit invocation in any language counts (e.g. 'прогони задачу через delegate'); a generic 'implement this' does not. A scope that needs several PRs, a second repository or a conditional gate stops and names `/orchestrate`."
---

# Delegate

Take **one medium task** — one PR in one repository — to a **validated,
reviewed, tested draft PR** on the project's base branch, in two layers and no
more. The session the person invoked it in is the first: it decides the
design, writes the spec, judges the diff, talks to the person and lands.
Codex, through the installed `codex` skill, is the second: it reads the code,
writes it, fixes it and gives the diff its second read. It is `orchestrate`
for a scope that is a single lane: the same gates in the same order, without
lanes, linked sessions or a reviewer fan-out, because the session is its own
first reader and one fresh pass reads the whole change.

**What this file optimizes.** The session's tokens at constant rigor. The
session is the expensive engine and pays for its whole context again on every
turn, so its turns go to what only it can do — the design, the spec, the
judgment of the diff, the person's decisions — and reading the code, writing
it, searching it and running it go to Codex or to a file (observed: two medium
tasks, each built by one session that read, wrote, tested and reviewed in its
own context: 340–370 turns and 120–145M tokens re-read each, two compactions
each, and the person asking of both PRs why they were so large; the person
then had one redone by typing this loop in by hand). The file itself stays
small: a rule enters it only when it removes friction a run actually met.

## What fits

A task that is **one PR**: one repository, one slice that reviews, ships and
reverts as a unit, a design one spec can carry. Say at intake which it is:

- **Smaller** — a fix of a few lines, a text change: no workflow. Say so and
  do it as the project's instructions say.
- **Larger** — slices or a stack, a second repository, or a conditional gate
  the project profile defines (a platform host, a performance-critical
  surface, cross-platform risk): stop and name `/orchestrate`
  (the Claude desktop app). A task found to be larger midway
  stops the same way, with what is built so far as that run's adopted work.

## Trigger (opt-in)

Use this skill only when the person explicitly names `delegate` or invokes
`/delegate`, or asks for this loop by description (a spec, Codex writes, the
session reviews, in rounds). Do not auto-trigger from generic repo work, a
language, file paths or task intent alone; ordinary tasks follow the
project's default behavior.

## Roots and the project profile

`SKILL_DIR` is the real installed directory containing this file; `SKILLS_ROOT`
is its parent. Resolve symlinks. The sibling packages this workflow uses —
`codex`, `github-create-pr` and `review-agent` — live under `SKILLS_ROOT`,
never in the target repository.

`PROJECT_ROOT` is the session's own checkout (`git rev-parse --show-toplevel`),
on a branch of its own cut from the base, where nobody else writes: Codex
edits it in place. A checkout other work shares is not one — make a worktree
as the profile's worktree guide says, and run every command there with an
explicit path (`git -C`, `--cd`).

The project profile is `PROJECT_ROOT/.agents/project-workflow.md`, read with
the root and nested `AGENTS.md`/`CLAUDE.md` under the shared
[project contract](../review-agent/references/project-contract.md). It
supplies what this file does not: the base branch and branch naming, the
checks and where they run, the live-test executor per changed surface,
clean-state rules, the readiness floor, the provider policy, the review docs,
PR conventions, the actions that need the person's consent, and where
evidence belongs. **Without a profile**, derive those facts from the
project's own instructions, README, CI configuration and scripts, and record
them in the scope record. Never import another repository's commands,
environment variables, branch names or paths. A required check the project
defines but the environment cannot run is a visible `blocked:` gate, never a
pass.

Read and use the project skills whose trigger the task matches (a design
diff, a deploy check); invoking `delegate` does not bypass another skill's
consent boundary.

## The two layers

| Need | Who | How |
|------|-----|-----|
| The design, the spec, the person's decisions, the judgment of the diff, commits, the PR | the session | its own turns |
| Where the design lands in the code, and what is wrong with it | Codex | one read-only run |
| Implementation, fixes included | Codex | a write handoff from a spec the session writes; by hand only a trivial edit (a word, a caption, a conflict resolution, a one-line revert) or a few lines that change no behavior, ten at most, noted in the scope record |
| The second read of the diff | Codex | a read-only run of its own, in a fresh context |
| The final review of the whole change | a `review-orchestrator` subagent of the session | `review-agent`'s pass, with a Codex leg of its own |
| A hands-on live run or probe | a subagent of the session | the executor the profile names for the surface |

Read the `codex` skill's [`SKILL.md`](../codex/SKILL.md) and its
[runtime findings](../codex/references/runtime-findings.md) once, before the
first run: the helper requires an explicit `--model`, `--cd` naming
`PROJECT_ROOT` and an absolute, unused `--out` path. The model and effort
come from the person's instruction for this run, else the profile's "Provider
policy", else **ask**; never a hardcoded model, a lower effort or a wider
sandbox to make a run pass. A run that came out on a cheaper tier than the
one chosen, or whose receipt cannot name its model, is `degraded:`, not a
pass.

**One Claude model for the whole run.** The session runs on the model and
effort the person started it on — this file names none — and every subagent
it spawns runs on that same pair, the live-run executor and the final review
alike. Spawn a subagent with no `model` or `effort` of its own where that
inherits the session's, name the session's own where the runtime's default
for subagents is another, and have its report name the model it ran on: one
that ran on another model is `degraded:`, not a pass. The session never
changes its own model, and no other engine joins: no linked session, and no
implementer or reviewer subagent besides the final review.

**Codex unreachable is a stop, not a mode.** A capacity refusal is retried
once, narrower, on the same model; an auth or proxy failure is re-probed with
one throwaway call (`--effort low --no-search "Reply with exactly: AUTH_OK"`)
before it is believed. If Codex stays unreachable, stop and ask: this workflow
has no single-engine form, and the session writing the code itself is the run
this file exists to prevent.

## The session's context

The session's turns are few and its context small, and every rule here is
how:

- **Codex reads the code; the session reads what Codex points at.** The
  session starts from the maps the project's instructions declare
  authoritative and from Codex's reports, and opens source by line range —
  the place an edit lands, a mechanism to reuse, the lines of a finding —
  never a whole file to learn it.
- **Output goes to a file.** A Codex run, a test, a build, a gate writes
  under the run's folder (`delegate/<run>/` in the ignored evidence location
  the profile names; without one, outside the repository), and the session
  reads the verdict lines and the final message, by range. Several checks
  run in one command.
- **The diff is read whole once.** The first round's diff in full; after that
  only what a round adds.
- **Hands-on work leaves the transcript.** Whatever is driven through a
  browser, a device or a scripted call goes to a subagent: a live run
  returns its verdict, and a probe the design is waiting on returns the
  facts it was asked for.
- **A wait costs no turns.** Every Codex run and every long check is one
  `Bash(run_in_background: true)` call, whose exit continues the session; the
  turn ends, or goes on with work that does not depend on it. Never a run
  started with `&`, which wakes no one, and never a poll loop of turns. The
  helper's own deadline bounds a Codex run, and every other long check gets
  one of its own: a background launch supplies the wake-up, not the bound. A
  quiet Codex run is checked through the skill's watcher before it is called
  stalled, and never stopped on silence.

## The loop

### 0 — Intake

Write the task down as a scope record before anything runs; the last check
holds the PR against it:

```md
Scope record
- initial_ask: <the person's request, verbatim or tightly quoted>
- outcome: <what exists when done>
- excluded: <deliberately out of scope>
- done_proof: <the checks that mean done>
- base: <the base branch, and the SHA the branch leaves it at>
- size: <appended at the Design gate: the surfaces touched, roughly how many lines>
- project_facts: <profile read, or the base/checks/executors derived without one>
```

The record is append-only: a scope change is an amendment carrying the
person's approval, never a silent rewrite.

Ask the person now only what the design cannot start without — which of two
readings of the task is meant. Everything else of theirs waits for the Design
run and reaches them once, with what the run found.

**Adopting existing work.** Invoked on a diff that already exists, freeze
further edits and take it as round zero: stage it, read it whole, once
(`git diff --cached <base-sha>`), and commit what was uncommitted, so that
later rounds stage only what they add. The Design gate validates the approach
it finds, or the smaller one it should have been, and Codex's first read in
phase 3 covers the whole change from the base, not its round alone. Record
`ran: adopted-existing-work`, and never claim the validation was pre-code.

### 1 — Design — **Design gate**

Draft the design from the task, the project's maps and the laws or contracts
of the topics it touches: the owner of each change, the mechanisms to reuse,
the contract delta, how it will be verified. A hypothesis is enough — do not
read the code to firm it up. Then hand it to **one read-only Codex run** with
two jobs:

- **Ground it**: where each part lands (`file:line`), the existing mechanisms
  it must reuse, every caller and contract it touches, the tests that pin the
  surface today, and the change's rough size.
- **Attack it**: a wrong owner, a missed contract, a simpler alternative, a
  mechanism the outcome does not need, the risks.

Ask for both between markers, per the `codex` skill's output contract. Fold
minor refinements in and go on. A design the run redirects is revised and
validated once more; a second redirect is a **Design gate failure — stop and
ask**. With the paths the run named, check work in flight on the same surface
— the open PRs whose changed files meet them (`gh pr list --limit 200 --json
number,title,files`): an overlap found now is a scope question, found later a
rebase.

**One round with the person, after the run.** Put to them at once everything
that is theirs to decide: each open product decision with the option the
design takes and what the others cost, the new coverage the project's
instructions make their call (each scenario by name, and their count), every
consent the profile lists that the task will need, and any departure from
what they asked for, for which nothing is written until they accept it. With
nothing of theirs open, tell them the design and its size in a few lines and
go on without waiting. Record the design's `size` in the scope record.

**Write no product code and no spec before the gate passes.**

### 2 — Spec and handoff

The spec is the session's main product, and Codex's whole world: a run starts
with a fresh context and has seen nothing of the conversation. Write it to
the run's folder and pass it as the prompt, with the rules repeated above it.
It carries, in this order:

```md
Spec
- goal: <the outcome, and the size it should come to>
- not in scope: <the excluded work, and the mechanisms the design refused>
- edits: <each one as the place today (`file:line`) and what is wanted there; the mechanism to reuse, by name; for a mechanism an edit removes or replaces, what it was for and what does that now>
- constraints: <the project rules that bind these edits, by path: the laws, invariants and conventions of the touched topics>
- behavior: <the cases as a before/after table, success and failure paths>
- tests: <the approved new scenarios by name, and their count; the existing tests that must stay green>
- verify by reading: <what to confirm in the code and report as `file:line`: every caller of what changed, each contract the design named>
- checks: <the commands to run, or that this sandbox cannot run them and the session will>
- rules: surgical edits only; DO NOT commit, and run no git command that writes; no setup or build target the profile reserves; nothing outside the named paths; caches outside the repository
- report: <between markers: what changed per file, what was left undone and why, where the spec was wrong — reported, never patched around>
```

Launch the write run (`--sandbox workspace-write`, `--cd` at `PROJECT_ROOT`,
`--network` only when the checks need it) in the background and end the turn.
Paths that sandbox keeps read-only — the runtime findings list them — are
asked for as a diff between markers, which the session applies. When the run
returns, read its report and confirm the tree holds what the spec named and
nothing else (`git status --porcelain`, `git diff --stat`). A contradiction
Codex reports in the spec is the design's to answer, not the next prompt's to
paper over. A run that died mid-write is resumed on its partial tree with a
resume note, as the runtime findings say, and is the same round.

### 3 — Review in rounds — **Code Review gate**

A round reads a tree that holds still. Run the formatters the project
requires, stage what Codex left (`git add -A`) and commit nothing yet, so
that `git diff --cached` is exactly what no one has read: the whole change in
the first round, the delta after it. Then start three things in one message,
and edit nothing while they run:

1. **The checks** the spec named, run by the session itself: never trust a
   "tests passed" claim. A failure is a finding like any other; what needs a
   pushed head waits for the floor.
2. **Codex's read**, a read-only run of its own, given that staged diff, the
   intended behavior in a few lines and the review docs the profile names,
   and nothing that argues for the implementation. Its remit is what needs
   the code around the diff: every caller and consumer of what changed,
   removed behavior, races and error paths, the contracts and conventions
   the project keeps, tests that would pass on a broken implementation. It
   returns every candidate it can tie to a quoted line and a concrete
   failure, ranked, with no count limit, between markers.
3. **The session's read**, of the same diff against the spec. Its remit is
   what Codex does not see in code Codex wrote:
   - **fidelity** — every edit the spec named is there, and nothing it did
     not ask for;
   - **size** — the diff against the design's `size`: one more than half
     again as large is read first for the mechanism that grew it, and a
     mechanism the outcome does not need comes out;
   - **quality** — a rule copied where the codebase already has it, a patch
     at the wrong level, branches and fallbacks for states that cannot occur,
     state that could be derived, a test that restates the implementation;
   - **correctness inside the diff** — each hunk in its enclosing function.

Neither read stands in for the other (observed on a small PR run this way:
Codex's reading audit found a real interleaving the spec had called
unreachable, and the session's read found what Codex's had not, two names
three letters apart in an access list).

Verify every candidate of either read against the code before acting on it —
CONFIRMED, PLAUSIBLE or REFUTED, each with the line that decides it; a claim
about what an outside service does stays PLAUSIBLE until probed or cited.
When the three are in, commit with proper attribution: on this branch a
commit means read. The verified, in-scope findings become **one fix spec** in
the same shape, Codex writes the next round, and its staged diff is **only
the delta**: the session reads it for what the fixes broke or missed, not to
confirm the list again, and Codex reads it too only when it is substantial or
reaches code no reader has seen; the session's read alone certifies a small
one.

**Three write rounds in all**, the first implementation included, unless the
person names another number. Whatever changes behavior spends one: a review
fix, a live-test fix, a final-review fix, a floor fix. So when a fix is
owed, one round is left and phase 5's review has not run, run it first, on
the committed head, and let that round carry the review's confirmed
findings too (observed: a run did so with a live finding owed, and its
third round settled the review's three findings with it).
A change the person asks for after seeing
the product is a round of its own, outside that count: their asking is its
word. A trivial leftover the session fixes by hand. Work still needed when
the rounds are spent, the two reads in conflict on a material point, or a fix
that needs a wider redesign than its finding names is a **Code Review gate
failure — stop and ask**.

The gate passes when both reads have covered the whole change, every later
delta has had a reader, the last round's checks are green and no confirmed
in-scope finding is open.

### 4 — Test under a clean state — **Live Test gate**

Size the test to the risk and record the tier with its reason. Source checks,
a green build, a launch, exercised behavior and inspected screenshots are
different proofs; one does not stand for another.

- **No runtime surface touched** → `not-applicable:` with the reason.
- **Covered risk** (the default) — the changed behavior is pinned by the
  tests that ran → one clean-state smoke of the touched area. A stand-in for
  an outside SDK pins nothing about how the real one loads.
- **Real risk** — behavior tests cannot pin (a UI flow, a live integration,
  persistence, a cross-system path) → a full exercise: the success and the
  failure path of every affected behavior, enumerated from the diff.

The executor and the clean-state rules are the profile's, by changed surface.
A scripted check is one command with its output in a file; a hands-on run
goes to a subagent with a time budget (a smoke 10–15 minutes, a full exercise
30–45) that returns verdict / checked / evidence / repro / state, and
`blocked` with what it did prove when the budget runs out. A smoke that shows
anything doubtful escalates to the full exercise. A check the person does not
watch runs headless or in the session's own browser, never in theirs, and a
step that needs the person starts only when they say they are there. Any
`fail`, `blocked` or `ambiguous` verdict is a **Live Test gate failure — stop
and ask**.

A fix for a live finding is a round like any other — a spec, a Codex write,
the checks, the delta read — before the retest.

### 5 — Final review, floor, ready — **Final Review gate**

1. **Hold the work against the scope record**: every outcome there, nothing
   beyond it, the size within the design's or its growth explained. A gap is
   a stop, not a footnote.
2. **Open the PR as a draft** through the `github-create-pr` skill, on the
   base the profile names, now that the code is final; nothing was pushed
   before, and adopted work updates the PR it has. Its validation notes
   quote what they rely on — the Design run's verdict, the rounds and what
   each read found, the live tier and verdict — and link nothing under the
   worktree, which does not outlive the session.
3. **Start what the final head still needs, in one message**, and edit
   nothing until it is in:
   - **The readiness floor** the profile names, on the final pushed head.
   - **The final review**, unless it already ran: `review-agent`'s pass over
     the whole change (`<base-sha>...HEAD`), by one fresh `review-orchestrator`
     subagent that
     has seen neither the spec nor the rounds. It picks the lenses the
     change calls for, inspects them itself and runs a Codex leg of its own
     beside it. Invoking `delegate` is the person's word for this pass:
     spawn it with the Agent tool, never through the Skill tool, which
     refuses an explicit-only skill by design. Hand it the range, the profile,
     the Codex model and effort this run resolved, what the two reads covered
     with any range neither read, and the change's
     stated limitations. Its result is the whole
     report, opening with `REVIEW COMPLETE` or `REVIEW INCOMPLETE`, returned
     as text: the pass writes no report file, so ask for none and save it
     in the run's folder. A pass that returned anything else, or that a
     limit cut off, is resumed as `review-agent` says, on the same model.
4. **Settle what they found.** The pass's findings are verified like any
   candidate, and the confirmed ones, a floor failure with them, are fixed
   through a round. The pass is not repeated for its own fixes: their delta
   is read as any round's is. `REVIEW INCOMPLETE` is a **Final Review gate
   failure — stop and ask**; `REVIEW COMPLETE` states coverage, not the
   absence of findings. The floor is unconditional: any commit after it
   means the live exercise it touched repeated, the new head pushed, the
   body brought up to date and the floor run again. A rebase before it needs
   no new read when `git range-diff <old-base>..<old-head>
   <new-base>..<new-head>` shows the hunks unchanged; a hunk it shows changed
   is read like a delta.
5. **Flip the PR ready** when the final review is complete with nothing
   confirmed open, the floor has passed on the final head and the body names
   both results; then report. **Never merge, deploy or publish** on a
   request to build: each is the person's word, asked for as its own
   question.

## Gates summary

| Gate | Condition to pass | On failure |
|------|-------------------|------------|
| **Design** | One read-only Codex run has grounded and attacked the design before any new code — for adopted work after its code, recorded as `ran: adopted-existing-work` — and the person has answered what was theirs to decide | **stop & ask**, then revise the design |
| **Code Review** | Codex's read and the session's read have both covered the whole change, every later delta has had a reader, the last round's checks are green, no confirmed in-scope finding is open, within the rounds allowed | **stop & ask** |
| **Live Test** | `not-applicable:` with its reason when no runtime surface is touched; otherwise the smoke or full exercise chosen returns a decisive `pass` under a clean state | **stop & ask**, then fix through a round and retest |
| **Final Review** | `review-agent`'s pass returned `REVIEW COMPLETE` on the head it read, on the session's model with its Codex leg; every later delta has had a round's read, and no confirmed finding is open | fix through a round; on `REVIEW INCOMPLETE` **stop & ask** |
| **Readiness floor** | The profile's floor on the final pushed head | fix through a round while one is left, then run it again; else **stop & ask** |

Record every gate with a tagged status — `ran:`, `not-applicable:`,
`blocked:`, `waived:` or `degraded:` — and never claim one passed without the
evidence that proves it.

## Stop conditions

Stop and ask the person when:

- the scope or the done proof is ambiguous, or the validated design departs
  from what they asked for
- the task turns out larger than one PR, or reaches a conditional gate of the
  profile
- the profile names no Codex model and they have not chosen one, or Codex
  stays unreachable after a re-probe
- the Design, Code Review or Live Test gate fails, the final review returns
  `REVIEW INCOMPLETE`, or a check the project requires cannot run
- the rounds are spent with work still needed
- an action the profile reserves for their consent is needed and not given

Bring the work to rest first — a run in flight finishes or is cancelled
through the helper — say where the tree stands (what is committed, what is
staged and unread), and batch every pending decision into one checkpoint:

```md
Hard Stop
- triggered_gate_or_rule:
- current_proof:
- smallest_safe_next_step:
- decision_needed:
```

## Closure

Report the smallest honest summary:

- the PR (link), draft or ready, and its base
- the scope-record verdict: each outcome shipped, amended or descoped, and
  the size delivered against the design's
- each gate's tagged status: the Design run's verdict, the rounds used and
  what each read found, the Live Test tier with the state cleared for it, the
  final review's verdict with the model each leg ran on, the floor's head and
  result, and the effective Codex model
- what was not exercised, and any open decision or risk
- elapsed wall clock, and the longest single wait with what it waited on

Do not call the task complete while required work or a run remains
outstanding; report the completed work and the precise gap instead.

## Self-improvement

Watch for friction while running: a stale instruction, a step that fought
you, a rule that cost more than it bought, the person's pushback. At closure
tell the person what you hit — the sentence, and what was observed — and offer
the fix as one small separate PR: this file or a sibling skill to
`sentifold/skills`, project policy to the project's profile. Never edit the
installed release mid-run, and never block the task on the improvement.

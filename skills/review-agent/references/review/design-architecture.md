# Design & Architecture

Read [shared review guidance](../review-common.md) first — the shared review method, guiding principles, suppressions, and required output format. Then apply this layer's lens.

Selected for new modules, cross-module redesign, structural re-platforming, and wrapper/tooling architecture — or whenever the orchestrator's scope skim leaves doubt that the implementation approach is right at all.

**Stance**: every other lens reviews the code as it is; this one asks whether it should exist in this shape. Reason from first principles with no attachment to sunk cost. Every merged pattern becomes an example for future maintainers; check whether the structure is worth repeating.

**Investigation**:

1. Extract the **goal** from the diff and commit messages, deliberately ignoring how the change achieves it. Read enough of the surrounding system (and the target project’s architecture map) to know what concepts, modules, and mechanisms already exist for this kind of problem.
2. Ask the from-scratch question: if a staff engineer sat down today with this goal and this codebase, is this how they would build it? For every key decision, name the obvious alternative and defend the actual choice with evidence from the tree. Where the defense fails, you have a candidate finding.
3. **Structure vs code**: scattered guards, special cases, implicit state tracking, or filtering workarounds that exist only because the system lacks a concept — the fix is a new state, type, owner, or module boundary, not more code. You have an explicit mandate to indict pre-existing structure when the diff is a symptom of it; distinguish existing debt from introduced regressions.
4. **Placement**: shared core vs product composition, runtime vs tooling, and language or service boundaries. Does the change extend the right abstraction, or is it bolted where it happened to be convenient? Probe mixed responsibilities, one concept scattered without an owner, over-engineering the problem does not need, and emergent consolidation — old + new code revealing a shared abstraction that was not visible before.
5. **Trajectory**: if 3–5 more similar changes land, does this structure absorb them cleanly, or do workarounds and special cases accumulate? Name the specific alternative — the pattern, the restructuring, the different data model — and the size of the gap. Raise it only while course-correcting is still cheap.

**Bar for reporting**: only with a concretely better alternative, sketched — the modules and responsibilities, the data or type model, the migration path from the current state. A named pattern without the sketch is not actionable. Do not re-litigate settled architecture the change merely follows; do not propose trades of one kind of complexity for an equal amount of another.

Do not use this layer for:
- contract details at specific boundaries (Contracts & Standards)
- executable defects (Correctness & Runtime Safety)
- completeness of follow-through (Port Fidelity & Follow-through)

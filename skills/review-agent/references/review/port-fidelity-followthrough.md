# Port Fidelity & Follow-through

Read [shared review guidance](../review-common.md) first — the shared review method, guiding principles, suppressions, and required output format. Then apply this layer's lens.

Selected for feature, port, UI, and multi-step workflow work. Look for behavior implemented off the real path, behavior that fails after restart, and contradictions between workflows. Project-provided escape statistics may refine its priority.

**Stance**: the author tested one happy path through one entry point; you walk everything else. A change is not what it claims — it is what it landed everywhere it needed to land.

**Investigation**:

1. **Follow-through audit.** Restate what the change claims to do (diff + commit messages). List every implied follow-through: call sites updated, registrations made, tests moved, docs touched, related features adjusted, state migrated, UI surfaces reflecting the new behavior. Check each against the actual diff — promised-but-missing is this lens's core finding type. Hunt the unfinished edge: half-wired flags, unreachable code paths, states no surface ever displays, handlers never registered.
2. **Entry-point sweep.** Enumerate every path that reaches the changed behavior — tabs, panels, modes, dialogs, scripts, AI-driven actions, batch processing vs individual creation — and verify the change holds on each, not only the one it was built around. The canonical escape: policy applied on a batch-load path but missed on individual creation.
3. **Hostile walks** over every state system the feature reads or writes (document snapshot, view state, history cursor, session/workflow state, runtime handles, active tab):
   - restart or kill mid-flow — what restores, and does the restored UI agree with the restored domain/runtime state?
   - undo/redo or restore an older snapshot — do feature-specific cursors, branches, and indicators follow?
   - switch tab/mode/panel mid-flow — can workflow guards be bypassed, contradictory state created?
   - cancel / clear / reload / re-enter later — is every related piece of state actually cleared or realigned?
   Track the actual persisted and in-memory state at each step; the visible UI must match the source of truth after every walk.
4. **Port fidelity**: compare against the source implementation or the stated capability. Does it reproduce on actual production entry points, not only in a demo, fixture, or preview?
5. **Repairability**: pick the two or three most likely failures (load fails, stream stalls, resource missing, task error). With only the diagnostics the project actually exposes, can a maintainer locate the failing source, operation, or pipeline stage and recover? Failure boundaries need useful, joinable context without secrets or duplicate noise; validation errors should point at the repairable input.

**Bar for reporting**: name the walk or entry point and the contradictory, lost, or dead-end state a real user (or authoring agent) hits. A finding is a sequence someone can actually perform.

Do not use this layer for:
- executing single-path defects under hostile schedules (Correctness & Runtime Safety)
- boundary and API-shape questions (Contracts & Standards)
- module placement (Design & Architecture)

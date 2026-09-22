# Speculative Complexity Cleanup

Read [shared linter guidance](../linter-common.md) first — the shared linter method, suppressions, and required output format. Then apply this layer's lens.

This layer targets complexity that often appears in AI-generated code: speculative extensibility, redundant indirection, stale compatibility shims, and fallback behavior that adds surface area without a real current need.

Judge the code, not who wrote it. Use this layer whenever the diff looks optimized for plausibility, optionality, or "future proofing" instead of a clear present-day requirement.

**Investigation** — do this before forming any finding:

1. For each new branch, option, fallback, abstraction, or alias in the diff, name its concrete current consumer — the caller, contract, or persisted artifact that needs it today. Grep for it; do not take the code's word.
2. Where no consumer exists, sketch the single-path version: what gets deleted, what becomes the one canonical representation. That sketch is the fix in your finding.
3. Where a consumer is claimed, verify it against the justification list below and collect the evidence the "intentional complexity" section requires.

Default investigation stance:
- Establish the target project’s compatibility and rollout contracts before judging an alternate path.
- Prefer one clear path, one canonical representation, and one implementation unless the diff proves a second path is required now.
- New abstractions, fallbacks, aliases, or toggles need a concrete current consumer, contract, or migration story.

Focus on:
- Backward-compatibility branches, aliases, deprecated parameter names, migration shims, or old/new option handling added without an explicit supported contract.
- Fallback code paths that silently mask failures instead of surfacing them.
- Multi-format parsing or multiple accepted spellings when the project has one canonical form.
- Factories, strategies, provider interfaces, wrapper types, or extension hooks added for hypothetical future use when there is only one real implementation.
- Wrapper-around-wrapper code, pass-through helpers, or extra indirection that does not create meaningful isolation.
- Duplicate or near-duplicate code produced instead of consolidating behavior into an existing local abstraction.
- Excessive configurability or optionality: boolean switches, null/default providers, env toggles, or mode parameters when the feature has one real mode.
- Comments/TODOs that admit uncertainty or speculative intent: "keep old path for now", "fallback just in case", "future proof", "temporary shim", or similar wording without an owner/removal trigger.
- Feature flags, rollout toggles, or alternate providers introduced without an explicit owner and cleanup trigger.

Require explicit justification for keeping speculative complexity:
- a public or external contract we intentionally support
- a persisted document/session format we still need to load
- a staged migration already in progress
- platform or dependency capability detection that is actually required
- multiple real implementations or deployment modes that the product currently supports

Evidence expected when complexity is intentional:
- who or what depends on the extra path or abstraction
- what the canonical path is
- why a simpler single-path design is not sufficient
- how the old or alternate path is signaled, constrained, or deprecated
- when or under what condition the extra path can be removed

Do not use this layer for:
- required compatibility for explicitly supported external contracts
- legitimate feature detection, version/capability negotiation, or platform gating required by third-party APIs
- resilience-oriented degradation paths with a real user-facing failure strategy
- abstractions that are already justified by multiple active implementations in the current codebase

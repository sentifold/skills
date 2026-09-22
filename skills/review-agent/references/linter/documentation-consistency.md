# Documentation Consistency

Read [shared linter guidance](../linter-common.md) first — the shared linter method, suppressions, and required output format. Then apply this layer's lens.

This layer checks for direct, mechanical drift between changed code and durable documentation/comments. Prefer findings that can be tied to specific touched behavior, config, CLI flags, persistence paths, or troubleshooting steps.

**Stance**: stale agent-facing docs are worse than no docs — CLAUDE.md, AGENTS files, and the project's `docs/` are context that every future agent loads and trusts, so drift steers every future change wrong. Read the target project’s actual documentation map and verify its changed claims against the code, not against plausibility.

**Investigation** — do this before forming any finding:

1. From the diff, list every behavior, command, flag, env var, path, or workflow that changed.
2. Grep docs (`docs/`, README files, CLAUDE.md/AGENTS files, runbooks, script help text) for each one and read what the docs currently claim.
3. For each touched doc claim, verify it against the changed code: does the documented command still run, the documented path still exist, the documented behavior still hold?
4. Check the comments in the diff itself: do they explain intent and invariants (why), or narrate the implementation and the change (what)? Are they understandable without PR context?

Focus on:
- Changed docs for behavior, contracts, workflows, or architecture when the diff clearly changes them (`docs/architecture`, product docs, README/runbooks, developer scripts).
- API/CLI/config/environment-variable changes documented with defaults, examples, and migration notes where needed.
- Persisted state paths, runtime assets, log/debug artifact paths, and developer workflows kept in sync with the code.
- Stale docs and outdated TODO notes that no longer match code behavior.
- In-code comments explain intent, invariants, and constraints (why), not temporary implementation narration (what).
- Comments are understandable without PR context; avoid fragile references like "this change", "new flow", or issue-only breadcrumbs without explanation.
- Non-obvious platform quirks, edge cases, and failure-mode assumptions are documented at point of use.
- Error-handling and troubleshooting guidance in docs remains aligned with actual runtime behavior and logs.

Do not use this layer for:
- broad product-doc strategy or whether the team wrote "enough" docs overall
- architecture decomposition arguments
- speculative requests for docs unrelated to the touched change scope

# Code Hygiene

Read [shared linter guidance](../linter-common.md) first — the shared linter method, suppressions, and required output format. Then apply this layer's lens.

This layer focuses on local, low-ambiguity cleanup and entropy reduction. Prefer findings that are obvious from the changed code and do not require architectural or domain-level judgment.

**Stance**: the entropy signatures in the shared guidance most often surface here as concrete code — near-duplicate helpers, dead branches, stale comments, drifting names. Hunt them deliberately rather than waiting to notice them.

**Investigation** — do this before forming any finding:

1. Read the full diff, then for each new function, type, or helper, grep the codebase for existing code that already does the same thing — check shared/utility modules and files adjacent to the changed ones. Reinvented helpers are a primary finding type.
2. For each identifier the diff adds or touches, check the name still matches the behavior after the change, and that the same concept keeps the same name across files.
3. For each comment in the diff, apply the test: would this be useful to someone who never saw any previous version of the code? Comments that narrate the change ("now uses X", "removed Y") are diff annotations, not documentation.
4. Check apparently-dead code is really dead (grep for references) before flagging it — then flag it for deletion, not commenting out.

**What to probe**:

- Unused, stale, or dead code; obviously dead branches and redundant control flow.
- Trivial duplication where the fix is local and mechanically clear.
- Bug-prone local patterns: boolean parameter traps, magic constants, stringly-typed flows.
- Stale, temporary, PR-context-only, or code-narrating comments.
- Header/include hygiene and compile-time friendliness.
- Names: vague (`data`, `handle`, `process`), drifted from behavior, too broad or narrow, or inconsistent for the same concept across files. Code is navigated by grep — by humans and agents — so each concept needs one distinctive, searchable name, and dynamically constructed identifiers hide callers from search.
- Consistent style and structure aligned with project conventions.
- **Dependency and tool reproducibility**: verify new or changed versions, lockfiles, action references, and images against the project’s pinning policy. A permitted manifest range with a valid lockfile is not automatically a defect.

Do not use this layer for:
- subsystem decomposition or module ownership questions
- comprehension/narrative-flow stumbles that need a cold read (Readability & Comprehension owns those)
- abstraction quality or duplication that needs design judgment
- runtime behavior bugs, lifecycle issues, or state integrity problems

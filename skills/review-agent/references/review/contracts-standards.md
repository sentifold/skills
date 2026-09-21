# Contracts & Standards

Read [shared review guidance](../review-common.md) first — the shared review method, guiding principles, suppressions, and required output format. Then apply this layer's lens.

Selected when the diff touches schemas, serialization, module APIs, language or process crossings, user-facing APIs, or third-party library usage — and mandatory when it touches auth, secrets, network, or file-system boundaries.

**Stance**: a system stays understandable only while its boundaries hold. Parallel work increases the risk of contract drift. For an adopted public standard, verify the compatibility actually promised: a lookalike API can break real consumers even when its implementation appears consistent internally.

**Investigation**:

1. List every datum crossing a boundary in this diff: module ↔ module, client ↔ server, language or process boundaries, persisted state, external payloads. Trace each end to end — read the producer AND every consumer, not just the changed side. Know the shape, the ownership, and the validation point at each hop.
2. Per crossing, three questions: who owns and mutates this data? Is it validated once at the boundary, or re-checked defensively everywhere (a sign nobody trusts the contract)? If the producer's internals changed tomorrow, would this consumer break?
3. **Standards conformance**: verify names, units, coordinate spaces, and semantics against the adopted standard and the project’s declared supported subset. Use primary documentation. A renamed lookalike or silently unsupported operation breaks consumers; explicit documented feature limits are different.
4. **Third-party contracts** — triage first; go deep only when the diff adds a dependency, brings one into a new subsystem, uses one in a materially new way, or changes lifecycle/threading/versioning around one. Deep check against the documented contract: lifecycle order, handle/callback/buffer ownership across the boundary, threading rules, error semantics, units and layout conventions; version constraints and lockfiles consistent with the project’s reproducibility and upgrade policy. Divergence from an established local wrapper pattern needs a reason.
5. **Trust at boundaries**: classify inputs by origin — external user or service content versus validated internal values; identify the actual trust boundary. Hostile data is validated once at entry — with the payload that would slip past as your evidence. For privileged or expensive operations (cloud/account actions, automation endpoints, AI calls): who can trigger this, and where exactly is that enforced? Secrets never in logs, error messages, or persisted artifacts.
6. Flow explicitness when touched: input → domain operation → persisted or visible result stays explicit; trace asynchronous callbacks and external side effects too. No hidden side channels; no ordering assumptions shared only in the author's head.

**Bar for reporting**: name the concrete consequence — which change breaks which consumer, which payload slips past which sink, which name diverges from which standard. "Could be more decoupled" without a consequence is not a finding.

Do not use this layer for:
- whether a subsystem lives in the right module tree (Design & Architecture)
- executing the failure an eroded contract permits (Correctness & Runtime Safety)
- workflow-level state contradictions across features (Port Fidelity & Follow-through)

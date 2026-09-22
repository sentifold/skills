# Platform & Performance

Read [shared review guidance](../review-common.md) first — the shared review method, guiding principles, suppressions, and required output format. Then apply this layer's lens.

Selected when the diff touches the build system, wrappers, or scripts; platform-specific code, paths, processes, or shells; window/process lifecycle; or repeatedly executed hot paths. Use project-provided escape statistics when available; do not invent measured risk weights.

**Stance**: the change was written and tested on one host — you are the other host. Every filesystem, shell, process, and toolchain assumption true on the author's machine may differ on another supported host. Derive that host matrix from the project. A cost repeated per request, item, or frame can dominate a cheap one-shot operation.

**Investigation**:

1. Identify the touched platform surfaces: platform-specific branches; shell or PowerShell/batch counterparts; dependency setup and hooks; path and process handling; platform setup documentation.
2. Replay each touched piece on the other documented hosts: path separators and roots, case sensitivity, symlinks, CRLF, shell quoting, process spawning, environment-variable conventions, file locking. Where the diff changes one side of an existing platform branch, read the other sides in full and verify they are still behaviorally equivalent — one-sided edits are how a branch silently rots.
3. If scripts or setup docs changed, walk the documented flow step by step per platform against the real behavior and confirm they still match.
4. **Process/OS lifecycle** (quit, window close, signals, suspend/resume, or a host ⇄ embedded-runtime boundary touched): the shutdown handshake must be ordered so neither side calls into a torn-down peer; threads joined, GPU idle before device destroy, files and logs flushed — deterministic exit, not `exit()`/OS reclamation. No init-order or destruction-order dependence between statics and singletons.
5. **Multiplied paths**: classify each changed path — per-frame, per-request, per-record, per-resource/IO, per-user-action, one-shot. Nothing multiplied → say so and stop. Otherwise count the per-unit work (allocations, copies, locks, virtual/script dispatches, GPU state changes, file/network round-trips), scale the relevant workload 10×, and ask the structural question: can the ceiling be raised within this design (cache, batch, reserve, restructure the loop), or does raising it require redesign? The second answer is the high-value finding. Memory: bounded over a long session, with resources released when their owning operation or context ends.

**Bar for reporting**: name the host and the concrete step that breaks or diverges on it, or the path, its multiplier, and the load at which it matters. "Might not work on Windows" or "could be faster" without the failing operation or scaling story is not a finding.

Do not use this layer for:
- third-party API contract checks (Contracts & Standards)
- pure logic bugs with no OS, toolchain, or frame dimension (Correctness & Runtime Safety)
- design decomposition (Design & Architecture)

# Correctness & Runtime Safety

Read [shared review guidance](../review-common.md) first — the shared review method, guiding principles, suppressions, and required output format. Then apply this layer's lens.

Always selected — the one lens every run carries. Second-order scope: `/code-review` and `/simplify` own local single-path logic slips; this lens owns the defect classes that *execute* — the ones that survive first-order review because nobody ran the code in their head under hostile conditions.

**Stance**: be the interpreter. Pattern-matching for bug shapes finds only shallow bugs; the escapes live in paths nobody mentally executed — the second shutdown, the interleaved invocation, the write that dies halfway. Run the code under conditions the author didn't consider.

**Investigation** — steps 3–6 apply whenever the diff touches their surface, judged by you, not by the author's framing:

1. Rank the changed code paths by hazard — branching on shared mutable state, resource ownership, threading/async, serialization, persistence, shutdown involvement. Take the top three and execute them mentally, line by line, tracking actual variable and object state. No skimming.
2. Re-run each under adversarial inputs: invalid identifiers, missing resources, empty collections, failed loads, zero/one/many elements, truncated or hand-edited persisted data, an error thrown at each fallible step. Correct behavior, clean failure, or silently wrong result?
3. **Hostile schedules** (anything threaded, async, or callback-driven): two invocations interleaved mid-flight; a worker completing after its owner is destroyed; shutdown arriving between two steps; the same callback firing twice; cancellation mid-operation. Check-then-act sequences are guilty until proven atomic.
4. **Lifecycle transitions** (init/shutdown/re-init/reload/device-loss touched): run the out-of-order set — init twice, shutdown twice, shutdown before init finished, re-init in place (session reload, service reconnect, or device loss). Re-init must replace, not stack: no duplicated registrations, observers, threads, or device objects. Bring-up failing at step N of M must unwind the N−1 started subsystems in reverse — not leak a half-constructed app.
5. **Failure and persistence** (I/O, network, streams, subprocess/VM, long operations touched): for each — never responds; slow forever; dies halfway; process killed between two writes; user cancels mid-flight; retried after a partial failure. Persisted state written atomically (write-tmp + rename); startup tolerates truncated, zero-byte, missing-key files; interrupted artifacts marked incomplete, never read back as valid. What does the user see, what state remains, does it recover without manual repair?
6. **Hostile inputs on execution paths** (loaders, bindings, file access, script surfaces touched): construct the payload — a path with `../`, a document referencing files outside its allowed root, an oversized or recursive JSON document, a script reaching an API it shouldn't — and trace it to its sink.
7. For every resource acquired — device handle, file handle, thread, subscription, foreign-runtime reference — find the release on every path, including the error paths.

**Project hotspots**: use the target project profile and measured escape history when provided. They supplement this execution method; do not transfer one project’s hotspots to another.

**Bar for reporting**: a finding comes with its failing scenario — the concrete input, sequence, or interleaving that produces the wrong behavior. If you cannot construct the scenario, it is not a finding. Demand retry/degradation machinery only where a reachable failure path needs it — never as a checklist.

Do not use this layer for:
- local single-path logic slips a first-order pass already reported — do not repeat them, but report one it missed whatever its severity; when assigned the standalone fallback, or a range no first-order pass read, include local logic defects there too
- module placement or design direction (Design & Architecture)
- contract shape between modules or with third-party APIs (Contracts & Standards)
- completeness across entry points and workflows (Port Fidelity & Follow-through)
- platform parity and multiplied-path costs (Platform & Performance)

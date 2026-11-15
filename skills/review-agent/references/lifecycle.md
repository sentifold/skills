# Bounded review ownership

The agent owning the review remains responsible until it returns a report or
an explicit incomplete result. An async child notification only says its turn
ended; inspect its actual result before marking its assignment complete.

Before dispatch, record a run ledger in working context: repository, scope
IDs/digest, selected lens paths, each child or provider job handle, owner,
start, deadline, last observed state, and result.
Choose an overall budget before launching: honor a user/project budget; absent
one use 30 minutes per chunk (an unchunked scope is one), and give each
provider helper a `--timeout` that leaves part of it for validation, since the
helper's own read-only default, 1800 s, is all of it (observed: chunks of
180–750 changed lines took 385–555 s each at `xhigh`; a light pass over 1,858
changed lines, unchunked, ran about 40 minutes). A
budget limits orchestration work, not arbitrary unrelated machine processes.

State progression is explicit:

```text
planned -> running -> completed-with-result
                   -> failed | timed-out | inaccessible
```

A final answer unrelated to the assigned scope, a plan, or “children are
running” is not completed-with-result. Keep its useful data, but its assignment
is unresolved.

Use native foreground results when available. For async work, wait in bounded
calls of at most 60 seconds (or the runtime's shorter maximum), retaining
cursors/handles and a fixed overall deadline. Spend intervening time collecting
finished results, validating evidence, and communicating meaningful changes.
Do not repeatedly poll unchanged state or use an unbounded shell `until` loop.
Where the runtime blocks a foreground `sleep` and exposes no wait tool
(observed in every pass of one orchestrate run), each bounded call is one
script run that rereads the provider receipt's `status` every five seconds,
waiting with Python's `threading.Event().wait(5)` rather than the shell's
`sleep`, and returns at a terminal status or after 60 seconds.
Run capacity-limited work in waves and release only children owned by this run
when the runtime supports it.

If nested spawn is unavailable, return the planned assignments and collected
results to the parent as `NEEDS_PARENT_FANOUT`. The parent can fan out its own
children or perform the remaining inspection itself, disclosing reduced
independence. Do not claim a missing capability is available because a skill
file or agent template names it.

If a child stops early, inspect its state. Resume once with the precise missing
assignment only when the actual runtime supports messaging/resume. Without that
capability, the parent collects accessible child results and continues the
remaining work. Do not call a nonexistent SendMessage tool, discard completed
legs, or restart an entire run merely to regain topology. A retry after a
transient error is allowed only within the original budget and with a changed,
evidence-based recovery step; record both attempts.

At deadline or unrecoverable failure, collect available results and use
REVIEW INCOMPLETE. Cancel only owned children/jobs through the runtime or
provider helper's ownership-aware cancellation. If cancellation is unavailable,
report the outstanding handles as still running; do not claim they stopped and
do not kill unrelated processes by name. A user may accept partial coverage,
but that acceptance does not retroactively make missing evidence complete.

Before a complete result, verify:

1. Every selected lens has an actual result for the same scope.
2. Both provider legs returned usable final answers; no status marker inside
   model-authored text alone proves the external process finished.
3. Required deterministic checks have current results; accepted missing checks
   remain incomplete coverage. Source changes invalidate affected receipts.
4. Findings survive code verification and reports name limitations honestly.
5. No silently abandoned child owns part of claimed coverage.

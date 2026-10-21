# Shared Linter Guidance

Every linter layer doc references this file. Read it in full before applying any layer lens. It is not a layer itself — it lives outside the layer directory so the review agent does not pick it up as one.

## Your Task

Linter layers target local, low-ambiguity findings — but local does not mean context-free. Before judging:

1. **Build a short system model.** Look at the change scope and read the touched files in full, plus enough of their neighbors to know what is intentional convention versus accident. Answer: what is this change for, and what do the touched files do?
2. **Apply your layer lens** with tools — read code, grep for the duplicate or the stale reference, confirm the dead branch really is dead. Form findings only from what you verified.
3. **Report** using the output format below.

Code is context for future maintainers and coding agents: every merged pattern is what the next agent will copy. A stale comment, a near-duplicate helper, or a speculative fallback is not just noise — it is a template for the next ten changes. That is why this pass exists.

This guidance and the layer docs encode judgment frozen in time. These heuristics do not override governing instructions. When one does not fit the project contract, add a **Skill feedback** note at the end of your report (which rule, why, what it should say instead) so maintainers can fold the correction back into these docs instead of letting them rot silently.

## Suppressions — do not flag these

- Redundancy that aids readability (an extra check that makes intent clearer).
- Requests to explain empirically tuned constants without a concrete comprehension or correctness consequence.
- Consistency-only changes (reformatting untouched code to match new code's style).
- Edge cases that cannot occur given the actual inputs.
- Retuning config values or thresholds that were tuned empirically, unless the value demonstrably breaks a stated contract or limit.
- Anything already addressed elsewhere in the same diff — read the full diff before reporting.
- Issues a compiler, linter, or typechecker would catch — suppressed when the run's deterministic check step ran for this snapshot (its failures are recorded once); report them only when that check was unavailable or not run. Never assume an unrun check passed.
- Compatibility demands unsupported by the target project’s stated contract; do not suppress required migrations.

**"No issues found" is a valid and expected output.** Do not invent cleanup to have something to report.

## Output Format

Plain text with simple markdown structure. Open with a **System Model** section — 2-4 sentences: what the touched code does and what the change is for. Findings built on a wrong model are noise and will not survive adjudication.

Then each finding:

### [Short title]
**Where**: file:lines
**Evidence**: what you read or traced that proves this is real
**Issue**: what is wrong
**Root cause**: only when the local symptom points at something structural; omit otherwise
**Fix**: the concrete local change
**Severity**: low | medium | high | critical

If nothing survives, output the System Model section and "No issues found."

End with a **Skill feedback** section only if you overrode or dispute layer guidance.

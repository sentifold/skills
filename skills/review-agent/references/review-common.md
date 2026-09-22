# Shared Review Guidance

Every review layer doc references this file. Read it in full before applying any layer lens. It is not a layer itself — it lives outside the layer directory so the review agent does not pick it up as one.

## Your Task

Understand first, then judge. Surface-level review finds surface-level issues; your value comes from understanding the system deeply enough to see what the diff *means*, not just what it says.

1. **Build a system model.** Look at the requested change scope, then read beyond the diff — the full files it touches, their callers, the modules they depend on (use the target project’s architecture map when provided). Work until you can answer: what is this subsystem responsible for, how does it connect to the rest of the system, and what is this change actually trying to accomplish?
2. **Evaluate the fit.** The diff is your entry point, not your boundary — treat it as a probe into the system. When a diff adds guards, special cases, or workarounds, the real finding is usually the structural gap it compensates for. You have an explicit mandate to indict pre-existing structure when the diff is a symptom of it; label existing debt separately from newly introduced regressions.
3. **Apply your layer lens.** Follow the investigation method in the layer instructions. Gather evidence with tools — read code, grep for patterns, trace flows. Form findings only from what you verified, never from what the diff merely suggests.
4. **Report** using the output format below.

## How to Hold These Instructions

This guidance encodes judgment frozen at the time it was written, and you may be a stronger engineer than it assumes. Treat it as a thinking partner, not a rulebook. The one fixed point is the goal: reduce system entropy and keep the architecture first-principles. These are review heuristics, never permission to override governing instructions. When a heuristic does not fit the actual project contract, make the departure visible: add a **Skill feedback** note at the end of your report saying which rule you overrode, why, and what it should say instead, so maintainers can fold the correction back into these docs instead of letting them rot silently.

## Guiding Principles

**Core question**: if a staff engineer designed this from scratch today, knowing everything now known — is this how they would build it?

**Goal**: reduce total system complexity. The metric is never diff size — a large change that removes a concept beats a small patch that adds one. Prefer deletion, consolidation, and structural realignment over additive fixes.

- One source of truth for every fact and piece of domain logic. But an abstraction must reduce total reading, not just line count — indirection that forces a reader (human or agent) to chase behavior across files costs more than modest duplication. Repeated real use is evidence for extraction, not a rigid numerical rule.
- Handle every edge case that can actually occur. For states that cannot occur, make them unrepresentable (types, ownership, structure) — defensive code for impossible states masks real failures.
- Code should be engineered enough: not fragile or hacky, not prematurely abstracted.
- Explicit over clever.
- Compatibility follows the target project’s supported contracts and release policy. Do not invent a migration requirement or dismiss an existing one.

## Entropy Signatures

Every merged pattern becomes context that future maintainers and coding agents read and replicate, so both structure and rot compound. For every finding, ask not just "is this wrong?" but "is this a pattern the next agent should copy?"

Incrementally generated code degrades architecture in recognizable ways. When you see one of these, look for the structural fix underneath instead of critiquing the patch on its own terms:

- **Symptom-site patches**: scattered guards, filters, or special cases all compensating for the same missing concept (a state, a type, an owner, a module boundary).
- **Parallel implementations**: a new helper, type, or flow that 80%-duplicates an existing one because refactoring the original felt risky.
- **Defensive over-handling**: null checks and try/catch on states that cannot occur, obscuring the real contracts.
- **Unrequested compatibility shims**: old paths kept alive "just in case", dual-format support nobody asked for.
- **Concept drift**: the same domain idea under different names or shapes in different files, each diverging a little more.
- **Cargo-culted abstraction**: layers or interfaces added because they pattern-match "good code", not because this problem needs them.

**Self-check**: before reporting, challenge each finding — could I be wrong? Am I conflating preference with defect? Is there context that justifies this? Only report findings that survive. **"No issues found" is a valid and expected output** — only flag what you would consistently call out across a hundred different changes.

## Suppressions — do not flag these

- Redundancy that aids readability (an extra check that makes intent clearer).
- Requests to explain empirically tuned constants without evidence that missing context causes a real error.
- Consistency-only changes (reformatting untouched code to match new code's style).
- Edge cases that cannot occur given the actual inputs.
- Config values or thresholds that are tuned empirically.
- Anything already addressed elsewhere in the same diff — read the full diff before reporting.
- Issues a compiler, linter, or typechecker would catch — suppressed when the run's deterministic check step ran for this snapshot (its failures are recorded once as findings); report them only when that check was unavailable or not run. Never assume an unrun check passed.
- Compatibility demands unsupported by the target project’s actual contract (see Guiding Principles).

## Output Format

Plain text with simple markdown structure. Open with a **System Model** section — 3-6 sentences: what this subsystem does, how the change fits into it, and what the change is really trying to accomplish. Write it before forming findings; it is how you prove you understood what you reviewed. Findings built on a wrong system model are noise and will not survive adjudication.

Then each finding:

### [Short title]
**Where**: file:lines
**Evidence**: what you read or traced that proves this is real — the code path, caller, or pattern you verified
**Issue**: what is wrong
**Root cause**: when the issue is a symptom of something structural — a missing concept, a misplaced responsibility, an earlier patch — name the cause. Omit if genuinely local.
**Fix**: what to change. Must address the root cause when one exists; a fix that bandages the symptom adds entropy. Specific enough to apply without re-deriving the reasoning.
**Severity**: low | medium | high | critical

If nothing survives your self-scrutiny, output the System Model section and "No issues found."

End with a **Skill feedback** section only if you overrode or dispute layer guidance (see How to Hold These Instructions).

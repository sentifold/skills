# Readability & Comprehension

Read [shared linter guidance](../linter-common.md) first — the shared linter method, suppressions, and required output format. Then apply this layer's lens.

This layer judges what the changed code is like to understand. The other layers judge what the code does; this one reads it cold, like an engineer (or coding agent) with zero context, and treats every stumble as data.

**Stance**: code is read far more often than it is written, and misunderstanding can propagate through later human or agent edits. Elegant code reads like well-written prose: it has a narrative, it reveals intention, it never astonishes, and a reader encountering it cold can follow the story without a guide.

**Investigation** — do this before forming any finding:

1. **Cold read**: take each changed file top to bottom as a newcomer — no diff context, no commit message. Narrate your understanding as you go: "this module is responsible for X… this function takes Y and produces Z… now it's doing — wait, why is it doing that?"
2. **Log every stumble**, honestly: you had to re-read a block; you had to leave the file (or chase a header) to understand it; you held too many facts in working memory to follow one function; a name promised one thing and the code did another; you reached the bottom unsure what the file is *for*. Each stumble is a candidate finding — locate what caused it.
3. **Check the narrative structure**: does the file read top-down, from intent to detail — public surface and high-level orchestration first, supporting detail below? Does each function stay at one level of abstraction, or does it mix high-level steps with low-level fiddling so the reader keeps changing altitude?
4. **The one-sentence test**: explain each changed file and significant function in one sentence. If the sentence needs an "and", the unit tells two stories. If you can't form the sentence, it has no story.

**What to probe**:

- **Locality of reasoning**: can each unit be understood without leaving it? Code that forces the reader through three other files (or a header maze) to understand one function has exported its complexity to every future reader.
- **Least astonishment**: does everything behave the way its name and signature promise? Hidden side effects, surprising mutation through references or pointers, functions doing more (or less) than they say.
- **Self-explanatory flow**: control flow a reader can follow linearly beats trampolining through indirection; conditions that state their meaning (`isExpired`) beat ones the reader must decode.
- **Working memory budget**: how many variables, flags, and pending conditions must the reader hold at once? Long-lived mutable locals and state machines hidden in booleans blow the budget.
- **Names that lie or drift**: identifiers whose meaning no longer matches behavior after this change, vague names (`data`, `handle`, `process`), or the same concept under different names across language or service surfaces.

**Boundary**: Code Hygiene owns mechanical smells — dead code, duplication, include hygiene, convention violations. Flag those here only when they caused an actual comprehension stumble in your cold read; your evidence is the stumble, not the rule.

**Bar for reporting**: report stumbles a typical engineer would also hit — not personal style preferences — and pair each with the rewrite that removes it (restructure the narrative, rename to match behavior, inline the needless indirection, split the two stories). "This could be cleaner" is not a finding; "I stumbled here, because X, and here is the version that reads straight through" is.

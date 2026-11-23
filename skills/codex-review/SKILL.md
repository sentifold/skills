---
name: codex-review
description: >-
  Review a change with Codex from Claude Code at fixed settings: model
  gpt-6.2-astra, reasoning effort xhigh, read-only sandbox. Use when the user
  asks for a review by Codex ("codex review", "ревью кодексом",
  "/codex-review"), optionally naming the scope: a branch, a PR, a commit or the
  uncommitted changes. A generic review request without Codex goes to
  /code-review instead.
license: MIT
metadata:
  author: Sentifold Inc
  version: "1.0.0"
  repository: https://github.com/sentifold/skills
---

# Codex review

One Codex review of one scope, launched from Claude Code through the sibling
`codex` skill's helper, with settings that are fixed here and never changed by
the caller:

| setting | value |
| --- | --- |
| model | `gpt-6.2-astra` |
| reasoning effort | `xhigh` |
| sandbox | `read-only` |
| mode | `--review` (`codex exec review`) |
| deadline | `--timeout 3600` |

Do not substitute another model or effort, not even after a failure. Read the
`codex` skill's `SKILL.md` and
[runtime-findings](../codex/references/runtime-findings.md) once before the
first run; this skill adds only the fixed settings, the scope and the report.

## 1. Scope

Resolve exactly one scope in the target repository and name it in the prompt:

- **The user named a PR**: `gh pr view <n> --json baseRefName,headRefName,headRefOid`.
  Review `origin/<base>...<headRefOid>` (fetch first). If the head is not the
  current checkout, review it by those refs without checking it out.
- **The user named a commit**: that commit's own diff (`git show <sha>`).
- **The user said "uncommitted"**: staged, unstaged and untracked changes only.
- **Nothing named (default)**: the current branch against its base, plus any
  uncommitted changes. The base is the open PR's base when the branch has one
  (`gh pr view --json baseRefName`), otherwise the remote's default branch
  (`git symbolic-ref --short refs/remotes/origin/HEAD`). Use the merge base:
  `git diff origin/<base>...HEAD`.

An empty scope is not reviewed: tell the user there is nothing to review.

## 2. Launch

```bash
CODEX_SKILL_DIR="/absolute/path/to/loaded/codex"   # sibling of this skill
LOG="$TMPDIR/codex-review-$(date +%s).log"
bash "$CODEX_SKILL_DIR/scripts/codex-ephemeral.sh" \
  --model gpt-6.2-astra --effort xhigh --sandbox read-only --review \
  --timeout 3600 --cd /absolute/repository -- "<prompt>" > "$LOG" 2>&1
```

Run it as ONE `Bash` call with `run_in_background: true`, never with `&`; the
harness notifies you when it exits. Tell the user it is running, what scope it
covers, and that an `xhigh` review usually takes several minutes and can take
up to an hour.

The prompt, in English, filled in for the resolved scope:

```text
Review <scope in words>, which you can see with `<exact git command>`.
Read the repository's AGENTS.md (and CLAUDE.md, if present) first and hold the
change to the rules they state. Look for bugs the change introduces or makes
worse: wrong behaviour, broken contracts with callers, data loss, security
holes, races, missing error handling, and rule violations. Read the
surrounding code before claiming anything; do not report style preferences.
For each finding give: severity (high / medium / low), file:line, what is
wrong, and a concrete input or sequence that shows it fails. Order findings by
severity. If you find nothing, say "No findings" and list what you checked.
Do not modify any file.
```

## 3. Result

When the run exits, read the `CODEX_RUN_EXIT` line in the log, then its
`receipt.json`:

- `status` must be `DONE`, and the receipt's `model` and `reasoning_effort`
  must read `gpt-6.2-astra` and `xhigh`. If either differs, the review did not
  run at the fixed settings: say so and do not present its findings as this
  review.
- A `provider_error` of `Selected model is at capacity` is transient: retry
  once at the same settings with the scope narrowed to the files that matter,
  then report the failure. Any other failure (authentication, model not
  available to this account, timeout) is reported as it is, with the
  receipt's `diagnostic`.

## 4. Report

Codex's findings are a second opinion, not verified facts. For each one, read
the cited code and mark it **confirmed**, **not confirmed** (say why) or
**unclear**. Then give the user:

- the scope reviewed and the commit it was reviewed at;
- the findings, most severe first, each with file:line, Codex's claim and
  your verdict;
- the path of the full Codex answer (the receipt's `output`).

Do not fix anything unless the user asks. A project's own rules (its
`AGENTS.md`) still decide what a fix, a test or a PR comment needs.

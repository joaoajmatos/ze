---
name: "doc-style"
description: "Copyediting rules for Ze's public-facing documentation (root READMEs, VISION.md, CONTRIBUTING.md, SECURITY.md, and docs/*.md). Apply George Orwell's six rules and an ASD-STE100-inspired plain-English discipline whenever drafting or editing these files. Does not apply to specs/, CLAUDE.md, or AGENTS.md."
metadata:
  scope: "docs"
user-invocable: true
disable-model-invocation: false
---

# Ze Documentation Style

Use this whenever drafting, editing, or reviewing prose in:
`README.md`, `VISION.md`, `CONTRIBUTING.md`, `SECURITY.md`, `apps/README.md`,
`core/README.md`, `integrations/README.md`, `packages/README.md`,
`plugins/README.md`, and any file under `docs/`.

**Out of scope:** `specs/` (design specs follow spec-kit conventions, not this
style), `CLAUDE.md`, `AGENTS.md` (agent instructions, not reader-facing prose).

## Orwell's six rules

1. Never use a metaphor, simile, or other figure of speech which you are used
   to seeing in print.
2. Never use a long word where a short one will do.
3. If it is possible to cut a word out, always cut it out.
4. Never use the passive where you can use the active.
5. Never use a foreign phrase, a scientific word, or a jargon word if you can
   think of an everyday English equivalent.
6. Break any of these rules sooner than say anything outright barbarous.

## ASD-STE100 baseline (plain technical English)

1. Short sentences. One main action or statement per sentence.
2. Clear subject, active verb. Name the actor when it matters (e.g. "Ze
   writes the fact," not "the fact is written").
3. Same term for the same thing — do not vary vocabulary just to avoid
   repetition.
4. Familiar words with one precise meaning. Avoid idioms, slang, figurative
   language, and vague verbs ("leverage," "utilize," "facilitate").
5. Use a specific technical term when accuracy requires it. Real technical
   content (LangGraph, asyncpg, WebSocket, Pydantic, …) is not fluff — keep it.
6. Keep noun groups short; use prepositions to show relationships.
7. Write procedures as direct instructions: condition, action, expected
   result.
8. Prefer positive instructions — state what the reader must do.
9. Consistent American English spelling.
10. Never touch code blocks, commands, file paths, identifiers, package
    names, table structure, or YAML/JSON snippets — simplify only the prose
    around them.

## Workflow

1. Read the file before editing.
2. Look for: passive constructions, stock metaphors, needless words, jargon
   with a plain equivalent, inconsistent terminology, bloated noun phrases,
   British spellings (British → American: -ise → -ize, -our → -or, etc.,
   except inside code/config where the source string is authoritative).
3. Make targeted, surgical edits — not a full rewrite. Preserve every
   technical fact, heading structure, table, code fence, and link exactly.
   Do not add or remove documented behavior; do not invent content.
4. `docs/package-readme-template.md` is a template — keep its placeholder
   tokens intact and edit only the instructional prose around them.
5. `VISION.md` uses deliberate extended metaphor (spine/organ/mind) as its
   core rhetorical voice — that is not an incidental cliché under rule 1;
   leave it unless asked to rewrite the document's voice itself.

For large sweeps across many files, split the file list into balanced
batches (by line count) and run them as parallel subagents, each briefed
with this ruleset in full — fresh agents have no memory of this skill.

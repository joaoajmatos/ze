# CF-16 text pass (user decision 2026-10-17)

The user folded a full text pass into CF-16:

- Apply both the `doc-style` skill and the `avoid-ai-writing` skill (edit mode) to every public doc: `README.md`, `VISION.md`, `CONTRIBUTING.md`, `SECURITY.md`, the area READMEs, and `docs/**`.
- Cut bragging and self-praise. The user objected to the old tagline "A personal AI that keeps a model of you, and says how sure it is" because it reads like a boast. Describe what Ze does in plain words. Don't sell it.
- **Rewrite `VISION.md`**, including its voice. The doc-style exemption for VISION's extended metaphor is lifted for this pass. Its opening line "Ze is a model of you." goes. Keep the substance of the direction (world-state, executive function, one mind) and state it plainly.
- Keep public status wording: pre-v1, one user, runs locally / self-hosted. Never write "never deployed".
- The README opening was already rewritten on 2026-10-17 (commit 471c0be4). Match its tone.

## Remove the cleanup and audit arch notes (user decision 2026-10-17)

The user doesn't want the working notes the cleanup added under `specs/arch/` to stay in the repo. As CF-16's final step, after applying every delta, delete them:

- `specs/arch/cleanup-report-2026-10.md`
- `specs/arch/cleanup-cf01-tool-schema.md`, `cleanup-cf02-embeddings.md`, `cleanup-cf04-contacts-watermark.md`, and any other `cleanup-cf*.md`
- `specs/arch/cost-audit-2026-10.md` and any cost-audit design note
- the whole `specs/arch/cleanup-doc-deltas/` folder, this file included

Before deleting, move any fact a reader still needs (a behavior, a config meaning, a migration note) into the owning doc or package README. Remove the links to these files from `specs/README.md`, `AGENTS.md` and the docs.

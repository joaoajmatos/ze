# CF-16 text pass (user decision 2026-10-17)

The user folded a full text pass into CF-16:

- Apply both the `doc-style` skill and the `avoid-ai-writing` skill (edit mode) to every public doc: `README.md`, `VISION.md`, `CONTRIBUTING.md`, `SECURITY.md`, the area READMEs, and `docs/**`.
- Cut bragging and self-praise. The user objected to the old tagline "A personal AI that keeps a model of you, and says how sure it is" because it reads like a boast. Describe what Ze does in plain words. Don't sell it.
- **Rewrite `VISION.md`**, including its voice. The doc-style exemption for VISION's extended metaphor is lifted for this pass. Its opening line "Ze is a model of you." goes. Keep the substance of the direction (world-state, executive function, one mind) and state it plainly.
- Keep public status wording: pre-v1, one user, runs locally / self-hosted. Never write "never deployed".
- The README opening was already rewritten on 2026-10-17 (commit 471c0be4). Match its tone.

# Quickstart: System One Skill Gating

1. Offline recall (no credits): `uv run python eval/calibration/skills.py --recall` — prints gold-skill recall at k = 3..8 per language and floor.
2. Live calibration (costs credits, needs `OPENROUTER_API_KEY`): `make calibrate-skills`.
3. Set the printed values under `system_one.surfaces.skills` in `apps/ze-api/config/config.yaml` and flip `enabled` plus the master `system_one.enabled`.
4. Chat with two similar active skills; open the trace panel. One automatic skill shows. A below-floor apply carries the mark and the `skill` / `needs_skill` judgment rows show `consumed`.
5. Unplug the key: the turn applies skills as before (114).

Tests: `make test-skills`, `make test-core`, `make test`.

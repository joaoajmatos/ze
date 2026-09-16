# Quickstart: Constraint Veto on Gated Writes

1. Add `constraint_gate=True` on a dummy `@tool` in tests (not a mail name).
2. Seed a reviewed `constraint` fact; call the dummy tool with violating args.
3. Assert the tool body never runs and the payload includes `ok: false`, `veto: true`.
4. Mark `send_email` / calendar mutations / reminder writes the same way.
5. Confirm unmarked tools (`remember_fact`) skip the hook.
6. Confirm prospecting send is `send_email`; do not gate `add_prospect`.
7. Companion may say it refused because of a constraint only after `veto` true.

# Quickstart: Retry Rollback

1. `make install && make db-up && make migrate` (applies `zc032`).
2. Unit suites: `make test-agents test-core test-memory test-priority test-worldstate test-automation test-calendar test-personal test-api test-sdk`, then `make test-web typecheck-web`.
3. `make dev-full`. In the web app:
   - "Remind me to stretch in 10 minutes" → hover the reply → Retry → the confirm step lists "set a reminder" with its note → Continue. The reminder list shows the first reminder cancelled; the new reply replaced the old one; its trace shows a Rollback section.
   - "Keep the tax return on my radar" twice in a new thread, then Retry the second reply → Retry unavailable, "cannot be undone cleanly this time" (reinforced loop).
   - "Remember my favourite colour is blue" when red is stored → Retry → Continue → memory shows red again until the new turn writes blue.
4. Evals: `make dev-eval`, `make eval-server`, run tag `retry` (see docs/eval.md).

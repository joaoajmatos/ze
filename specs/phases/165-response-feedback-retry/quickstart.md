# Quickstart: Response Feedback and Retry

1. `make db-up && make migrate` (applies `zm024`, `zc031`).
2. `make dev-full`. Send "What is the capital of Portugal?" Hover the reply: thumbs and Retry appear.
3. Press thumbs down, reload: it stays. Open the trace panel: Feedback section shows the rating.
4. Press Retry: a new reply replaces the old; the old one's trace shows "Retried".
5. Send "Remind me at 5pm to call Ana." Hover the reply: Retry is disabled; the reason says it set a reminder and can be undone separately.
6. Tests: `make test-memory test-core test-api test-agents test-web`; eval: `eval/scenarios/retry_*.yaml`.

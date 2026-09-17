# Quickstart: 159 Concurrent Thread Identity

1. Fail-first: two `trace_update`s, different `thread_id`s; active A does not show B.
2. Fail-first: cancel on A leaves B’s pending confirmation.
3. Keep 4000 test; keep `selectSession` without `reconnect()`.
4. Command/cancel: pass `thread_id`; use `thread_pending_requests`.
5. Mark 99 transport-shipped in README.

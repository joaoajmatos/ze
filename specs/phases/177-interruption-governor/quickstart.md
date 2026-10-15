# Quickstart: validate the Interruption Governor

## Automated

```bash
make test-proactive test-priority test-worldstate test-correlation test-automation \
     test-memory test-calendar test-personal test-finance test-messenger
make test                     # includes apps/ze-api/tests/test_push_inventory.py and test_governor_acceptance.py (SC-001)
make test-web && make typecheck-web && make lint
```

`apps/ze-api/tests/test_governor_acceptance.py` is the acceptance check: one simulated day, quiet hours 23:00–08:00 `Europe/Lisbon`, budget 5, 2 requested + 6 accountability + 9 discretionary pushes, a fake interface that records chat messages and ntfy buzzes, and a fixed clock driven through the release job. It asserts every SC-001 number.

## Manual (dev server)

Prerequisites: `make db-up && make migrate`, then `make dev-full`. Disconnect the web client (close the tab) when checking ntfy buzzes; ntfy only fires while the client is offline.

1. **Settings form.** Open Settings › Notifications. Quiet hours are off; timezone shows your browser zone. Enable with a window that contains the current time (for example now−1 h to now+1 h). Save. The status line says "Quiet hours are on now · 0 held". Reload: values persist. Try start = end: the form shows an error and nothing is saved.
2. **REST.** `curl -H "Authorization: Bearer $ZE_API_KEY" localhost:8000/api/v0/notifications/quiet-hours` returns the saved window with `"active_now": true`.
3. **Hold.** In a Python shell against the dev container (or by waiting for a job), trigger a discretionary push, e.g. run the attention arbitration job, or call `await container.notifier.notify(INSIGHT, title="t", body="b", budget_key="manual:1")`. Expected: no chat message, no ntfy; the bell shows the item labelled "Held for quiet hours"; `held_count` is 1.
4. **Requested breaks through.** Ask Ze in chat: "remind me in 2 minutes to stretch". Close the tab. After 2 minutes ntfy buzzes with "⏰ stretch".
5. **Release.** Change the window so it ended a minute ago and save. Within 5 minutes the held item appears in chat, followed by "While quiet hours were on, I held 1 update." and one ntfy buzz (tab closed). The bell label disappears.
6. **Budget.** Turn quiet hours off. Send six discretionary pushes with different budget keys. Five deliver; the sixth is in the bell labelled "Not pushed: daily limit".
7. **Catch-up.** Stop the server. In `psql`, set `UPDATE proactive_job_runs SET last_started_at = now() - interval '2 days' WHERE job_id = 'morning_briefing';` (use the briefing job id from the logs). Start the server: the log shows `proactive_job_catch_up job_id=… missed_at=…` once, and one briefing is sent (held if inside quiet hours). Restart again immediately: no catch-up.
8. **Overdue calendar reminder.** With a calendar event reminder row in `calendar_reminders` whose `fire_at` is in the past and `sent_at` NULL, restart: it fires once, body ends "(late, was due HH:MM)".

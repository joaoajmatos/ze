# ADR: A Conversation Is a Thread; a Session Is a Burst of Activity

> **Status:** Accepted
> **Date:** 2026-10-22 (architecture review; implemented by phase 207)
> **Scope:** The names `session` and `thread` in tables, REST routes, WS frames, the SDK and the web app.

---

## Context and Problem Statement

"Session" means three things today:

1. **A conversation.** The `sessions` table id is the `thread_id`. There is `/api/v0/sessions`,
   `InvokeResult.session_id` and the Ask "sessions rail".
2. **A burst of activity on one thread.** `fetch_context` logs `session_expired` after an inactivity
   gap, and the resume recap fires "on session resume".
3. **An onboarding session,** plus the "session spend ceiling" from phase 113.

A reader cannot tell whether "the session ended" means the conversation is gone or the user stepped
away.

## Considered Options

1. **Hard-cut the conversation to `thread` everywhere.** "Session" then means only a burst of
   activity.
2. **Keep `session` for the conversation** and rename the burst. But "session" is the weaker word
   for a durable conversation, and `thread_id` is already the key every store uses.

## Decision Outcome

**Option 1, as a pre-v1 hard cut** (`pre-v1-hard-cuts.md`):

- The `sessions` table becomes `threads`, the REST routes become `/api/v0/threads`, the SDK and WS
  fields become `thread_*`, and the web rail becomes the threads rail. There are no aliases.
- **Session** means one burst of activity on a thread, ended by an inactivity gap. Only the resume
  recap, compaction and the spend ceiling use it.
- Onboarding sessions keep their name, because they are their own domain record.

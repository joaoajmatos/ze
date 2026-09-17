# Research: Concurrent Thread Identity

**Feature**: `159-concurrent-thread-identity`  
**Date**: 2026-09-16

## 1. Do not re-implement 99

**Decision:** Treat multiplexed `ConnectionManager`, per-thread `try_set_busy`, ChatNav thinking/attention, and session switch without reconnect as **shipped**. 159 only closes conductor-era globals.

**Rejected:** Rewriting `connection.py` or adding a socket per thread.

## 2. Close 4000 stays

**Decision:** One live WebSocket per user session. Second connect still 4000. That is the single-user live-client rule, not “one conversation.”

**Rejected:** Multiple concurrent tabs as in-scope (would be a different product).

## 3. Trace is the P1 leak

**Decision:** `useTraceSocket` / trace store must key by `thread_id` (ignore or bucket other threads). 154 ConductorSection stays; it reads whatever the store exposes for the active thread.

**Rejected:** Global “latest trace_update wins.”

## 4. Cancel must not use first pending

**Decision:** Command/cancel requires `thread_id` and only aborts that thread’s abort token + pending configs for that thread’s `request_id`s.

**Rejected:** `next(iter(pending_configs))` as the cancel target.

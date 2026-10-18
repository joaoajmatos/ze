---
name: ze-web-verify
description: Verifies a ze-web change in the agent's own Maestri portal, with a screenshot, before it goes to review. Use when finishing or reviewing any change under apps/ze-web, packages/ze-ui or packages/ze-client, or when asked to check that a web page renders.
---

# Verify web changes in your own portal

Not "should render": snapshot it. Run the steps in order.

1. Serve your checkout on your assigned port (the Maestro assigns ports from 5192 up):
   `scripts/process/web_portal.sh <PORT> "<Name> Web"`
   It starts vite from this checkout with `--strictPort`, finds a Node 20+, waits for 200, and prints the portal command.
2. Prove it answers: `scripts/process/web_portal.sh --check <PORT>` must exit 0.
3. Run the printed `maestri portal create ...` command. For phone checks, add a second portal with `--size 390x844`.
4. Backend is the shared test API at `http://127.0.0.1:8010` (DB `ze_e2e_web`). On the setup screen use that Server URL and the `ZE_API_KEY` from `~/coding/ze/apps/ze-api/.env`. Never paste the key into commits, notes or handoffs. If 8010 is down, tell the Maestro. Never start an API on 8000 or touch DB `ze`.
5. For each story: `maestri portal navigate`, `snapshot`, `click`/`fill`, `logs-start` then `logs` (no console errors), `screenshot`.
6. Hand the screenshot to the gate: `make process-ready PORTAL_SHOT=<path to png>`. The receipt records it.
7. Put the screenshot paths and what you checked in your Handoffs note. Reviewers re-check in their own portal.
8. Reply to the Maestro with `portal ok <PORT>` plus the `maestri portal info` line.

Stop the server when done: `scripts/process/web_portal.sh --stop <PORT>`.

# Security Policy

## Scope

Ze is a self-hosted, single-user assistant with access to Gmail, Google Calendar, and arbitrary tool execution. Security issues in the following areas are in scope:

- Authentication bypass (WebSocket or REST)
- Privilege escalation or unauthenticated access to the API
- Prompt injection enabling unintended tool execution
- Escape from the workspace sidecar, or a bypass of the workspace gate or the skill-script approval
- Credential or secret exposure (API keys, OAuth tokens)
- Dependency vulnerabilities with a credible exploit path

Issues with the React web client, deployment configuration, or third-party services (OpenRouter, Fly.io, ntfy) are generally out of scope unless they stem from Ze's own code.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: **joaoajmatos@proton.me**

Include:
- A description of the vulnerability and its impact
- Steps to reproduce (proof of concept if possible)
- The version or commit you tested against

## Responsible disclosure

Please give us reasonable time to address the issue before public disclosure. Once we release a fix, you're welcome to publish a write-up — please coordinate the timing with us.

## Security model

Ze is **single-user by design**. There is no multi-tenant isolation. Before exposing your instance:

1. Generate a strong `ZE_API_KEY` — this is the sole gate for both REST and WebSocket access.
2. Keep `.env` out of version control; use `fly secrets` in production.
3. Know the write-confirmation gate: an irreversible write tool asks you to confirm before it runs, unless the tool explicitly opts out with a stated reason.
4. Use a non-guessable ntfy topic and set an access token.
5. Import only skills you trust. A new skill waits for your review before it affects a conversation. A skill script runs in the workspace only after a second, separate approval.
6. Keep the workspace sidecar off the public network. It runs shell commands. In chat, Ze asks you to confirm a command, and unattended runs (goals, workflows) can use the workspace without a prompt. "Forget this server" clears your browser's local connection settings only — it does not delete data on the server.

Do not deploy Ze as a shared service without substantial hardening.

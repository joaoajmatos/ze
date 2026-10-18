# Quickstart: UI Primitives v2 (191a)

## Automated
- `make test-components`, `make test-agents`, `make test` (ze-api), `make test-web`, `make typecheck-web`, `make lint`.
- `rtk proxy grep -rn "onButtonAction\|\"rest:\|'rest:\|msg:" apps/ze-web/src packages/ze-ui/src core/kernel/ze-components` returns nothing.

## Manual against `make dev-full`
1. Open `/dev/primitives`: every primitive shows in each fixture state, including a fallback table for an unknown type; at 390 nothing overflows.
2. In chat, ask "show my spending this week as stats": the agent draws a stat row (render tool).
3. In the gallery, press a card action wired to a reversible fixture tool: it runs and a notice shows the line.
4. Press an action wired to an irreversible tool: the confirmation appears; deny it: "Okay, I didn't …"; approve it: the tool runs once.
5. A production build (`make web-build`) has no `/dev/primitives` route: `rtk proxy grep -rl "dev-primitives\|fixtures/" apps/ze-web/dist` returns nothing.
6. Open an old conversation with a confirm card from before 191a: the text shows, the card shows with its buttons disabled ("This older button no longer works.").
7. Press an irreversible action, then send a new message before answering: the confirmation is replaced and "Okay, I didn't …" shows; reload the page with a confirmation open: it shows again.

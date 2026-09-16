# Contract: Earned confirmation gate

Identifiers from the spec’s Verbatim Constraints: `remember_fact`, `forget_fact`, `ok`, Principle VIII.

## Function (companion)

`enforce_memory_confirmations(response: str, tool_calls: list[ToolCall]) -> str`

- `earned_remember` iff some call named `remember_fact` has payload `ok` true.
- `earned_forget` iff some call named `forget_fact` has payload `ok` true.
- Payload is the tool `result` mapping, or JSON parsed from a string result. Missing/unparsable `ok` is not earned.

## Rules

1. If not `earned_remember`, the returned text MUST NOT claim the fact is in memory (`I'll remember`, `I will remember`, `remembered that`, `I've stored`, close equivalents, plus `vou lembrar` / `já me lembrei` if implemented).
2. If not `earned_forget`, the returned text MUST NOT claim forgotten (`I forgot`, `I've forgotten`, `forgotten that`, `wiped`, plus `já esqueci` if implemented).
3. Strip claiming sentences. If the remainder is empty or whitespace, use `I could not store that.` (remember claims) or `I could not forget that.` (forget claims). If both classes appear unearned, prefer a combined honest miss rather than a success sentence.
4. `got it` / `okay` without a memory-success claim MUST remain.
5. Mixed sentence that both confirms an earned write and invents another memory: drop that sentence.

## Turn path (no dual door)

- `CompanionAgent.run` MUST apply this function to the `agentic_loop` text before returning `AgentResult`.
- `ctx.token_sink` MUST receive the **gated** text, not the raw model text. Buffer during the loop; flush after the gate.
- `CompanionAgent.stream` MUST NOT complete via tool-free `_client.stream`. Same gated `run` result (yield as one chunk is allowed).
- Adding a prompt paragraph does not satisfy this contract.

## Tests code against

- Unearned remember sentence → fallback or stripped text; no “remember” success claim.
- Earned `ok` true → confirmation may remain.
- `ok` false with `success` true → unearned.
- Sink receives gated text only.

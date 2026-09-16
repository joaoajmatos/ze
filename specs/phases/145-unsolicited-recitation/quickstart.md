# Quickstart: Unsolicited Recitation

1. Inject reviewed facts; user turn is not a recall question.
2. Model outputs “I remember that you like aisle seats.”
3. User-visible reply after `enforce_memory_confirmations` does not contain that recitation.
4. User asks “what do you know about my seating?” — stating the fact is allowed.
5. After `remember_fact` `ok` true, “I’ll remember that” is not stripped as recitation.
6. `token_sink` still sees only gated text.

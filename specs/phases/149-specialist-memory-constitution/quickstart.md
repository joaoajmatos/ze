# Quickstart: Specialist Memory Constitution

1. For calendar, messenger, and news, build a system prompt with retrieved facts.
2. Assert `MEMORY_CONSTITUTION` and job text appear before `## Retrieved biography`.
3. Assert catalogs exclude `remember_fact` / `forget_fact`.
4. Model claims “I’ll remember that” → user-visible reply does not claim remember-tool success.
5. Domain job rules (ISO times, send, news grounding) remain present.

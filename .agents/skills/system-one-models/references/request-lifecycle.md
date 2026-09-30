# Request lifecycle — Reference

The standard workflow for integrating System One model judgments into an application.

## The workflow

```
1. Receive input (user message, record, document, event)
2. Handle deterministic states in code (closed ticket → no_action)
3. Build the state (only what the questions need)
4. Design questions (one narrow judgment per question, ask them together)
5. Call the model (one request, wait for response)
6. Read typed answers (no parsing needed)
7. Compose in code (if/else, weights, thresholds, confidence gates)
8. Act or escalate
```

## Conceptual code structure

```python
def handle(ticket, customer):
    # Step 2: deterministic early return
    if ticket["status"] == "closed":
        return "no_action"

    # Step 3: build state with only relevant context
    state = {
        "ticket": {"message": ticket["message"], "sender": ticket["sender"]},
        "customer": {"plan": customer["plan"], "orders": customer["orders"]},
    }

    # Step 4: define questions (narrow, independent, together)
    questions = {
        "topic": Choice(
            instructions="Which team should handle `ticket.message`?",
            criteria={ "billing": "...", "orders": "...", "account": "..." },
        ),
        "refund_requested": Noul(
            instructions="Does `ticket.message` request a refund?",
        ),
        "frustration": Score(
            instructions="How frustrated is the customer in `ticket.message`?",
            criteria=["Calm", "Frustrated but civil", "Very angry"],
        ),
    }

    # Step 5: one call (provider-specific SDK, exact API varies)
    response = client.system_one(state=state, questions=questions)
    answers = response.answers

    # Step 6-8: compose in code
    if answers["topic"].choice == "billing" and answers["refund_requested"].noul > 0.7:
        return route_to_billing(ticket)

    if answers["topic"].confidence < 0.75:
        return route_to_human_review(ticket)
```

---
name: ze-request-review
description: Sends a commit range to a reviewer and records the request, or records and delivers a review verdict, as files that cannot be lost in chat. Use when an engineer finishes a story and needs it reviewed, or when a reviewer finishes a review.
---

# Request a review, deliver a verdict

Reviews are files in `.process/reviews/`. Chat alone does not count.

**Engineer or lead, after finishing a story:**
1. Commit the story. Run `make process-ready` first so the receipt exists.
2. `make process-review-request RANGE=<a>..<b> REVIEWER="<name>"`
   - The first range starts at the merge base with main. A later range starts where the last APPROVE ended (or where a request in flight ends). After a CHANGES verdict, send the fix as one range from the end of the last APPROVE, so the reviewer approves everything still unapproved.
   - After 60 seconds it checks the reviewer's terminal. A busy reviewer counts as started. If the request is still unsubmitted in the input box it presses Enter once, then prints an ALERT and tells the requester; run the same command again to resend. Do not assume the review started.
3. Keep working. Fix the findings when the verdict arrives.

**Reviewer, when done:** write the findings to a file in your own scratchpad, then
`make process-review-verdict RANGE=<a>..<b> VERDICT=APPROVE|CHANGES FINDINGS=<file>`
A CHANGES verdict needs findings. The command records the verdict, asks the requester and appends to the Handoffs note. The stop hook blocks a reviewer who ends a turn with an undelivered verdict.

Landing needs an APPROVE chain from the merge base to HEAD, so a CHANGES verdict must be followed by a request for the fix range, starting at the end of the last APPROVE.

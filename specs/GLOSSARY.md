# Ze

Ze is a personal assistant for one user. It keeps a world-state: its model of the user and of what is open in their life. Every conversation, job and plugin reads that world-state and proposes changes to it.

## World-state and claims

**World-state**:
Ze's continuous model of the user and their active concerns, in four faces: self, user, bounded world, active concerns. It is the interpretation; memory is the record.
_Avoid_: world model, memory (as a synonym)

**Face**:
One of the four parts of the world-state that a contribution targets.
_Avoid_: section, domain

**Claim**:
One statement Ze holds about the user or their world, with a claim kind, a provenance and a confidence.
_Avoid_: belief (outside the UI), knowledge

**Claim kind**:
The epistemic category of a claim: identity, fact, inference, suspicion or priority. The two record kinds, action record and feedback record, share this vocabulary but are evidence, not claims.
_Avoid_: claim type, fact type

**Fact**:
A grounded, discrete claim that perception observed or the user stated. A newer fact supersedes it, and evidence can contradict it.
_Avoid_: memory, belief, user fact

**Inference**:
A claim Ze derived from other claims. It cites them and falls when they fall.
_Avoid_: insight, synthesized fact

**Suspicion**:
A low-confidence hunch that Ze offers only as a question.
_Avoid_: guess, hypothesis (a hypothesis is one kind of suspicion)

**Identity claim**:
A slow-changing claim about who the user is or how they relate to someone.
_Avoid_: profile fact

**Priority**:
A judgment about what deserves the user's attention now. It orders what Ze shows and never asserts truth.
_Avoid_: importance, urgency, confidence

**Provenance**:
How a claim entered Ze's reasoning: recalled from memory, found by a web search, supplied by the user or the user's own sources (their words, documents, mail and calendar), or synthesized by reflection. A paraphrase of what the user said is still supplied by the user.
_Avoid_: source, inflow, origin

**Inflow**:
The channel that delivered the material a claim came from: conversation, email, calendar or ingestion.
_Avoid_: provenance, source type

**Confidence**:
How sure Ze is that a claim is true.
_Avoid_: score, priority, similarity

**Contribution**:
A function's typed proposal to change the world-state. It carries a claim kind, provenance, confidence, target face and evidence.
_Avoid_: write, update, UI contribution

**Collision**:
Two contributions from different functions that disagree about the same face.
_Avoid_: conflict, contradiction

**Hypothesis**:
A suspicion that correlation forms about a connection across the user's life, with cited evidence.
_Avoid_: insight, correlation, suspected loop

**Signal**:
One item that perception reports from a source, such as an article or an inbound message.
_Avoid_: event, rank input

**Episode**:
Memory's record of one conversational exchange.
_Avoid_: turn, session

## Commitments and active concerns

**Commitment**:
Something the user owes or is waiting on. It is not a record itself: it is held as an open loop, a goal or a reminder, and related records are linked.
_Avoid_: task, concern, to-do

**Open loop**:
One item of unfinished business that Ze tracks: suspected, active, drifting, closed or dropped. While suspected it is a suspicion. Once active it is a priority.
_Avoid_: loop (in code that also has agent runs), concern, task

**Closed**:
The state of an open loop that got done. Evidence that it is done closes a loop even if it was only suspected.
_Avoid_: resolved, completed

**Dropped**:
The state of an open loop the user decided was not real or not wanted. That evidence does not bring it back.
_Avoid_: closed, dismissed

**Suspected loop**:
An open loop that perception proposed and nobody has confirmed.
_Avoid_: draft loop, hypothesis

**Drifting**:
The state of an active loop whose deadline passed without new evidence, or that new evidence contradicts.
_Avoid_: stale, stuck (stuck is for goals)

**Corroboration**:
Independent evidence from a new source that matches an open loop.
_Avoid_: confirmation (the user's act)

**Goal**:
A multi-week outcome the user committed to, which Ze works toward through milestones and gates.
_Avoid_: project, objective

**Milestone**:
One planned stage of a goal.
_Avoid_: step, phase

**Gate**:
A checkpoint in a goal where Ze stops for the user's verdict.
_Avoid_: check, approval

**Reminder**:
A timed alert, either one the user asked for or one Ze sets before a calendar event.
_Avoid_: notification, loop

**Waiting-on**:
An open loop where the user awaits someone else's action, rather than owing one.
_Avoid_: follow-up, pending

## Doing

**Workflow**:
A reusable multi-step automation with branches, run on a schedule or on demand.
_Avoid_: procedure, playbook, pipeline

**Workflow run**:
One execution of a workflow.
_Avoid_: execution, workflow execution

**Workspace run**:
One command run on Ze's isolated computer.
_Avoid_: job, execution

**Procedure**:
A how-to that Ze learned from its own action evidence and that was reviewed before use.
_Avoid_: skill, workflow, routine

**Skill**:
Instructions imported from a SKILL.md file and approved by the user, which narrow an agent's tools for matching requests.
_Avoid_: procedure, plugin, capability

**Action record**:
Ze's append-only record of something it did, citing the domain record it touched.
_Avoid_: log, audit entry, fact

## Asking first, interrupting, undoing

**Confirmation**:
A request for the user's yes or no before Ze proceeds.
_Avoid_: prompt, approval request

**Parked write**:
A write that Ze paused mid-reply until the user confirms it.
_Avoid_: pending write, held write

**Held write**:
A write that an unattended goal or workflow run wanted but was not pre-approved for. It waits up to 24 hours.
_Avoid_: parked write, queued action

**Approval**:
The user's yes to a confirmation, a gate or a held write. Approval given at plan time is pre-approval.
_Avoid_: consent, confirm

**Pending decision**:
Anything waiting on the user's answer: parked and held writes, open gates, suspected loops.
_Avoid_: needs-you item, todo

**Push**:
A message Ze sends unprompted, classed as requested, accountability or discretionary.
_Avoid_: notification, alert, ping

**Notification**:
The stored record of a push, shown in the bell.
_Avoid_: push, message

**Attention budget**:
The daily limit on discretionary pushes, shared by every source.
_Avoid_: push budget, interruption budget

**Quiet hours**:
A daily window when Ze defers pushes the user did not request and then releases them in one summary.
_Avoid_: do-not-disturb

**Retry**:
Regenerating Ze's latest reply.
_Avoid_: redo, regenerate

**Rollback**:
Undoing a reply's reversible actions before a retry.
_Avoid_: revert

**Undo**:
The reversal of one reversible tool call.
_Avoid_: rollback

## Conversation and screen

**Thread**:
One conversation between the user and Ze.
_Avoid_: session, chat

**Session**:
A burst of activity on a thread, ended by a long gap. Ze recaps when the user comes back.
_Avoid_: thread

**Turn**:
One user input and Ze's handling of it, ending in one reply.
_Avoid_: message, exchange, episode

**Trace**:
The explanation of how Ze produced one reply.
_Avoid_: Ze's Mind, log, goal trace

**Screen context**:
What the user is looking at when they speak: place, subject, selection and what is visible.
_Avoid_: page state

**Place**:
One of the five top-level areas of the web app: World, Ask, Doing, Mind, Governance.
_Avoid_: page, route, section

**Module**:
One titled panel in a place, including panels that plugins add to a slot.
_Avoid_: widget, card, component

## People and sources

**Person**:
Someone in the user's life. Each person is exactly one entity in Ze's memory graph.
_Avoid_: contact, user (the user is not a person record)

**Contact**:
A person's address-book record: aliases, relationship and contact channels.
_Avoid_: person, entity

**Entity**:
A node in the memory graph: a person, organisation, topic, project, place or similar.
_Avoid_: object, thing

**Channel**:
A way to reach someone or to receive messages, such as an email account.
_Avoid_: inflow, transport

**Persona**:
The profile and dials that set how Ze sounds.
_Avoid_: personality, self

## Relationships

- A **Commitment** is held as one **Open loop**, **Goal** or **Reminder**. One utterance creates at most one of them and links it to a matching record that already exists.
- A **Suspected loop** becomes active by **Approval** or by **Corroboration**. It becomes **Closed** when evidence says it is done.
- A **Hypothesis** and a **Suspected loop** are both **Suspicions**: one is about a connection, the other about an obligation. Confirming one does not corroborate the other.
- **Contributions** carry **Claims**. Perception contributes **Facts** and **Signals**, Executive contributes **Priorities** and **Suspicions**, and Action contributes **Action records**.
- A **Push** is stored as a **Notification**. Discretionary pushes spend the **Attention budget**, in the user's order.
- A **Turn** produces one reply, one **Trace** and one **Episode**. A **Thread** holds many turns across many **Sessions**.
- A **Rollback** is made of **Undos** and comes before a **Retry**.
- A **Pending decision** is a **Parked write**, a **Held write**, an open **Gate** or a **Suspected loop**. Approving a parked write also clears a held write for the same action.
- A **Person** is one memory-graph **Entity**, and has at most one **Contact**.

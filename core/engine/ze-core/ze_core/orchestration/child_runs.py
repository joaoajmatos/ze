"""Inputs to a child run and the merge of what it hands back (phase 200).

`execute_tool` builds each child context with `ze_agents.derive.for_subtask`. The values
that call needs come from here: the live handles in `config`, the write-gate inputs, and
the conductor and procedure state that `AgentState` carries between graph steps. After the
children finish, `merge_outcomes` writes their outcomes back to `AgentState` once, so state
is the only copy of conductor and procedure state between steps.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from langchain_core.runnables import RunnableConfig

from ze_agents.derive import ChildRunOutcome, RuntimeHandles
from ze_agents.types import (
    ConductorState,
    DelegateTally,
    ProcedureInvocation,
    WriteGateState,
)


def runtime_handles(config: RunnableConfig, *, stream: bool) -> RuntimeHandles:
    """The live objects a child carries. Only a streaming run gets the token sink."""
    configurable = config["configurable"]
    embedder = configurable.get("embedder")
    return RuntimeHandles(
        reporter=configurable.get("reporter"),
        identity_builder=configurable.get("identity_builder"),
        abort_token=configurable.get("abort_token"),
        embed_fn=embedder.encode_query if embedder is not None else None,
        token_sink=configurable.get("token_sink") if stream else None,
        tool_sink=configurable.get("tool_sink"),
        script_runner=configurable.get("script_runner"),
    )


def _pre_approved(
    turn_gate: WriteGateState, config: RunnableConfig, state: dict
) -> frozenset[str]:
    extra = config["configurable"].get("pre_approved_writes") or ()
    step = state.get("pre_approved_writes") or ()
    return frozenset(turn_gate.pre_approved) | frozenset(extra) | frozenset(step)


def gate_input(
    turn: Any, state: dict, config: RunnableConfig, index: int
) -> WriteGateState:
    """The write-gate part for subtask `index`, re-entering its parked loop if it parked."""
    parked = {ps.index: ps for ps in state.get("parked_subtasks") or []}
    decisions = {d.item_id: d for d in state.get("write_decisions") or []}
    confirmation = state.get("write_confirmation")
    gate = WriteGateState(
        retry_mode=turn.write_gate.retry_mode,
        pre_approved=_pre_approved(turn.write_gate, config, state),
        round=int(state.get("write_rounds") or 0),
    )
    if index in parked and decisions:
        gate.resume = parked[index].loop
        gate.decisions = decisions
        gate.approval_request_id = (
            confirmation.request_id if confirmation is not None else None
        )
    return gate


def tally_from(state: dict) -> DelegateTally:
    """The turn's delegate tally, one object shared by every subtask of a pass."""
    return DelegateTally(
        counts=dict(state.get("conductor_delegate_counts") or {}),
        total=int(state.get("conductor_delegate_total") or 0),
    )


def _ledger_slot(state: dict, index: int) -> list[dict[str, str]]:
    ledgers = state.get("conductor_ledgers") or []
    return [dict(entry) for entry in ledgers[index]] if index < len(ledgers) else []


def conductor_input(state: dict, index: int, tally: DelegateTally) -> ConductorState:
    """Subtask `index`'s conductor state. A missing ledger slot reads as empty."""
    return ConductorState(
        hint=state.get("conductor_hint"),
        ledger=_ledger_slot(state, index),
        tally=tally,
    )


def procedure_input(state: dict, index: int) -> ProcedureInvocation | None:
    """The invocation subtask `index` started before a pause, if any."""
    for invocation in state.get("procedure_invocations") or []:
        if invocation.subtask == index:
            return replace(invocation, tool_names=list(invocation.tool_names))
    return None


def merge_outcomes(
    state: dict, outcomes: list[ChildRunOutcome], tally: DelegateTally
) -> dict[str, Any]:
    """The state updates for the conductor and procedure parts after one execution pass.

    Ledger slots of subtasks that did not run this pass keep their value; slots below the
    highest finished index that nothing wrote are padded with `[]`.
    """
    ledgers = [list(ledger) for ledger in state.get("conductor_ledgers") or []]
    finished = {o.index for o in outcomes}
    top = max(finished, default=-1)
    while len(ledgers) <= top:
        ledgers.append([])
    for outcome in outcomes:
        ledgers[outcome.index] = list(outcome.conductor.ledger)

    kept = [
        inv
        for inv in state.get("procedure_invocations") or []
        if inv.subtask not in finished
    ]
    invoked = [o.procedure for o in outcomes if o.procedure is not None]
    procedures = sorted(kept + invoked, key=lambda inv: inv.subtask)

    return {
        "conductor_ledgers": ledgers,
        "conductor_delegate_counts": dict(tally.counts),
        "conductor_delegate_total": tally.total,
        "procedure_invocations": procedures,
    }


def turn_ledger(state: dict) -> list[dict[str, str]]:
    """Every subtask's ledger, flattened in subtask order."""
    return [
        dict(entry)
        for ledger in state.get("conductor_ledgers") or []
        for entry in ledger
    ]

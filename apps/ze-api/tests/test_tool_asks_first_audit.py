"""The irreversible-tool audit table is what the registry holds (Phase 181, FR-003)."""

from __future__ import annotations


from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, registered_tools

from tests.test_tool_reversibility import _load_all_tool_modules

_ASK = {
    "send_email",
    "archive_email",
    "create_event",
    "update_event",
    "delete_event",
    "cancel_reminder",
    "forget_fact",
    "set_contact_channel",
    "abandon_goal",
    "update_workflow",
    "edit_workflow_steps",
    "delete_workflow",
}
_OPT_OUT = {
    "draft_email": "Creates a draft in the user's mailbox; nothing is sent.",
    "confirm_project_membership": "Records the user's own confirmation of an inferred claim; a later statement corrects it.",
    "steer_goal": "Queues the user's own instruction for the goal; the next milestone reads it.",
    "trigger_workflow": "Starts a run now; the run's own asks-first steps are gated by plan pre-approval.",
    "cancel_workflow_run": "Stops a run the user asked to stop; the workflow itself is kept.",
    "close_loop": "Bookkeeping the user asked for; `track_loop` re-opens the concern.",
    "drop_loop": "Bookkeeping the user asked for; `track_loop` re-opens the concern.",
    "reprioritize_item": "A decaying override; the user can reorder again.",
    "confirm_recurring": "The user's own classification of an expense.",
    "dismiss_recurring": "The user's own classification of an expense.",
    "ingest_url": "Saves content the user asked to save; nothing leaves Ze.",
    "ingest_text": "Saves content the user asked to save; nothing leaves Ze.",
    "add_prospect": "An internal campaign record.",
    "draft_outreach": "A draft; nothing is sent.",
    "log_outreach_event": "An internal campaign record.",
    "ingest_workspace_file": "Saves a workspace file the user asked to save; nothing leaves Ze.",
}
_WORKSPACE_CHECK = {
    "workspace_write",
    "workspace_delete",
    "workspace_run",
    "workspace_run_skill_script",
    "workspace_reset",
}
_REVERSIBLE_PAIR = {"pause_goal": "resume_goal", "resume_goal": "pause_goal"}


def _writes() -> dict:
    _load_all_tool_modules()
    return {
        name: spec
        for name, spec in registered_tools().items()
        if spec.access is ToolAccess.WRITE
    }


def test_the_asks_first_set_is_exactly_the_ask_rows() -> None:
    asking = {n for n, s in _writes().items() if s.asks_first is True}
    expected = _ASK
    unexpected = sorted(asking - expected)
    missing = sorted(expected - asking)
    assert (unexpected, missing) == ([], []), (
        "A tool's asks_first changed. Edit the audit table in "
        "specs/phases/181-irreversible-write-confirmation/spec.md and this test."
    )


def test_opt_outs_carry_the_table_reason() -> None:
    writes = _writes()
    for name, reason in _OPT_OUT.items():
        spec = writes[name]
        assert spec.asks_first is False, name
        assert spec.no_ask_reason == reason, name


def test_goal_pause_and_resume_are_each_others_undo() -> None:
    writes = _writes()
    for name, undo in _REVERSIBLE_PAIR.items():
        spec = writes[name]
        assert spec.reversibility is ToolReversibility.REVERSIBLE, name
        assert spec.undo_tool == undo, name
        assert spec.asks_first is None


def test_send_email_body_is_editable() -> None:
    assert _writes()["send_email"].editable_field == "body"


def test_workspace_tools_decide_with_a_pre_call_check() -> None:
    writes = _writes()
    for name in _WORKSPACE_CHECK:
        assert writes[name].ask_check is not None, name


def test_every_irreversible_tool_is_in_the_table() -> None:
    table = _ASK | set(_OPT_OUT) | _WORKSPACE_CHECK
    unknown = sorted(
        name
        for name, spec in _writes().items()
        if spec.reversibility is ToolReversibility.IRREVERSIBLE and name not in table
    )
    assert unknown == [], (
        f"New IRREVERSIBLE tool(s) {unknown}: they ask first by default. Add them "
        "to the audit table in spec.md (and here) or declare asks_first=False with "
        "a no_ask_reason."
    )

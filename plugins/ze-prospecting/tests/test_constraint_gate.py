from ze_agents.tool import get_tool
from ze_prospecting.agents.agent import ProspectingAgent
import ze_messenger.agents.messenger.tools  # noqa: F401
import ze_prospecting.agents.tools  # noqa: F401


def test_add_prospect_is_not_constraint_gated():
    assert get_tool("add_prospect").constraint_gate is False


def test_prospecting_outbound_send_is_shared_send_email_gate():
    assert "send_email" not in ProspectingAgent.tools
    assert get_tool("send_email").constraint_gate is True

import pytest

from ze_agents.interrupt import workspace_confirmed


@pytest.fixture
def goal_writes_confirmed():
    """Run a goal write tool as if the user already approved its confirmation."""
    token = workspace_confirmed.set(True)
    yield
    workspace_confirmed.reset(token)

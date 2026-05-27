from __future__ import annotations

import pytest
import yaml

from ze.agents.testing import make_gate


@pytest.fixture
def config_file(tmp_path):
    """Write a standard config.yaml and return agent config dict."""
    agents = {
        "research": {
            "enabled": True,
            "capabilities": {
                "read": "autonomous",
                "reason": "confirm",
            },
        },
        "companion": {
            "enabled": True,
            "capabilities": {
                "reason": "autonomous",
                "create": "draft_only",
            },
        },
        "calendar": {
            "enabled": False,
            "capabilities": {
                "read": "autonomous",
                "create": "confirm",
            },
        },
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump({"agents": agents}))
    return agents

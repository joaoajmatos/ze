from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from ze_api.api.ws.commands import handle_command
from ze_api.api.ws.connection import ConnectionManager
from ze_api.api.ws.schemas import WsCommandFrame


@pytest.mark.parametrize("name", ["reset", "reset_preview"])
def test_reset_command_names_fail_schema_validation(name):
    with pytest.raises(ValidationError):
        WsCommandFrame(type="command", name=name)


@pytest.mark.parametrize("name", ["reset", "reset_preview"])
async def test_reset_command_sends_no_frame_and_logs_unknown(name):
    mgr = AsyncMock(spec=ConnectionManager)
    container = AsyncMock()

    with pytest.MonkeyPatch.context() as mp:
        warnings: list[tuple] = []
        from ze_api.api.ws import commands

        mp.setattr(
            commands.log,
            "warning",
            lambda event, **kw: warnings.append((event, kw)),
        )
        await handle_command(
            AsyncMock(), {"type": "command", "name": name}, container, mgr, {}, {}
        )

    mgr.send_frame.assert_not_called()
    assert warnings == [("ws_unknown_command", {"name": name})]

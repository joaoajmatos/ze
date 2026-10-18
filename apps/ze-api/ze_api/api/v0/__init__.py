from fastapi import APIRouter

from ze_api.api.v0.costs.router import router as costs_router
from ze_api.api.v0.data.router import router as data_router
from ze_api.api.v0.goals.router import router as goals_router
from ze_api.api.v0.held_writes.router import router as held_writes_router
from ze_api.api.v0.hypotheses.router import router as hypotheses_router
from ze_api.api.v0.loops.router import router as loops_router
from ze_api.api.v0.memory.router import router as memory_router
from ze_api.api.v0.messages.router import router as messages_router
from ze_api.api.v0.notifications.router import router as notifications_router
from ze_api.api.v0.priority.router import router as priority_router
from ze_api.api.v0.proactive.router import router as proactive_router
from ze_api.api.v0.procedures.router import router as procedures_router
from ze_api.api.v0.sessions.router import router as sessions_router
from ze_api.api.v0.skills.router import router as skills_router
from ze_api.api.v0.system.router import router as system_router
from ze_api.api.v0.system.ui import ui_router
from ze_api.api.v0.voice.router import router as voice_router
from ze_api.api.v0.webhooks.router import router as webhooks_router
from ze_api.api.v0.workflows.router import router as workflows_router
from ze_api.api.v0.workspace.router import router as workspace_router

API_V0_PREFIX = "/api/v0"

router = APIRouter(prefix=API_V0_PREFIX)
for _domain_router in (
    system_router,
    memory_router,
    workflows_router,
    costs_router,
    goals_router,
    held_writes_router,
    hypotheses_router,
    sessions_router,
    messages_router,
    data_router,
    notifications_router,
    loops_router,
    priority_router,
    proactive_router,
    procedures_router,
    skills_router,
    workspace_router,
    ui_router,
    voice_router,
    webhooks_router,
):
    router.include_router(_domain_router)

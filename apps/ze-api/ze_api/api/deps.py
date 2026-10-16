from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ze_core.conversation.messages import PostgresMessageStore as MessageStore
from ze_api.settings import Settings, get_settings as _get_settings


_bearer = HTTPBearer(auto_error=False)


async def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    expected: str = request.app.state.settings.ze_api_key
    token = credentials.credentials if credentials else ""
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )


def get_settings() -> Settings:
    return _get_settings()


def get_container(request: Request):
    return request.app.state.container


def get_workflow_store(request: Request):
    return request.app.state.container.workflow_store


def get_held_write_store(request: Request):
    return request.app.state.container.held_write_store


def get_held_write_resumer(request: Request):
    return request.app.state.container.held_write_resumer


def get_message_store(request: Request) -> MessageStore:
    return request.app.state.container.message_store


def get_feedback_store(request: Request):
    return request.app.state.container.feedback_store


def get_turn_lock(request: Request):
    return request.app.state.container.turn_lock


def get_confirmation_store(request: Request):
    return request.app.state.container.confirmation_store


def get_connection_manager(request: Request):
    return request.app.state.container.connection_manager


def get_notification_store(request: Request):
    return request.app.state.container.notification_store


def get_interruption_settings_store(request: Request):
    return request.app.state.container.interruption_settings_store


def get_notifier(request: Request):
    return request.app.state.container.notifier


def get_loop_store(request: Request):
    return request.app.state.container.loop_store


def get_skill_store(request: Request):
    return request.app.state.container.skill_store


def get_procedure_admission(request: Request):
    return request.app.state.container.procedure_admission


def get_collision_store(request: Request):
    return request.app.state.container.collision_store


def get_priority_view(request: Request):
    return request.app.state.container.priority_view


def get_priority_override_store(request: Request):
    return request.app.state.container.priority_override_store


def get_nli_client(request: Request):
    return request.app.state.container.nli_client


def get_workspace_store(request: Request):
    return request.app.state.container.workspace_store


def get_workspace_client(request: Request):
    return request.app.state.container.workspace_client


def get_workspace_run_watcher(request: Request):
    return request.app.state.container.workspace_run_watcher

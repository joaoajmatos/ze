import pytest
from pydantic import TypeAdapter, ValidationError

from ze.api.schemas import (
    CapabilityModeUpdate,
    ConfirmationExpiredMessage,
    ConfirmationRequest,
    ConfirmMessage,
    DoneMessage,
    ErrorMessage,
    FactReviewRequest,
    TokenMessage,
    UserMessage,
    WsClientMessage,
)
from ze.logging import configure_logging


@pytest.fixture(autouse=True)
def setup_logging():
    configure_logging()


_adapter = TypeAdapter(WsClientMessage)


# ── WsClientMessage discriminator ────────────────────────────────────────────

def test_parse_user_message():
    msg = _adapter.validate_python({"type": "message", "content": "hello"})
    assert isinstance(msg, UserMessage)
    assert msg.content == "hello"


def test_parse_confirm_yes():
    msg = _adapter.validate_python({"type": "confirm", "decision": "yes"})
    assert isinstance(msg, ConfirmMessage)
    assert msg.decision == "yes"
    assert msg.edit_content is None


def test_parse_confirm_edit_with_content():
    msg = _adapter.validate_python({
        "type": "confirm",
        "decision": "edit",
        "edit_content": "revised text",
    })
    assert isinstance(msg, ConfirmMessage)
    assert msg.edit_content == "revised text"


def test_parse_unknown_type_raises():
    with pytest.raises(ValidationError):
        _adapter.validate_python({"type": "unknown", "content": "x"})


# ── Server messages ───────────────────────────────────────────────────────────

def test_token_message_json():
    msg = TokenMessage(content="hello")
    data = msg.model_dump()
    assert data["type"] == "token"
    assert data["content"] == "hello"


def test_done_message_json():
    msg = DoneMessage(agent="research", routing_method="embedding", confidence=0.9)
    data = msg.model_dump()
    assert data["type"] == "done"
    assert data["confidence"] == pytest.approx(0.9)


def test_done_message_null_confidence():
    msg = DoneMessage(agent="research", routing_method="haiku", confidence=None)
    assert msg.confidence is None


def test_confirmation_request_json():
    msg = ConfirmationRequest(draft="send email", agent="email", action="create")
    data = msg.model_dump()
    assert data["type"] == "confirmation_request"


def test_error_message_json():
    msg = ErrorMessage(message="something went wrong")
    assert msg.model_dump()["type"] == "error"


def test_confirmation_expired_json():
    msg = ConfirmationExpiredMessage()
    assert msg.model_dump()["type"] == "confirmation_expired"


# ── REST schemas ──────────────────────────────────────────────────────────────

def test_capability_mode_update_valid():
    m = CapabilityModeUpdate(mode="autonomous")
    assert m.mode == "autonomous"


def test_capability_mode_update_invalid():
    with pytest.raises(ValidationError):
        CapabilityModeUpdate(mode="full_send")


def test_fact_review_request_confirm():
    import uuid
    req = FactReviewRequest(actions=[{
        "id": str(uuid.uuid4()),
        "action": "confirm",
    }])
    assert req.actions[0].action == "confirm"


def test_fact_review_request_invalid_action():
    import uuid
    with pytest.raises(ValidationError):
        FactReviewRequest(actions=[{
            "id": str(uuid.uuid4()),
            "action": "maybe",
        }])

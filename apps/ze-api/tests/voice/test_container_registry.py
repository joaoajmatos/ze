from ze_api.voice.registry import TranscriptionRegistry
from ze_api.wiring.container import ZeContainer


def test_container_exposes_transcription_registry():
    field = ZeContainer.__dataclass_fields__["transcription_registry"]
    assert isinstance(field.default_factory(), TranscriptionRegistry)

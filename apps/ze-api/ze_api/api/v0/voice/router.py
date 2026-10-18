from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ze_agents.defaults import MODEL_WHISPER
from ze_agents.errors import (
    AudioToolMissingError,
    AudioTooLongError,
    AudioUnreadableError,
    TranscriptionFailedError,
)
from ze_api.api.deps import get_container, require_api_key
from ze_api.api.v0.voice.limits import MAX_RECORDING_BYTES, TOO_LARGE_DETAIL
from ze_api.api.v0.voice.schemas import TranscriptionResponse
from ze_core.voice import transcribe_audio
from ze_logging import get_logger

log = get_logger(__name__)

router = APIRouter(
    prefix="/voice", tags=["voice"], dependencies=[Depends(require_api_key)]
)

_ACCEPTED_TYPES = frozenset(
    {
        "audio/webm",
        "audio/ogg",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/wav",
        "audio/x-wav",
    }
)
_READ_CHUNK = 1024 * 1024
_UNREADABLE = "I couldn't make out the recording."


async def _read_capped(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_READ_CHUNK):
        total += len(chunk)
        if total > MAX_RECORDING_BYTES:
            raise HTTPException(status_code=413, detail=TOO_LARGE_DETAIL)
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/transcriptions",
    response_model=TranscriptionResponse,
    operation_id="transcribeVoice",
    summary="Transcribe a voice recording",
    description=(
        "Upload a recording (WebM, Ogg, MP4 or WAV, up to 10 MB and 2 minutes). "
        "Returns the transcript, the measured duration and a reference the next "
        "message can cite to be marked as a voice turn. No audio is kept."
    ),
)
async def transcribe_voice(
    file: UploadFile | None = File(None),
    container=Depends(get_container),
) -> TranscriptionResponse:
    if file is None:
        raise HTTPException(
            status_code=422, detail="Send the recording as a file named file."
        )
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in _ACCEPTED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported recording type. Use WebM, Ogg, MP4 or WAV.",
        )
    data = await _read_capped(file)

    config = getattr(container.settings, "config", {}) or {}
    model = config.get("models", {}).get("whisper", MODEL_WHISPER)
    try:
        result = await transcribe_audio(
            container.openrouter_client, data, file.content_type, model=model
        )
    except AudioTooLongError:
        raise HTTPException(
            status_code=413,
            detail="That recording is too long: the limit is 2 minutes.",
        )
    except AudioUnreadableError:
        raise HTTPException(status_code=422, detail=_UNREADABLE)
    except TranscriptionFailedError:
        raise HTTPException(status_code=502, detail=_UNREADABLE)
    except AudioToolMissingError:
        log.error("voice_ffmpeg_missing")
        raise HTTPException(
            status_code=503, detail="Voice input is not available on this server."
        )

    transcription_id = container.transcription_registry.register(
        result.text, result.duration_s
    )
    return TranscriptionResponse(
        transcript=result.text,
        duration_s=result.duration_s,
        transcription_id=transcription_id,
    )

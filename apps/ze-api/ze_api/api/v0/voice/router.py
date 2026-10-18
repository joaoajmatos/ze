from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ze_api.api.deps import require_api_key
from ze_api.api.v0.voice.schemas import TranscriptionResponse

router = APIRouter(
    prefix="/voice", tags=["voice"], dependencies=[Depends(require_api_key)]
)


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
async def transcribe_voice(file: UploadFile = File(...)) -> TranscriptionResponse:
    raise HTTPException(status_code=501, detail="Voice input is not available yet.")

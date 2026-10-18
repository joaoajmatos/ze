from pydantic import BaseModel


class TranscriptionResponse(BaseModel):
    transcript: str
    duration_s: float
    transcription_id: str

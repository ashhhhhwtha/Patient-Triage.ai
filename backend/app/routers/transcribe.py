import os, requests
from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter(tags=["voice"])
GROQ_KEY = os.getenv("GROQ_API_KEY")

@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    if not GROQ_KEY:
        raise HTTPException(503, "GROQ_API_KEY not set on the server")
    r = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        files={"file": (audio.filename or "audio.webm", await audio.read(),
                        audio.content_type or "audio/webm")},
        data={"model": "whisper-large-v3"},
        timeout=60,
    )
    if r.status_code != 200:
        raise HTTPException(502, f"Transcription failed: {r.text[:200]}")
    return {"text": r.json().get("text", "")}
"""Voice + language AI endpoints — PROVIDER-AGNOSTIC.
Uses Groq (Llama 3.3 + Whisper) if GROQ_API_KEY is set, otherwise Google Gemini
if GEMINI_API_KEY is set. Same endpoints either way; the frontend never knows.
DESIGN RULE: the LLM handles language only. It NEVER decides severity and NEVER
invents clinical content (doses, timings, medicines)."""
import os, json, requests
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["voice-ai"])
GROQ_KEY = os.getenv("GROQ_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GROQ_BASE = "https://api.groq.com/openai/v1"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def _llm(prompt: str) -> str:
    """One text-in, text-out call. Tries Groq first, then Gemini."""
    if GROQ_KEY:
        r = requests.post(
            f"{GROQ_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}"},
            json={"model": "llama-3.3-70b-versatile", "temperature": 0,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        if not GEMINI_KEY:  # no fallback available -> surface the Groq error
            raise HTTPException(502, f"Groq failed: {r.text[:200]}")
    if GEMINI_KEY:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            params={"key": GEMINI_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0}},
            timeout=30,
        )
        if r.status_code != 200:
            raise HTTPException(502, f"Gemini failed: {r.text[:200]}")
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    raise HTTPException(503, "No LLM key set (GROQ_API_KEY or GEMINI_API_KEY)")


def _llm_json(prompt: str) -> dict:
    raw = _llm(prompt).replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except Exception:
        raise HTTPException(502, "LLM returned non-JSON")


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """HD voice needs Whisper (Groq only). Without a working Groq key the frontend
    silently falls back to the browser mic — by design."""
    if not GROQ_KEY:
        raise HTTPException(503, "HD voice needs GROQ_API_KEY; browser mic still works")
    r = requests.post(
        f"{GROQ_BASE}/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        files={"file": (audio.filename or "audio.webm", await audio.read(),
                        audio.content_type or "audio/webm")},
        data={"model": "whisper-large-v3"},
        timeout=60,
    )
    if r.status_code != 200:
        raise HTTPException(502, f"Transcription failed: {r.text[:200]}")
    return {"text": r.json().get("text", "")}


class ExtractIn(BaseModel):
    text: str

from app.triage.nlp_local import extract_fields as _local_extract

@router.post("/extract")
async def extract(body: ExtractIn):
    """Intake understanding — LOCAL NLP, no API key needed, runs offline.
    Synonym lexicon normalizes figurative language ("elephants on my chest")
    into the engine's controlled vocabulary; relationship-aware name extraction;
    word-number age parsing. Deterministic and auditable."""
    return _local_extract(body.text)


class RxIn(BaseModel):
    text: str

@router.post("/rx/check")
async def rx_clarity_check(body: RxIn):
    data = _llm_json(
        "You are reviewing a DRAFT medical prescription for CLARITY ONLY.\n"
        "List information a patient would need that is missing or ambiguous, such as: "
        "when to take each medicine (morning/night/frequency), for how many days, "
        "with or without food, quantity per dose, and any unclear abbreviations.\n"
        "STRICT RULES: Do NOT suggest, guess or invent any medicine, dose, timing or duration. "
        "Only name what is missing or unclear.\n"
        'Return ONLY JSON, no markdown: {"clear": true/false, '
        '"gaps": ["short description of each missing/unclear item"], '
        '"note": "one-line overall summary"}\n'
        f"Draft prescription:\n{body.text}"
    )
    return {"clear": bool(data.get("clear")), "gaps": data.get("gaps") or [],
            "note": data.get("note") or ""}

@router.post("/rx/explain")
async def rx_explain(body: RxIn):
    text = _llm(
        "Explain this signed prescription to a patient in very simple, kind language.\n"
        "STRICT RULES: Use ONLY information written in the prescription. Do NOT add any dose, "
        "timing, duration or advice that is not written. If something a patient needs is not "
        "written, say exactly: 'ask your care team about ...'. Keep it short: what each item is "
        "for (only if stated), and how to take it (only as written). Plain text, no markdown.\n"
        "End with exactly this line: "
        "'This is a simpler explanation only — always follow your doctor's original prescription.'\n"
        f"Prescription:\n{body.text}"
    )
    return {"explanation": text.strip()}

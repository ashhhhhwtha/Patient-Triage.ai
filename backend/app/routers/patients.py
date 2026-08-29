"""Phase 4: endpoints are async and broadcast over WebSocket after every change.
Adds POST /patients/demo/surge — injects ~3x volume for the surge demo.
Adds GET /patients/{id}/history — previous-visit digest for the clinician:
deterministic summarizer as the floor (runs offline), optional LLM simplification
on top when a key exists. The summary NEVER decides severity — it surfaces
history for clinical correlation, nothing more."""
import random
import re
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Patient, VitalsReading, TriageResult, Override, Prescription
from app.schemas import PatientIn, VitalsIn
from app.auth import require_role, get_current_user
from app.audit import audit
from app.triage.engine import run_triage
from app.ws import manager

router = APIRouter(prefix="/patients", tags=["patients"])

@router.get("/lookup")
def lookup_patient(name: str, age: int | None = None,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Returning-patient recognition: search PREVIOUS (completed) visits by name
    (+/- 2 years on age when given). Links the new check-in to prior history, which
    raises triage confidence. DEMO ONLY by name — production links via MRN/ABHA
    number through the hospital EHR, never name-matching (names misidentify)."""
    term = (name or "").strip()
    if len(term) < 3:
        return {"found": False, "records": []}
    q = (db.query(Patient)
           .filter(Patient.status == "completed")
           .filter(Patient.name.ilike(f"%{term}%"))
           .order_by(Patient.arrived_at.desc()))
    matches = q.all()
    if age is not None:
        matches = [m for m in matches if abs(m.age - age) <= 2]
    records = []
    for m in matches[:5]:
        t = (db.query(TriageResult).filter_by(patient_id=m.id)
               .order_by(TriageResult.created_at.desc()).first())
        records.append({
            "id": m.id, "name": m.name, "age": m.age, "gender": m.gender,
            "last_visit": str(m.arrived_at), "concern": m.concern,
            "category": t.category if t else None,
            "specialty": t.specialty if t else None,
        })
    return {"found": len(records) > 0, "records": records}

# ---------------------------------------------------------------------------
# Previous-visit history digest (shown on the Doctor Console)
# ---------------------------------------------------------------------------
# Words too generic to signal that two concerns are clinically related.
_GENERIC_WORDS = {
    "pain", "ache", "days", "weeks", "week", "since", "morning", "night",
    "home", "problem", "feeling", "feels", "after", "last", "mild", "severe",
    "today", "yesterday", "very", "also", "with", "without", "having",
}

def _kw(text: str) -> set:
    """Meaningful keywords from a concern string (deterministic, auditable)."""
    return {w for w in re.findall(r"[a-z]+", (text or "").lower())
            if len(w) >= 4 and w not in _GENERIC_WORDS}

def _deterministic_summary(cur_spec, visits):
    """The offline floor: a factual digest built purely from stored data.
    States facts and flags recurrence — never advises, never decides."""
    if not visits:
        return "No previous visits on record — first-time presentation."
    rel = [v for v in visits if v["related"]]
    unrel = [v for v in visits if not v["related"]]
    parts = [f"{len(visits)} previous visit{'s' if len(visits) != 1 else ''} on record."]
    if rel:
        items = "; ".join(f"\u201c{v['concern'][:70]}\u201d ({v['when']})" for v in rel)
        parts.append(
            f"{len(rel)} appear{'s' if len(rel) == 1 else ''} related to today's presentation"
            + (f" ({cur_spec})" if cur_spec else "")
            + f": {items}. Recurring same-system history — surfaced for clinical correlation."
        )
    if unrel:
        specs = sorted({v["specialty"] or "General" for v in unrel})
        parts.append(f"{len(unrel)} unrelated ({', '.join(specs)}).")
    if any(v["override"] for v in visits):
        parts.append("One prior visit carried a nurse override — see details below.")
    return " ".join(parts)

def _try_llm_summary(p, cur_spec, visits):
    """Optional garnish: if an LLM key is configured, simplify the digest into
    2-3 kind, plain sentences. STRICT: facts only, no advice, no severity.
    Any failure falls silently back to the deterministic summary."""
    try:
        from app.routers.transcribe import GROQ_KEY, GEMINI_KEY, _llm
        if not (GROQ_KEY or GEMINI_KEY):
            return None
        import json as _json
        prompt = (
            "You are simplifying a patient's previous hospital visits for a busy ED doctor "
            "who has five seconds to read.\n"
            "STRICT RULES: use ONLY the facts given below. Do NOT add diagnoses, medicines, "
            "doses, or advice. Do NOT decide or suggest urgency.\n"
            "Write 2-3 short plain-text sentences: how many prior visits, which relate to "
            "today's concern and why (same body system / specialty / recurring symptom), and "
            "anything notable such as a prior nurse override.\n"
            f"Today's concern: {p.concern}\n"
            f"Today's routed specialty: {cur_spec}\n"
            f"Prior visits (JSON):\n{_json.dumps(visits, default=str)}"
        )
        text = _llm(prompt).strip()
        return text or None
    except Exception:
        return None

@router.get("/{patient_id}/history")
def patient_history(patient_id: int, db: Session = Depends(get_db),
                    user=Depends(require_role("nurse", "doctor"))):
    """Previous-visit digest for the clinician reviewing this patient.
    Linked by exact name (+/-2y age) for the DEMO — production links via
    MRN/ABHA number through the hospital EHR, never name-matching."""
    p = db.get(Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")

    cur = (db.query(TriageResult).filter_by(patient_id=p.id)
             .order_by(TriageResult.created_at.desc()).first())
    cur_spec = cur.specialty if cur else None
    cur_kw = _kw(p.concern)

    priors = (db.query(Patient)
                .filter(Patient.status == "completed", Patient.id != p.id)
                .filter(func.lower(Patient.name) == (p.name or "").strip().lower())
                .order_by(Patient.arrived_at.desc())
                .all())
    priors = [m for m in priors if abs((m.age or 0) - (p.age or 0)) <= 2][:5]

    visits = []
    for m in priors:
        t = (db.query(TriageResult).filter_by(patient_id=m.id)
               .order_by(TriageResult.created_at.desc()).first())
        o = (db.query(Override).filter_by(patient_id=m.id)
               .order_by(Override.created_at.desc()).first())
        rx = (db.query(Prescription).filter_by(patient_id=m.id)
                .order_by(Prescription.created_at.desc()).first())
        overlap = cur_kw & _kw(m.concern)
        same_spec = bool(cur_spec and t and t.specialty == cur_spec)
        related = bool(overlap) or same_spec
        visits.append({
            "id": m.id,
            "when": m.arrived_at.strftime("%d %b %Y") if m.arrived_at else "unknown date",
            "concern": m.concern,
            "category": t.category if t else "lower",
            "specialty": t.specialty if t else None,
            "related": related,
            "matched_on": (sorted(overlap) if overlap else (["same specialty"] if same_spec else [])),
            "override": (f"{o.from_category} -> {o.to_category}: {o.reason}" if o else None),
            "prescription": ((rx.text[:120] + ("…" if len(rx.text) > 120 else "")) if rx else None),
        })

    llm = _try_llm_summary(p, cur_spec, visits) if visits else None
    summary = llm or _deterministic_summary(cur_spec, visits)
    return {"patient_id": p.id, "visits": visits,
            "summary": summary, "llm_used": bool(llm)}

def _triage_and_store(db, patient, vitals_dict):
    t = run_triage(patient.age, vitals_dict, patient.concern, patient.pain,
                   patient.source, patient.appearance, patient.has_history)
    db.add(TriageResult(patient_id=patient.id, **t))
    return t

@router.get("/completed")
def completed_patients(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Recently completed visits — so the patient portal can show finished
    consultations and their prescriptions, not just the waiting queue."""
    rows = (db.query(Patient).filter(Patient.status == "completed")
              .order_by(Patient.arrived_at.desc()).limit(50).all())
    out = []
    for m in rows:
        t = (db.query(TriageResult).filter_by(patient_id=m.id)
               .order_by(TriageResult.created_at.desc()).first())
        out.append({"id": m.id, "name": m.name, "age": m.age, "gender": m.gender,
                    "concern": m.concern, "category": t.category if t else "lower",
                    "specialty": t.specialty if t else None,
                    "confidence": t.confidence if t else 0.5,
                    "escalated": t.escalated if t else False,
                    "status": "completed"})
    return out

@router.post("")
async def register_patient(body: PatientIn, db: Session = Depends(get_db),
                           user=Depends(require_role("kiosk", "nurse", "doctor", "patient"))):
    p = Patient(name=body.name, age=body.age, gender=body.gender, concern=body.concern,
                pain=body.pain, has_history=body.has_history, source=body.source,
                appearance=body.appearance)
    db.add(p); db.flush()
    vitals_dict = None
    if body.vitals:
        db.add(VitalsReading(patient_id=p.id, **body.vitals.dict()))
        vitals_dict = body.vitals.dict()
    t = _triage_and_store(db, p, vitals_dict)
    audit(db, user["display"], "register",
          f"{p.name} ({p.age}{p.gender}) -> {t['category']} conf {t['confidence']:.0%} {t['specialty']}"
          + (" ESCALATED" if t["escalated"] else ""))
    db.commit()
    await manager.broadcast("queue_updated", {"action": "register", "patient_id": p.id})
    return {"patient_id": p.id, "triage": t}

@router.post("/{patient_id}/vitals")
async def new_vitals(patient_id: int, body: VitalsIn, db: Session = Depends(get_db),
                     user=Depends(require_role("nurse"))):
    p = db.get(Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    db.add(VitalsReading(patient_id=p.id, **body.dict()))
    t = _triage_and_store(db, p, body.dict())   # automatic re-triage on new vitals
    audit(db, user["display"], "revitals", f"{p.name}: new vitals -> re-triaged {t['category']}")
    db.commit()
    await manager.broadcast("queue_updated", {"action": "revitals", "patient_id": p.id})
    return {"patient_id": p.id, "triage": t}

SURGE_CONCERNS = [
    "Fever and body ache", "Breathless and cough", "Chest pain radiating to arm",
    "Fall from bike, knee pain", "Vomiting and stomach pain", "Headache and dizziness",
    "Bleeding cut on leg", "High fever child, breathing fast",
]

@router.post("/demo/surge")
async def demo_surge(db: Session = Depends(get_db), user=Depends(get_current_user)):
    waiting = db.query(Patient).filter(Patient.status == "waiting").count()
    n = max(10, waiting * 2)   # -> roughly 3x total volume
    for i in range(n):
        concern = SURGE_CONCERNS[i % len(SURGE_CONCERNS)]
        age = random.randint(3, 9) if "child" in concern else random.randint(18, 85)
        vit = None if i % 3 == 0 else dict(
            hr=random.randint(65, 150), bp_sys=random.randint(92, 165),
            bp_dia=random.randint(60, 95), spo2=random.randint(90, 100),
            temp=round(random.uniform(36.3, 39.6), 1))
        p = Patient(name=f"Surge Pt {i+1}", age=age, gender=random.choice(["M", "F"]),
                    concern=concern, pain=random.randint(1, 9),
                    has_history=bool(i % 2), source="kiosk", appearance=[])
        # backdate some arrivals so the re-assessment monitor has something to flag
        p.arrived_at = datetime.utcnow() - timedelta(minutes=random.randint(0, 45))
        db.add(p); db.flush()
        if vit:
            db.add(VitalsReading(patient_id=p.id, **vit))
        t = run_triage(p.age, vit, p.concern, p.pain, p.source, p.appearance, p.has_history)
        db.add(TriageResult(patient_id=p.id, **t))
    audit(db, user["display"], "surge", f"SURGE SIMULATION: {n} patients injected (~3x volume)")
    db.commit()
    await manager.broadcast("queue_updated", {"action": "surge", "count": n})
    return {"injected": n}

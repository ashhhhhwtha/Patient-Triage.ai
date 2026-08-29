"""Phase 4: endpoints are async and broadcast over WebSocket after every change.
Adds POST /patients/demo/surge — injects ~3x volume for the surge demo."""
import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Patient, VitalsReading, TriageResult
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

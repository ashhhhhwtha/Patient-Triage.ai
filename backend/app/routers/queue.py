from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.db import get_db
from app.models import Patient, TriageResult, VitalsReading, AuditLog
from app.auth import get_current_user

router = APIRouter(tags=["queue"])
CAT_RANK = {"emergency": 0, "urgent": 1, "lower": 2}
SAFE_WAIT_MIN = {"emergency": 10, "urgent": 30, "lower": 120}
HANDLE_MIN = {"emergency": 8, "urgent": 14, "lower": 20}

@router.get("/queue")
def get_queue(db: Session = Depends(get_db), user=Depends(get_current_user)):
    patients = db.query(Patient).filter(Patient.status == "waiting").all()
    rows = []
    for p in patients:
        t = (db.query(TriageResult).filter_by(patient_id=p.id)
               .order_by(TriageResult.created_at.desc()).first())
        if not t:
            continue
        v = (db.query(VitalsReading).filter_by(patient_id=p.id)
               .order_by(VitalsReading.taken_at.desc()).first())
        waited = int((datetime.utcnow() - p.arrived_at).total_seconds() // 60)
        rows.append({
            "id": p.id, "name": p.name, "age": p.age, "gender": p.gender,
            "concern": p.concern, "source": p.source, "has_history": p.has_history,
            "appearance": p.appearance, "category": t.category, "score": t.score,
            "confidence": t.confidence, "specialty": t.specialty,
            "escalated": t.escalated, "reasons": t.reasons,
            "model_version": t.model_version,
            "vitals": {"hr": v.hr, "bp_sys": v.bp_sys, "bp_dia": v.bp_dia,
                       "spo2": v.spo2, "temp": v.temp} if v else None,
            "waited_min": waited,
            "reassess_due": waited > SAFE_WAIT_MIN[t.category],
        })
    # THE brief requirement: category first, urgency score inside category, then arrival
    rows.sort(key=lambda r: (CAT_RANK[r["category"]], -r["score"], r["id"]))
    # wait estimate: everyone ahead of you in your own specialty
    for i, r in enumerate(rows):
        ahead = [x for x in rows[:i] if x["specialty"] == r["specialty"]]
        r["est_wait_min"] = sum(HANDLE_MIN[x["category"]] for x in ahead)
    return rows

@router.get("/audit")
def get_audit(db: Session = Depends(get_db), user=Depends(get_current_user)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return [{"at": str(l.created_at), "actor": l.actor, "action": l.action,
             "detail": l.detail} for l in logs]
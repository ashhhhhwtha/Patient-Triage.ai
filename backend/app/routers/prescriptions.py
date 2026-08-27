from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Patient, Prescription
from app.schemas import PrescriptionIn
from app.auth import require_role
from app.audit import audit
from app.ws import manager

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])

@router.post("")
async def create_prescription(body: PrescriptionIn, db: Session = Depends(get_db),
                              user=Depends(require_role("doctor"))):
    p = db.get(Patient, body.patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    db.add(Prescription(patient_id=p.id, doctor=user["display"], text=body.text))
    p.status = "completed"
    audit(db, user["display"], "prescription", f"issued for {p.name}")
    db.commit()
    await manager.broadcast("prescription_ready",
                            {"patient_id": p.id, "name": p.name, "doctor": user["display"]})
    await manager.broadcast("queue_updated", {"action": "prescription", "patient_id": p.id})
    return {"ok": True}

@router.get("/{patient_id}")
def get_prescription(patient_id: int, db: Session = Depends(get_db)):
    rx = (db.query(Prescription).filter_by(patient_id=patient_id)
            .order_by(Prescription.created_at.desc()).first())
    if not rx:
        raise HTTPException(404, "No prescription yet")
    return {"doctor": rx.doctor, "text": rx.text, "at": str(rx.created_at)}

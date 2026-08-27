from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Patient, TriageResult, Override
from app.schemas import OverrideIn
from app.auth import require_role
from app.audit import audit
from app.ws import manager

router = APIRouter(prefix="/overrides", tags=["overrides"])

@router.post("")
async def create_override(body: OverrideIn, db: Session = Depends(get_db),
                          user=Depends(require_role("nurse"))):
    if not body.reason.strip():
        raise HTTPException(422, "Override reason is mandatory")
    p = db.get(Patient, body.patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    t = (db.query(TriageResult).filter_by(patient_id=p.id)
           .order_by(TriageResult.created_at.desc()).first())
    db.add(Override(patient_id=p.id, from_category=t.category,
                    to_category=body.to_category, reason=body.reason, nurse=user["display"]))
    db.add(TriageResult(patient_id=p.id, category=body.to_category, score=t.score,
                        confidence=t.confidence, specialty=t.specialty, escalated=False,
                        reasons=t.reasons + [f"NURSE OVERRIDE: {t.category} -> {body.to_category} ({body.reason})"],
                        model_version=t.model_version))
    audit(db, user["display"], "override",
          f"{p.name}: {t.category} -> {body.to_category}. Reason: {body.reason}")
    db.commit()
    await manager.broadcast("queue_updated", {"action": "override", "patient_id": p.id})
    return {"ok": True}

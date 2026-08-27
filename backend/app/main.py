"""PatientTriage.ai API — Phase 4: adds WebSocket hub + waiting-room re-assessment monitor."""
import asyncio
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine, SessionLocal
from app.models import Patient, TriageResult, AuditLog
from app.routers import auth_routes, patients, queue, overrides, prescriptions, transcribe
from app import ws

Base.metadata.create_all(bind=engine)

app = FastAPI(title="PatientTriage.ai API", version="4.0",
              description="Hybrid triage decision support. Clinician always in charge.")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth_routes.router, patients.router, queue.router,
          overrides.router, prescriptions.router, ws.router, transcribe.router):
    app.include_router(r)

@app.get("/")
def health():
    return {"status": "ok", "service": "PatientTriage.ai API"}

# ---- Waiting-room monitor: brief requirement ----
# Every 30s, flag any waiting patient past the safe wait threshold for their category.
SAFE_WAIT = {"emergency": 10, "urgent": 30, "lower": 120}
_flagged: set[int] = set()

@app.on_event("startup")
async def start_monitor():
    async def loop():
        while True:
            await asyncio.sleep(30)
            try:
                db = SessionLocal()
                for p in db.query(Patient).filter(Patient.status == "waiting").all():
                    t = (db.query(TriageResult).filter_by(patient_id=p.id)
                           .order_by(TriageResult.created_at.desc()).first())
                    if not t:
                        continue
                    waited = (datetime.utcnow() - p.arrived_at).total_seconds() / 60
                    if waited > SAFE_WAIT.get(t.category, 120) and p.id not in _flagged:
                        _flagged.add(p.id)
                        db.add(AuditLog(actor="monitor", action="reassess_due",
                                        detail=f"{p.name} waited {int(waited)}m > safe "
                                               f"{SAFE_WAIT[t.category]}m for {t.category} — re-assessment required"))
                        db.commit()
                        await ws.manager.broadcast("reassess_due",
                                                   {"patient_id": p.id, "name": p.name})
                db.close()
            except Exception as e:
                print("[monitor] error:", e)
    asyncio.create_task(loop())

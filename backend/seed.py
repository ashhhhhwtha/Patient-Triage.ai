"""Loads 5 demo patients through the real API pipeline. Run: python seed.py
(The other 11 prototype patients can be added the same way — or via the frontend once wired.)"""
from app.db import SessionLocal, Base, engine
from app.models import Patient, VitalsReading, TriageResult
from app.triage.engine import run_triage

Base.metadata.create_all(bind=engine)
db = SessionLocal()

SEED = [
    dict(name="Ramesh Kalita", age=58, gender="M", concern="Crushing chest pain and sweating for 30 minutes",
         pain=9, source="ambulance", appearance=["pale", "sweating"], has_history=True,
         vitals=dict(hr=118, bp_sys=92, bp_dia=60, spo2=93, temp=36.9)),
    dict(name="Aarav Sharma", age=3, gender="M", concern="High fever and not eating, breathing fast",
         pain=3, source="kiosk", appearance=["lethargic"], has_history=True,
         vitals=dict(hr=158, bp_sys=88, bp_dia=55, spo2=95, temp=39.2)),
    dict(name="Bimala Devi", age=78, gender="F", concern="Fall at home, mild hip pain, feels weak",
         pain=3, source="kiosk", appearance=["confused"], has_history=True,
         vitals=dict(hr=108, bp_sys=96, bp_dia=62, spo2=94, temp=37.6)),
    dict(name="Priya Das", age=29, gender="F", concern="Chest tightness and palpitations, also anxiety",
         pain=4, source="kiosk", appearance=[], has_history=False,
         vitals=dict(hr=104, bp_sys=128, bp_dia=82, spo2=98, temp=36.8)),
    dict(name="Kabir Hussain", age=19, gender="M", concern="Rash on arms, itching, no fever",
         pain=1, source="kiosk", appearance=[], has_history=False,
         vitals=dict(hr=72, bp_sys=116, bp_dia=74, spo2=99, temp=36.6)),
]

for s in SEED:
    vit = s.pop("vitals")
    p = Patient(**s)
    db.add(p); db.flush()
    db.add(VitalsReading(patient_id=p.id, **vit))
    t = run_triage(p.age, vit, p.concern, p.pain, p.source, p.appearance, p.has_history)
    db.add(TriageResult(patient_id=p.id, **t))
    print(f"{p.name:18} -> {t['category']:9} conf {t['confidence']:.0%}  {t['specialty']}")
db.commit()
print("Seeded.")
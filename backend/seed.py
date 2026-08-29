"""Seed the live system with 16 simulated patients — covering every Round 2 minimum:
ambiguous presentation, pediatric + geriatric cases, zero-history patients, ambulance
arrivals — plus ONE pre-captured nurse override so the audit trail demonstrates the
override->log requirement the moment a judge opens the app.

NEW: 4 COMPLETED PRIOR VISITS seeded first (backdated, with prescriptions), so the
Doctor Console's "Previous visits" panel demonstrates on first view:
  - Ramesh Kalita  : prior exertional chest pain  -> RELATED to today's crushing chest pain
  - Farhan Ali     : prior wheezing / night cough -> RELATED to today's asthma attack
  - Anjali Roy     : prior lower back pain        -> RELATED to today's back pain flare-up
  - Lakshmi Gogoi  : prior knee arthritis flare   -> UNRELATED to today's fever + cough

Run from backend:  python seed.py
(For a clean demo, delete the old SQLite database file first, then run seed.py.)
"""
from datetime import datetime, timedelta
from app.db import SessionLocal, Base, engine
from app.models import Patient, VitalsReading, TriageResult, Override, AuditLog, Prescription
from app.triage.engine import run_triage

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ---------------------------------------------------------------------------
# PRIOR (COMPLETED) VISITS — these power the Doctor Console history panel.
# Linked to today's patients by name+age (demo); production: MRN/ABHA via EHR.
# ---------------------------------------------------------------------------
PRIOR_VISITS = [
    # RELATED: same cardiac story, four months earlier
    dict(name="Ramesh Kalita", age=58, gender="M",
         concern="Chest pain while climbing stairs, settled after rest",
         pain=5, source="kiosk", appearance=[], has_history=False, days_ago=126,
         vitals=dict(hr=94, bp_sys=138, bp_dia=88, spo2=97, temp=36.8),
         doctor="Dr. A. Choudhury",
         rx="Diagnosis: Exertional chest pain — stable angina suspected.\n"
            "Rx:\n1. Tab Ecosprin 75 mg — once daily after food\n"
            "2. Tab Sorbitrate 5 mg — under the tongue if pain recurs\n"
            "Advice: Cardiology OPD in 1 week; treadmill test advised."),
    # RELATED: same respiratory story, two months earlier
    dict(name="Farhan Ali", age=8, gender="M",
         concern="Wheezing and night cough for one week, worse with play",
         pain=2, source="kiosk", appearance=[], has_history=False, days_ago=64,
         vitals=dict(hr=118, bp_sys=100, bp_dia=64, spo2=95, temp=37.0),
         doctor="Dr. S. Bhattacharya",
         rx="Diagnosis: Childhood asthma — poorly controlled.\n"
            "Rx:\n1. Salbutamol inhaler with spacer — 2 puffs when wheezy\n"
            "2. Budesonide inhaler — 1 puff twice daily\n"
            "Advice: Inhaler technique taught; review in 2 weeks."),
    # RELATED: the "old problem" her today-concern refers to
    dict(name="Anjali Roy", age=55, gender="F",
         concern="Lower back pain after lifting a heavy pot at home",
         pain=6, source="kiosk", appearance=[], has_history=False, days_ago=210,
         vitals=dict(hr=80, bp_sys=130, bp_dia=84, spo2=98, temp=36.6),
         doctor="Dr. M. Begum",
         rx="Diagnosis: Mechanical low back pain, no red flags.\n"
            "Rx:\n1. Tab Paracetamol 650 mg — twice daily for 5 days\n"
            "Advice: Hot fomentation, avoid heavy lifting, physiotherapy referral."),
    # UNRELATED: orthopedic history; today she presents with fever + cough
    dict(name="Lakshmi Gogoi", age=72, gender="F",
         concern="Knee swelling and stiffness, known arthritis, difficulty walking",
         pain=5, source="kiosk", appearance=[], has_history=False, days_ago=95,
         vitals=dict(hr=84, bp_sys=136, bp_dia=82, spo2=97, temp=36.7),
         doctor="Dr. M. Begum",
         rx="Diagnosis: Osteoarthritis flare, left knee.\n"
            "Rx:\n1. Tab Paracetamol 650 mg — twice daily for 5 days\n"
            "Advice: Knee X-ray done; orthopedic OPD follow-up in 3 weeks."),
]

print("Seeding prior (completed) visits for the history panel:")
print("-" * 70)
for s in PRIOR_VISITS:
    days = s.pop("days_ago"); vit = s.pop("vitals")
    rx_text = s.pop("rx"); doc_name = s.pop("doctor")
    p = Patient(**s)
    p.status = "completed"
    p.arrived_at = datetime.utcnow() - timedelta(days=days)
    db.add(p); db.flush()
    db.add(VitalsReading(patient_id=p.id, **vit))
    t = run_triage(p.age, vit, p.concern, p.pain, p.source, p.appearance, p.has_history)
    db.add(TriageResult(patient_id=p.id, **t))
    db.add(Prescription(patient_id=p.id, doctor=doc_name, text=rx_text))
    db.add(AuditLog(actor="seed", action="register",
                    detail=f"[prior visit, {days}d ago] {p.name} ({p.age}{p.gender}) "
                           f"-> {t['category']} {t['specialty']} — completed, Rx on file"))
    print(f"{p.name:22} {days:>3}d ago  {t['category']:10} {t['specialty']}")
print()

# ---------------------------------------------------------------------------
# TODAY'S 16 WAITING PATIENTS (unchanged)
# name age gender concern pain source appearance has_history vitals
# ---------------------------------------------------------------------------
SEED = [
    dict(name="Ramesh Kalita", age=58, gender="M", concern="Crushing chest pain and sweating for 30 minutes",
         pain=9, source="ambulance", appearance=["pale", "sweating"], has_history=True,
         vitals=dict(hr=118, bp_sys=92, bp_dia=60, spo2=93, temp=36.9)),
    # AMBIGUOUS presentation: cardiac vs anxiety
    dict(name="Priya Das", age=29, gender="F", concern="Chest tightness and palpitations, also anxiety before exams",
         pain=4, source="kiosk", appearance=[], has_history=False,
         vitals=dict(hr=104, bp_sys=128, bp_dia=82, spo2=98, temp=36.8)),
    # PEDIATRIC case: fever thresholds band-calibrated
    dict(name="Aarav Sharma", age=3, gender="M", concern="High fever and not eating, mother says breathing fast",
         pain=3, source="kiosk", appearance=["lethargic"], has_history=True,
         vitals=dict(hr=158, bp_sys=88, bp_dia=55, spo2=95, temp=39.2)),
    # GERIATRIC case: under-reported pain, blunted fever response
    dict(name="Bimala Devi", age=78, gender="F", concern="Fall at home, mild hip pain, feels a bit weak",
         pain=3, source="kiosk", appearance=["confused"], has_history=True,
         vitals=dict(hr=108, bp_sys=96, bp_dia=62, spo2=94, temp=37.6)),
    # ZERO-HISTORY first-time patient, ambulance arrival
    dict(name="Unknown Male", age=45, gender="M", concern="Road accident, bleeding from head, brought by bystander",
         pain=7, source="ambulance", appearance=["bleeding visible", "distressed"], has_history=False,
         vitals=dict(hr=122, bp_sys=88, bp_dia=58, spo2=91, temp=36.2)),
    dict(name="Sunita Boro", age=34, gender="F", concern="Pregnant 36 weeks, labor pains every 5 minutes",
         pain=8, source="kiosk", appearance=[], has_history=True,
         vitals=dict(hr=96, bp_sys=132, bp_dia=84, spo2=98, temp=37.0)),
    dict(name="Joydeep Nath", age=22, gender="M", concern="Twisted ankle playing football, maybe fracture",
         pain=5, source="kiosk", appearance=[], has_history=True,
         vitals=dict(hr=82, bp_sys=122, bp_dia=78, spo2=99, temp=36.7)),
    dict(name="Meera Saikia", age=67, gender="F", concern="Slurred speech since morning, right arm weakness",
         pain=1, source="kiosk", appearance=["confused"], has_history=True,
         vitals=dict(hr=88, bp_sys=176, bp_dia=98, spo2=96, temp=36.9)),
    dict(name="Farhan Ali", age=8, gender="M", concern="Asthma attack, inhaler not helping, breathless",
         pain=4, source="kiosk", appearance=["distressed"], has_history=True,
         vitals=dict(hr=148, bp_sys=96, bp_dia=60, spo2=90, temp=37.1)),
    dict(name="Gita Baruah", age=41, gender="F", concern="Stomach pain and vomiting since last night",
         pain=6, source="kiosk", appearance=[], has_history=True,
         vitals=dict(hr=94, bp_sys=118, bp_dia=76, spo2=98, temp=37.9)),
    dict(name="Dhruv Patel", age=26, gender="M", concern="Mild headache and dizziness after long shift",
         pain=3, source="kiosk", appearance=[], has_history=False,
         vitals=dict(hr=76, bp_sys=118, bp_dia=74, spo2=99, temp=36.6)),
    dict(name="Lakshmi Gogoi", age=72, gender="F", concern="Fever and cough for two days, weakness",
         pain=2, source="kiosk", appearance=[], has_history=True,
         vitals=dict(hr=102, bp_sys=108, bp_dia=68, spo2=92, temp=38.1)),
    dict(name="Rohit Deka", age=31, gender="M", concern="Deep cut on hand while cooking, bleeding controlled",
         pain=4, source="kiosk", appearance=[], has_history=True,
         vitals=dict(hr=84, bp_sys=124, bp_dia=80, spo2=99, temp=36.8)),
    dict(name="Anjali Roy", age=55, gender="F", concern="Back pain flare-up, old problem",
         pain=5, source="kiosk", appearance=[], has_history=True,
         vitals=dict(hr=78, bp_sys=134, bp_dia=86, spo2=98, temp=36.7)),
    dict(name="Kabir Hussain", age=19, gender="M", concern="Rash on arms, itching, no fever",
         pain=1, source="kiosk", appearance=[], has_history=False,
         vitals=dict(hr=72, bp_sys=116, bp_dia=74, spo2=99, temp=36.6)),
    dict(name="Nayan Bora", age=63, gender="M", concern="Seizure at home 20 minutes ago, now drowsy",
         pain=0, source="ambulance", appearance=["lethargic"], has_history=True,
         vitals=dict(hr=98, bp_sys=142, bp_dia=90, spo2=95, temp=37.0)),
]

priya_id = None
print(f"{'Patient':22} {'Category':10} {'Conf':5} {'Specialty':18} Escalated")
print("-" * 70)
for s in SEED:
    vit = s.pop("vitals")
    p = Patient(**s)
    db.add(p); db.flush()
    db.add(VitalsReading(patient_id=p.id, **vit))
    t = run_triage(p.age, vit, p.concern, p.pain, p.source, p.appearance, p.has_history)
    db.add(TriageResult(patient_id=p.id, **t))
    db.add(AuditLog(actor="seed", action="register",
                    detail=f"{p.name} ({p.age}{p.gender}) -> {t['category']} conf {t['confidence']:.0%} {t['specialty']}"
                           + (" ESCALATED" if t["escalated"] else "")))
    if p.name == "Priya Das":
        priya_id, priya_triage = p.id, t
    print(f"{p.name:22} {t['category']:10} {t['confidence']:.0%}  {t['specialty']:18} {'YES' if t['escalated'] else ''}")

# --- Pre-captured clinician override (brief minimum: capture one override + show the log) ---
if priya_id:
    db.add(Override(patient_id=priya_id, from_category=priya_triage["category"], to_category="urgent",
                    reason="Known anxiety history, ECG normal at bedside; keeping cardiac watch but not resus priority",
                    nurse="Nurse J. Kalita"))
    db.add(TriageResult(patient_id=priya_id, category="urgent", score=priya_triage["score"],
                        confidence=priya_triage["confidence"], specialty=priya_triage["specialty"],
                        escalated=False,
                        reasons=priya_triage["reasons"] + [
                            "NURSE OVERRIDE: " + priya_triage["category"] + " -> urgent "
                            "(Known anxiety history, ECG normal at bedside)"],
                        model_version=priya_triage["model_version"]))
    db.add(AuditLog(actor="Nurse J. Kalita", action="override",
                    detail=f"Priya Das: {priya_triage['category']} -> urgent. Reason: Known anxiety history, "
                           f"ECG normal at bedside; keeping cardiac watch. AI conf {priya_triage['confidence']:.0%}. "
                           f"Fed to nightly retraining."))
    print("-" * 70)
    print("Pre-captured 1 nurse override (Priya Das) + audit entry - brief requirement met on first view.")

db.commit()
print(f"\nSeeded {len(PRIOR_VISITS)} prior visits + {len(SEED)} waiting patients. Done.")
print("History panel demo: open Doctor Console -> Ramesh Kalita / Farhan Ali / Anjali Roy (related)")
print("and Lakshmi Gogoi (unrelated prior) — 'Previous visits' appears above the vitals.")

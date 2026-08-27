"""Nightly (or manual) retraining that folds nurse overrides back into the model.
Each override row is added 3x -- nurse judgement is weighted above synthetic data.
Run FROM the backend folder:  python ml/retrain.py"""
import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV

from app.db import SessionLocal
from app.models import Override, Patient, VitalsReading
from app.triage.engine import _symptoms

LABEL = {"lower": 0, "urgent": 1, "emergency": 2}
FEATURES = ["age", "band", "hr", "spo2", "temp", "bp_sys", "pain",
            "symptom_weight", "ambulance", "appearance_flags"]

db = SessionLocal()
rows = []
for o in db.query(Override).all():
    p = db.get(Patient, o.patient_id)
    v = (db.query(VitalsReading).filter_by(patient_id=p.id)
           .order_by(VitalsReading.taken_at.desc()).first())
    w, *_ = _symptoms(p.concern)
    band = 0 if p.age < 12 else (2 if p.age >= 65 else 1)
    rows.append(dict(age=p.age, band=band,
                     hr=(v.hr if v else 85) or 85, spo2=(v.spo2 if v else 97) or 97,
                     temp=(v.temp if v else 36.8) or 36.8,
                     bp_sys=(v.bp_sys if v else 120) or 120,
                     pain=p.pain or 0, symptom_weight=w,
                     ambulance=int(p.source == "ambulance"),
                     appearance_flags=len(p.appearance or []),
                     label=LABEL[o.to_category]))
db.close()

synth = pd.read_csv("ml/synthetic_ed.csv")
if rows:
    ov = pd.DataFrame(rows)
    data = pd.concat([synth, ov, ov, ov], ignore_index=True)  # 3x weight on nurse judgement
    print(f"retraining on {len(synth)} synthetic + {len(ov)} overrides (x3)")
else:
    data = synth
    print("no overrides yet; retraining on synthetic only")

base = Pipeline([("scale", StandardScaler()),
                 ("lr", LogisticRegression(max_iter=2000, class_weight={0: 1, 1: 2, 2: 5}))])
model = CalibratedClassifierCV(base, cv=3)
model.fit(data[FEATURES], data["label"])
joblib.dump({"model": model, "features": FEATURES, "version": "hybrid-v1.1-retrained",
             "thresholds": {"emerg": 0.10, "urgent": 0.30}},
            "models/triage_model.pkl")
print("saved models/triage_model.pkl (restart the server to load it)")

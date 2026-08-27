import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, confusion_matrix

FEATURES = ["age", "band", "hr", "spo2", "temp", "bp_sys", "pain",
            "symptom_weight", "ambulance", "appearance_flags"]

df = pd.read_csv("ml/synthetic_ed.csv")
X, y = df[FEATURES], df["label"]
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

base = Pipeline([
    ("scale", StandardScaler()),
    # class_weight punishes under-triage 5x harder than over-triage:
    # this one line implements the brief's "asymmetric costs" requirement.
    ("lr", LogisticRegression(max_iter=2000, class_weight={0: 1, 1: 2, 2: 5})),
])
model = CalibratedClassifierCV(base, cv=3)  # calibration -> confidence % is statistically meaningful
model.fit(Xtr, ytr)

# COST-SENSITIVE DECISION RULE (not argmax): emergency and urgent are taken at low
# probability thresholds because missing a sick patient costs far more than over-calling one.
T_EMERG, T_URGENT = 0.10, 0.30
import numpy as np
P = model.predict_proba(Xte)
pred = np.zeros(len(P), dtype=int)
pred[(P[:, 1] + P[:, 2]) >= T_URGENT] = 1
pred[P[:, 2] >= T_EMERG] = 2
print(classification_report(yte, pred, target_names=["lower", "urgent", "emergency"]))
cm = confusion_matrix(yte, pred)
print("Confusion matrix (rows=true, cols=predicted):")
print(pd.DataFrame(cm, index=["true_lower", "true_urgent", "true_emerg"],
                   columns=["pred_lower", "pred_urgent", "pred_emerg"]))
under = (cm[2][0] + cm[2][1] + cm[1][0]) / cm.sum()
over = (cm[0][1] + cm[0][2] + cm[1][2]) / cm.sum()
print(f"\nUnder-triage rate: {under:.3%}   <- report THIS in your slides, not accuracy")
print(f"Over-triage rate:  {over:.3%}   (deliberate: we bias toward escalation)")

joblib.dump({"model": model, "features": FEATURES, "version": "hybrid-v1",
             "thresholds": {"emerg": T_EMERG, "urgent": T_URGENT}},
            "models/triage_model.pkl")
print("saved models/triage_model.pkl")

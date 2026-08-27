"""Hybrid triage engine v1.
- Rules safety floor (rules.py): ML can never downgrade below it.
- Calibrated logistic regression: refines priority, provides meaningful confidence.
- Escalate-on-uncertainty: confidence < 65% moves the patient UP one level, never down.
If the trained model file is missing, falls back to rules-only so the server always boots.
Same run_triage() signature as Phase 2 -> no other file changes."""

from pathlib import Path
import numpy as np
import pandas as pd

from app.triage.rules import rules_floor, age_band

CATS = ["emergency", "urgent", "lower"]  # index 0 = most severe

KEYWORDS = {
    "chest pain": ("Cardiology", 34), "chest tightness": ("Cardiology", 30),
    "palpitations": ("Cardiology", 18),
    "breathing": ("Pulmonology", 28), "breathless": ("Pulmonology", 28),
    "shortness of breath": ("Pulmonology", 30), "asthma": ("Pulmonology", 24),
    "stroke": ("Neurology", 42), "slurred speech": ("Neurology", 40),
    "seizure": ("Neurology", 36), "unconscious": ("Neurology", 45),
    "headache": ("Neurology", 12), "dizziness": ("Neurology", 12),
    "bleeding": ("Trauma & Surgery", 32), "accident": ("Trauma & Surgery", 26),
    "burn": ("Trauma & Surgery", 26), "cut": ("Trauma & Surgery", 14),
    "fracture": ("Orthopedics", 20), "fall": ("Orthopedics", 16),
    "broken": ("Orthopedics", 20), "back pain": ("Orthopedics", 10),
    "stomach pain": ("Gastroenterology", 18), "abdominal": ("Gastroenterology", 20),
    "vomiting": ("Gastroenterology", 12), "diarrhea": ("Gastroenterology", 10),
    "pregnan": ("Obstetrics", 30), "labor": ("Obstetrics", 34),
    "fever": ("General Medicine", 10), "weakness": ("General Medicine", 10),
    "rash": ("General Medicine", 8),
}

# ---- load trained model once at import time ----
_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "triage_model.pkl"
_MODEL, _FEATURES, _VERSION = None, None, "rules-fallback"
_T_EMERG, _T_URGENT = 0.10, 0.30  # cost-sensitive decision thresholds (asymmetric costs)
try:
    import joblib
    _bundle = joblib.load(_MODEL_PATH)
    _MODEL, _FEATURES, _VERSION = _bundle["model"], _bundle["features"], _bundle["version"]
    _T_EMERG = _bundle.get("thresholds", {}).get("emerg", _T_EMERG)
    _T_URGENT = _bundle.get("thresholds", {}).get("urgent", _T_URGENT)
    print(f"[triage] loaded ML model {_VERSION} from {_MODEL_PATH}")
except Exception as e:
    print(f"[triage] WARNING: no ML model ({e}); running rules-only fallback")


def _symptoms(text):
    text = (text or "").lower()
    weight, spec_scores, matched = 0.0, {}, []
    for kw, (sp, w) in KEYWORDS.items():
        if kw in text:
            weight += w
            spec_scores[sp] = spec_scores.get(sp, 0) + w
            matched.append((kw, sp, w))
    ranked = sorted(spec_scores.items(), key=lambda x: -x[1])
    ambiguous = len(ranked) >= 2 and ranked[1][1] >= ranked[0][1] * 0.7
    return weight, ranked, matched, ambiguous


def run_triage(age, vitals, concern, pain, source, appearance, has_history):
    reasons = []
    v = vitals or {}
    band = age_band(age)

    # 1) RULES SAFETY FLOOR
    floor, rule_reasons = rules_floor(age, vitals, concern, pain, source)
    reasons += rule_reasons

    # 2) SYMPTOM -> SPECIALTY
    symptom_weight, ranked, matched, ambiguous = _symptoms(concern)
    for kw, sp, w in matched:
        reasons.append(f'"{kw}" -> {sp} (+{w})')
    specialty = ranked[0][0] if ranked else ("Pediatrics" if band == "pediatric" else "General Medicine")

    # 3) ML PREDICTION (calibrated probabilities)
    band_num = 0 if band == "pediatric" else (2 if band == "geriatric" else 1)
    if _MODEL is not None:
        X = pd.DataFrame([[age, band_num,
                           v.get("hr") or 85, v.get("spo2") or 97,
                           v.get("temp") or 36.8, v.get("bp_sys") or 120,
                           pain or 0, symptom_weight,
                           int(source == "ambulance"), len(appearance or [])]],
                          columns=_FEATURES)
        probs = _MODEL.predict_proba(X)[0]  # [p_lower, p_urgent, p_emergency]
        # COST-SENSITIVE DECISION (not argmax): missing a sick patient costs far more
        # than over-calling one, so emergency/urgent trigger at low thresholds.
        if probs[2] >= _T_EMERG:
            ml_cat = "emergency"
        elif probs[1] + probs[2] >= _T_URGENT:
            ml_cat = "urgent"
        else:
            ml_cat = "lower"
        reasons.append(f"ML {_VERSION}: P(emerg)={probs[2]:.2f} P(urgent)={probs[1]:.2f} "
                       f"P(lower)={probs[0]:.2f} -> {ml_cat} "
                       f"(cost-sensitive thresholds {_T_EMERG:.2f}/{_T_URGENT:.2f})")
        confidence = float(np.max(probs))
        score = float(probs[2] * 100 + probs[1] * 45 + symptom_weight * 0.3)
    else:  # rules-only fallback (model file missing)
        ml_cat = "lower"
        confidence, score = 0.5, symptom_weight
        reasons.append("ML unavailable: rules-only fallback")

    # 4) HYBRID MERGE -- most severe wins; the floor can only push UP
    category = ml_cat
    if floor is not None and CATS.index(floor) < CATS.index(ml_cat):
        category = floor
        reasons.append(f"SAFETY FLOOR: rules raise {ml_cat} -> {floor} (floor can never lower)")

    # 5) CONFIDENCE PENALTIES for missing/ambiguous data
    if not v or all(x is None for x in v.values()):
        confidence *= 0.80; reasons.append("no vitals: confidence reduced")
    if not has_history:
        confidence *= 0.93
    if not matched:
        confidence *= 0.75; reasons.append("free text matched no known symptoms: confidence reduced")
    if ambiguous:
        confidence *= 0.86; reasons.append("symptoms point to multiple specialties")
    confidence = round(max(0.20, confidence), 2)

    # 6) ESCALATE UNDER UNCERTAINTY -- never downgrade
    escalated = False
    if confidence < 0.65 and category != "emergency":
        category = CATS[CATS.index(category) - 1]
        escalated = True
        reasons.append(f"confidence {confidence:.0%} < 65% -> escalated one level (never down)")

    return {"category": category, "score": round(score, 1), "confidence": confidence,
            "specialty": specialty, "escalated": escalated, "reasons": reasons,
            "model_version": _VERSION}

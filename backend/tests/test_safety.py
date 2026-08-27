"""Safety properties the system must NEVER violate.
Run with:  pytest -v
Green output here is the strongest 10 seconds of your demo."""
from app.triage.engine import run_triage

ORDER = ["emergency", "urgent", "lower"]  # lower index = more severe

def sev(cat):
    return ORDER.index(cat)

def test_pediatric_fever_more_urgent_than_adult():
    child = run_triage(3, {"hr": 150, "spo2": 96, "temp": 39.0, "bp_sys": 95},
                       "fever", 3, "kiosk", [], True)
    adult = run_triage(30, {"hr": 80, "spo2": 98, "temp": 39.0, "bp_sys": 120},
                       "fever", 3, "kiosk", [], True)
    assert sev(child["category"]) <= sev(adult["category"])
    assert child["category"] in ("emergency", "urgent")

def test_rules_floor_beats_ml():
    # SpO2 87% is a hard emergency floor no ML output can lower,
    # even when the patient says they feel okay.
    r = run_triage(45, {"spo2": 87, "hr": 80, "temp": 36.8, "bp_sys": 125},
                   "feeling okay", 1, "kiosk", [], True)
    assert r["category"] == "emergency"

def test_low_confidence_escalates_never_downgrades():
    # No vitals, no history, unmatched complaint -> confidence collapses -> must go UP
    r = run_triage(40, None, "unwell somehow", 2, "kiosk", [], False)
    assert r["escalated"] is True
    assert r["category"] in ("urgent", "emergency")

def test_geriatric_blunted_fever():
    # 38.1C: below the adult fever threshold, ABOVE the geriatric one
    old = run_triage(78, {"temp": 38.1, "hr": 88, "spo2": 96, "bp_sys": 130},
                     "weakness", 2, "kiosk", [], True)
    assert old["category"] in ("emergency", "urgent")

"""Age-calibrated red-flag rules. Output = the MINIMUM severity allowed.
The ML model can raise severity above this floor, never lower it.
This is deliberately simple, auditable, and clinically conservative."""

def age_band(age: int) -> str:
    return "pediatric" if age < 12 else ("geriatric" if age >= 65 else "adult")

THRESHOLDS = {
    "pediatric": dict(fever_high=39.5, fever_low=38.0, hr_high=160, hr_low=70, bp_shock=80),
    "adult":     dict(fever_high=39.5, fever_low=38.3, hr_high=120, hr_low=50, bp_shock=90),
    # Geriatric fever thresholds are LOWER on purpose: blunted immune response means a
    # "mild" fever in a 75-year-old is a serious signal.
    "geriatric": dict(fever_high=38.0, fever_low=37.5, hr_high=110, hr_low=50, bp_shock=90),
}

RED_FLAG_KEYWORDS = [
    "unconscious", "not breathing", "stroke", "face drooping",
    "slurred speech", "seizure", "severe bleeding", "chest pain",
]

def rules_floor(age, vitals, concern, pain, source):
    """Returns (floor, reasons). floor is 'emergency', 'urgent', or None."""
    t = THRESHOLDS[age_band(age)]
    v = vitals or {}
    reasons, floor = [], None
    order = {"emergency": 0, "urgent": 1}

    def esc(level, why):
        nonlocal floor
        if floor is None or order[level] < order[floor]:
            floor = level
        reasons.append(f"RULE: {why} -> floor={level}")

    if v.get("spo2") is not None:
        if v["spo2"] < 90:
            esc("emergency", f"SpO2 {v['spo2']}% critical hypoxia")
        elif v["spo2"] < 94:
            esc("urgent", f"SpO2 {v['spo2']}% low")
    if v.get("bp_sys") is not None and v["bp_sys"] < t["bp_shock"]:
        esc("emergency", f"BP {v['bp_sys']} possible shock (age-adjusted)")
    if v.get("temp") is not None:
        if v["temp"] >= t["fever_high"] or v["temp"] < 35:
            esc("emergency", f"temp {v['temp']}C extreme for {age_band(age)}")
        elif v["temp"] >= t["fever_low"]:
            esc("urgent", f"fever {v['temp']}C ({age_band(age)}-calibrated)")
    if v.get("hr") is not None and (v["hr"] > t["hr_high"] or v["hr"] < t["hr_low"]):
        esc("urgent", f"HR {v['hr']} abnormal for {age_band(age)}")

    text = (concern or "").lower()
    for kw in RED_FLAG_KEYWORDS:
        if kw in text:
            esc("emergency", f'red-flag phrase "{kw}"')
    if source == "ambulance" and floor is None:
        esc("urgent", "ambulance arrival defaults to at least urgent")
    if age_band(age) == "geriatric" and (pain or 0) <= 3 and floor is not None:
        reasons.append("RULE: geriatric + low self-reported pain + red flags -> pain report treated as unreliable")
    return floor, reasons

"""Lay-language synonym lexicon — figurative/informal phrases -> the engine's
controlled symptom vocabulary. Dependency-free so BOTH the intake NLP and the
triage engine itself can use it: normalization happens at DECISION time, so it
covers every entry path (kiosk voice, typed concern, ambulance form, pre-booking)."""
import re

SYNONYMS = {
    "elephants sitting on my chest": "chest tightness",
    "elephant sitting on my chest": "chest tightness",
    "elephants on my chest": "chest tightness",
    "elephant on my chest": "chest tightness",
    "weight on my chest": "chest tightness",
    "pressure on my chest": "chest tightness",
    "pressure in my chest": "chest tightness",
    "heaviness in my chest": "chest tightness",
    "heaviness in chest": "chest tightness",
    "heavy chest": "chest tightness",
    "chest feels tight": "chest tightness",
    "chest is tight": "chest tightness",
    "crushing pain": "chest pain",
    "squeezing in my chest": "chest pain",
    "heart is racing": "palpitations",
    "heart racing": "palpitations",
    "heart is pounding": "palpitations",
    "heart pounding": "palpitations",
    "skipping beats": "palpitations",
    "fluttering in my chest": "palpitations",
    "can't breathe": "breathless",
    "cant breathe": "breathless",
    "cannot breathe": "breathless",
    "hard to breathe": "breathless",
    "out of breath": "breathless",
    "gasping": "breathless",
    "short of breath": "shortness of breath",
    "head is exploding": "headache",
    "head exploding": "headache",
    "splitting headache": "headache",
    "head is splitting": "headache",
    "pounding in my head": "headache",
    "hammering in my head": "headache",
    "room is spinning": "dizziness",
    "head is spinning": "dizziness",
    "giddy": "dizziness",
    "lightheaded": "dizziness",
    "light headed": "dizziness",
    "tummy ache": "stomach pain",
    "tummy pain": "stomach pain",
    "tummy hurts": "stomach pain",
    "belly ache": "stomach pain",
    "belly pain": "stomach pain",
    "stomach ache": "stomach pain",
    "loose motion": "diarrhea",
    "loose motions": "diarrhea",
    "throwing up": "vomiting",
    "puking": "vomiting",
    "fits": "seizure",
    "convulsions": "seizure",
    "shaking uncontrollably": "seizure",
    "fainted": "unconscious",
    "passed out": "unconscious",
    "blacked out": "unconscious",
    "knocked out": "unconscious",
    "not waking up": "unconscious",
    "won't wake up": "unconscious",
    "face is drooping": "face drooping",
    "face drooped": "face drooping",
    "speech is slurred": "slurred speech",
    "slurring": "slurred speech",
    "words are slurring": "slurred speech",
    "scalded": "burn",
    "burnt": "burn",
    "bone is broken": "broken",
    "gash": "cut",
    "bleeding a lot": "severe bleeding",
    "bleeding heavily": "severe bleeding",
    "blood everywhere": "severe bleeding",
    "expecting a baby": "pregnan",
    "labour pains": "labor",
    "labour pain": "labor",
    "contractions": "labor",
    "burning up": "fever",
    "high temperature": "fever",
    "running a temperature": "fever",
}

# flexible patterns: allow filler words between the key tokens ("elephants ARE sitting on my chest")
REGEX_SYNONYMS = [
    (r"elephants?\b.{0,30}\bchest", {"chest tightness", "chest pain"}),
    (r"(weight|pressure|heaviness|heavy|squeez\w*|crush\w*|tight\w*)\b.{0,20}\bchest", {"chest tightness", "chest pain"}),
    (r"chest\b.{0,20}\b(tight\w*|heavy|pressure|crush\w*|squeez\w*)", {"chest tightness", "chest pain"}),
    (r"head\b.{0,15}\b(explod\w*|split\w*|pound\w*|hammer\w*|burst\w*)", {"headache"}),
    (r"(explod\w*|split\w*|pound\w*)\b.{0,15}\bhead", {"headache"}),
    (r"heart\b.{0,15}\b(rac\w*|pound\w*|flutter\w*|skip\w*)", {"palpitations"}),
    (r"(room|head|everything)\b.{0,15}\bspin\w*", {"dizziness"}),
    (r"(can'?t|cannot|hard to|difficult\w* to)\b.{0,10}\bbreath\w*", {"breathless"}),
    (r"(won'?t|not|isn'?t)\b.{0,12}\bwak\w*\s*up", {"unconscious"}),
    (r"bleed\w*\b.{0,12}\b(a lot|heavil\w*|badly|everywhere|non.?stop)", {"severe bleeding"}),
]


def lay_terms(text: str) -> set:
    """All canonical vocabulary terms whose lay/figurative expression appears in text."""
    t = " " + re.sub(r"\s+", " ", (text or "").lower()) + " "
    found = set()
    for phrase, canonical in SYNONYMS.items():
        if phrase in t:
            found.add(canonical)
    for pattern, canonicals in REGEX_SYNONYMS:
        if re.search(pattern, t):
            found.update(canonicals)
    return found

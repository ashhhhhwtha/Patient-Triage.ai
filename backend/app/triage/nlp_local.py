"""Local intake NLP — NO API keys, runs fully offline, deterministic and auditable.

Three techniques, all local:
1. LAY-LANGUAGE SYNONYM LEXICON: figurative/informal phrases ("100 elephants sitting
   on my chest") -> the engine's controlled symptom vocabulary ("chest tightness").
   Deterministic: the same sentence always normalizes the same way.
2. NAME EXTRACTION: spaCy statistical NER (PERSON entities) when installed, with a
   relationship-aware regex fallback — "my son" is a relationship, never a name.
3. PATTERN + WORD-NUMBER AGE PARSING: "he is 5", "aged 70", "about seventy".

If the optional spaCy model is missing, everything still works via the fallbacks.
"""
import re
from app.triage.engine import KEYWORDS as ENGINE_KEYWORDS

# ---- optional statistical NER (pip install spacy && python -m spacy download en_core_web_sm)
try:
    import spacy
    try:
        _NLP = spacy.load("en_core_web_sm")
    except Exception:
        _NLP = None
except Exception:
    _NLP = None

RED_FLAGS = ["unconscious", "not breathing", "stroke", "face drooping",
             "slurred speech", "seizure", "severe bleeding", "chest pain"]

NOT_NAMES = {"son", "my son", "daughter", "my daughter", "father", "my father", "dad",
             "mother", "my mother", "mom", "mum", "wife", "my wife", "husband",
             "my husband", "brother", "sister", "baby", "child", "kid", "friend",
             "my friend", "grandfather", "grandmother", "grandpa", "grandma", "uncle",
             "aunt", "neighbour", "neighbor", "patient", "someone", "me", "myself",
             "here", "for"}

# lay phrase -> canonical term from the ENGINE's own vocabulary (kept in sync by import)
from app.triage.synonyms import SYNONYMS, REGEX_SYNONYMS

_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
          "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
          "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
          "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}

def _words_to_num(phrase: str):
    parts = re.split(r"[\s-]+", phrase.strip().lower())
    if len(parts) == 1:
        return _TENS.get(parts[0]) or _UNITS.get(parts[0])
    if len(parts) == 2 and parts[0] in _TENS and parts[1] in _UNITS:
        return _TENS[parts[0]] + _UNITS[parts[1]]
    return None

def _extract_age(t: str):
    for pat in (r"\b(\d{1,3})\s*(?:years?\s*old|years?|yrs?|yo)\b",
                r"\b(?:age|aged)\s*(\d{1,3})\b",
                r"\b(?:he|she|i)\s*(?:is|am|'s)\s*(?:about|around|nearly)?\s*(\d{1,3})\b"):
        m = re.search(pat, t)
        if m:
            n = int(m.group(1))
            if 0 < n < 120:
                return n
    for pat in (r"\b(?:about|around|nearly|is|am|aged?)\s+([a-z]+(?:[\s-][a-z]+)?)\s*(?:years?\s*old|years?)?\b",
                r"\b([a-z]+(?:[\s-][a-z]+)?)\s+years?\s*old\b"):
        for m in re.finditer(pat, t):
            cand = m.group(1)
            n = _words_to_num(cand)
            if n is None:
                # capture may have swallowed a qualifier ("about seventy") — retry each token
                for part in re.split(r"[\s-]+", cand):
                    n = _words_to_num(part)
                    if n:
                        break
            if n and 0 < n < 120:
                return n
    return None

def _extract_name(text: str):
    if _NLP:
        doc = _NLP(text)
        for ent in doc.ents:
            if ent.label_ == "PERSON" and ent.text.strip().lower() not in NOT_NAMES \
               and len(ent.text.split()) <= 3:
                return ent.text.strip()
    trig = re.search(r"(?:my name is|name is|i am|this is|his name is|her name is)\s+", text, re.I)
    if trig:
        m = re.match(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", text[trig.end():])
        if m:
            cand = m.group(1).strip()
            tokens = [w.lower() for w in cand.split()]
            if cand.lower() not in NOT_NAMES and not any(w in NOT_NAMES for w in tokens):
                return cand
    return None

_F_HINTS = ["she", "her", "female", "woman", "girl", "wife", "mother", "daughter",
            "sister", "grandmother", "grandma", "aunt", "mrs", "pregnant"]
_M_HINTS = ["he", "his", "him", "male", "man", "boy", "husband", "father", "son",
            "brother", "grandfather", "grandpa", "uncle", "mr"]

def _extract_gender(t: str):
    f = sum(len(re.findall(rf"\b{h}\b", t)) for h in _F_HINTS)
    m = sum(len(re.findall(rf"\b{h}\b", t)) for h in _M_HINTS)
    if f > m:
        return "F"
    if m > f:
        return "M"
    return None

def extract_fields(text: str) -> dict:
    """Same output shape as the old LLM extractor — the frontend never knows."""
    t = " " + re.sub(r"\s+", " ", (text or "").lower()) + " "

    symptoms = set()
    for phrase, canonical in SYNONYMS.items():
        if phrase in t:
            symptoms.add(canonical)
    for pattern, canonicals in REGEX_SYNONYMS:
        if re.search(pattern, t):
            symptoms.update(canonicals)
    for kw in ENGINE_KEYWORDS:            # direct vocabulary mentions count too
        if kw in t:
            symptoms.add(kw)

    red_flags = [f for f in RED_FLAGS if f in t or f in symptoms]

    return {
        "name": _extract_name(text or ""),
        "age": _extract_age(t),
        "gender": _extract_gender(t),
        "concern": (text or "").strip(),
        "symptoms": sorted(symptoms),
        "red_flags": red_flags,
        "engine": "local-nlp" + ("+spacy" if _NLP else ""),
    }

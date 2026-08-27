<div align="center">

# 🏥 PatientTriage.ai

### AI-powered emergency department triage — where the clinician is always in charge

*A hybrid rules + machine-learning system that prioritizes patients safely, explains every
decision in seconds, learns from nurses, and escalates when uncertain — never the other way.*

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![scikit--learn](https://img.shields.io/badge/scikit--learn-calibrated_LR-F7931E?logo=scikitlearn&logoColor=white)
![WebSockets](https://img.shields.io/badge/WebSockets-live_queue-purple)
![Voice AI](https://img.shields.io/badge/voice-Whisper_+_Llama_3.3-8A2BE2)
![Tests](https://img.shields.io/badge/safety_tests-4%2F4_passing-brightgreen)
![Under-triage](https://img.shields.io/badge/under--triage_rate-3.3%25-blue)
![Emergencies missed](https://img.shields.io/badge/emergencies_classified_%22lower%22-0-critical)

</div>

---

## 📑 Table of Contents

1. [The Problem](#-the-problem)
2. [Our Solution in One Paragraph](#-our-solution-in-one-paragraph)
3. [System Architecture](#-system-architecture)
4. [The Triage Engine — How a Decision Is Made](#-the-triage-engine--how-a-decision-is-made)
5. [The Machine Learning Methodology](#-the-machine-learning-methodology)
6. [Measured Results](#-measured-results)
7. [Every Screen, Every Role](#-every-screen-every-role)
8. [The Learning Loop — Nurses Teach the Model](#-the-learning-loop--nurses-teach-the-model)
9. [Safety Engineering & the Test Suite](#-safety-engineering--the-test-suite)
10. [Challenge Requirements → Where We Solved Them](#-challenge-requirements--where-we-solved-them)
11. [Security, Privacy & Compliance](#-security-privacy--compliance)
12. [Scalability — Rural Clinic to Trauma Center](#-scalability--rural-clinic-to-trauma-center)
13. [Tech Stack & Why Each Choice](#-tech-stack--why-each-choice)
14. [Run It Locally](#-run-it-locally)
15. [The 60-Second Demo](#-the-60-second-demo)
16. [Project Structure](#-project-structure)
17. [Honest Limitations & Roadmap](#-honest-limitations--roadmap)

---

## 🚨 The Problem

Emergency departments lose patients to bad **queues**, not bad doctors. Triage happens in
seconds, under pressure, with incomplete information — a returning patient may have a rich
record on file while a first-timer has nothing beyond what a nurse can observe in the moment.
And the cost of error is brutally asymmetric: **sending a heart attack to the waiting room is
categorically worse than fast-tracking a sprained ankle.**

Most triage tools quietly make three mistakes:

1. **One adult-calibrated model for every age.** A 38.5 °C fever is routine in an adult,
   alarming in a 3-year-old, and — because immune response blunts with age — a genuinely
   dangerous signal in a 75-year-old. A single threshold under-triages the very patients who
   present most atypically.
2. **Optimizing for average accuracy.** Accuracy treats both error directions the same. Triage
   must not: under-triage kills, over-triage merely inconveniences.
3. **Black-box scores.** A nurse juggling five patients cannot trust a number she can't verify
   in five seconds — so staff work around the tool, and the tool dies.

PatientTriage.ai is engineered against all three, end to end.

## 💡 Our Solution in One Paragraph

A patient checks in by **speaking naturally at a kiosk** (or is entered by an **ambulance
crew en route**): **Whisper** transcribes the speech and an **LLM (Llama 3.3 70B) extracts**
name, age, symptoms and red flags from the messy narrative — returning patients are
**recognised against their previous visits**, linking history that raises triage confidence.
Connected devices capture vitals; a nurse or the patient records how they look. A **hybrid
triage engine** — an auditable rules layer fused with a trained, calibrated ML model — assigns
one of three categories (**Emergency / Urgent / Lower Urgency**), a **specialty routing**
(Cardiology, Pediatrics, …), a **confidence score**, and a human-readable list of reasons.
Low confidence **escalates the patient upward, never down**. Every screen in the hospital —
queue board, nurse review, doctor console, the patient's own phone — shares **one live queue
over WebSockets**. Nurses confirm or override with mandatory reasons; overrides **retrain the
model**. Doctors prescribe digitally; the prescription lands on the patient's phone as a
**signed PDF**. A background monitor **re-flags anyone waiting past the safe threshold** for
their severity. Every action, human or AI, lands in an **append-only audit trail**.

## 🏗 System Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │                REACT FRONTEND (Vite)             │
                    │  Kiosk · Ambulance · Queue Board · Nurse Review  │
                    │  Doctor Console · Patient Portal · Audit Trail   │
                    └───────────────┬───────────────────┬─────────────┘
                          REST (axios + JWT)    WebSocket (live queue)
                    ┌───────────────┴───────────────────┴─────────────┐
                    │                 FASTAPI BACKEND                  │
                    │  auth (JWT roles) · patients · queue · overrides │
                    │  prescriptions · transcribe (Whisper) · /ws hub  │
                    │  background re-assessment monitor (every 30 s)   │
                    └───────┬──────────────────┬──────────────────────┘
                    ┌───────┴────────┐  ┌──────┴───────────────────────┐
                    │ HYBRID TRIAGE  │  │  SQLAlchemy ORM              │
                    │    ENGINE      │  │  SQLite (dev) → PostgreSQL   │
                    │ (see below)    │  │  via ONE env var             │
                    └────────────────┘  └──────────────────────────────┘
```

## 🧠 The Triage Engine — How a Decision Is Made

Every patient flows through three layers. This is the heart of the project:

```
 patient speaks freely ──► WHISPER (speech → text, neural)
        │
        ▼
 ⓪  LLM CLINICAL INTAKE  (Llama 3.3 70B — /extract)
     Understands the messy narrative → structured fields + RED FLAGS.
     Detected red flags are appended into the concern text so the rules
     floor sees them. THE LLM INFORMS TRIAGE — IT NEVER DECIDES SEVERITY.
     (Regex fallback if the LLM is unavailable — intake can never break.)
        │
        ▼
 patient data (concern + red flags · vitals · pain · appearance · history · source)
        │
        ├──► ①  RULES SAFETY FLOOR  (app/triage/rules.py)
        │       Age-calibrated red flags set a MINIMUM severity.
        │       SpO₂ < 90% → emergency. BP < 90 (age-adjusted) → emergency.
        │       Fever thresholds differ by band: pediatric 38.0 · adult 38.3
        │       · geriatric 37.5 (blunted immune response = lower bar).
        │       Red-flag phrases ("unconscious", "stroke", "chest pain") floor
        │       to emergency. Ambulance arrivals floor at urgent.
        │       ➜ The ML may RAISE severity above this floor. Never lower it.
        │
        └──► ②  CALIBRATED ML MODEL  (app/triage/engine.py)
                Logistic regression over 10 features (age, age-band, HR, SpO₂,
                temp, BP, pain, symptom weight, ambulance flag, appearance
                count), Platt-calibrated so its probabilities are honest.
                COST-SENSITIVE DECISION RULE — we do NOT take the most likely
                class: emergency triggers at P ≥ 0.10, urgent at P ≥ 0.30,
                because missing a sick patient costs far more than over-calling.
                        │
                        ▼
              HYBRID MERGE: the most severe of ① and ② wins
                        │
                        ▼
        ③  ESCALATION UNDER UNCERTAINTY
            Confidence = calibrated max-probability, penalized for missing
            vitals, no prior record, unmatched free text, or symptoms pointing
            to multiple specialties. If confidence < 65% and the category is
            not already Emergency → move the patient UP one level.
            The system can never talk itself into downgrading a patient.
```

**Worked example — the ambiguous case the brief warns about.** *Priya, 29, "chest tightness
and palpitations, also anxiety", HR 104, no prior record.* Keywords split between Cardiology
and a benign explanation; her vitals are borderline. An accuracy-optimized model files her
under "lower priority." Our engine: the symptom weights route her to **Cardiology**, the
calibrated model's emergency probability crosses the 0.10 cost-sensitive threshold, and her
missing history further depresses confidence — she surfaces as **Emergency, Cardiology**, with
every step of that reasoning printed for the nurse to confirm or override. *Chest pain that
might be anxiety is exactly the patient triage systems exist to protect.*

**Three AI models in one pipeline:** Whisper *hears* the patient, an LLM *understands*
them, and a calibrated ML model *decides* the risk — generative AI where language lives,
measurable AI where lives depend on it.

**Why three levels instead of the standard five?** Five-level scales (ESI/CTAS) exist partly
to manage resource-assignment granularity. For decision support at the door we collapse to the
three distinctions that change *behaviour*: see-now (Emergency), see-soon (Urgent),
safe-to-wait (Lower Urgency) — a fatigued nurse acting in seconds needs an answer, not a
taxonomy. The underlying score and calibrated probabilities remain continuous, so a five-level
presentation is a configuration change, not a redesign.

**Explainability is not a feature — it's the interface.** Every decision ships with its full
reason list, e.g.:

```
RULE: fever 39.2C (pediatric-calibrated) -> floor=urgent
"breathing" -> Pulmonology (+28)
ML hybrid-v1: P(emerg)=0.34 P(urgent)=0.51 P(lower)=0.15 -> urgent (cost-sensitive thresholds 0.10/0.30)
confidence 58% < 65% -> escalated one level (never down)
```

A nurse reads that in five seconds and knows exactly what the machine saw.

## 🔬 The Machine Learning Methodology

- **Training data:** 20,000 synthetic ED encounters generated from published vital-sign
  reference ranges, with a latent acuity variable driving both vitals and labels — including
  age-dependent effects (pediatric tachycardia norms, geriatric pain under-reporting).
  **We state this openly**: the pipeline is dataset-agnostic and accepts a real dataset
  (e.g. MIMIC-IV-ED) with zero code changes.
- **Model:** logistic regression inside a scikit-learn pipeline, wrapped in
  `CalibratedClassifierCV` — so the confidence number shown to clinicians is a *statistically
  meaningful probability*, not a vibe.
- **Asymmetric costs, twice:** class weights `{lower:1, urgent:2, emergency:5}` during
  training, **and** cost-sensitive decision thresholds at inference. Found the hard way: our
  first argmax-based version scored 15% under-triage in testing; thresholding cut it to 3.3%.
  That discovery-and-fix is part of our story, not hidden.
- **Why not deep learning / an LLM deciding severity?** Triage decisions must be explainable
  in seconds and defensible in an audit. LR coefficients *are* the explanation. Where an LLM
  helps — structuring messy speech into fields — we use one; it **never** decides severity.

## 📊 Measured Results

Held-out test set (4,000 encounters), evaluated under the deployed decision rule:

| Metric | Value | Meaning |
|---|---|---|
| **Under-triage rate** | **3.3 %** | truly-sicker patients ranked less urgent — *the* metric |
| **True emergencies classified "lower"** | **0** | the worst failure mode: eliminated |
| Over-triage rate | 28.7 % | **deliberate** — we bias toward escalation, as the brief demands |
| Safety test suite | **4 / 4 ✅** | `pytest -v`, see below |
| Live decision latency | < 50 ms | rules + LR inference is effectively instant |

```
Confusion matrix (rows = truth, cols = prediction)
               pred_lower  pred_urgent  pred_emerg
true_lower           1677          734          10
true_urgent           117          883         406
true_emerg              0           16         157      ← zero in "lower"
```

## 🖥 Every Screen, Every Role

| Role | Screen | What happens there |
|---|---|---|
| 🎤 **Patient** | Kiosk | Speaks naturally (browser mic **or** Whisper HD voice); an **LLM extracts** name, age, gender, concern and red flags from the raw speech; **returning patients are recognised** ("Welcome back — last visit linked") which raises triage confidence; connected devices capture SpO₂/BP/temp/HR; appearance recorded and confirmed |
| 🚑 **Ambulance crew** | Pre-arrival entry | Details + vitals entered en route; patient joins the queue **before arriving**, floored at Urgent |
| 📺 **Charge nurse** | Live Queue Board | One live queue, grouped **by department** (each doctor's crowd, emergency-first within it) with a by-severity toggle; amber re-assessment flags |
| 👩‍⚕️ **Nurse** | Nurse Review | Full AI reasoning per patient; confirm or **override with a mandatory reason**; re-record vitals → automatic re-triage |
| 🩺 **Doctor** | Doctor Console | Signs in to a **department-locked** queue (Cardiology sees only Cardiology); writes the e-prescription; one click sends it |
| 📱 **Patient** | Patient Portal | Live queue position + honest wait estimate, notifications, **PDF prescription download**, and **emergency pre-booking** from home |
| 📋 **Everyone** | Audit Trail | Append-only record of every registration, AI decision, override, re-vitals, surge, and prescription — with actor and time |

**Cross-cutting:** every mutation broadcasts over WebSockets, so a kiosk check-in appears on
the charge nurse's board **in under a second, no refresh**. A **⚡ 3× surge simulation**
floods the queue on demand; the background monitor then starts flagging anyone waiting past
the safe threshold for their category (Emergency 10 min · Urgent 30 · Lower 120).

## 🔁 The Learning Loop — Nurses Teach the Model

```
nurse override (mandatory reason) ──► overrides table ──► audit trail
                                            │
                                   ml/retrain.py (nightly)
                                            │
                     override cases folded in at 3× sample weight
                                            │
                          new model saved · version bumps to
                          hybrid-v1.1-retrained · visible in every
                          subsequent decision's provenance
```

Clinician judgement outweighs synthetic data by design. The model version is stamped on every
triage record, so the audit trail always shows **which brain made which decision**.

## 🛡 Safety Engineering & the Test Suite

Four properties the system must never violate, enforced by `tests/test_safety.py`:

| Test | Guarantee |
|---|---|
| `test_pediatric_fever_more_urgent_than_adult` | The same fever is treated as more serious in a 3-year-old than a 30-year-old |
| `test_rules_floor_beats_ml` | SpO₂ 87% is an emergency **even if the patient says they feel fine** — no ML output can lower a rules floor |
| `test_low_confidence_escalates_never_downgrades` | An unrecognized complaint with no vitals and no history must move **up**, never quietly sit in "lower" |
| `test_geriatric_blunted_fever` | 38.1 °C — below the adult threshold — still escalates a 78-year-old |

```bash
python -m pytest -v      # ➜ 4 passed
```

## ✅ Challenge Requirements → Where We Solved Them

| Round 2 brief requirement | Our implementation |
|---|---|
| Age-calibrated severity (pediatric/adult/geriatric) | Banded thresholds in `rules.py` + age features in the ML — demonstrated by two live cases (3yo @ 39.2° and 78yo @ 37.6° both flag; an adult at 37.6° doesn't) |
| Bias toward escalation under uncertainty — shown explicitly | Three mechanisms: rules floor, cost-sensitive thresholds (P≥0.10 → emergency), confidence <65% → escalate. 28.7% over-triage accepted **on purpose**; safety test enforces it |
| Explainable within seconds | Every decision carries a plain-language reason list; nurses see it before confirming |
| No score without a confidence indicator | Calibrated confidence on every patient card (ring UI), penalized for missing data |
| 15–20 simulated patients incl. ambiguous, pediatric/geriatric, zero-history | **16-patient seed**: Priya (cardiac-vs-anxiety, ambiguous), Aarav (3, pediatric), Bimala (78, under-reporting), an unknown accident victim with no record, ambulance arrivals, stroke, asthma, obstetric and more |
| Surge behavior (~3× volume) | `/patients/demo/surge` endpoint + one-click UI; emergencies stay pinned, wait estimates stretch honestly |
| Monitor waiting patients; re-assess past safe thresholds or on worsening vitals | 30-second background monitor flags overdue patients live; re-recorded vitals trigger automatic re-triage |
| Clinician override, reviewable, with audit trail | Mandatory-reason overrides, nurse-role-only, append-only audit — **one override ships pre-captured in the seed data** so the log demonstrates it on first view |
| Mixed data availability (~half with records) | `has_history` drives confidence → escalation; **returning-patient lookup** links prior completed visits at check-in (demo by name; production via MRN/ABHA through the EHR); zero-history seed case included |
| Stated regulatory jurisdiction | India DPDP Act 2023; consent/retention module swappable for HIPAA/GDPR |
| Adoption by fatigued staff | Five-second explainability, one-tap confirm, overrides that visibly teach the model, and the AI never blocks a human decision |

## 🔒 Security, Privacy & Compliance

- **JWT authentication with server-side role enforcement** — a nurse account *physically
  cannot* sign a prescription; the API returns `403`. Kiosk, nurse, and doctor see different
  tabs and different data.
- **Append-only audit trail** — no update or delete endpoints exist for it, by construction.
- **Decision provenance** — every triage record stores the engine version that produced it.
- **Data protection posture** — encrypted in transit, role-based access, jurisdiction stated
  as **India (DPDP Act 2023)**; the consent + retention layer is a swappable module for
  HIPAA / GDPR deployments.
- **On-premise friendly** — everything except optional Whisper voice runs fully local, which
  answers hospital data-residency requirements.

## 📈 Scalability — Rural Clinic to Trauma Center

Same engine, different configuration:

| Dimension | Rural clinic | Urban trauma center |
|---|---|---|
| Intake | Nurse tablet (kiosk optional) | Voice kiosks + ambulance pre-arrival feed |
| Specialties | 2–3 active | All 9 departments |
| Notifications | SMS fallback | Push + portal |
| Database | SQLite on one machine | PostgreSQL (`DATABASE_URL` env var — one-line swap) |
| Deployment | Single laptop | On-prem Docker / cloud |

The thresholds, categories, and safe-wait limits are configuration, not code.

## 🛠 Tech Stack & Why Each Choice

| Layer | Choice | Why |
|---|---|---|
| Frontend | React 18 + Vite + Tailwind | Fast to build, professional UI, instant hot reload |
| Backend | FastAPI | Async, WebSocket-native, and auto-generates interactive API docs at `/docs` |
| Database | SQLAlchemy: SQLite → PostgreSQL | The entire migration is one environment variable |
| ML | scikit-learn LR + `CalibratedClassifierCV` | Explainable by construction; calibrated confidence is honest |
| Real-time | FastAPI WebSockets | One live queue across every screen in the hospital |
| Auth | PyJWT, role claims | Clinical accountability enforced at the API, not the UI |
| Voice & language | Web Speech API + Whisper (`whisper-large-v3`) + **Llama 3.3 70B extraction** | Works offline day one; HD path handles Indian-English accents; the LLM structures speech into fields + red flags — and never decides severity |
| PDF | jsPDF | Prescription downloads with zero backend load |

## 🚀 Run It Locally

```bash
git clone https://github.com/YOUR_USERNAME/patient-triage-ai.git
cd patient-triage-ai
```

**Backend** (terminal 1):
```bash
cd backend
python -m venv venv
venv\Scripts\Activate.ps1          # Windows · Mac/Linux: source venv/bin/activate
pip install -r requirements.txt

python ml/generate_data.py          # 20k synthetic encounters
python ml/train.py                  # trains + calibrates, prints the under-triage rate
python -m pytest -v                 # 4 safety tests must pass
python seed.py                      # demo patients

# optional — enables HD voice (Whisper) + LLM intake extraction
# (free key at console.groq.com; everything else runs without it):
# $env:GROQ_API_KEY = "gsk_..."

python -m uvicorn app.main:app --reload
```
Watch for the boot line: `[triage] loaded ML model hybrid-v1` — the hybrid engine is live.

**Frontend** (terminal 2):
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** · interactive API docs at **http://localhost:8000/docs**

| Username | Password | Role |
|---|---|---|
| `kiosk` | `kiosk123` | Reception kiosk |
| `nurse1` | `nurse123` | Nurse — review, override, re-vitals |
| `doc1` | `doctor123` | Dr. A. Choudhury — Cardiology |
| `doc2` | `doctor123` | Dr. S. Bhattacharya — Pediatrics |

## ⚡ The 60-Second Demo

1. Open **two browser windows**: nurse (Queue Board) and kiosk (check-in), side by side
2. **Speak** a messy check-in — *"this is for my father, he's about seventy, his face is
   drooping and his speech is slurred"* — the **LLM extracts** the fields and red flags, the
   rules floor catches them, and the patient lands **Emergency / Neurology** on the nurse's
   board **in under a second** — no refresh, that's the WebSocket
2½. Type a past patient's name → **🔎 Find my previous record** → *"Welcome back"* — history
   linked, confidence up
3. Nurse opens the patient → reads the AI's full reasoning → overrides with a reason → the
   board reshuffles live
4. Doctor (department-locked) prescribes → the patient's portal pops a notification → **PDF
   downloads**
5. Hit **⚡ Simulate 3× surge** → the board floods; within a minute the monitor starts
   flagging overdue patients for re-assessment
6. Open the Audit Trail: every step above is there, with actor and timestamp

## 📁 Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app · WebSocket hub · re-assessment monitor
│   ├── auth.py              # JWT + role enforcement (nurse ≠ doctor ≠ kiosk)
│   ├── models.py            # patients · vitals · triage · overrides · prescriptions · audit
│   ├── ws.py                # live broadcast manager
│   ├── triage/
│   │   ├── rules.py         # age-calibrated safety floor
│   │   └── engine.py        # hybrid engine: rules + calibrated ML + escalation
│   └── routers/             # auth · patients (+surge +lookup) · queue · overrides ·
│                            # prescriptions · transcribe (Whisper + LLM /extract)
├── ml/
│   ├── generate_data.py     # 20k synthetic ED encounters
│   ├── train.py             # train + calibrate + cost-sensitive evaluation
│   └── retrain.py           # learn-from-nurse-overrides loop (3× weight)
├── tests/test_safety.py     # the 4 guarantees the system must never violate
└── seed.py                  # demo patients (ambiguous · pediatric · geriatric · no-history)
frontend/
└── src/
    ├── App.jsx              # all 7 role screens, live over WebSocket
    └── api.js               # REST + WebSocket client
```

## 🗺 Honest Limitations & Roadmap

**What's simulated in the demo:** device readings (the capture button generates plausible
values) and the patient data. **What's real:** the trained model, the calibration, the API,
the auth, the WebSockets, the audit trail, the voice transcription.

**Known limitations we'd tackle next:**
- [ ] **FHIR resource layer** — interoperability with hospital record systems
- [ ] **Web Bluetooth** — live readings from real pulse oximeters and BP cuffs
- [ ] **Real clinical dataset** (MIMIC-IV-ED) through the existing, unchanged pipeline
- [ ] **Multilingual voice** — Assamese · Hindi · English code-switching at the kiosk
- [ ] **SMS notifications** for patients without smartphones
- [ ] **Docker Compose** one-command on-premise deployment + per-hospital config profiles
- [ ] Cross-visit identity via **MRN/ABHA number** through the EHR (demo lookup is name-based, honestly labeled)
- [ ] Keyword symptom weights → embedding-based matching (typo- and phrasing-robust)

---

<div align="center">

**Three independent layers against under-triage: a rules floor the ML can never lower,
cost-sensitive decision thresholds, and escalation under uncertainty.**

*Decision support, not decision replacement — the clinician is always in charge.*

Built for the PatientTriage.ai Challenge · Round 2

</div>

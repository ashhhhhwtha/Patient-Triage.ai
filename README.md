<div align="center">

# 🏥 PatientTriage.ai

### AI-powered emergency department triage — where the clinician is always in charge

*A hybrid rules + machine-learning system that prioritizes patients safely,
explains every decision in seconds, and escalates when uncertain — never the other way.*

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![scikit--learn](https://img.shields.io/badge/scikit--learn-calibrated_LR-F7931E?logo=scikitlearn&logoColor=white)
![Tests](https://img.shields.io/badge/safety_tests-4%2F4_passing-brightgreen)
![Under-triage](https://img.shields.io/badge/under--triage_rate-3.3%25-blue)

</div>

---

## 🚨 The Problem

Emergency departments lose patients to bad **queues**, not bad doctors. Triage decisions are made
in seconds, under pressure, with incomplete information — and the cost of mistakes is brutally
asymmetric: **sending a heart attack to the waiting room is categorically worse than
fast-tracking a sprained ankle.**

Most triage tools make three silent mistakes:
1. One adult-calibrated model for every age — a 38.5 °C fever means very different things in a toddler, an adult, and a 75-year-old
2. Optimizing for average accuracy instead of minimizing the *dangerous* kind of error
3. Black-box scores a nurse can't verify in five seconds — so staff work around the tool

PatientTriage.ai is built against all three.

## 🧠 The Architecture — Three Layers Against Under-Triage

```
 patient data (voice · vitals devices · observation · history)
        │
        ├──► ①  RULES SAFETY FLOOR
        │       age-calibrated red flags set a MINIMUM severity
        │       (the ML can raise it — never lower it)
        │
        └──► ②  CALIBRATED ML MODEL  (logistic regression, Platt-calibrated)
                cost-sensitive decision thresholds — emergency triggers
                at P ≥ 0.10, because missing a sick patient costs 5× more
                        │
                        ▼
              most severe verdict wins
                        │
                        ▼
        ③  confidence < 65% ? → ESCALATE one level. Never downgrade.
```

**Measured results** (20 000-encounter held-out test set):

| Metric | Value | Note |
|---|---|---|
| Under-triage rate | **3.3 %** | the metric that matters |
| True emergencies classified "lower" | **0** | zero, by design |
| Over-triage rate | 28.7 % | *deliberate* — we bias toward escalation |
| Safety test suite | 4 / 4 ✅ | `pytest -v` |

## ✨ Features

| Role | What they get |
|---|---|
| 🎤 **Patient (kiosk)** | Voice check-in (browser mic + Whisper HD), connected vitals devices (SpO₂ · BP · temp · HR), appearance capture |
| 🚑 **Ambulance crew** | Pre-arrival entry en route — patient joins the queue before reaching the door, floored at Urgent |
| 👩‍⚕️ **Nurse** | Full AI reasoning per patient, one-tap confirm, mandatory-reason overrides that **retrain the model nightly**, live re-vitals → automatic re-triage |
| 🩺 **Doctor** | Department-locked queue (Cardiology sees only Cardiology), e-prescriptions signed & pushed to the patient's phone |
| 📱 **Patient portal** | Live queue position & wait estimate, notifications, **PDF prescription download**, emergency pre-booking from home |
| 📊 **Everyone** | One live queue over **WebSockets** — every screen updates in under a second, no refresh |

Plus: **3× surge simulation**, a background monitor that flags anyone waiting past the safe
threshold for their severity, JWT role security (a nurse account *physically cannot* prescribe —
the API returns 403), and an **append-only audit trail** of every registration, decision,
override, and prescription.

## 🛠️ Tech Stack

**Frontend** React 18 · Vite · Tailwind CSS · jsPDF · Web Speech API
**Backend** FastAPI · SQLAlchemy (SQLite dev → PostgreSQL via one env var) · WebSockets · PyJWT
**ML** scikit-learn — logistic regression + `CalibratedClassifierCV`, cost-sensitive thresholds
**Voice** Browser speech recognition, upgradable to Whisper (`whisper-large-v3` via Groq)

## 🚀 Run It Locally

```bash
git clone https://github.com/ashhhhhwtha/Patient-Triage.ai.git
cd Patient-Triage.ai
```

**Backend** (terminal 1):
```bash
cd backend
python -m venv venv
venv\Scripts\Activate.ps1        # Windows · Mac/Linux: source venv/bin/activate
pip install -r requirements.txt

python ml/generate_data.py       # 20k synthetic encounters
python ml/train.py               # trains + calibrates, prints under-triage rate
python -m pytest -v              # 4 safety tests must pass
python seed.py                   # demo patients

# optional — HD voice via Whisper:
# $env:GROQ_API_KEY = "gsk_..."  (free key: console.groq.com)

python -m uvicorn app.main:app --reload
```

**Frontend** (terminal 2):
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** · interactive API docs at **http://localhost:8000/docs**

### Demo accounts

| Username | Password | Role |
|---|---|---|
| `kiosk` | `kiosk123` | Reception kiosk |
| `nurse1` | `nurse123` | Nurse (review, override, re-vitals) |
| `doc1` | `doctor123` | Dr. A. Choudhury — Cardiology |
| `doc2` | `doctor123` | Dr. S. Bhattacharya — Pediatrics |

### The 60-second wow

Open **two browser windows**: nurse on the Queue Board, kiosk on check-in.
Speak a check-in in one → the patient appears on the other **in under a second**.
Then hit **⚡ Simulate 3× surge** and watch the monitor start flagging overdue patients.

## 🔬 The Learning Loop

Every nurse override is stored with a mandatory reason, audited, and folded back into
training at **3× sample weight** — the model learns from clinicians, never the reverse:

```bash
python ml/retrain.py     # → model_version bumps to hybrid-v1.1-retrained
```

## 🔒 Compliance & Safety Posture

- **Clinician-in-the-loop by construction** — the AI never has the last word
- **Append-only audit trail** — no update/delete endpoints exist for it
- **Server-side role enforcement** — JWT roles, prescription requires `doctor`
- **Stated jurisdiction:** India DPDP Act 2023 (consent + retention module swappable for HIPAA / GDPR)
- **Honest data provenance:** trained on synthetic encounters generated from published
  vital-sign reference ranges; the pipeline accepts real datasets (e.g. MIMIC-IV-ED) unchanged

## 📁 Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app · WebSocket hub · re-assessment monitor
│   ├── auth.py              # JWT + role enforcement
│   ├── models.py            # patients · vitals · triage · overrides · audit
│   ├── ws.py                # live broadcast manager
│   ├── triage/
│   │   ├── rules.py         # age-calibrated safety floor
│   │   └── engine.py        # hybrid engine (rules + calibrated ML + escalation)
│   └── routers/             # auth · patients · queue · overrides · prescriptions · transcribe
├── ml/
│   ├── generate_data.py     # synthetic ED encounters
│   ├── train.py             # train + calibrate + cost-sensitive evaluation
│   └── retrain.py           # nightly learn-from-overrides loop
├── tests/test_safety.py     # the 4 guarantees the system must never violate
└── seed.py
frontend/
└── src/
    ├── App.jsx              # all 7 role screens
    └── api.js               # REST + WebSocket client
```

## 🗺️ Roadmap

- [ ] FHIR resource layer for hospital-records interoperability
- [ ] Web Bluetooth — live readings from real pulse oximeters / BP cuffs
- [ ] Multilingual voice check-in (Assamese · Hindi · English code-switching)
- [ ] SMS notifications for patients without smartphones
- [ ] Docker Compose one-command on-premise deployment
- [ ] Per-hospital config profiles (rural clinic → urban trauma center)

---

<div align="center">

*Built for the PatientTriage.ai challenge (Round 2).*
**Decision support, not decision replacement — the clinician is always in charge.**

</div>

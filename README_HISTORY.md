# History Pack — "Previous visits" panel on the Doctor Console

History stops being an invisible confidence nudge and becomes visible clinical
value: when a doctor selects a patient, the console shows their prior completed
visits, AI-summarized, with a **related to today** badge on visits that map to
the same specialty or share meaningful symptom keywords.

Design mirrors the intake philosophy: a **deterministic digest is the floor**
(runs offline, fully auditable), and an **LLM simplification layers on top only
if a GROQ/GEMINI key is set** — facts only, no invented advice, never decides
urgency. Any LLM failure silently falls back to the deterministic summary.

## Files in this pack (apply in this order)

1. `backend/app/routers/patients.py`  — FULL REPLACEMENT.
   Adds `GET /patients/{id}/history` (nurse/doctor roles only). No other
   endpoint changed. No database schema change — uses existing tables.
2. `backend/seed.py`                  — FULL REPLACEMENT.
   Adds 4 completed PRIOR visits (backdated, with prescriptions) before the
   existing 16 waiting patients:
   - Ramesh Kalita — prior exertional chest pain (126d ago)  -> RELATED
   - Farhan Ali    — prior wheezing / night cough (64d ago)  -> RELATED
   - Anjali Roy    — prior lower back pain (210d ago)        -> RELATED
   - Lakshmi Gogoi — prior knee arthritis flare (95d ago)    -> UNRELATED
3. `frontend/src/App.jsx`             — FULL REPLACEMENT.
   Built on the patient-view-pack version (duty doctor doc3 included).
   Adds: `getHistory` import, `History` icon import, `HistoryPanel` component,
   and the panel inside DoctorView (between the concern box and vitals line).
4. `frontend/src/api.js`              — ONE LINE TO ADD YOURSELF (file not in
   this pack). Copy the style of your existing `getCompleted` /
   `getPrescription` helpers, e.g.:

   ```js
   export const getHistory = (id) => api.get(`/patients/${id}/history`).then((r) => r.data);
   ```

   (Replace `api` with whatever your axios instance is named in that file.)

## Fresh database required

The prior visits must exist in the DB, so re-seed cleanly:

```
cd backend
# delete the old SQLite file (whatever yours is named, e.g. triage.db / app.db)
python seed.py
python -m uvicorn app.main:app --reload
```

Watch the seed output — it prints the 4 prior visits first, then the 16
waiting patients as before.

## Verify (60 seconds)

1. Log in as **Dr. A. Choudhury — Cardiology** → select **Ramesh Kalita**.
   → violet "Previous visits · AI summary" panel: 1 prior visit, badge
   **related to today**, prior Rx (Ecosprin / Sorbitrate) visible.
2. Log in as **Dr. M. Begum — Duty Doctor** → select **Lakshmi Gogoi**
   (fever + cough today). → prior knee-arthritis visit shows badge
   **unrelated** — the relevance flag stays honest when history doesn't apply.
3. Select **Priya Das** (or any first-timer) → "First recorded visit — no
   prior history on file."
4. Sanity: check the related/unrelated flags in the seed output match what
   you see — if the engine routes a prior visit to an unexpected specialty,
   the keyword overlap still catches Ramesh/Anjali; Farhan relies on both
   specialty and no keyword overlap, so confirm his badge fires.

## The judge line

"History doesn't just raise a confidence number — the doctor sees WHY.
Prior visits are summarized in two lines with an explicit relevance flag,
built deterministically so it runs air-gapped and stays auditable; an LLM
only rephrases the same facts when a key exists, and it never adds clinical
content or decides urgency. Linked by name for the demo; production links
via MRN/ABHA through the EHR."

## After this: commit + deploy (still the critical path)

git add . && git commit -m "Doctor console: AI-summarized previous-visit history" && git push

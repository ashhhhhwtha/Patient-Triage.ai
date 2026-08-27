UPGRADE PACK — AI voice understanding · returning-patient recognition · repo hygiene

===== FILE PLACEMENT =====
  backend/app/routers/transcribe.py   -> REPLACE (or create) backend\app\routers\transcribe.py
  backend/app/routers/patients.py     -> REPLACE backend\app\routers\patients.py
  frontend/src/api.js                 -> REPLACE frontend\src\api.js
  frontend/src/App.jsx                -> REPLACE frontend\src\App.jsx

main.py: no change needed IF you already added transcribe to the imports + router
loop earlier. Verify both lines mention "transcribe"; if not, add it.

===== APPLY =====
Backend terminal:  Ctrl+C the server, then:
    pip install requests
    $env:GROQ_API_KEY = "gsk_your_key"
    python -m uvicorn app.main:app --reload
Frontend: files hot-reload; hard-refresh the browser (Ctrl+Shift+R).

===== WHAT'S NEW =====
1) LLM CLINICAL INTAKE (/extract, Llama 3.3 70B):
   Speak or type ANY messy sentence at the kiosk — the LLM extracts name, age,
   gender, a clean concern summary, and RED FLAGS. Red flags are appended into
   the concern so the rules safety floor sees them: the LLM informs triage,
   it never decides severity. Regex remains as automatic fallback (demo can't break).

2) RETURNING-PATIENT RECOGNITION (GET /patients/lookup):
   Kiosk step 1 now has "🔎 Find my previous record". Enter/speak a name (+age)
   of someone with a COMPLETED prior visit -> "Welcome back" banner with their
   last visit + specialty, has_history auto-ticks -> triage confidence improves.
   Honestly labeled: demo matches by name; production uses MRN/ABHA via EHR.

3) DEPLOYMENT-PROOFING: HD voice + extract now go through api.js (VITE_API_URL),
   no hardcoded localhost anywhere -> ready for the Render/Vercel deploy.

===== TEST SCRIPT (3 minutes) =====
A. Kiosk -> type in Concern box... actually use a sample chip or speak:
   "uh this is for my father, he is about seventy, his face is drooping and
    his speech is slurred since breakfast"
   -> Extract: name null, age 70, concern summary + (red flags: face drooping,
      slurred speech) -> submit -> lands EMERGENCY / Neurology. That's
      Whisper -> LLM -> rules floor -> ML, end to end.
B. Doctor: prescribe for any patient (completes their visit). Then Kiosk ->
   type that patient's name -> "Find my previous record" -> Welcome back banner.
C. Stop the backend key (restart without GROQ_API_KEY) -> speak at kiosk ->
   fields still fill via regex fallback. Restart with key after.

===== REPO HYGIENE (run from Accenture root, before pushing) =====
    git ls-files | Select-String "pkl|synthetic_ed|triage.db|node_modules|venv"
        -> MUST return nothing. If anything appears:
           git rm --cached <that path>   (removes from repo, keeps on disk)
    git grep gsk_
        -> MUST return nothing (no API keys in code)
    cd backend; pip freeze > requirements.txt; cd ..
    git add . ; git commit -m "AI intake (LLM extract), returning-patient recognition, hygiene"
    git push

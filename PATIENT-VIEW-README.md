# Patient View Pack — one-click role entry + patient phone view

## Files (all REPLACE)
| From zip | Into |
|---|---|
| backend/app/auth.py | backend\app\auth.py |
| backend/app/routers/patients.py | backend\app\routers\patients.py |
| frontend/src/App.jsx | frontend\src\App.jsx |

(api.js unchanged from the upgrade pack — keep it.)

## What changed
1. **One-click login** — the login screen is now 5 role cards; one tap signs a judge in
   (kiosk / nurse / two doctors / **patient**). JWT auth is still real behind the scenes;
   the card supplies the credentials. Note on screen explains: production = staff SSO +
   tokenized SMS links for patients.
2. **Patient role** — new `patient / patient123` account. Sees ONLY the Patient Portal tab
   (their "phone"), can pre-book emergencies, cannot see the board, surge button hidden.
3. **patients.py** — pre-booking endpoint now accepts the patient role (it's their feature).

## Apply
- Paste the 3 files → backend terminal: Ctrl+C → restart uvicorn (with GROQ key if using
  voice) → hard-refresh browser.
- IMPORTANT: this auth.py must be the one with HTTPBearer (it is — full file included),
  so /docs Authorize button keeps working.

## Test (90 seconds — the judge's experience)
1. Open localhost:5173 → login screen shows 5 cards → tap **📱 Patient** →
   lands directly in the Patient Portal, single tab, no surge button.
2. Pick a patient from the dropdown → category, confidence, queue position, wait estimate.
3. Tap **Sign out** → tap **Dr. A. Choudhury** → doctor console in one click.
4. Prescribe for a patient → sign out → Patient card → select that patient →
   notification + PDF download. Full loop, zero typing.

PHASE 4 FILES — frontend wired to backend, live WebSockets, notifications, PDF, surge

===== WHERE FILES GO =====

BACKEND (replace existing files):
  backend/app/ws.py                        (NEW)
  backend/app/main.py                      (REPLACE)
  backend/app/routers/patients.py          (REPLACE — adds broadcasts + /patients/demo/surge)
  backend/app/routers/overrides.py         (REPLACE — adds broadcast)
  backend/app/routers/prescriptions.py     (REPLACE — adds broadcasts)
  (auth_routes.py, queue.py, models.py etc. — UNCHANGED, leave as they are)

FRONTEND:
  frontend/src/api.js                      (NEW)
  frontend/src/App.jsx                     (REPLACE the Phase 1 prototype)

===== SETUP STEPS =====

1) Frontend terminal, inside the frontend folder:
     npm install jspdf
2) Copy the files into place as above.
3) Backend terminal (backend folder, venv active):
     python -m uvicorn app.main:app --reload
4) Frontend terminal:
     npm run dev
5) Open http://localhost:5173

===== LOGIN ACCOUNTS =====
  kiosk  / kiosk123     -> Kiosk + Ambulance tabs only
  nurse1 / nurse123     -> Board, Kiosk, Ambulance, Nurse Review, Patient Portal, Audit
  doc1   / doctor123    -> Dr. A. Choudhury (Cardiology): Board, Doctor, Patient, Audit
  doc2   / doctor123    -> Dr. S. Bhattacharya (Pediatrics)

===== 5-MINUTE VERIFICATION (the money demo) =====
1. Open TWO browser windows side by side.
   Window A: login as nurse1 -> Queue Board.
   Window B: login as kiosk -> Kiosk tab.
2. In B, check in a patient (sample voice -> vitals -> submit).
   >>> They appear on A's board in under a second. No refresh. That's the WebSocket.
3. In A (nurse): open Nurse Review -> select the new patient -> read the AI reasons
   (RULE lines + ML probabilities) -> override with a reason -> board updates live.
4. Login window B as doc1 -> Doctor tab -> only Cardiology patients visible ->
   write prescription -> Send.
   >>> Window A gets a toast "Prescription ready"; Patient Portal (pick that patient)
   shows the notification and a "Download prescription (PDF)" button.
5. Click "Simulate 3x surge" in the header -> board floods live, emergencies stay on
   top; within ~30-60s the monitor starts flagging overdue patients (amber rows +
   toasts) because surge arrivals are backdated on purpose.
6. Audit Trail tab: every one of the above actions is there with actor + time.

===== COMMON ERRORS =====
- "Login failed — is the backend running": start uvicorn; check http://localhost:8000/
- Header shows "offline" red pill: WebSocket didn't connect — backend not running,
  or main.py wasn't replaced (no /ws/queue route). Check backend terminal for errors.
- Failed to resolve import "jspdf": run  npm install jspdf  in the frontend folder.
- 403 on prescription: you're not logged in as a doctor account.
- Everything 401 after ~8h: token expired — sign out and back in.
- Old duplicated patients cluttering the queue:  del triage.db  ->  python seed.py
  -> restart uvicorn.

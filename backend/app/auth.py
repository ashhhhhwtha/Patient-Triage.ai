import os, time, hashlib
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod")
ALGO = "HS256"

def _hash(pw: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), b"triage-salt", 100_000).hex()

USERS = {
    "kiosk":   {"pw": _hash("kiosk123"),   "role": "kiosk",   "display": "Reception Kiosk"},
    "nurse1":  {"pw": _hash("nurse123"),   "role": "nurse",   "display": "Nurse J. Kalita"},
    "doc1":    {"pw": _hash("doctor123"),  "role": "doctor",  "display": "Dr. A. Choudhury", "dept": "Cardiology"},
    "doc2":    {"pw": _hash("doctor123"),  "role": "doctor",  "display": "Dr. S. Bhattacharya", "dept": "Pediatrics"},
    "doc3":    {"pw": _hash("doctor123"), "role": "doctor",  "display": "Dr. M. Begum (Duty Medical Officer)"},
    # limited demo account: sees only the Patient Portal (their own "phone")
    "patient": {"pw": _hash("patient123"), "role": "patient", "display": "Patient (demo phone)"},
}

def verify_login(username: str, password: str):
    u = USERS.get(username)
    if not u or u["pw"] != _hash(password):
        return None
    return u

def create_token(username: str) -> str:
    u = USERS[username]
    payload = {"sub": username, "role": u["role"], "display": u["display"],
               "dept": u.get("dept"), "exp": time.time() + 8 * 3600}
    return jwt.encode(payload, SECRET, algorithm=ALGO)

bearer_scheme = HTTPBearer()

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        return jwt.decode(creds.credentials, SECRET, algorithms=[ALGO])
    except Exception:
        raise HTTPException(401, "Invalid or expired token")

def require_role(*roles):
    def dep(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, f"This action requires role: {', '.join(roles)}")
        return user
    return dep

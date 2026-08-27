from fastapi import APIRouter, HTTPException
from app.schemas import LoginIn
from app.auth import verify_login, create_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
def login(body: LoginIn):
    u = verify_login(body.username, body.password)
    if not u:
        raise HTTPException(401, "Invalid username or password")
    return {"token": create_token(body.username), "role": u["role"],
            "display": u["display"], "dept": u.get("dept")}
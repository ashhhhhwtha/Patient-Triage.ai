from app.models import AuditLog

def audit(db, actor: str, action: str, detail: str):
    db.add(AuditLog(actor=actor, action=action, detail=detail))
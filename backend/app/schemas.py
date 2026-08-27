from pydantic import BaseModel
from typing import Optional, List

class VitalsIn(BaseModel):
    hr: Optional[int] = None
    bp_sys: Optional[int] = None
    bp_dia: Optional[int] = None
    spo2: Optional[int] = None
    temp: Optional[float] = None

class PatientIn(BaseModel):
    name: str
    age: int
    gender: str = ""
    concern: str
    pain: int = 0
    has_history: bool = False
    source: str = "kiosk"
    appearance: List[str] = []
    vitals: Optional[VitalsIn] = None

class OverrideIn(BaseModel):
    patient_id: int
    to_category: str            # emergency | urgent | lower
    reason: str

class PrescriptionIn(BaseModel):
    patient_id: int
    text: str

class LoginIn(BaseModel):
    username: str
    password: str
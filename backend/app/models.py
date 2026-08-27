from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from app.db import Base

class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(1), default="")
    concern = Column(Text, nullable=False)
    pain = Column(Integer, default=0)
    has_history = Column(Boolean, default=False)
    source = Column(String, default="kiosk")
    appearance = Column(JSON, default=list)
    status = Column(String, default="waiting")
    arrived_at = Column(DateTime, server_default=func.now())

class VitalsReading(Base):
    __tablename__ = "vitals"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), index=True)
    hr = Column(Integer, nullable=True)
    bp_sys = Column(Integer, nullable=True)
    bp_dia = Column(Integer, nullable=True)
    spo2 = Column(Integer, nullable=True)
    temp = Column(Float, nullable=True)
    taken_at = Column(DateTime, server_default=func.now())

class TriageResult(Base):
    __tablename__ = "triage_results"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), index=True)
    category = Column(String)
    score = Column(Float)
    confidence = Column(Float)
    specialty = Column(String)
    escalated = Column(Boolean, default=False)
    reasons = Column(JSON, default=list)
    model_version = Column(String, default="rules-v0")
    created_at = Column(DateTime, server_default=func.now())

class Override(Base):
    __tablename__ = "overrides"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), index=True)
    from_category = Column(String)
    to_category = Column(String)
    reason = Column(Text, nullable=False)
    nurse = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), index=True)
    doctor = Column(String)
    text = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    actor = Column(String)
    action = Column(String)
    detail = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
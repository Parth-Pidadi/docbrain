from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


# ── Document schemas ──────────────────────────────────────────────────────────

class DocType(str, Enum):
    invoice = "invoice"
    receipt = "receipt"
    bank_statement = "bank_statement"
    contract = "contract"
    unknown = "unknown"


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    message: str


class ExtractionResult(BaseModel):
    doc_id: str
    doc_type: DocType
    extracted_fields: Dict[str, Any]
    raw_text: Optional[str] = None
    parse_method: Optional[str] = None   # donut | tesseract | pdfplumber | *_local
    confidence: Optional[float] = None
    created_at: datetime = datetime.utcnow()


class QARequest(BaseModel):
    question: str
    doc_ids: Optional[List[str]] = None  # None = search all user's docs


class QASource(BaseModel):
    doc_id: str
    filename: str
    chunk: str
    score: float


class QAResponse(BaseModel):
    answer: str
    sources: List[QASource]
    model: str


# ── Auth schemas ──────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

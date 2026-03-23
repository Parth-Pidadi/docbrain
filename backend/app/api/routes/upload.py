import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.database import Document, User
from app.models.schemas import UploadResponse
from app.services.auth import get_current_user

router = APIRouter()


@router.get("/")
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all documents belonging to the current user."""
    docs = db.query(Document).filter(Document.user_id == current_user.id).order_by(Document.id).all()
    return [
        {
            "doc_id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "doc_type": doc.doc_type,
            "is_extracted": doc.extracted_fields is not None,
        }
        for doc in docs
    ]


@router.post("/", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ext = file.filename.split(".")[-1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '.{ext}' not supported. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )

    doc_id = str(uuid.uuid4())
    upload_path = Path(settings.UPLOAD_DIR) / f"{doc_id}.{ext}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Persist document metadata tied to the current user
    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        filename=file.filename,
        file_type=ext,
    )
    db.add(doc)
    db.commit()

    return UploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        file_type=ext,
        message="Document uploaded successfully. Call /api/extract/{doc_id} to process.",
    )

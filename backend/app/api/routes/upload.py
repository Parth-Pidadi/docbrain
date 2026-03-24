import hashlib
import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.database import Document, User
from app.models.schemas import UploadResponse
from app.services.auth import get_current_user

router = APIRouter()


class RenameRequest(BaseModel):
    filename: str


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

    # Read file bytes once — used for both hashing and saving
    file_bytes = await file.read()

    # Check file size
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB} MB.",
        )

    # SHA-256 content hash — same file bytes = same hash
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Reject if this exact file was already uploaded by this user
    existing = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.file_hash == file_hash,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate file: '{existing.filename}' has identical content. Delete it first if you want to re-upload.",
        )

    doc_id = str(uuid.uuid4())
    upload_path = Path(settings.UPLOAD_DIR) / f"{doc_id}.{ext}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    with open(upload_path, "wb") as f:
        f.write(file_bytes)

    # Persist document metadata tied to the current user
    doc = Document(
        id=doc_id,
        user_id=current_user.id,
        filename=file.filename,
        file_type=ext,
        file_hash=file_hash,
    )
    db.add(doc)
    db.commit()

    return UploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        file_type=ext,
        message="Document uploaded successfully. Call /api/extract/{doc_id} to process.",
    )


@router.patch("/{doc_id}")
def rename_document(
    doc_id: str,
    body: RenameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename a document (display name only — physical file is keyed by UUID)."""
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    new_name = body.filename.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Filename cannot be empty.")

    doc.filename = new_name
    db.commit()
    return {"doc_id": doc_id, "filename": doc.filename}


@router.delete("/{doc_id}")
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document: removes DB record, uploaded file, and ChromaDB vectors."""
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # 1. Delete physical file from disk
    upload_dir = Path(settings.UPLOAD_DIR)
    for f in upload_dir.glob(f"{doc_id}.*"):
        try:
            f.unlink()
        except Exception:
            pass

    # 2. Remove vectors from ChromaDB
    try:
        import chromadb
        chroma = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        collection = chroma.get_or_create_collection("docbrain")
        # Delete all chunks for this doc (chunk IDs follow pattern "{doc_id}_chunk_{n}")
        existing = collection.get(where={"doc_id": {"$eq": doc_id}})
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass  # ChromaDB cleanup is best-effort

    # 3. Remove from PostgreSQL
    db.delete(doc)
    db.commit()

    return {"deleted": doc_id}

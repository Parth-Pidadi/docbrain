from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import Document, User
from app.models.schemas import ExtractionResult
from app.services import classifier, embedder, extractor, vision
from app.services.auth import get_current_user

router = APIRouter()


@router.post("/{doc_id}", response_model=ExtractionResult)
async def extract_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify the document exists and belongs to this user
    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.user_id == current_user.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Step 1: OCR / parse the document
    raw_text, donut_json, parse_method = await vision.parse(doc_id)
    if not raw_text:
        raise HTTPException(status_code=422, detail="Could not extract text from document.")

    # Step 2: Classify document type
    doc_type = await classifier.classify(raw_text)

    # Step 3: Always run Groq for clean normalized fields
    # raw_text may be CORD JSON (from Donut) or plain text (Tesseract/pdfplumber)
    extracted_fields = await extractor.extract(raw_text, doc_type)
    # Keep Donut raw output for reference if available
    if donut_json and isinstance(donut_json, dict):
        extracted_fields["_donut_raw"] = donut_json

    # Step 4: Embed and store in ChromaDB (scoped to this user)
    await embedder.embed_and_store(doc_id, raw_text, user_id=str(current_user.id))

    # Step 5: Persist extraction results to PostgreSQL
    doc.doc_type = doc_type.value
    doc.extracted_fields = extracted_fields
    db.commit()

    return ExtractionResult(
        doc_id=doc_id,
        doc_type=doc_type,
        extracted_fields=extracted_fields,
        raw_text=raw_text,
        parse_method=parse_method,
    )

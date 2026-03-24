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
        # File found but OCR returned nothing — give a clear reason
        if parse_method == "not_found":
            raise HTTPException(
                status_code=404,
                detail="Uploaded file not found on server. Please re-upload the document.",
            )
        raise HTTPException(
            status_code=422,
            detail=(
                "OCR could not extract any text from this image. "
                "Try uploading a higher-quality scan (300 DPI+, good lighting, flat surface). "
                "PDF documents with embedded text work best. "
                f"Parse method attempted: {parse_method}"
            ),
        )

    # Step 2: Classify document type
    doc_type = await classifier.classify(raw_text)

    # Step 3: Always run Groq for clean normalized fields
    # raw_text may be CORD JSON (from Donut) or plain text (Tesseract/pdfplumber)
    extracted_fields = await extractor.extract(raw_text, doc_type)
    # Keep Donut raw output for reference if available
    if donut_json and isinstance(donut_json, dict):
        extracted_fields["_donut_raw"] = donut_json

    # Step 4: Embed and store in ChromaDB — best-effort, never blocks extraction
    embedding_note = None
    try:
        await embedder.embed_and_store(doc_id, raw_text, user_id=str(current_user.id))
    except Exception as emb_err:
        # Colab is offline or sentence-transformers not installed.
        # Extraction + SQL insights still work; only RAG Q&A is degraded.
        embedding_note = f"Embedding skipped (Colab offline): {str(emb_err)[:120]}"
        print(f"[extract] WARNING: {embedding_note}")

    # Step 5: Persist extraction results to PostgreSQL
    doc.doc_type = doc_type.value
    doc.extracted_fields = extracted_fields
    db.commit()

    result = ExtractionResult(
        doc_id=doc_id,
        doc_type=doc_type,
        extracted_fields=extracted_fields,
        raw_text=raw_text,
        parse_method=parse_method,
    )
    # Surface embedding warning to caller without failing
    if embedding_note:
        result.extracted_fields["_embedding_warning"] = (
            "Colab GPU server was offline — semantic Q&A may be limited. "
            "SQL-based insights and structured queries still work normally."
        )
    return result

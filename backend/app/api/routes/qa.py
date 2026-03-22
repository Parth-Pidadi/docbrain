from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import Document, User
from app.models.schemas import QARequest, QAResponse
from app.services import qa as qa_service
from app.services.auth import get_current_user

router = APIRouter()


@router.post("/", response_model=QAResponse)
async def ask_question(
    request: QARequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # If specific doc_ids requested, verify they all belong to this user
    if request.doc_ids:
        owned = db.query(Document.id).filter(
            Document.id.in_(request.doc_ids),
            Document.user_id == current_user.id,
        ).all()
        owned_ids = [r.id for r in owned]
        unauthorized = set(request.doc_ids) - set(owned_ids)
        if unauthorized:
            raise HTTPException(status_code=403, detail="Access denied to one or more documents.")
        doc_ids = owned_ids
    else:
        # Search only within this user's documents
        user_docs = db.query(Document.id).filter(
            Document.user_id == current_user.id
        ).all()
        doc_ids = [r.id for r in user_docs]

    result = await qa_service.answer(request.question, doc_ids, user_id=str(current_user.id))
    return result

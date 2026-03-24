"""
Document Classifier: uses Gemini to detect document type from raw text.
"""
from app.models.schemas import DocType
from app.core.config import settings
from openai import OpenAI

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    return _client


CLASSIFY_PROMPT = """You are a document classifier. Given the following document text, identify the document type.

Respond with ONLY one of these labels (no explanation):
- invoice
- receipt
- bank_statement
- contract
- unknown

Document text:
{text}

Document type:"""


async def classify(raw_text: str) -> DocType:
    snippet = raw_text[:2000]
    client = _get_client()

    response = client.chat.completions.create(
        model=settings.GEMINI_MODEL,
        messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(text=snippet)}],
        max_tokens=10,
        temperature=0,
    )

    label = response.choices[0].message.content.strip().lower()
    try:
        return DocType(label)
    except ValueError:
        return DocType.unknown

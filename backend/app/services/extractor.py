"""
Structured Extractor: uses Groq LLM to pull key-value fields from documents.
Returns a dict of extracted fields as JSON.
"""
import json
from app.models.schemas import DocType
from app.core.config import settings
import groq

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = groq.Groq(api_key=settings.GROQ_API_KEY)
    return _client


EXTRACTION_PROMPTS = {
    DocType.invoice: """Extract these fields from the invoice (return valid JSON only):
vendor_name, invoice_number, invoice_date, due_date, total_amount, currency, line_items (array of {description, qty, unit_price, amount}), tax_amount, payment_terms""",

    DocType.receipt: """Extract these fields from the receipt (return valid JSON only):
merchant_name, date, total_amount, currency, items (array of {name, price}), payment_method, tax_amount""",

    DocType.bank_statement: """Extract these fields from the bank statement (return valid JSON only):
bank_name, account_holder, account_number, statement_period_start, statement_period_end, opening_balance, closing_balance, transactions (array of {date, description, debit, credit, balance})""",

    DocType.contract: """Extract these fields from the contract (return valid JSON only):
parties (array of names), contract_date, effective_date, expiry_date, contract_type, key_terms (array of strings), governing_law""",

    DocType.unknown: """Extract any key information from this document (return valid JSON only):
document_summary, key_entities, key_dates, key_amounts, other_fields""",
}

EXTRACTION_SYSTEM = "You are a structured data extraction engine. Return only valid JSON. No markdown, no explanation."


async def extract(raw_text: str, doc_type: DocType) -> dict:
    client = _get_client()
    prompt = EXTRACTION_PROMPTS[doc_type]

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM},
            {"role": "user", "content": f"{prompt}\n\nDocument text:\n{raw_text[:4000]}"},
        ],
        max_tokens=1024,
        temperature=0,
    )

    content = response.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw_extraction": content}

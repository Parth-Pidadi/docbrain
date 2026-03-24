"""
Structured Extractor: uses Groq LLM to pull key-value fields from documents.
Returns a dict of extracted fields as JSON.
"""
import json
import groq
from app.models.schemas import DocType
from app.core.config import settings

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
merchant_name, date, total_amount, currency, items (array of {name, price}), payment_method, tax_amount.

The input may be plain OCR text OR structured Donut CORD JSON. Handle both:

CORD JSON format example:
{"menu": [{"nm": "ITEM NAME", "price": "3.74"}, {"nm": "ITEM 2", "unitprice": "1.00", "cnt": "2", "price": "2.00"}],
 "sub_total": {"subtotal_price": "5.74"}, "tax": {"tax_price": "0.46"}, "total": {"total_price": "6.20"},
 "store_name": "Walmart"}

If CORD JSON:
- merchant_name → store_name or first store identifier
- items → menu[].nm as name, menu[].price as price
- total_amount → total.total_price or total.cashprice
- tax_amount → tax.tax_price
- date → look for date field or any date pattern

If plain OCR text:
- total_amount: look for TOTAL, TOT, TOTAL PURCHASE, AMOUNT DUE — return as a number like 3.74
- merchant_name: store name at the top (e.g. Walmart, Target, CVS)
- date: look for MM/DD/YY or any date pattern
- If garbled, still extract numbers after TOTAL or AMOUNT

Return null for fields you cannot find. Never skip total_amount if any dollar amount is visible.""",

    DocType.bank_statement: """Extract these fields from the bank statement (return valid JSON only):
bank_name, account_holder, account_number, statement_period_start, statement_period_end, opening_balance, closing_balance, transactions (array of {date, description, debit, credit, balance})""",

    DocType.contract: """Extract these fields from the contract (return valid JSON only):
parties (array of names), contract_date, effective_date, expiry_date, contract_type, governing_law,
payment_terms, termination_conditions (array of strings),
liability_clauses (array of strings — any clauses limiting or assigning liability),
indemnification (array of strings — who indemnifies whom),
auto_renewal (true/false and terms if present),
non_compete (true/false and scope if present),
intellectual_property (who owns IP created during contract),
penalty_clauses (array of {trigger, penalty}),
red_flags (array of strings — unusual, risky, or missing standard protections),
key_obligations (object with party names as keys, array of obligations as values),
summary (2-3 sentence plain English summary of what this contract does)""",

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

    if content.startswith("```"):
        lines = content.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        content = "\n".join(lines).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"raw_extraction": content}

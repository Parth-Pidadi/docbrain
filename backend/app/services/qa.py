"""
RAG Q&A with LLM Tool Calling.

LLaMA 3.3 acts as a router:
  - Structured queries (spending, vendors, transactions) → SQL via tool calls
  - Semantic queries (contract terms, document content)  → RAG via ChromaDB
"""
from __future__ import annotations

import json
from typing import Optional

import groq
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import Document
from app.models.schemas import QAResponse, QASource
from app.services import embedder

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = groq.Groq(api_key=settings.GROQ_API_KEY)
    return _client


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_spending",
            "description": (
                "Get total spending, per-vendor breakdown, and individual records "
                "from invoices and receipts. Use for questions about: total spent, "
                "expenses, costs, spending in a month, how much was paid."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {
                        "type": "string",
                        "description": "Month filter in YYYY-MM format, e.g. '2024-03'. Only include if the user specifies a month.",
                    },
                    "vendor": {
                        "type": "string",
                        "description": "Vendor name to filter by. Only include if the user specifies a vendor.",
                    },
                    "doc_type": {
                        "type": "string",
                        "enum": ["invoice", "receipt", "bank_statement"],
                        "description": "Filter by document type.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vendors",
            "description": (
                "List all vendors and merchants with their total spending. "
                "Use for questions about: vendors, suppliers, merchants, who was paid, "
                "top vendors, vendor list."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transactions",
            "description": (
                "Get bank statement transactions with debits and credits. "
                "Use for questions about: bank transactions, account activity, "
                "debits, credits, bank statement details."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {
                        "type": "string",
                        "description": "Month filter in YYYY-MM format.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_contract",
            "description": (
                "Analyze legal contracts for risks, red flags, and key clauses. "
                "Use for questions about: contract risks, loopholes, red flags, dangerous clauses, "
                "liability, indemnification, non-compete, auto-renewal, penalties, obligations, "
                "what should I watch out for, is this contract fair, contract summary."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "description": "Specific aspect to focus on: 'red_flags', 'liability', 'payment', 'termination', 'ip', 'obligations', or 'full' for complete analysis.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_receipt_items",
            "description": (
                "Get all items/products purchased from receipts and invoices. "
                "Use for questions about: what items were bought, what was purchased, "
                "list of products, what did I buy, items on receipt, line items."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_type": {
                        "type": "string",
                        "enum": ["receipt", "invoice"],
                        "description": "Filter by document type. Omit to search all.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search document contents for specific information. "
                "Use for questions about: contract terms, payment terms, clauses, "
                "document details, invoice numbers, dates, specific text in documents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant document content.",
                    }
                },
                "required": ["query"],
            },
        },
    },
]

ROUTER_SYSTEM = """You are DocBrain, an AI assistant for document intelligence.
You have access to tools that query the user's uploaded documents.
Always use the most appropriate tool to answer the question accurately.

Tool selection guide:
- Financial questions (spending, totals, amounts, costs) → get_spending
- Vendor/merchant questions → get_vendors
- Bank transactions → get_transactions
- Receipt items / what was purchased → get_receipt_items
- Contract risks, red flags, loopholes, clauses, obligations, legal analysis → analyze_contract
- Document content, specific text, terms, dates → search_documents

For contract analysis: always highlight red flags clearly, warn about risky clauses,
and explain legal terms in plain English. Be specific about what could harm the user.
After getting tool results, give a clear, structured answer in plain English.
Use bullet points for lists of risks or obligations."""


# ── Tool execution ─────────────────────────────────────────────────────────────

_MONTH_NAMES = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}


def _normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM-DD for consistent filtering."""
    import re
    if not date_str:
        return ""
    date_str = str(date_str).strip()
    if re.match(r'^\d{4}-\d{2}', date_str):
        return date_str[:10]
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', date_str)
    if m:
        month, day, year = m.groups()
        if len(year) == 2:
            year = ('20' if int(year) < 50 else '19') + year
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    m = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', date_str)
    if m:
        day, month, year = m.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    m = re.match(r'^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$', date_str)
    if m:
        mon_name, day, year = m.groups()
        mon_num = _MONTH_NAMES.get(mon_name.lower())
        if mon_num:
            return f"{year}-{mon_num}-{day.zfill(2)}"
    m = re.match(r'^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$', date_str)
    if m:
        day, mon_name, year = m.groups()
        mon_num = _MONTH_NAMES.get(mon_name.lower())
        if mon_num:
            return f"{year}-{mon_num}-{day.zfill(2)}"
    m = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})$', date_str)
    if m:
        year, month, day = m.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return date_str


_SLOGAN_KEYWORDS = [
    "save money", "live better", "thank you", "come again",
    "survey", "feedback", "receipt", "have a nice", "we appreciate",
    "visit us", "www.", ".com", "tell us", "sign up",
]

def _normalize_vendor(name: str, filename: str = "") -> str:
    """Detect slogans/taglines masquerading as vendor names and fix them."""
    if not name:
        return "Unknown"
    lowered = name.lower()
    # Check if it's a slogan
    if any(kw in lowered for kw in _SLOGAN_KEYWORDS) or len(name) > 50:
        # Try to extract brand from filename (e.g. "walmart_receipt.png" → "Walmart")
        import re
        if filename:
            base = filename.rsplit(".", 1)[0]
            parts = re.split(r'[_\-\s]+', base)
            for part in parts:
                if len(part) > 2 and not part.isdigit():
                    return part.title()
        return "Unknown"
    return name


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        cleaned = str(value).replace(",", "").replace("$", "").replace("£", "").replace("€", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _extract_amount(fields: dict) -> Optional[float]:
    for key in ("total_amount", "amount"):
        val = _safe_float(fields.get(key))
        if val is not None:
            return val
    cord_total = fields.get("total")
    if isinstance(cord_total, list) and cord_total:
        val = _safe_float(cord_total[0].get("total_price"))
        if val is not None:
            return val
    val = _safe_float(fields.get("total"))
    if val is not None:
        return val
    sub = fields.get("sub_total")
    if isinstance(sub, dict):
        val = _safe_float(sub.get("subtotal_price"))
        if val is not None:
            return val
    return None


def _exec_get_spending(args: dict, user_id: str, db: Session) -> dict:
    month = args.get("month")
    vendor_filter = args.get("vendor")
    doc_type = args.get("doc_type")

    q = db.query(Document).filter(
        Document.user_id == user_id,
        Document.extracted_fields.isnot(None),
    )
    if doc_type:
        q = q.filter(Document.doc_type == doc_type)
    docs = q.all()

    records = []
    for doc in docs:
        fields = doc.extracted_fields or {}
        amount = _extract_amount(fields)
        if amount is None:
            continue
        raw_date = fields.get("invoice_date") or fields.get("date") or fields.get("transaction_date") or ""
        date = _normalize_date(raw_date)
        raw_vendor = fields.get("vendor_name") or fields.get("merchant_name") or fields.get("vendor") or ""
        vendor_name = _normalize_vendor(raw_vendor, doc.filename)

        if month and not str(date).startswith(month):
            continue
        if vendor_filter and vendor_filter.lower() not in str(vendor_name).lower():
            continue

        records.append({"filename": doc.filename, "doc_type": doc.doc_type,
                        "date": date, "vendor": vendor_name, "amount": amount})

    total = round(sum(r["amount"] for r in records), 2)
    vendor_totals: dict = {}
    for r in records:
        v = r["vendor"]
        vendor_totals[v] = round(vendor_totals.get(v, 0) + r["amount"], 2)

    return {
        "total_spent": total,
        "record_count": len(records),
        "vendor_breakdown": sorted(
            [{"vendor": k, "total": v} for k, v in vendor_totals.items()],
            key=lambda x: x["total"], reverse=True
        ),
        "records": records[:10],
    }


def _exec_get_vendors(user_id: str, db: Session) -> dict:
    docs = db.query(Document).filter(
        Document.user_id == user_id,
        Document.extracted_fields.isnot(None),
    ).all()

    vendor_totals: dict = {}
    for doc in docs:
        fields = doc.extracted_fields or {}
        raw_vendor = fields.get("vendor_name") or fields.get("merchant_name") or fields.get("vendor") or ""
        vendor_name = _normalize_vendor(raw_vendor, doc.filename)
        if not vendor_name or vendor_name == "Unknown":
            continue
        amount = _extract_amount(fields)
        if amount:
            vendor_totals[vendor_name] = round(vendor_totals.get(vendor_name, 0) + amount, 2)

    return {
        "vendors": sorted(
            [{"vendor": k, "total_spent": v} for k, v in vendor_totals.items()],
            key=lambda x: x["total_spent"], reverse=True
        )
    }


def _exec_get_transactions(args: dict, user_id: str, db: Session) -> dict:
    month = args.get("month")
    docs = db.query(Document).filter(
        Document.user_id == user_id,
        Document.doc_type == "bank_statement",
        Document.extracted_fields.isnot(None),
    ).all()

    transactions = []
    for doc in docs:
        fields = doc.extracted_fields or {}
        txns = fields.get("transactions", [])
        if not isinstance(txns, list):
            continue
        for txn in txns:
            date = txn.get("date", "")
            if month and not str(date).startswith(month):
                continue
            transactions.append({
                "date": date,
                "description": txn.get("description", ""),
                "debit": _safe_float(txn.get("debit")),
                "credit": _safe_float(txn.get("credit")),
            })

    total_debits = round(sum(t["debit"] or 0 for t in transactions), 2)
    total_credits = round(sum(t["credit"] or 0 for t in transactions), 2)
    return {
        "transaction_count": len(transactions),
        "total_debits": total_debits,
        "total_credits": total_credits,
        "net": round(total_credits - total_debits, 2),
        "transactions": transactions[:20],
    }


def _exec_analyze_contract(args: dict, user_id: str, db: Session) -> dict:
    focus = args.get("focus", "full")
    docs = db.query(Document).filter(
        Document.user_id == user_id,
        Document.doc_type == "contract",
        Document.extracted_fields.isnot(None),
    ).all()

    if not docs:
        return {"error": "No contracts found. Please upload and extract a contract first."}

    results = []
    for doc in docs:
        fields = doc.extracted_fields or {}

        analysis = {"filename": doc.filename, "contract_type": fields.get("contract_type", "Unknown")}

        if focus in ("full", "red_flags"):
            analysis["red_flags"] = fields.get("red_flags", [])

        if focus in ("full", "liability"):
            analysis["liability_clauses"] = fields.get("liability_clauses", [])
            analysis["indemnification"] = fields.get("indemnification", [])

        if focus in ("full", "payment"):
            analysis["payment_terms"] = fields.get("payment_terms", "Not specified")
            analysis["penalty_clauses"] = fields.get("penalty_clauses", [])

        if focus in ("full", "termination"):
            analysis["termination_conditions"] = fields.get("termination_conditions", [])
            analysis["auto_renewal"] = fields.get("auto_renewal", False)

        if focus in ("full", "ip"):
            analysis["intellectual_property"] = fields.get("intellectual_property", "Not specified")

        if focus in ("full", "obligations"):
            analysis["key_obligations"] = fields.get("key_obligations", {})

        if focus == "full":
            analysis["summary"] = fields.get("summary", "")
            analysis["parties"] = fields.get("parties", [])
            analysis["governing_law"] = fields.get("governing_law", "")
            analysis["non_compete"] = fields.get("non_compete", False)
            analysis["expiry_date"] = fields.get("expiry_date", "")

        results.append(analysis)

    return {"contracts_analyzed": len(results), "analysis": results}


def _exec_get_receipt_items(args: dict, user_id: str, db: Session) -> dict:
    doc_type = args.get("doc_type")
    q = db.query(Document).filter(
        Document.user_id == user_id,
        Document.extracted_fields.isnot(None),
    )
    if doc_type:
        q = q.filter(Document.doc_type == doc_type)
    else:
        q = q.filter(Document.doc_type.in_(["receipt", "invoice"]))
    docs = q.all()

    all_items = []
    for doc in docs:
        fields = doc.extracted_fields or {}

        # Standard receipt format: items: [{name, price}]
        items = fields.get("items", [])
        # Invoice format: line_items: [{description, amount}]
        if not items:
            items = fields.get("line_items", [])
        # Donut CORD format: menu: [{nm, price, unitprice, sub_nm}]
        if not items:
            menu = fields.get("menu", [])
            if isinstance(menu, list):
                cord_items = []
                for m in menu:
                    if not isinstance(m, dict):
                        continue
                    # Try multiple name fields
                    nm = m.get("nm") or m.get("name") or m.get("item_name") or ""
                    # Try multiple price fields, strip "X" suffix (qty marker)
                    price_raw = str(m.get("unitprice") or m.get("price") or m.get("amount") or "")
                    price_clean = price_raw.replace("$", "").replace(",", "").replace(" X", "").strip()
                    # Also check nested sub_nm (CORD sub-item format)
                    if not nm and m.get("sub_nm"):
                        sub = m["sub_nm"]
                        if isinstance(sub, list) and sub:
                            nm = sub[0].get("nm", "")
                    # Validate: price must be numeric, name not a slogan/address
                    if not nm or len(nm) > 50:
                        continue
                    lowered_nm = nm.lower()
                    if any(kw in lowered_nm for kw in ["www.", ".com", "survey", "feedback", "thank", "http"]):
                        continue
                    try:
                        float(price_clean)
                        cord_items.append({"name": nm, "price": price_clean})
                    except (ValueError, TypeError):
                        continue
                items = cord_items

        for item in items:
            if isinstance(item, dict):
                all_items.append({
                    "source": doc.filename,
                    "doc_type": doc.doc_type,
                    "name": item.get("name") or item.get("nm") or item.get("description") or "Unknown",
                    "price": item.get("price") or item.get("amount") or item.get("unit_price") or "?",
                })

    return {
        "item_count": len(all_items),
        "items": all_items,
    }


async def _exec_search_documents(args: dict, doc_ids: list, user_id: str) -> dict:
    query = args.get("query", "")
    chunks = await embedder.search(query, doc_ids=doc_ids, user_id=user_id, top_k=5)
    return {"chunks": [{"doc_id": c["doc_id"][:8], "text": c["chunk"], "score": c["score"]} for c in chunks]}


# ── Main answer function ───────────────────────────────────────────────────────

async def answer(
    question: str,
    doc_ids: Optional[list] = None,
    user_id: str = "",
    db: Optional[Session] = None,
    history: Optional[list] = None,
) -> QAResponse:
    client = _get_client()

    messages = [{"role": "system", "content": ROUTER_SYSTEM}]

    # Inject conversation history (last 6 messages max to stay within context)
    if history:
        for msg in history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": question})

    # Step 1: Ask LLaMA to pick a tool
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        max_tokens=1024,
        temperature=0.1,
    )

    message = response.choices[0].message
    sources = []

    # Step 2: Execute tool if called
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        if tool_name == "get_spending" and db:
            tool_result = _exec_get_spending(tool_args, user_id, db)
        elif tool_name == "get_vendors" and db:
            tool_result = _exec_get_vendors(user_id, db)
        elif tool_name == "get_transactions" and db:
            tool_result = _exec_get_transactions(tool_args, user_id, db)
        elif tool_name == "analyze_contract" and db:
            tool_result = _exec_analyze_contract(tool_args, user_id, db)
        elif tool_name == "get_receipt_items" and db:
            tool_result = _exec_get_receipt_items(tool_args, user_id, db)
        elif tool_name == "search_documents":
            tool_result = await _exec_search_documents(tool_args, doc_ids or [], user_id)
            # Build sources from chunks
            for c in tool_result.get("chunks", []):
                sources.append(QASource(doc_id=c["doc_id"], filename=c["doc_id"],
                                        chunk=c["text"], score=c["score"]))
        else:
            tool_result = {"error": "Tool not available"}

        # Step 3: Send tool result back for final answer
        messages.append({"role": "assistant", "tool_calls": message.tool_calls})
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(tool_result),
        })

        final = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            max_tokens=512,
            temperature=0.1,
        )
        answer_text = final.choices[0].message.content.strip()

    else:
        # LLaMA answered directly
        answer_text = message.content.strip() if message.content else "I couldn't find an answer."

    return QAResponse(answer=answer_text, sources=sources, model=settings.GROQ_MODEL)

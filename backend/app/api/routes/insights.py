"""
Insights: SQL-powered structured queries over extracted document data.
Handles aggregations like total spending, vendor breakdowns, date-range filters.
This complements RAG — SQL for numbers/facts, RAG for language reasoning.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, cast, Float
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import Document, User
from app.services.auth import get_current_user

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_docs(db: Session, user: User, doc_type: Optional[str] = None):
    """Base query: all extracted docs belonging to this user."""
    q = db.query(Document).filter(
        Document.user_id == user.id,
        Document.extracted_fields.isnot(None),
    )
    if doc_type:
        q = q.filter(Document.doc_type == doc_type)
    return q


def _safe_float(value) -> Optional[float]:
    """Parse a value to float, stripping currency symbols."""
    if value is None:
        return None
    try:
        cleaned = str(value).replace(",", "").replace("$", "").replace("£", "").replace("€", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return None


_SLOGAN_KEYWORDS = [
    "save money", "live better", "thank you", "come again",
    "survey", "feedback", "receipt", "have a nice", "we appreciate",
    "visit us", "www.", ".com", "tell us", "sign up",
]


def _normalize_vendor(name: str, filename: str = "") -> str:
    """Detect slogans masquerading as vendor names and fix them."""
    import re
    if not name:
        return "Unknown"
    lowered = name.lower()
    if any(kw in lowered for kw in _SLOGAN_KEYWORDS) or len(name) > 50:
        if filename:
            base = filename.rsplit(".", 1)[0]
            parts = re.split(r'[_\-\s]+', base)
            for part in parts:
                if len(part) > 2 and not part.isdigit() and not part.lower().startswith("screenshot"):
                    return part.title()
        return "Unknown"
    return name


_MONTH_NAMES = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}


def _normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM-DD.

    Handles:
      - Already ISO:        2024-03-05            → 2024-03-05
      - US slash:           03/05/2024 or 3/5/24  → 2024-03-05
      - EU dash:            05-03-2024            → 2024-03-05
      - Month name long:    March 5, 2024         → 2024-03-05
      - Month name short:   05 Mar 2024           → 2024-03-05
      - Slash month name:   2024/March/05         → 2024-03-05
    """
    import re
    if not date_str:
        return ""
    date_str = str(date_str).strip()

    # Already ISO or ISO-month prefix (2024-03...)
    if re.match(r'^\d{4}-\d{2}', date_str):
        return date_str[:10]

    # US slash: MM/DD/YYYY or MM/DD/YY
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', date_str)
    if m:
        month, day, year = m.groups()
        if len(year) == 2:
            year = ('20' if int(year) < 50 else '19') + year
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # EU dash: DD-MM-YYYY
    m = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', date_str)
    if m:
        day, month, year = m.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # "March 5, 2024" or "March 5 2024"
    m = re.match(r'^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$', date_str)
    if m:
        mon_name, day, year = m.groups()
        mon_num = _MONTH_NAMES.get(mon_name.lower())
        if mon_num:
            return f"{year}-{mon_num}-{day.zfill(2)}"

    # "5 March 2024" or "05 Mar 2024"
    m = re.match(r'^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$', date_str)
    if m:
        day, mon_name, year = m.groups()
        mon_num = _MONTH_NAMES.get(mon_name.lower())
        if mon_num:
            return f"{year}-{mon_num}-{day.zfill(2)}"

    # YYYY/MM/DD
    m = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})$', date_str)
    if m:
        year, month, day = m.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    return date_str  # return as-is if nothing matched


def _extract_amount(fields: dict) -> Optional[float]:
    """Extract total amount handling flat fields and Donut CORD nested format."""
    # Standard fields
    for key in ("total_amount", "amount"):
        val = _safe_float(fields.get(key))
        if val is not None:
            return val

    # Donut CORD: total is an array [{total_price: "30.38", ...}]
    cord_total = fields.get("total")
    if isinstance(cord_total, list) and cord_total:
        val = _safe_float(cord_total[0].get("total_price"))
        if val is not None:
            return val

    # Plain total string
    val = _safe_float(fields.get("total"))
    if val is not None:
        return val

    # sub_total fallback
    sub = fields.get("sub_total")
    if isinstance(sub, dict):
        val = _safe_float(sub.get("subtotal_price"))
        if val is not None:
            return val

    return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Overall document summary for the current user."""
    docs = _user_docs(db, current_user).all()

    type_counts: dict = {}
    for doc in docs:
        t = doc.doc_type or "unknown"
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "total_documents": len(docs),
        "by_type": type_counts,
    }


@router.get("/spending")
def get_spending(
    month: Optional[str] = Query(None, description="Filter by month prefix, e.g. '2024-03'"),
    vendor: Optional[str] = Query(None, description="Filter by vendor name (partial match)"),
    doc_type: Optional[str] = Query(None, description="invoice | receipt | bank_statement"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Aggregate spending across invoices and receipts.
    Returns total, per-vendor breakdown, and individual records.
    """
    docs = _user_docs(db, current_user, doc_type=doc_type or None).all()

    records = []
    for doc in docs:
        fields = doc.extracted_fields or {}

        amount = _extract_amount(fields)
        if amount is None:
            continue

        raw_date = (
            fields.get("invoice_date")
            or fields.get("date")
            or fields.get("transaction_date")
            or ""
        )
        date = _normalize_date(raw_date)
        raw_vendor = (
            fields.get("vendor_name")
            or fields.get("merchant_name")
            or fields.get("vendor")
            or ""
        )
        vendor_name = _normalize_vendor(raw_vendor, doc.filename)
        currency = fields.get("currency", "USD")

        # Apply filters
        if month and not str(date).startswith(month):
            continue
        if vendor and vendor.lower() not in str(vendor_name).lower():
            continue

        records.append({
            "doc_id": doc.id,
            "filename": doc.filename,
            "doc_type": doc.doc_type,
            "date": date,
            "vendor": vendor_name,
            "amount": amount,
            "currency": currency,
        })

    total = round(sum(r["amount"] for r in records), 2)

    # Vendor breakdown
    vendor_totals: dict = {}
    for r in records:
        v = r["vendor"]
        vendor_totals[v] = round(vendor_totals.get(v, 0) + r["amount"], 2)

    vendor_breakdown = sorted(
        [{"vendor": k, "total": v} for k, v in vendor_totals.items()],
        key=lambda x: x["total"],
        reverse=True,
    )

    return {
        "total": total,
        "currency": records[0]["currency"] if records else "USD",
        "record_count": len(records),
        "filters": {"month": month, "vendor": vendor, "doc_type": doc_type},
        "vendor_breakdown": vendor_breakdown,
        "records": records,
    }


@router.get("/vendors")
def get_vendors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All vendors the user has transacted with, sorted by total spend."""
    docs = _user_docs(db, current_user).all()

    vendor_totals: dict = {}
    for doc in docs:
        fields = doc.extracted_fields or {}
        raw_vendor = (
            fields.get("vendor_name")
            or fields.get("merchant_name")
            or fields.get("vendor")
            or ""
        )
        vendor_name = _normalize_vendor(raw_vendor, doc.filename)
        if not vendor_name or vendor_name == "Unknown":
            continue
        amount = _extract_amount(fields)
        if amount:
            vendor_totals[vendor_name] = round(
                vendor_totals.get(vendor_name, 0) + amount, 2
            )

    return {
        "vendors": sorted(
            [{"vendor": k, "total_spent": v} for k, v in vendor_totals.items()],
            key=lambda x: x["total_spent"],
            reverse=True,
        )
    }


@router.get("/transactions")
def get_transactions(
    month: Optional[str] = Query(None, description="Filter by month prefix, e.g. '2024-03'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    All transactions from bank statements.
    Useful for 'what did I spend in March?' type questions via SQL.
    """
    docs = _user_docs(db, current_user, doc_type="bank_statement").all()

    all_transactions = []
    for doc in docs:
        fields = doc.extracted_fields or {}
        transactions = fields.get("transactions", [])
        if not isinstance(transactions, list):
            continue
        for txn in transactions:
            date = txn.get("date", "")
            if month and not str(date).startswith(month):
                continue
            all_transactions.append({
                "doc_id": doc.id,
                "filename": doc.filename,
                "date": date,
                "description": txn.get("description", ""),
                "debit": _safe_float(txn.get("debit")),
                "credit": _safe_float(txn.get("credit")),
                "balance": _safe_float(txn.get("balance")),
            })

    total_debits = round(sum(t["debit"] or 0 for t in all_transactions), 2)
    total_credits = round(sum(t["credit"] or 0 for t in all_transactions), 2)

    return {
        "transaction_count": len(all_transactions),
        "total_debits": total_debits,
        "total_credits": total_credits,
        "net": round(total_credits - total_debits, 2),
        "filters": {"month": month},
        "transactions": sorted(all_transactions, key=lambda x: x["date"], reverse=True),
    }

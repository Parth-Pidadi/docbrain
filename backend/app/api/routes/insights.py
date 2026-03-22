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

        # Support both invoice and receipt field naming
        amount_raw = fields.get("total_amount") or fields.get("total") or fields.get("amount")
        amount = _safe_float(amount_raw)
        if amount is None:
            continue

        date = (
            fields.get("invoice_date")
            or fields.get("date")
            or fields.get("transaction_date")
            or ""
        )
        vendor_name = (
            fields.get("vendor_name")
            or fields.get("merchant_name")
            or fields.get("vendor")
            or "Unknown"
        )
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
        vendor_name = (
            fields.get("vendor_name")
            or fields.get("merchant_name")
            or fields.get("vendor")
        )
        if not vendor_name:
            continue
        amount = _safe_float(
            fields.get("total_amount") or fields.get("total") or fields.get("amount")
        )
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

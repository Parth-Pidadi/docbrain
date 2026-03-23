"""
Vision Engine — three-tier document parsing:

  Tier 1 (GPU, Colab):  Donut OCR-free model via colab_client
  Tier 2 (CPU, local):  pdfplumber for digital PDFs / Tesseract for images
  Tier 3 (fallback):    error

Priority: Colab GPU → local CPU → error
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.services import colab_client


# ── Public API ────────────────────────────────────────────────────────────────

async def parse(doc_id: str) -> tuple[str, Optional[dict], str]:
    """
    Parse an uploaded document.

    Returns:
        (raw_text, donut_json_or_None, method_used)
    """
    file_path = _find_file(doc_id)
    if not file_path:
        return "", None, "not_found"

    ext = file_path.suffix.lower().lstrip(".")

    # ── Tier 1: Colab GPU ─────────────────────────────────────────────────────
    colab_result = await colab_client.parse_document(
        file_path,
        use_donut=(ext in {"png", "jpg", "jpeg", "tiff", "webp"}),
    )
    if colab_result:
        return (
            colab_result["raw_text"],
            colab_result.get("donut_json"),
            colab_result["method"],
        )

    # ── Tier 2: Local CPU ─────────────────────────────────────────────────────
    if ext == "pdf":
        text, method = _local_pdf(file_path)
    else:
        text = _local_image(file_path)
        method = "tesseract_local"

    return text, None, method


# ── Local fallbacks ───────────────────────────────────────────────────────────

def _find_file(doc_id: str) -> Optional[Path]:
    upload_dir = Path(settings.UPLOAD_DIR)
    matches = list(upload_dir.glob(f"{doc_id}.*"))
    return matches[0] if matches else None


def _local_pdf(path: Path) -> tuple[str, str]:
    """pdfplumber for digital PDFs; Tesseract for scanned pages."""
    import pdfplumber

    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"

    if text.strip():
        return text.strip(), "pdfplumber_local"

    return _tesseract_pdf(path), "tesseract_local"


def _maybe_set_tessdata():
    """Auto-detect tessdata path when running in Nix/Railway environment."""
    import os
    import glob as _glob

    if os.environ.get("TESSDATA_PREFIX"):
        return  # already set

    # Search for tessdata in common Nix store paths
    candidates = _glob.glob("/nix/store/*/share/tessdata") + _glob.glob("/usr/share/tesseract-ocr/*/tessdata")
    if candidates:
        os.environ["TESSDATA_PREFIX"] = candidates[0]


def _tesseract_pdf(path: Path) -> str:
    from pdf2image import convert_from_path
    import pytesseract

    _maybe_set_tessdata()
    pages = convert_from_path(str(path), dpi=300)
    return "\n".join(pytesseract.image_to_string(p) for p in pages).strip()


def _local_image(path: Path) -> str:
    import pytesseract
    from PIL import Image, ImageFilter, ImageEnhance

    # Ensure Tesseract can find its language data when installed via Nix
    _maybe_set_tessdata()

    img = Image.open(path).convert("RGB")

    # Upscale small images so Tesseract has enough DPI to work with
    min_dim = 1400
    w, h = img.size
    if max(w, h) < min_dim:
        scale = min_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Convert to grayscale and boost contrast — greatly improves receipt OCR
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = ImageEnhance.Sharpness(img).enhance(2.0)

    # Try with Tesseract page segmentation mode 6 (uniform block of text)
    config = "--psm 6 --oem 3"
    text = pytesseract.image_to_string(img, config=config).strip()

    # If still empty, retry with psm 4 (single column of text)
    if not text:
        config = "--psm 4 --oem 3"
        text = pytesseract.image_to_string(img, config=config).strip()

    return text

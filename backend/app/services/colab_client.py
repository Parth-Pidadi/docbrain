"""
Colab Client: HTTP bridge to the DocBrain GPU inference server running on Colab Pro.

When COLAB_URL is set in .env, heavy inference (Donut parsing, BGE embeddings)
is routed to the GPU server. Falls back to local CPU processing if unavailable.
"""
import base64
import httpx
from pathlib import Path
from typing import Optional
from app.core.config import settings

# Shared async client (reused across requests)
_client: Optional[httpx.AsyncClient] = None
_colab_available: Optional[bool] = None  # cached health-check result


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.COLAB_URL,
            timeout=httpx.Timeout(120.0),  # Donut inference can take ~10-30s
        )
    return _client


async def is_available() -> bool:
    """Ping the Colab server. Returns True if reachable."""
    global _colab_available
    if not settings.COLAB_URL:
        return False
    try:
        r = await _get_client().get("/health", timeout=5.0)
        _colab_available = r.status_code == 200
    except Exception:
        _colab_available = False
    return _colab_available


async def parse_document(file_path: Path, use_donut: bool = True) -> Optional[dict]:
    """
    Send a file to Colab for parsing.

    Returns:
        {
            "raw_text": str,
            "donut_json": dict | None,
            "method": "donut" | "tesseract" | "pdfplumber"
        }
    or None if Colab is unavailable.
    """
    if not await is_available():
        return None

    file_bytes = file_path.read_bytes()
    file_b64 = base64.b64encode(file_bytes).decode()

    payload = {
        "file_b64": file_b64,
        "filename": file_path.name,
        "use_donut": use_donut,
    }

    try:
        r = await _get_client().post("/parse", json=payload, timeout=120.0)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[colab_client] parse failed: {e}")
        return None


async def embed_texts(texts: list[str]) -> Optional[list[list[float]]]:
    """
    Send text chunks to Colab for GPU embedding.

    Returns list of embedding vectors, or None if Colab is unavailable.
    """
    if not await is_available():
        return None

    try:
        r = await _get_client().post(
            "/embed",
            json={"texts": texts},
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json()["embeddings"]
    except Exception as e:
        print(f"[colab_client] embed failed: {e}")
        return None

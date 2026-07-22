"""Paths for durable local state on Railway volume (/data)."""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    raw = (os.environ.get("DATA_DIR") or "").strip()
    if raw:
        p = Path(raw)
    elif Path("/data").is_dir() and os.access("/data", os.W_OK):
        p = Path("/data")
    else:
        p = Path(__file__).resolve().parent.parent / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p

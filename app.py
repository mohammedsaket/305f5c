"""Vercel entrypoint. Docker runs the same app from backend/ with DAYMARK_ROOT set."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("DAYMARK_ROOT", str(ROOT))
os.environ.setdefault("DAYMARK_STATIC", str(ROOT / "public"))
sys.path.insert(0, str(ROOT / "backend"))

from daymark.api import app  # noqa: E402

"""Download the January 2026 WINDFOR and FUELHH extracts.

The committed files under data/raw are enough to rebuild the app. This module
is the way to refresh them from Elexon.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from daymark.store import raw_dir

BASE = "https://data.elexon.co.uk/bmrs/api/v1"
WINDOWS = (
    ("2026-01-01T00:00:00Z", "2026-01-08T00:00:00Z", "windfor_20260101_0108.json"),
    ("2026-01-08T00:00:00Z", "2026-01-15T00:00:00Z", "windfor_20260108_0115.json"),
    ("2026-01-15T00:00:00Z", "2026-01-22T00:00:00Z", "windfor_20260115_0122.json"),
    ("2026-01-22T00:00:00Z", "2026-01-29T00:00:00Z", "windfor_20260122_0129.json"),
    ("2026-01-29T00:00:00Z", "2026-02-01T00:00:00Z", "windfor_20260129_0201.json"),
)


def _get(url: str, dest: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "daymark-ingest/1.0"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = response.read()
    parsed = json.loads(payload)
    if not isinstance(parsed, list) or not parsed:
        raise RuntimeError(f"Unexpected payload from {url}")
    dest.write_bytes(payload)
    print(f"{dest.name}: {len(parsed)} rows")


def main() -> None:
    folder = raw_dir()
    folder.mkdir(parents=True, exist_ok=True)
    for start, end, name in WINDOWS:
        url = f"{BASE}/datasets/WINDFOR/stream?publishDateTimeFrom={start}&publishDateTimeTo={end}"
        _get(url, folder / name)
        time.sleep(0.4)
    fuel = (
        f"{BASE}/datasets/FUELHH/stream"
        "?settlementDateFrom=2026-01-01&settlementDateTo=2026-02-01&fuelType=WIND"
    )
    _get(fuel, folder / "fuelhh_wind_20260101_20260201.json")


if __name__ == "__main__":
    main()

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from daymark.api import create_app
from daymark.store import ActualRow, ForecastRow, Series

UTC = timezone.utc


def _fixture() -> Series:
    delivery = datetime(2026, 1, 15, tzinfo=UTC).date()
    forecasts = []
    actuals = []
    publish = datetime(2026, 1, 14, 9, 30, tzinfo=UTC)
    for hour in range(24):
        start = datetime(2026, 1, 15, hour, tzinfo=UTC)
        forecasts.append(ForecastRow(publish, start, 1200))
        actuals.append(ActualRow(start, delivery, hour * 2 + 1, 1000, start))
        half = start + timedelta(minutes=30)
        actuals.append(ActualRow(half, delivery, hour * 2 + 2, 1000, half))
    return Series(forecasts, actuals)


def test_desk_and_rejected_dates():
    client = TestClient(create_app(_fixture()))
    health = client.get("/api/health")
    assert health.status_code == 200

    desk = client.get("/api/desk", params={"decision_date": "2026-01-14", "auction": "n2ex"})
    assert desk.status_code == 200
    body = desk.json()
    assert body["vintage"]["slot"] == "09:30"
    assert body["summary"]["error_mwh"] == 4800

    rejected = client.get("/api/desk", params={"decision_date": "2026-02-01", "auction": "n2ex"})
    assert rejected.status_code == 400
    assert "January 2026" in rejected.json()["error"]

    unknown = client.get("/api/desk", params={"decision_date": "2026-01-14", "auction": "nordpool"})
    assert unknown.status_code == 400

    book = client.get("/api/book.csv", params={"decision_date": "2026-01-14", "auction": "n2ex"})
    assert book.status_code == 200
    assert book.text.splitlines()[0].startswith("settlement_period")
    assert "daymark-n2ex-2026-01-15.csv" in book.headers["content-disposition"]

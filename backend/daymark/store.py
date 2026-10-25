"""Load the Elexon extracts and the sqlite store built from them.

Raw JSON is the input. The database is a straight copy of those rows so the
API does not re-read the extracts, and so a rebuild can be checked.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc


def root() -> Path:
    env = os.environ.get("DAYMARK_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def raw_dir() -> Path:
    return root() / "data" / "raw"


def db_path() -> Path:
    return root() / "data" / "daymark.sqlite"


def static_dir() -> Path:
    env = os.environ.get("DAYMARK_STATIC")
    if env:
        return Path(env)
    return root() / "static"


def parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ForecastRow:
    publish_time: datetime
    start_time: datetime
    mw: float


@dataclass(frozen=True)
class ActualRow:
    start_time: datetime
    settlement_date: date
    settlement_period: int
    mw: float
    publish_time: datetime


@dataclass
class Series:
    forecasts: list[ForecastRow]
    actuals: list[ActualRow]
    by_publish: dict[datetime, dict[datetime, float]] = field(init=False)
    publishes: list[datetime] = field(init=False)
    actual: dict[datetime, ActualRow] = field(init=False)

    def __post_init__(self) -> None:
        by_publish: dict[datetime, dict[datetime, float]] = {}
        for row in self.forecasts:
            by_publish.setdefault(row.publish_time, {})[row.start_time] = row.mw
        actual: dict[datetime, ActualRow] = {}
        for row in self.actuals:
            current = actual.get(row.start_time)
            if current is None or row.publish_time >= current.publish_time:
                actual[row.start_time] = row
        self.by_publish = by_publish
        self.publishes = sorted(by_publish)
        self.actual = actual

    def hourly_actual(self, hour_start: datetime) -> float | None:
        first = self.actual.get(hour_start)
        second = self.actual.get(hour_start + timedelta(minutes=30))
        if first is None or second is None:
            return None
        if first.settlement_date != second.settlement_date:
            return None
        return (first.mw + second.mw) / 2.0


def load_raw() -> Series:
    folder = raw_dir()
    forecast_files = sorted(folder.glob("windfor_2026*.json"))
    actual_path = folder / "fuelhh_wind_20260101_20260201.json"
    if not forecast_files or not actual_path.exists():
        raise FileNotFoundError(
            f"Expected WINDFOR extracts and {actual_path.name} in {folder}."
        )

    seen: dict[tuple[datetime, datetime], float] = {}
    forecasts: list[ForecastRow] = []
    for path in forecast_files:
        payload = json.loads(path.read_text())
        if not isinstance(payload, list):
            raise ValueError(f"{path.name} is not a list of rows.")
        for row in payload:
            publish = parse_time(row["publishTime"])
            start = parse_time(row["startTime"])
            mw = float(row["generation"])
            key = (publish, start)
            previous = seen.get(key)
            if previous is not None and previous != mw:
                raise ValueError(f"Conflicting WINDFOR values for {key} in {path.name}.")
            if previous is None:
                seen[key] = mw
                forecasts.append(ForecastRow(publish, start, mw))

    actual_payload = json.loads(actual_path.read_text())
    actuals: list[ActualRow] = []
    for row in actual_payload:
        if row.get("fuelType") != "WIND":
            continue
        actuals.append(
            ActualRow(
                start_time=parse_time(row["startTime"]),
                settlement_date=date.fromisoformat(row["settlementDate"]),
                settlement_period=int(row["settlementPeriod"]),
                mw=float(row["generation"]),
                publish_time=parse_time(row["publishTime"]),
            )
        )
    if not forecasts or not actuals:
        raise ValueError("The extracts did not contain wind rows.")
    return Series(forecasts, actuals)


def build_database(series: Series | None = None) -> dict[str, int]:
    series = series or load_raw()
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            create table forecasts (
                publish_time text not null,
                start_time text not null,
                generation_mw real not null,
                primary key (publish_time, start_time)
            )
            """
        )
        connection.execute(
            """
            create table actuals (
                start_time text primary key,
                settlement_date text not null,
                settlement_period integer not null,
                generation_mw real not null,
                publish_time text not null
            )
            """
        )
        connection.executemany(
            "insert into forecasts values (?, ?, ?)",
            [(iso(row.publish_time), iso(row.start_time), row.mw) for row in series.forecasts],
        )
        # Keep the latest outturn if a half hour was revised.
        latest: dict[datetime, ActualRow] = {}
        for row in series.actuals:
            current = latest.get(row.start_time)
            if current is None or row.publish_time >= current.publish_time:
                latest[row.start_time] = row
        connection.executemany(
            "insert into actuals values (?, ?, ?, ?, ?)",
            [
                (
                    iso(row.start_time),
                    row.settlement_date.isoformat(),
                    row.settlement_period,
                    row.mw,
                    iso(row.publish_time),
                )
                for row in latest.values()
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return {"forecasts": len(series.forecasts), "actuals": len(latest)}


def load_database() -> Series:
    path = db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"No database at {path}. Run `python -m daymark.build` from backend/."
        )
    connection = sqlite3.connect(path)
    try:
        forecast_rows = connection.execute(
            "select publish_time, start_time, generation_mw from forecasts"
        ).fetchall()
        actual_rows = connection.execute(
            """
            select start_time, settlement_date, settlement_period, generation_mw, publish_time
            from actuals
            """
        ).fetchall()
    finally:
        connection.close()
    return Series(
        forecasts=[
            ForecastRow(parse_time(publish), parse_time(start), float(mw))
            for publish, start, mw in forecast_rows
        ],
        actuals=[
            ActualRow(
                start_time=parse_time(start),
                settlement_date=date.fromisoformat(settlement_date),
                settlement_period=int(period),
                mw=float(mw),
                publish_time=parse_time(publish),
            )
            for start, settlement_date, period, mw, publish in actual_rows
        ],
    )

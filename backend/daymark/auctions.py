"""GB day-ahead gates used by the desk.

The clock times are the published GMT gates. In January 2026, Europe/London is
on GMT, so the civil clock and GMT are the same. The pilot does not include a
summer day, when those clocks differ. Delivery intervals themselves are taken
from Elexon's settlement dates, not rebuilt from a timezone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

DECISION_START = date(2026, 1, 1)
DECISION_END = date(2026, 1, 31)

# Hours of a delivery day that a usable issue must cover. A newer issue with
# only a fragment of the day must not displace a complete older one.
MIN_COVER_HOURS = 20


@dataclass(frozen=True)
class Auction:
    id: str
    name: str
    gate_hour: int
    gate_minute: int
    product: str
    blurb: str

    @property
    def gate_clock(self) -> str:
        return f"{self.gate_hour:02d}:{self.gate_minute:02d}"


AUCTIONS: dict[str, Auction] = {
    "n2ex": Auction(
        id="n2ex",
        name="N2EX",
        gate_hour=9,
        gate_minute=50,
        product="Hourly",
        blurb=(
            "Nord Pool GB day-ahead auction. Gate closure 09:50 GMT. "
            "Results are published by 10:00 GMT."
        ),
    ),
    "epex": Auction(
        id="epex",
        name="EPEX hourly",
        gate_hour=9,
        gate_minute=20,
        product="Hourly",
        blurb=(
            "EPEX SPOT GB day-ahead hourly auction. Gate closure 09:20 GMT, "
            "before the 09:30 wind issue."
        ),
    ),
    "epex_hh": Auction(
        id="epex_hh",
        name="EPEX half-hour",
        gate_hour=15,
        gate_minute=30,
        product="Half-hour",
        blurb=(
            "EPEX SPOT GB day-ahead half-hour auction. Gate closure 15:30 GMT. "
            "Results are published from 15:45 GMT."
        ),
    ),
}

LEADS: tuple[int, ...] = (0, 15, 30)


def decision_dates() -> list[date]:
    days = []
    cursor = DECISION_START
    while cursor <= DECISION_END:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def delivery_date(decision: date) -> date:
    return decision + timedelta(days=1)


def gate_time(decision: date, auction: Auction) -> datetime:
    local = datetime(
        decision.year,
        decision.month,
        decision.day,
        auction.gate_hour,
        auction.gate_minute,
        tzinfo=LONDON,
    )
    return local.astimezone(ZoneInfo("UTC"))


def cutoff_time(decision: date, auction: Auction, lead_minutes: int) -> datetime:
    return gate_time(decision, auction) - timedelta(minutes=lead_minutes)


def timezone_name(day: date) -> str:
    probe = datetime(day.year, day.month, day.day, 12, tzinfo=LONDON)
    return probe.tzname() or "GMT"

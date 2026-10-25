"""Score the wind forecast a desk could have bid, and nothing later.

Error is forecast minus outturn. Positive means the issue was high and a desk
that counted on it was short of wind. The scored unit is the clock hour,
because WINDFOR is hourly. The half-hour book repeats that hourly value across
both settlement periods.

The level adjustment is a share of the forecast, k = total error / total
forecast, fit on the other delivery days. It describes January. It is not a
forecast for February.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from daymark.auctions import (
    AUCTIONS,
    DECISION_START,
    LEADS,
    MIN_COVER_HOURS,
    LONDON,
    Auction,
    cutoff_time,
    decision_dates,
    delivery_date,
    gate_time,
    timezone_name,
)
from daymark.store import Series, iso

MONTHS = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
MON = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
BUFFER_COVERAGES = (0.5, 0.7, 0.8, 0.9, 0.95)


class PilotError(Exception):
    """A request the pilot can explain."""


@dataclass(frozen=True)
class HourPoint:
    start: datetime
    forecast_mw: float
    actual_mw: float

    @property
    def error_mw(self) -> float:
        return self.forecast_mw - self.actual_mw


@dataclass(frozen=True)
class DayScore:
    decision: date
    delivery: date
    publish_time: datetime
    hours: tuple[HourPoint, ...]

    @property
    def slot(self) -> str:
        return slot_of(self.publish_time)


def long_label(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month]} {day.year}"


def heading(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month]}"


def short_label(day: date) -> str:
    return f"{day.day} {MON[day.month]}"


def slot_of(moment: datetime) -> str:
    local = moment.astimezone(LONDON)
    return f"{local.hour:02d}:{local.minute:02d}"


def minute_of(moment: datetime) -> int:
    local = moment.astimezone(LONDON)
    return local.hour * 60 + local.minute


def clock(moment: datetime) -> str:
    local = moment.astimezone(LONDON)
    return f"{local.hour:02d}:{local.minute:02d}"


def _slot_sort(slot: str) -> int:
    hour, minute = slot.split(":")
    return int(hour) * 60 + int(minute)


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def mae(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(abs(value) for value in values) / len(values)


def rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def percentile(values: list[float], probability: float) -> float | None:
    """Linear percentile. `probability` is between 0 and 1."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def correlation(left: list[float], right: list[float]) -> float | None:
    count = len(left)
    if count < 2 or count != len(right):
        return None
    mean_left = sum(left) / count
    mean_right = sum(right) / count
    numerator = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right))
    spread_left = math.sqrt(sum((x - mean_left) ** 2 for x in left))
    spread_right = math.sqrt(sum((y - mean_right) ** 2 for y in right))
    if spread_left == 0 or spread_right == 0:
        return None
    return numerator / (spread_left * spread_right)


def histogram(values: list[float], width: float = 500.0) -> list[dict[str, float]]:
    if not values:
        return []
    low = math.floor(min(values) / width) * width
    high = math.ceil(max(values) / width) * width
    if high == low:
        high = low + width
    bins = int(round((high - low) / width))
    while bins > 28:
        width *= 2
        low = math.floor(min(values) / width) * width
        high = math.ceil(max(values) / width) * width
        if high == low:
            high = low + width
        bins = int(round((high - low) / width))
    counts = [0] * bins
    for value in values:
        index = int((value - low) / width)
        if index == bins:
            index -= 1
        counts[index] += 1
    return [
        {"lo": low + index * width, "hi": low + (index + 1) * width, "count": counts[index]}
        for index in range(bins)
    ]


def hour_starts(series: Series, delivery: date) -> list[datetime]:
    starts = [
        row.start_time
        for row in series.actual.values()
        if row.settlement_date == delivery
        and row.start_time.minute == 0
        and row.start_time.second == 0
    ]
    return sorted(set(starts))


def points_from(series: Series, covered: dict[datetime, float]) -> list[HourPoint]:
    points = []
    for start, forecast in sorted(covered.items()):
        actual = series.hourly_actual(start)
        if actual is None:
            continue
        points.append(HourPoint(start, forecast, actual))
    return points


def choose_issue(
    series: Series, delivery: date, cutoff: datetime
) -> tuple[datetime, dict[datetime, float]] | None:
    hours = hour_starts(series, delivery)
    candidates: list[tuple[datetime, dict[datetime, float]]] = []
    for publish in series.publishes:
        if publish > cutoff:
            continue
        table = series.by_publish.get(publish, {})
        covered = {hour: table[hour] for hour in hours if hour in table}
        if covered:
            candidates.append((publish, covered))
    if not candidates:
        return None
    complete = [item for item in candidates if len(item[1]) >= MIN_COVER_HOURS]
    pool = complete or candidates
    return max(pool, key=lambda item: item[0])


def score_biddable_days(series: Series, auction: Auction, lead_minutes: int) -> list[DayScore]:
    scored = []
    for decision in decision_dates():
        delivery = delivery_date(decision)
        chosen = choose_issue(series, delivery, cutoff_time(decision, auction, lead_minutes))
        if chosen is None:
            continue
        publish, covered = chosen
        scored.append(
            DayScore(
                decision=decision,
                delivery=delivery,
                publish_time=publish,
                hours=tuple(points_from(series, covered)),
            )
        )
    return scored


def _covered(series: Series, publish: datetime, delivery: date) -> dict[datetime, float]:
    hours = hour_starts(series, delivery)
    table = series.by_publish.get(publish, {})
    return {hour: table[hour] for hour in hours if hour in table}


def _k_excluding(days: list[DayScore], delivery: date) -> tuple[float | None, int]:
    forecast = 0.0
    error = 0.0
    used = 0
    for day in days:
        if day.delivery == delivery or not day.hours:
            continue
        used += 1
        forecast += sum(point.forecast_mw for point in day.hours)
        error += sum(point.error_mw for point in day.hours)
    if used == 0 or forecast == 0:
        return None, 0
    return error / forecast, used


def auction_dict(auction: Auction) -> dict[str, str]:
    zone = timezone_name(DECISION_START)
    return {
        "id": auction.id,
        "name": auction.name,
        "gate_label": f"{auction.gate_clock} {zone}",
        "gate_clock": auction.gate_clock,
        "product": auction.product,
        "blurb": auction.blurb,
    }


def _summary(points: list[HourPoint], k: float | None) -> dict[str, float | int | None]:
    forecast_mwh = sum(point.forecast_mw for point in points)
    actual_mwh = sum(point.actual_mw for point in points)
    errors = [point.error_mw for point in points]
    adjusted_mwh = None if k is None else sum(point.forecast_mw * (1.0 - k) for point in points)
    return {
        "hours_scored": len(points),
        "hours_expected": 24,
        "forecast_mwh": forecast_mwh,
        "actual_mwh": actual_mwh,
        "error_mwh": forecast_mwh - actual_mwh,
        "mae_mw": mae(errors),
        "bias_mw": mean(errors),
        "adjusted_mwh": adjusted_mwh,
        "adjusted_error_mwh": None if adjusted_mwh is None else adjusted_mwh - actual_mwh,
    }


def _periods(
    series: Series, delivery: date, by_hour: dict[datetime, float], k: float | None
) -> list[dict]:
    rows = [row for row in series.actual.values() if row.settlement_date == delivery]
    rows.sort(key=lambda row: row.start_time)
    periods = []
    for row in rows:
        hour = row.start_time.replace(minute=0, second=0, microsecond=0)
        forecast = by_hour.get(hour)
        end = row.start_time + timedelta(minutes=30)
        adjusted = None if forecast is None or k is None else forecast * (1.0 - k)
        periods.append(
            {
                "sp": row.settlement_period,
                "start": iso(row.start_time),
                "start_label": clock(row.start_time),
                "end_label": clock(end),
                "forecast_mw": forecast,
                "actual_mw": row.mw,
                "error_mw": None if forecast is None else forecast - row.mw,
                "adjusted_mw": adjusted,
                "forecast_mwh": None if forecast is None else forecast * 0.5,
                "actual_mwh": row.mw * 0.5,
            }
        )
    return periods


def _vintage(
    series: Series,
    decision: date,
    delivery: date,
    publish: datetime,
    gate: datetime,
    cutoff: datetime,
    selected: datetime,
) -> dict:
    covered = _covered(series, publish, delivery)
    points = points_from(series, covered)
    forecast_mwh = sum(point.forecast_mw for point in points)
    actual_mwh = sum(point.actual_mw for point in points)
    return {
        "publish_time": iso(publish),
        "slot": slot_of(publish),
        "minute": minute_of(publish),
        "minutes_before_gate": (gate - publish).total_seconds() / 60.0,
        "biddable": publish <= cutoff,
        "selected": publish == selected,
        "hours_covered": len(covered),
        "forecast_mwh": forecast_mwh,
        "error_mwh": forecast_mwh - actual_mwh,
    }


def desk_view(
    series: Series,
    decision: date,
    auction: Auction,
    lead_minutes: int,
    issue: datetime | None = None,
) -> dict:
    if decision < decision_dates()[0] or decision > decision_dates()[-1]:
        raise PilotError("This pilot only covers decisions made in January 2026.")
    if lead_minutes not in LEADS:
        raise PilotError("Lead time must be 0, 15, or 30 minutes.")
    delivery = delivery_date(decision)
    gate = gate_time(decision, auction)
    cutoff = cutoff_time(decision, auction, lead_minutes)
    if issue is None:
        chosen = choose_issue(series, delivery, cutoff)
        if chosen is None:
            raise PilotError("No wind issue was published before this bid had to be in.")
        selected, by_hour = chosen
    else:
        if issue not in series.by_publish:
            raise PilotError("That issue was not published in this pilot.")
        by_hour = _covered(series, issue, delivery)
        if not by_hour:
            raise PilotError("That issue does not cover this delivery day.")
        selected = issue
    days = score_biddable_days(series, auction, lead_minutes)
    k, reference_days = _k_excluding(days, delivery)
    points = points_from(series, by_hour)
    vintages = []
    for publish in series.publishes:
        on_decision_day = publish.astimezone(LONDON).date() == decision
        if not on_decision_day and publish != selected:
            continue
        covered = _covered(series, publish, delivery)
        if len(covered) < MIN_COVER_HOURS and publish != selected:
            continue
        vintages.append(_vintage(series, decision, delivery, publish, gate, cutoff, selected))
    zone = timezone_name(decision)
    return {
        "decision_date": decision.isoformat(),
        "delivery_date": delivery.isoformat(),
        "decision_label": long_label(decision),
        "delivery_label": long_label(delivery),
        "delivery_heading": heading(delivery),
        "auction": auction_dict(auction),
        "lead_minutes": lead_minutes,
        "gate_time": iso(gate),
        "gate_minute": auction.gate_hour * 60 + auction.gate_minute,
        "cutoff_time": iso(cutoff),
        "cutoff_minute": minute_of(cutoff),
        "timezone": zone,
        "vintage": next(item for item in vintages if item["selected"]),
        "vintages": vintages,
        "haircut": {
            "k": k,
            "reference_days": reference_days,
            "reference": "other delivery days, using only the issue that was biddable",
        },
        "summary": _summary(points, k),
        "periods": _periods(series, delivery, by_hour, k),
    }


def _residuals(days: list[DayScore]) -> tuple[list[float], list[float], float | None]:
    total_error = sum(point.error_mw for day in days for point in day.hours)
    total_forecast = sum(point.forecast_mw for day in days for point in day.hours)
    total_count = sum(len(day.hours) for day in days)
    proportional: list[float] = []
    constant: list[float] = []
    full_k = total_error / total_forecast if total_forecast else None
    for day in days:
        day_error = sum(point.error_mw for point in day.hours)
        day_forecast = sum(point.forecast_mw for point in day.hours)
        others = total_count - len(day.hours)
        other_forecast = total_forecast - day_forecast
        if others <= 0 or other_forecast == 0:
            continue
        share = (total_error - day_error) / other_forecast
        flat = (total_error - day_error) / others
        for point in day.hours:
            proportional.append(point.error_mw - share * point.forecast_mw)
            constant.append(point.error_mw - flat)
    return proportional, constant, full_k


def _quintiles(points: list[HourPoint]) -> list[dict[str, float | int]]:
    ordered = sorted(points, key=lambda point: point.forecast_mw)
    count = len(ordered)
    if count < 5:
        return []
    bands = []
    for index in range(5):
        chunk = ordered[index * count // 5 : (index + 1) * count // 5]
        errors = [point.error_mw for point in chunk]
        bands.append(
            {
                "lo_mw": chunk[0].forecast_mw,
                "hi_mw": chunk[-1].forecast_mw,
                "bias_mw": mean(errors),
                "mae_mw": mae(errors),
                "n": len(chunk),
            }
        )
    return bands


def _previous_same_hour(start: datetime) -> datetime:
    local = start.astimezone(LONDON)
    return (local - timedelta(days=1)).astimezone(start.tzinfo)


def month_view(series: Series, auction: Auction, lead_minutes: int) -> dict:
    if lead_minutes not in LEADS:
        raise PilotError("Lead time must be 0, 15, or 30 minutes.")
    days = score_biddable_days(series, auction, lead_minutes)
    points = [point for day in days for point in day.hours]
    errors = [point.error_mw for point in points]
    proportional, constant, full_k = _residuals(days)
    persistence = []
    for point in points:
        baseline = series.hourly_actual(_previous_same_hour(point.start))
        if baseline is None:
            continue
        persistence.append(baseline - point.actual_mw)
    by_clock: dict[int, dict[date, float]] = defaultdict(dict)
    for day in days:
        for point in day.hours:
            by_clock[point.start.astimezone(LONDON).hour][day.delivery] = point.actual_mw
    climatology = []
    for day in days:
        for point in day.hours:
            hour = point.start.astimezone(LONDON).hour
            others = [
                value for key, value in by_clock[hour].items() if key != day.delivery
            ]
            if not others:
                continue
            climatology.append(sum(others) / len(others) - point.actual_mw)
    persistence_mae = mae(persistence)
    climatology_mae = mae(climatology)
    forecast_mae = mae(errors)
    by_hour_errors: dict[int, list[float]] = defaultdict(list)
    for point in points:
        by_hour_errors[point.start.astimezone(LONDON).hour].append(point.error_mw)
    used_counts = Counter(day.slot for day in days)
    usual_slot = None
    usual_days = 0
    if used_counts:
        usual_slot, usual_days = max(used_counts.items(), key=lambda item: (item[1], _slot_sort(item[0])))

    issue_rows = _issue_table(series, auction, lead_minutes, days)
    day_rows = []
    for day in days:
        forecast_mwh = sum(point.forecast_mw for point in day.hours)
        actual_mwh = sum(point.actual_mw for point in day.hours)
        k, _ = _k_excluding(days, day.delivery)
        adjusted = None if k is None else sum(point.forecast_mw * (1.0 - k) for point in day.hours)
        day_rows.append(
            {
                "decision_date": day.decision.isoformat(),
                "delivery_date": day.delivery.isoformat(),
                "label": short_label(day.delivery),
                "error_mwh": forecast_mwh - actual_mwh,
                "forecast_mwh": forecast_mwh,
                "actual_mwh": actual_mwh,
                "mae_mw": mae([point.error_mw for point in day.hours]),
                "slot": day.slot,
                "adjusted_error_mwh": None if adjusted is None else adjusted - actual_mwh,
            }
        )
    return {
        "auction": auction_dict(auction),
        "lead_minutes": lead_minutes,
        "summary": {
            "days": len(days),
            "hours": len(points),
            "mae_mw": forecast_mae,
            "rmse_mw": rmse(errors),
            "bias_mw": mean(errors),
            "correlation": correlation(
                [point.forecast_mw for point in points],
                [point.actual_mw for point in points],
            ),
            "mean_forecast_mw": mean([point.forecast_mw for point in points]),
            "mean_actual_mw": mean([point.actual_mw for point in points]),
            "total_forecast_mwh": sum(point.forecast_mw for point in points),
            "total_actual_mwh": sum(point.actual_mw for point in points),
            "total_error_mwh": sum(errors),
            "hours_high": sum(1 for value in errors if value > 0),
            "hours_low": sum(1 for value in errors if value < 0),
            "days_high": sum(1 for row in day_rows if row["error_mwh"] > 0),
            "days_low": sum(1 for row in day_rows if row["error_mwh"] < 0),
            "k": full_k,
            "loo_mae_mw": mae(proportional),
            "constant_loo_mae_mw": mae(constant),
            "persistence_mae_mw": persistence_mae,
            "climatology_mae_mw": climatology_mae,
            "skill_persistence": None
            if persistence_mae in (None, 0) or forecast_mae is None
            else 1 - forecast_mae / persistence_mae,
            "skill_climatology": None
            if climatology_mae in (None, 0) or forecast_mae is None
            else 1 - forecast_mae / climatology_mae,
            "p10_mw": percentile(errors, 0.10),
            "p50_mw": percentile(errors, 0.50),
            "p90_mw": percentile(errors, 0.90),
            "residual_p10_mw": percentile(proportional, 0.10),
            "residual_p50_mw": percentile(proportional, 0.50),
            "residual_p90_mw": percentile(proportional, 0.90),
            "usual_slot": usual_slot,
            "usual_slot_days": usual_days,
        },
        "quintiles": _quintiles(points),
        "histogram": histogram(errors),
        "histogram_adjusted": histogram(proportional),
        "by_hour": [
            {
                "hour": hour,
                "label": f"{hour:02d}",
                "bias_mw": mean(by_hour_errors[hour]),
                "mae_mw": mae(by_hour_errors[hour]),
                "n": len(by_hour_errors[hour]),
            }
            for hour in range(24)
            if hour in by_hour_errors
        ],
        "by_day": day_rows,
        "by_issue": issue_rows,
        "buffers": [
            {
                "coverage": coverage,
                "raw_mw": percentile(errors, coverage),
                "adjusted_mw": percentile(proportional, coverage),
            }
            for coverage in BUFFER_COVERAGES
        ],
        "notes": publish_notes(series),
    }


def _issue_table(
    series: Series, auction: Auction, lead_minutes: int, days: list[DayScore]
) -> list[dict]:
    located: dict[tuple[date, str], datetime] = {}
    for publish in series.publishes:
        local = publish.astimezone(LONDON)
        located[(local.date(), slot_of(publish))] = publish
    used = Counter(day.slot for day in days)
    slots = sorted({slot for _, slot in located}, key=_slot_sort)
    rows = []
    gate_minute = auction.gate_hour * 60 + auction.gate_minute - lead_minutes
    for slot in slots:
        errors: list[float] = []
        seen = 0
        for decision in decision_dates():
            publish = located.get((decision, slot))
            if publish is None:
                continue
            points = points_from(series, _covered(series, publish, delivery_date(decision)))
            if not points:
                continue
            seen += 1
            errors.extend(point.error_mw for point in points)
        if seen == 0:
            continue
        rows.append(
            {
                "slot": slot,
                "minute": _slot_sort(slot),
                "days_seen": seen,
                "days_used": used.get(slot, 0),
                "usable": _slot_sort(slot) <= gate_minute,
                "mae_mw": mae(errors),
                "bias_mw": mean(errors),
                "rmse_mw": rmse(errors),
                "n_hours": len(errors),
            }
        )
    return rows


def publish_notes(series: Series) -> list[str]:
    found: dict[date, set[str]] = {day: set() for day in decision_dates()}
    for publish in series.publishes:
        local_date = publish.astimezone(LONDON).date()
        if local_date in found:
            found[local_date].add(slot_of(publish))
    pattern_counts: Counter[frozenset[str]] = Counter(frozenset(slots) for slots in found.values())
    modal = set(max(pattern_counts, key=lambda slots: (pattern_counts[slots], len(slots))))
    notes = []
    for day in decision_dates():
        slots = found[day]
        if slots == modal:
            continue
        missing = sorted(modal - slots, key=_slot_sort)
        extra = sorted(set(slots) - modal, key=_slot_sort)
        parts = []
        if missing:
            parts.append("no " + " or ".join(missing) + " issue")
        if extra:
            parts.append("an extra " + " and ".join(extra) + " issue")
        if parts:
            notes.append(f"{long_label(day)} had " + " and ".join(parts) + ".")
    return notes


def meta_view(series: Series) -> dict:
    return {
        "auctions": [auction_dict(auction) for auction in AUCTIONS.values()],
        "leads": [
            {"minutes": 0, "label": "Bid at the gate"},
            {"minutes": 15, "label": "15 minutes to bid"},
            {"minutes": 30, "label": "30 minutes to bid"},
        ],
        "decision_start": decision_dates()[0].isoformat(),
        "decision_end": decision_dates()[-1].isoformat(),
        "default_decision_date": "2026-01-14",
        "forecast_rows": len(series.forecasts),
        "actual_rows": len(series.actual),
        "publish_count": len(series.publishes),
        "timezone": timezone_name(DECISION_START),
        "notes": publish_notes(series),
        "sources": {
            "forecast": "https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream",
            "forecast_docs": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream",
            "actual": "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream",
            "actual_docs": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream",
        },
    }

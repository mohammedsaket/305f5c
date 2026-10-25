from datetime import date, datetime, timedelta, timezone

from daymark.analysis import desk_view, month_view, percentile
from daymark.auctions import AUCTIONS, gate_time
from daymark.store import ActualRow, ForecastRow, Series

UTC = timezone.utc


def _stamp(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def _add_issue(forecasts, decision: date, hour: int, minute: int, megawatts, hours=range(24)):
    delivery = decision + timedelta(days=1)
    publish = _stamp(decision, hour, minute)
    for step in hours:
        start = _stamp(delivery, step)
        value = megawatts(step) if callable(megawatts) else megawatts
        forecasts.append(ForecastRow(publish, start, value))


def _add_outturn(actuals, delivery: date, first, second=None):
    for step in range(24):
        start = _stamp(delivery, step)
        left = first(step) if callable(first) else first
        right = left if second is None else second(step) if callable(second) else second
        actuals.append(ActualRow(start, delivery, step * 2 + 1, left, start))
        half = start + timedelta(minutes=30)
        actuals.append(ActualRow(half, delivery, step * 2 + 2, right, half))


def _series(*builders) -> Series:
    forecasts, actuals = [], []
    for builder in builders:
        builder(forecasts, actuals)
    return Series(forecasts, actuals)


def test_january_gate_is_gmt():
    gate = gate_time(date(2026, 1, 14), AUCTIONS["n2ex"])
    assert gate.utcoffset().total_seconds() == 0
    assert gate.hour == 9 and gate.minute == 50
    epex = gate_time(date(2026, 1, 14), AUCTIONS["epex"])
    assert epex.hour == 9 and epex.minute == 20
    half = gate_time(date(2026, 1, 14), AUCTIONS["epex_hh"])
    assert half.hour == 15 and half.minute == 30


def test_percentile_is_linear():
    assert percentile([0, 10], 0.5) == 5
    assert percentile([1, 2, 3], 0.5) == 2
    assert percentile([], 0.9) is None


def test_n2ex_takes_0930_and_epex_hourly_cannot():
    decision = date(2026, 1, 14)
    delivery = date(2026, 1, 15)

    def build(forecasts, actuals):
        _add_outturn(actuals, delivery, 1000)
        _add_issue(forecasts, decision, 7, 30, 1100)
        _add_issue(forecasts, decision, 9, 30, 1200)
        _add_issue(forecasts, decision, 11, 30, 1300)
        _add_issue(forecasts, decision, 15, 30, 1400)

    series = _series(build)
    n2ex = desk_view(series, decision, AUCTIONS["n2ex"], 0)
    assert n2ex["vintage"]["slot"] == "09:30"
    assert n2ex["vintage"]["biddable"] is True
    assert n2ex["vintage"]["minutes_before_gate"] == 20
    assert n2ex["summary"]["bias_mw"] == 200
    assert n2ex["summary"]["error_mwh"] == 200 * 24
    assert n2ex["periods"][0]["sp"] == 1
    assert n2ex["periods"][0]["forecast_mw"] == 1200
    assert n2ex["periods"][1]["forecast_mw"] == 1200

    epex = desk_view(series, decision, AUCTIONS["epex"], 0)
    assert epex["vintage"]["slot"] == "07:30"
    assert epex["summary"]["bias_mw"] == 100

    early = desk_view(series, decision, AUCTIONS["n2ex"], 30)
    assert early["vintage"]["slot"] == "07:30"
    assert early["vintages"][-1]["slot"] == "15:30"
    assert early["vintages"][-1]["biddable"] is False

    half = desk_view(series, decision, AUCTIONS["epex_hh"], 0)
    assert half["vintage"]["slot"] == "15:30"
    assert half["vintage"]["minutes_before_gate"] == 0

    hurried = desk_view(series, decision, AUCTIONS["epex_hh"], 15)
    assert hurried["vintage"]["slot"] == "11:30"


def test_a_fragment_does_not_replace_a_complete_issue():
    decision = date(2026, 1, 14)
    delivery = date(2026, 1, 15)

    def build(forecasts, actuals):
        _add_outturn(actuals, delivery, 100)
        _add_issue(forecasts, decision, 7, 30, 90)
        _add_issue(forecasts, decision, 9, 30, 80, hours=range(10))

    view = desk_view(_series(build), decision, AUCTIONS["n2ex"], 0)
    assert view["vintage"]["slot"] == "07:30"
    assert all(item["slot"] != "09:30" for item in view["vintages"])


def test_hourly_score_does_not_double_count_the_half_hours():
    decision = date(2026, 1, 14)
    delivery = date(2026, 1, 15)

    def build(forecasts, actuals):
        _add_outturn(actuals, delivery, 0, 10)
        _add_issue(forecasts, decision, 9, 30, 5)

    view = desk_view(_series(build), decision, AUCTIONS["n2ex"], 0)
    assert view["summary"]["mae_mw"] == 0
    assert view["summary"]["error_mwh"] == 0
    assert view["periods"][0]["error_mw"] == 5
    assert view["periods"][1]["error_mw"] == -5
    assert view["periods"][0]["forecast_mwh"] == 2.5
    assert view["periods"][0]["actual_mwh"] == 0


def test_haircut_is_fit_on_the_other_day_only():
    def build(forecasts, actuals):
        for decision, forecast, actual in (
            (date(2026, 1, 14), 100, 80),
            (date(2026, 1, 15), 200, 100),
        ):
            _add_outturn(actuals, decision + timedelta(days=1), actual)
            _add_issue(forecasts, decision, 9, 30, forecast)

    view = desk_view(_series(build), date(2026, 1, 14), AUCTIONS["n2ex"], 0)
    assert view["haircut"]["reference_days"] == 1
    assert view["haircut"]["k"] == 0.5
    assert view["summary"]["adjusted_mwh"] == 50 * 24
    assert view["summary"]["adjusted_error_mwh"] == (50 - 80) * 24

    month = month_view(_series(build), AUCTIONS["n2ex"], 0)
    # Day 1 residuals are -30 MW, day 2 residuals are 60 MW.
    assert month["summary"]["loo_mae_mw"] == 45
    assert month["summary"]["k"] == 0.4

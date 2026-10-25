from datetime import date, datetime, timezone

import pytest

from daymark.analysis import desk_view, meta_view, month_view
from daymark.auctions import AUCTIONS
from daymark.store import load_raw


@pytest.fixture(scope="module")
def series():
    return load_raw()


def test_meta_lists_the_three_gates(series):
    meta = meta_view(series)
    assert [item["id"] for item in meta["auctions"]] == ["n2ex", "epex", "epex_hh"]
    assert meta["timezone"] == "GMT"
    assert meta["forecast_rows"] == 18104


def test_n2ex_uses_the_0930_issue_all_month(series):
    view = month_view(series, AUCTIONS["n2ex"], 0)
    summary = view["summary"]
    assert summary["days"] == 31
    assert summary["hours"] == 744
    assert summary["usual_slot"] == "09:30"
    assert summary["usual_slot_days"] == 31
    assert summary["mae_mw"] == pytest.approx(2012.6, abs=2)
    assert summary["bias_mw"] == pytest.approx(1730, abs=2)
    assert summary["days_high"] == 28
    assert summary["hours_high"] == 627
    assert summary["correlation"] == pytest.approx(0.931, abs=0.01)
    assert summary["persistence_mae_mw"] == pytest.approx(3976, abs=2)
    assert summary["climatology_mae_mw"] == pytest.approx(3807, abs=2)
    assert summary["skill_persistence"] > 0.4
    assert summary["k"] == pytest.approx(0.133, abs=0.002)
    assert summary["loo_mae_mw"] < summary["mae_mw"]
    assert summary["loo_mae_mw"] < summary["constant_loo_mae_mw"]
    assert view["quintiles"][-1]["bias_mw"] > view["quintiles"][0]["bias_mw"] * 5
    assert view["notes"] == [
        "Thursday 15 January 2026 had no 11:30 issue and an extra 12:25 issue."
    ]


def test_earlier_and_later_gates_move_the_issue(series):
    epex = month_view(series, AUCTIONS["epex"], 0)
    assert epex["summary"]["usual_slot"] == "07:30"
    assert epex["summary"]["usual_slot_days"] == 31

    half = month_view(series, AUCTIONS["epex_hh"], 0)
    assert half["summary"]["usual_slot"] == "15:30"

    hurried = month_view(series, AUCTIONS["n2ex"], 30)
    assert hurried["summary"]["usual_slot"] == "07:30"

    half_hour_desk = month_view(series, AUCTIONS["epex_hh"], 15)
    used = {row["slot"]: row["days_used"] for row in half_hour_desk["by_issue"]}
    assert used["11:30"] == 30
    assert used["12:25"] == 1
    assert used["15:30"] == 0


def test_a_wednesday_book_is_the_0930_issue(series):
    view = desk_view(series, date(2026, 1, 14), AUCTIONS["n2ex"], 0)
    assert view["delivery_date"] == "2026-01-15"
    assert view["vintage"]["slot"] == "09:30"
    assert view["vintage"]["biddable"] is True
    assert len(view["periods"]) == 48
    assert view["summary"]["hours_scored"] == 24
    assert view["periods"][0]["sp"] == 1
    assert view["periods"][0]["start_label"] == "00:00"
    assert view["periods"][1]["forecast_mw"] == view["periods"][0]["forecast_mw"]


def test_counterfactual_issue_is_marked_too_late(series):
    view = desk_view(
        series,
        date(2026, 1, 14),
        AUCTIONS["n2ex"],
        0,
        issue=datetime(2026, 1, 14, 11, 30, tzinfo=timezone.utc),
    )
    assert view["vintage"]["slot"] == "11:30"
    assert view["vintage"]["biddable"] is False

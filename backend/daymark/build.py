"""Build the sqlite store and refuse an incomplete January."""

from __future__ import annotations

from daymark.analysis import score_biddable_days
from daymark.auctions import AUCTIONS, decision_dates, timezone_name
from daymark.store import build_database, load_raw


def validate(series) -> None:
    name = timezone_name(decision_dates()[0])
    if name != "GMT":
        raise SystemExit(f"January decisions were expected to be GMT, got {name}.")
    days = score_biddable_days(series, AUCTIONS["n2ex"], 0)
    short = [day for day in days if len(day.hours) != 24]
    if len(days) != 31 or short:
        detail = ", ".join(day.decision.isoformat() for day in short) or "missing days"
        raise SystemExit(f"January is incomplete for the N2EX gate ({detail}).")


def main() -> None:
    series = load_raw()
    validate(series)
    counts = build_database(series)
    print(
        f"Built {counts['forecasts']} forecast rows and {counts['actuals']} actuals "
        f"for {len(decision_dates())} decision days."
    )


if __name__ == "__main__":
    main()

"""HTTP edge for Daymark. Scoring lives in analysis.py; this module only parses
the request and returns the result."""

from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from daymark import __version__
from daymark.analysis import PilotError, desk_view, meta_view, month_view
from daymark.auctions import AUCTIONS, DECISION_END, DECISION_START
from daymark.store import load_database, parse_time, static_dir


@asynccontextmanager
async def lifespan(app: FastAPI):
    if app.state.series is None:
        app.state.series = load_database()
        print(
            f"Daymark {__version__} loaded {len(app.state.series.forecasts)} forecast rows "
            f"and {len(app.state.series.actual)} actuals."
        )
    yield


def create_app(series=None) -> FastAPI:
    app = FastAPI(
        title="Daymark",
        version=__version__,
        description="National wind as it stood when a GB day-ahead bid had to be in.",
        lifespan=lifespan,
    )
    app.state.series = series
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.exception_handler(PilotError)
    async def explain(_request: Request, exc: PilotError) -> JSONResponse:
        return JSONResponse({"error": str(exc)}, status_code=400)

    @app.middleware("http")
    async def cache_reads(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=300"
        return response

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": __version__}

    @app.get("/api/meta")
    def meta(request: Request) -> dict:
        return meta_view(request.app.state.series)

    @app.get("/api/desk")
    def desk(
        request: Request,
        decision_date: str,
        auction: str,
        lead_minutes: int = 0,
        issue: str | None = None,
    ) -> dict:
        day, chosen, lead, published = _selection(decision_date, auction, lead_minutes, issue)
        return desk_view(request.app.state.series, day, chosen, lead, published)

    @app.get("/api/accuracy")
    def accuracy(request: Request, auction: str = "n2ex", lead_minutes: int = 0) -> dict:
        if auction not in AUCTIONS:
            raise PilotError("Choose n2ex, epex, or epex_hh.")
        return month_view(request.app.state.series, AUCTIONS[auction], lead_minutes)

    @app.get("/api/book.csv")
    def book(
        request: Request,
        decision_date: str,
        auction: str,
        lead_minutes: int = 0,
        issue: str | None = None,
    ) -> Response:
        day, chosen, lead, published = _selection(decision_date, auction, lead_minutes, issue)
        view = desk_view(request.app.state.series, day, chosen, lead, published)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "settlement_period",
                "start_utc",
                "start_gmt",
                "end_gmt",
                "forecast_mw",
                "outturn_mw",
                "miss_mw",
                "haircut_mw",
                "forecast_mwh",
                "outturn_mwh",
            ]
        )
        for period in view["periods"]:
            writer.writerow(
                [
                    period["sp"],
                    period["start"],
                    period["start_label"],
                    period["end_label"],
                    _cell(period["forecast_mw"]),
                    _cell(period["actual_mw"]),
                    _cell(period["error_mw"]),
                    _cell(period["adjusted_mw"]),
                    _cell(period["forecast_mwh"]),
                    _cell(period["actual_mwh"]),
                ]
            )
        filename = f"daymark-{chosen.id}-{view['delivery_date']}.csv"
        return Response(
            buffer.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/")
    def index():
        return _page(request_path="")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api"):
            return JSONResponse({"error": "That API path does not exist."}, status_code=404)
        return _page(full_path)

    return app


def _page(request_path: str):
    folder = static_dir().resolve()
    if request_path:
        candidate = (folder / request_path).resolve()
        if folder == candidate or folder in candidate.parents:
            if candidate.is_file():
                return FileResponse(candidate)
    index = folder / "index.html"
    if index.is_file():
        return FileResponse(index)
    return JSONResponse(
        {"error": "The interface has not been built. Start the Vite dev server, or build the Docker image."},
        status_code=404,
    )


def _selection(
    decision_date: str, auction: str, lead_minutes: int, issue: str | None
) -> tuple[date, object, int, datetime | None]:
    try:
        day = date.fromisoformat(decision_date)
    except ValueError:
        raise PilotError("Use a date like 2026-01-14.") from None
    if day < DECISION_START or day > DECISION_END:
        raise PilotError("This pilot only covers decisions made in January 2026.")
    if auction not in AUCTIONS:
        raise PilotError("Choose n2ex, epex, or epex_hh.")
    published = None
    if issue:
        try:
            published = parse_time(issue)
        except ValueError:
            raise PilotError("Issue time should look like 2026-01-14T09:30:00Z.") from None
    return day, AUCTIONS[auction], lead_minutes, published


def _cell(value) -> str:
    if value is None:
        return ""
    return f"{value:.4f}".rstrip("0").rstrip(".")


app = create_app()

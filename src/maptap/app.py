import os
import pathlib
from contextlib import closing

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from maptap.db import connect
from maptap.metrics import (
    all_entries,
    combative_win_counts,
    daily_leaderboard_page,
    daily_win_counts,
    green_jersey_win_counts,
    hero_stats,
    player_summary,
)

_BASE = pathlib.Path(__file__).parent
_NUMBER_WORDS = (
    "Zero", "One", "Two", "Three", "Four", "Five", "Six",
    "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
)


def number_word(count: int) -> str:
    """The count spelled out and capitalised, or its digits once past twelve."""
    return _NUMBER_WORDS[count] if 0 <= count < len(_NUMBER_WORDS) else str(count)


templates = Jinja2Templates(directory=str(_BASE / "templates"))
templates.env.filters["number_word"] = number_word

app = FastAPI(title="Map Tappers League")
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")


def _conn():
    return connect(os.environ.get("MAPTAP_DB", "maptap.db"))


@app.get("/")
def index():
    return RedirectResponse("/days")


@app.get("/league", response_class=HTMLResponse)
def league(request: Request):
    with closing(_conn()) as conn:
        context = {"entries": all_entries(conn), "stats": hero_stats(conn), "active": "league"}
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/players", response_class=HTMLResponse)
def players(request: Request):
    with closing(_conn()) as conn:
        context = {"players": player_summary(conn), "stats": hero_stats(conn), "active": "players"}
    return templates.TemplateResponse(request, "players.html", context)


@app.get("/days", response_class=HTMLResponse)
def days(request: Request, page: int = 1):
    with closing(_conn()) as conn:
        context = {
            **daily_leaderboard_page(conn, page=page),
            "win_rows": [
                ("Yellow", daily_win_counts(conn, metric="cumulative")),
                ("Green", green_jersey_win_counts(conn)),
                ("Combative", combative_win_counts(conn)),
            ],
            "stats": hero_stats(conn),
            "active": "days",
        }
    return templates.TemplateResponse(request, "days.html", context)

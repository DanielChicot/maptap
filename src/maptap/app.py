import os
import pathlib
from contextlib import closing

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from maptap.db import connect
from maptap.metrics import (
    all_entries,
    daily_leaderboard,
    daily_win_counts,
    green_jersey_win_counts,
    hero_stats,
    player_summary,
)

_BASE = pathlib.Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))

app = FastAPI(title="Map Tappers League")
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")


def _conn():
    return connect(os.environ.get("MAPTAP_DB", "maptap.db"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with closing(_conn()) as conn:
        context = {"entries": all_entries(conn), "stats": hero_stats(conn), "active": "league"}
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/players", response_class=HTMLResponse)
def players(request: Request):
    with closing(_conn()) as conn:
        context = {"players": player_summary(conn), "stats": hero_stats(conn), "active": "players"}
    return templates.TemplateResponse(request, "players.html", context)


@app.get("/days", response_class=HTMLResponse)
def days(request: Request, sort: str = "cumulative"):
    if sort not in ("cumulative", "maptap"):
        sort = "cumulative"
    with closing(_conn()) as conn:
        context = {
            "days": daily_leaderboard(conn, sort=sort),
            "win_counts": daily_win_counts(conn, metric=sort),
            "green_wins": green_jersey_win_counts(conn),
            "stats": hero_stats(conn),
            "active": "days",
            "sort": sort,
        }
    return templates.TemplateResponse(request, "days.html", context)

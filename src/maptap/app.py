import os
import pathlib
from contextlib import closing

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from maptap.db import connect
from maptap.metrics import all_entries, daily_leaderboard, player_summary

_BASE = pathlib.Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))

app = FastAPI(title="Map Tappers League")
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")


def _conn():
    return connect(os.environ.get("MAPTAP_DB", "maptap.db"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with closing(_conn()) as conn:
        rows = all_entries(conn)
    return templates.TemplateResponse(request, "index.html", {"entries": rows})


@app.get("/players", response_class=HTMLResponse)
def players(request: Request):
    with closing(_conn()) as conn:
        rows = player_summary(conn)
    return templates.TemplateResponse(request, "players.html", {"players": rows})


@app.get("/days", response_class=HTMLResponse)
def days(request: Request):
    with closing(_conn()) as conn:
        rows = daily_leaderboard(conn)
    return templates.TemplateResponse(request, "days.html", {"days": rows})

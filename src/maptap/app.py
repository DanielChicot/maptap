import os
import pathlib

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
    conn = _conn()
    rows = all_entries(conn)
    conn.close()
    return templates.TemplateResponse(
        request, "index.html", {"entries": rows}
    )


@app.get("/players", response_class=HTMLResponse)
def players(request: Request):
    conn = _conn()
    rows = player_summary(conn)
    conn.close()
    return templates.TemplateResponse(
        request, "players.html", {"players": rows}
    )


@app.get("/days", response_class=HTMLResponse)
def days(request: Request):
    conn = _conn()
    rows = daily_leaderboard(conn)
    conn.close()
    return templates.TemplateResponse(request, "days.html", {"days": rows})

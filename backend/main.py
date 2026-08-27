from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.clickhouse import query
from routers import turns

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Pigugu Admin", version="0.1.0")
app.include_router(turns.router, prefix="/api")


@app.get("/api/health")
async def health():
    try:
        await query("SELECT 1")
        ch = "ok"
    except Exception as exc:  # noqa: BLE001 - surface any connectivity failure
        ch = f"error: {exc.__class__.__name__}"
    return {"status": "ok", "clickhouse": ch}


if WEB_DIR.exists():
    # Registered after the API routes so /api/* wins and everything else
    # falls through to the static page.
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

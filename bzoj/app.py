from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="BZOJ")
HOME = Path(__file__).parent / "templates" / "home.html"


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return HOME.read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

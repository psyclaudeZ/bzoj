from pathlib import Path
from html import escape

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from bzoj.execution import ExecutionError, run_hello_world

app = FastAPI(title="BZOJ")
HOME = Path(__file__).parent / "templates" / "home.html"


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return render_home()


def render_home(result: str = "") -> str:
    return HOME.read_text(encoding="utf-8").replace("<!-- result -->", result)


@app.post("/hello-world", response_class=HTMLResponse)
def hello_world() -> HTMLResponse:
    try:
        output = run_hello_world()
    except ExecutionError as exc:
        return HTMLResponse(
            render_home(f'<p role="alert">{escape(str(exc))}</p>'),
            status_code=502,
        )
    return HTMLResponse(
        render_home(f'<p role="status">Success</p><pre>{escape(output)}</pre>')
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from bzoj.runner import MAX_SOURCE_BYTES, run_source

ROOT = Path(__file__).parent
STARTER = (ROOT / "scripts" / "hello_world.py").read_text(encoding="utf-8")
templates = Jinja2Templates(directory=ROOT / "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger("uvicorn.error").warning(
        "Local execution enabled: submitted Python runs with your permissions. "
        "Timeouts and output limits are not a security sandbox."
    )
    yield


app = FastAPI(title="BZOJ", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="problems.html")


def problem_page(request: Request, source: str = STARTER, **context):
    return templates.TemplateResponse(
        request=request, name="problem.html", context={"source": source, **context}
    )


@app.get("/problems/hello-world", response_class=HTMLResponse)
def problem(request: Request):
    return problem_page(request)


@app.post("/problems/hello-world/submit", response_class=HTMLResponse)
async def submit(request: Request):
    # Prevent unrelated websites from posting Python into this local service.
    origin = request.headers.get("origin")
    if (origin is not None and origin != str(request.base_url).rstrip("/")) or (
        request.headers.get("sec-fetch-site") == "cross-site"
    ):
        raise HTTPException(403, "Submit code from this local workspace.")
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/x-www-form-urlencoded":
        raise HTTPException(415, "Expected an HTML form submission.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_SOURCE_BYTES * 3 + 128:
            raise HTTPException(413, "Source must be at most 64 KiB.")
    try:
        fields = parse_qs(body.decode("utf-8"), keep_blank_values=True, errors="strict", max_num_fields=2)
    except (UnicodeError, ValueError):
        raise HTTPException(400, "Invalid form submission.") from None
    if set(fields) != {"source"} or len(fields["source"]) != 1:
        raise HTTPException(400, "Provide one source field.")
    source = fields["source"][0]
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise HTTPException(413, "Source must be at most 64 KiB.")
    result = await run_in_threadpool(run_source, source)
    response = problem_page(request, source, result=result)
    if result.status == "Server error":
        response.status_code = 502
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

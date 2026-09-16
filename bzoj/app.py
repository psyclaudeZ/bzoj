from contextlib import asynccontextmanager
import logging
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from markupsafe import Markup
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from bzoj.runner import MAX_SOURCE_BYTES
from bzoj.judge import judge
from bzoj.problems import catalog

ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=ROOT / "templates")
templates.env.globals["css_version"] = lambda: (ROOT / "static" / "app.css").stat().st_mtime_ns
markdown = MarkdownIt("commonmark", {"html": False})
templates.env.filters["markdown"] = lambda text: Markup(markdown.render(text))


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
def home(request: Request, sort: str = "number"):
    problems, errors = catalog()
    sort = sort if sort in {"number", "name"} else "number"
    ordered = sorted(
        problems.values(),
        key=lambda problem: (problem.title.casefold(), problem.number)
        if sort == "name" else (problem.number,),
    )
    return templates.TemplateResponse(
        request=request, name="problems.html",
        context={"problems": ordered, "errors": errors, "sort": sort},
    )


def get_problem(slug: str):
    problems, _ = catalog()
    if slug not in problems:
        raise HTTPException(404, "Problem not found. Check the problem list for loading errors.")
    return problems[slug]


def problem_page(request: Request, problem, source: str | None = None, **context):
    return templates.TemplateResponse(
        request=request, name="problem.html", context={
            "problem": problem,
            "examples": [test for test in problem.tests if not test.hidden],
            "source": problem.starter_code if source is None else source, **context,
        }
    )


@app.get("/problems/{slug}", response_class=HTMLResponse)
def problem(request: Request, slug: str):
    return problem_page(request, get_problem(slug))


@app.post("/problems/{slug}/submit", response_class=HTMLResponse)
async def submit(request: Request, slug: str):
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
    problem = get_problem(slug)
    result = await run_in_threadpool(judge, problem, source)
    response = problem_page(request, problem, source, result=result)
    if result.status == "Judge error":
        response.status_code = 502
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

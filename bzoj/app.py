from contextlib import asynccontextmanager
import logging
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from markupsafe import Markup
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from bzoj.runner import MAX_SOURCE_BYTES
from bzoj.judge import judge
from bzoj.problems import catalog
from bzoj import storage
from bzoj.judge import JudgeResult

ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=ROOT / "templates")
templates.env.globals["css_version"] = lambda: (ROOT / "static" / "app.css").stat().st_mtime_ns
templates.env.globals["script_version"] = lambda: (ROOT / "static" / "problem.js").stat().st_mtime_ns
templates.env.globals["editor_version"] = lambda: (ROOT / "static" / "editor.bundle.js").stat().st_mtime_ns
markdown = MarkdownIt("commonmark", {"html": False})
templates.env.filters["markdown"] = lambda text: Markup(markdown.render(text))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_in_threadpool(storage.initialize)
    logging.getLogger("uvicorn.error").warning(
        "Local execution enabled: submitted Python runs with your permissions. "
        "Timeouts and output limits are not a security sandbox."
    )
    yield


app = FastAPI(title="BZOJ", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def home(request: Request, sort: str = "number", tag: str = ""):
    problems, errors = catalog()
    sort = sort if sort in {"number", "name"} else "number"
    tags = sorted({tag for problem in problems.values() for tag in problem.tags}, key=str.casefold)
    ordered = sorted(
        (problem for problem in problems.values() if not tag or tag in problem.tags),
        key=lambda problem: (problem.title.casefold(), problem.number)
        if sort == "name" else (problem.number,),
    )
    return templates.TemplateResponse(
        request=request, name="problems.html",
        context={"problems": ordered, "errors": errors, "sort": sort,
                 "tags": tags, "selected_tag": tag, "accepted_slugs": storage.accepted_slugs()},
    )


def get_problem(slug: str):
    problems, _ = catalog()
    if slug not in problems:
        raise HTTPException(404, "Problem not found. Check the problem list for loading errors.")
    return problems[slug]


def problem_page(request: Request, problem, source: str | None = None, **context):
    problems, _ = catalog()
    current = problems.get(problem.slug)
    parent = problems.get(current.follow_up_of) if current else None
    return templates.TemplateResponse(
        request=request, name="problem.html", context={
            "problem": problem,
            "parent": parent,
            "examples": [test for test in problem.tests if not test.hidden],
            "source": problem.starter_code if source is None else source, **context,
        }
    )


@app.get("/problems/{slug}", response_class=HTMLResponse)
def problem(request: Request, slug: str, submission: int | None = None):
    current = get_problem(slug)
    if submission is not None:
        record = storage.get_submission(submission)
        if record is None or record["problem_slug"] != slug:
            raise HTTPException(404, "Submission not found for this problem.")
        return problem_page(request, record["problem"], record["source"],
                            result=record["result"], submission_id=submission)
    return problem_page(request, current, storage.latest_source(slug))


@app.get("/problems/{slug}/parent-submission")
def parent_submission(slug: str):
    current = get_problem(slug)
    if current.follow_up_of is None:
        raise HTTPException(404, "This problem has no parent.")
    try:
        source = storage.latest_source(current.follow_up_of)
    except sqlite3.Error:
        raise HTTPException(503, "Could not load the parent submission. Try again.") from None
    if source is None:
        raise HTTPException(404, "No submissions for the parent problem yet.")
    return JSONResponse({"source": source}, headers={"Cache-Control": "no-store"})


@app.get("/submissions", response_class=HTMLResponse)
def history(request: Request, problem: str | None = None, before: int | None = None):
    rows = storage.list_submissions(problem, before)
    return templates.TemplateResponse(request=request, name="history.html", context={
        "submissions": rows[:50], "slug": problem,
        "older": rows[49]["id"] if len(rows) > 50 else None,
    })


@app.get("/problems/{slug}/history", response_class=HTMLResponse)
def problem_history(request: Request, slug: str, before: int | None = None):
    get_problem(slug)
    rows = storage.list_submissions(slug, before)
    return templates.TemplateResponse(request=request, name="history_panel.html", context={
        "slug": slug, "submissions": rows[:50],
        "older": rows[49]["id"] if len(rows) > 50 else None,
    })


@app.get("/problems/{slug}/history/{submission_id}", response_class=HTMLResponse)
def problem_history_detail(request: Request, slug: str, submission_id: int):
    record = storage.get_submission(submission_id)
    if record is None or record["problem_slug"] != slug:
        raise HTTPException(404, "Submission not found for this problem.")
    return templates.TemplateResponse(request=request, name="history_panel.html", context={
        "slug": slug, "submission": record, "result": record["result"],
    })


@app.get("/submissions/{submission_id}", response_class=HTMLResponse)
def submission_detail(request: Request, submission_id: int):
    record = storage.get_submission(submission_id)
    if record is None:
        raise HTTPException(404, "Submission not found.")
    return templates.TemplateResponse(request=request, name="submission.html", context={
        "submission": record, "result": record["result"],
    })


async def read_source(request: Request) -> str:
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
    return source


@app.post("/problems/{slug}/test", response_class=HTMLResponse)
async def test_samples(request: Request, slug: str):
    source = await read_source(request)
    problem = get_problem(slug)
    samples = [case for case in problem.tests if not case.hidden]
    if not samples:
        return problem_page(request, problem, source, sample_run=True,
                            error="This problem has no sample inputs.")
    try:
        result = await run_in_threadpool(judge, problem.model_copy(update={"tests": samples}), source)
    except Exception:
        logging.getLogger("uvicorn.error").exception("Sample execution failed")
        result = JudgeResult(status="Judge error", stderr="The judge could not complete this test run.")
    response = problem_page(request, problem, source, result=result, sample_run=True)
    if result.status == "Judge error":
        response.status_code = 502
    return response


@app.post("/problems/{slug}/submit", response_class=HTMLResponse)
async def submit(request: Request, slug: str):
    source = await read_source(request)
    problem = get_problem(slug)
    try:
        submission_id = await run_in_threadpool(storage.create_submission, problem, source)
    except sqlite3.Error:
        response = problem_page(request, problem, source, error="Could not save the submission. Code was not run.")
        response.status_code = 503
        return response
    try:
        result = await run_in_threadpool(judge, problem, source)
    except Exception:
        logging.getLogger("uvicorn.error").exception("Submission execution failed")
        result = JudgeResult(status="Judge error", stderr="The judge could not complete this submission.")
    try:
        await run_in_threadpool(storage.finish_submission, submission_id, result)
    except sqlite3.Error:
        response = problem_page(request, problem, source, result=result,
                                error="Code was saved, but saving its result failed.")
        response.status_code = 503
        return response
    if result.status == "Judge error":
        response = problem_page(request, problem, source, result=result, submission_id=submission_id)
        response.status_code = 502
        return response
    return RedirectResponse(f"/problems/{slug}?submission={submission_id}", status_code=303)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

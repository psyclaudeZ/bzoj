"""Private, local SQLite submission storage. Connections are scoped per operation."""

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from bzoj.judge import JudgeResult
from bzoj.problems import Problem

DB_PATH = Path(__file__).resolve().parent.parent / 'local' / 'bzoj.sqlite3'


def definition_hash(problem: Problem) -> str:
    definition = {'driver_code': problem.driver_code,
                  'tests': [test.model_dump() for test in problem.tests]}
    encoded = json.dumps(definition, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > 1:
                raise sqlite3.DatabaseError('Database schema is newer than this application.')
            if version == 0:
                db.execute('''CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    problem_slug TEXT NOT NULL,
                    problem_title TEXT NOT NULL,
                    definition_hash TEXT NOT NULL,
                    problem_snapshot TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )''')
                db.execute('CREATE INDEX IF NOT EXISTS submissions_problem ON submissions(problem_slug, id DESC)')
                db.execute('PRAGMA user_version = 1')
            yield db
    finally:
        db.close()


def initialize() -> None:
    with connection():
        pass


def create_submission(problem: Problem, source: str) -> int:
    pending = JudgeResult(status='Running')
    with connection() as db:
        cursor = db.execute('''INSERT INTO submissions
            (problem_slug, problem_title, definition_hash, problem_snapshot, source,
             status, result_json, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                problem.slug, problem.title, definition_hash(problem), problem.model_dump_json(), source,
                pending.status, json.dumps(asdict(pending)), 0,
                datetime.now(timezone.utc).isoformat(timespec='microseconds'),
            ))
        return cursor.lastrowid


def finish_submission(submission_id: int, result: JudgeResult) -> None:
    with connection() as db:
        db.execute('UPDATE submissions SET status=?, result_json=?, duration_ms=? WHERE id=?',
                   (result.status, json.dumps(asdict(result)), result.duration_ms, submission_id))


def get_submission(submission_id: int) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM submissions WHERE id=?', (submission_id,)).fetchone()
    if row is None:
        return None
    record = dict(row)
    record['result'] = json.loads(record.pop('result_json'))
    record['problem'] = Problem.model_validate_json(record.pop('problem_snapshot'))
    return record


def latest_source(slug: str) -> str | None:
    with connection() as db:
        row = db.execute('SELECT source FROM submissions WHERE problem_slug=? ORDER BY id DESC LIMIT 1',
                         (slug,)).fetchone()
    return row['source'] if row else None


def list_submissions(slug: str | None = None, before: int | None = None) -> list[dict]:
    clauses, values = [], []
    if slug is not None:
        clauses.append('problem_slug=?')
        values.append(slug)
    if before is not None:
        clauses.append('id<?')
        values.append(before)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    with connection() as db:
        rows = db.execute('SELECT id, problem_slug, problem_title, status, duration_ms, created_at '
                          'FROM submissions' + where + ' ORDER BY id DESC LIMIT 51', values).fetchall()
    return [dict(row) for row in rows]

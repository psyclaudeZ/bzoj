"""Single-file problem definitions; private files live under local/problems/."""

import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples" / "problems"
PRIVATE = ROOT / "local" / "problems"
MAX_PROBLEM_BYTES = 1024 * 1024


class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    input: JsonValue
    expected: JsonValue
    hidden: bool = False
    explanation: str = ""


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    schema_version: Literal[1]
    number: int = Field(gt=0)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    title: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    follow_up_of: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    statement: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    starter_code: str
    driver_code: str = Field(min_length=1)
    tests: list[TestCase] = Field(min_length=1, max_length=100)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: list[str]) -> list[str]:
        normalized = []
        for tag in tags:
            tag = tag.strip().lstrip("#").strip()
            if not tag:
                raise ValueError("Tags must not be blank.")
            if tag not in normalized:
                normalized.append(tag)
        return normalized


class ProblemError(ValueError):
    pass


def load_problem(path: Path) -> Problem:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_PROBLEM_BYTES + 1)
        if len(raw) > MAX_PROBLEM_BYTES:
            raise ValueError("Problem file exceeds 1 MiB.")
        data = json.loads(raw, parse_constant=lambda value: reject_constant(value))
        # JSON decoding can turn an overflowing numeric literal into infinity.
        json.dumps(data, allow_nan=False)
        problem = Problem.model_validate(data)
        compile(problem.driver_code, "driver_code", "exec")
        return problem
    except (OSError, ValueError, SyntaxError, RecursionError) as exc:
        raise ProblemError(f"{path.name}: {exc}") from exc


def reject_constant(value: str):
    raise ValueError(f"Non-finite JSON number: {value}")


def catalog() -> tuple[dict[str, Problem], list[str]]:
    loaded = []
    errors = []
    for directory in (EXAMPLES, PRIVATE):
        for path in sorted(directory.glob("*.json")):
            try:
                problem = load_problem(path)
                loaded.append((path, problem))
            except ProblemError as exc:
                errors.append(str(exc))
    slugs = Counter(problem.slug for _, problem in loaded)
    numbers = Counter(problem.number for _, problem in loaded)
    problems = {}
    for path, problem in sorted(loaded, key=lambda item: item[1].number):
        conflicts = []
        if slugs[problem.slug] > 1:
            conflicts.append(f"duplicate slug '{problem.slug}'")
        if numbers[problem.number] > 1:
            conflicts.append(f"duplicate number {problem.number}")
        if conflicts:
            errors.append(f"{path.name}: {', '.join(conflicts)}.")
        else:
            problems[problem.slug] = problem
    invalid = set()
    for slug in problems:
        seen = set()
        parent = slug
        while parent is not None:
            if parent in seen or parent not in problems:
                reason = "cycle" if parent in seen else f"missing parent '{parent}'"
                errors.append(f"{slug}: invalid follow_up_of chain ({reason}).")
                invalid.add(slug)
                break
            seen.add(parent)
            parent = problems[parent].follow_up_of
    return {slug: problem for slug, problem in problems.items() if slug not in invalid}, errors

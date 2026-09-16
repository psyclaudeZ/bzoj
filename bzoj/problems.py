"""Single-file problem definitions; private files live under local/problems/."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

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
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    title: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    starter_code: str
    driver_code: str = Field(min_length=1)
    tests: list[TestCase] = Field(min_length=1, max_length=100)


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
    problems = {}
    errors = []
    duplicates = set()
    for directory in (EXAMPLES, PRIVATE):
        for path in sorted(directory.glob("*.json")):
            try:
                problem = load_problem(path)
                if problem.slug in problems or problem.slug in duplicates:
                    problems.pop(problem.slug, None)
                    duplicates.add(problem.slug)
                    raise ProblemError(f"{path.name}: duplicate slug '{problem.slug}'.")
                problems[problem.slug] = problem
            except ProblemError as exc:
                errors.append(str(exc))
    return problems, errors

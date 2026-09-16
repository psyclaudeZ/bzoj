"""Run problem drivers sequentially with a submission-wide time/output budget."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import time

from bzoj import runner
from bzoj.problems import Problem

HARNESS = Path(__file__).with_name('harness.py').read_text(encoding='utf-8')


@dataclass
class JudgeResult:
    status: str = 'Accepted'
    stdout: str = ''
    stderr: str = ''
    duration_ms: int = 0
    cases: list[dict] = field(default_factory=list)


def equal(actual, expected) -> bool:
    if type(actual) is not type(expected):
        return type(actual) in (int, float) and type(expected) in (int, float) and actual == expected
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(equal(a, b) for a, b in zip(actual, expected))
    if isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(equal(actual[k], expected[k]) for k in actual)
    return actual == expected


def judge(problem: Problem, source: str) -> JudgeResult:
    if len(source.encode('utf-8')) > runner.MAX_SOURCE_BYTES:
        raise ValueError('Source must be at most 64 KiB.')
    result = JudgeResult()
    started = time.monotonic()
    remaining_output = runner.MAX_OUTPUT_BYTES
    stopped = False
    for index, test in enumerate(problem.tests, start=1):
        case = {'number': index, 'hidden': test.hidden, 'status': 'Not run'}
        result.cases.append(case)
        if stopped:
            continue
        remaining_time = runner.TIMEOUT_SECONDS - (time.monotonic() - started)
        if remaining_time <= 0:
            case['status'] = result.status = 'Time limit exceeded'
            stopped = True
            continue
        execution = runner.run_source(HARNESS, files={
            'user.py': source,
            'driver.py': problem.driver_code,
            'case.json': json.dumps(test.input, allow_nan=False),
        }, timeout=remaining_time, output_limit=remaining_output)
        remaining_output -= len(execution.stdout.encode('utf-8')) + len(execution.stderr.encode('utf-8'))
        remaining_output = max(0, remaining_output)
        case['status'] = execution.status
        if not test.hidden:
            result.stdout += execution.stdout
            result.stderr += execution.stderr
        if execution.status == 'Success':
            try:
                report = json.loads(execution.report)
                status = report['status']
                if status == 'Returned':
                    actual = report['actual']
                    case['status'] = 'Accepted' if equal(actual, test.expected) else 'Wrong answer'
                    if not test.hidden:
                        case.update(input=test.input, expected=test.expected, actual=actual)
                elif status in ('Runtime error', 'Judge error', 'Output limit exceeded'):
                    case['status'] = status
                else:
                    raise ValueError('Invalid report status')
            except (ValueError, KeyError, TypeError):
                # Includes user code exiting before the harness writes its result.
                case['status'] = 'Runtime error'
        elif execution.status == 'Server error':
            case['status'] = 'Judge error'
        if case['status'] != 'Accepted' and result.status == 'Accepted':
            result.status = case['status']
        if case['status'] in ('Time limit exceeded', 'Output limit exceeded', 'Judge error'):
            result.status = case['status']
            stopped = True
    result.duration_ms = round((time.monotonic() - started) * 1000)
    return result

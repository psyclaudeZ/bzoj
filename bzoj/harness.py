"""Child-process entry point. Run one case with fresh submission globals."""

import json
import math
from pathlib import Path
import traceback


def json_value(value):
    if value is None or type(value) in (bool, int, str):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(json_value(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and json_value(item) for key, item in value.items())
    return False


def main():
    namespace = {"__name__": "submission"}
    try:
        exec(compile(Path("user.py").read_text(), "user.py", "exec"), namespace)
    except BaseException:
        traceback.print_exc()
        return {"status": "Runtime error"}
    try:
        exec(compile(Path("driver.py").read_text(), "driver.py", "exec"), namespace)
        driver = namespace["run_case"]
        if not callable(driver):
            raise TypeError("driver_code must define run_case(case)")
        case = json.loads(Path("case.json").read_text())
    except BaseException:
        traceback.print_exc()
        return {"status": "Judge error"}
    try:
        actual = driver(case)
        if not json_value(actual):
            raise TypeError("run_case must return a JSON-compatible value")
        return {"status": "Returned", "actual": actual}
    except BaseException:
        traceback.print_exc()
        return {"status": "Runtime error"}


if __name__ == "__main__":
    report = json.dumps(main(), allow_nan=False)
    if len(report.encode("utf-8")) > 65536:
        report = json.dumps({"status": "Output limit exceeded"})
    Path("result.json").write_text(report, encoding="utf-8")

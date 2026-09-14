from pathlib import Path
import time
from unittest.mock import patch

import pytest

from bzoj.runner import MAX_OUTPUT_BYTES, MAX_SOURCE_BYTES, run_source


def test_executes_source_and_captures_streams() -> None:
    result = run_source("import sys\nprint(6 * 7)\nprint('detail', file=sys.stderr)")
    assert result.status == "Success"
    assert result.stdout == "42\n"
    assert result.stderr == "detail\n"
    assert result.exit_code == 0


@pytest.mark.parametrize("source", ["raise ValueError('bad input')", "def broken("])
def test_runtime_and_syntax_errors(source) -> None:
    result = run_source(source)
    assert result.status == "Runtime error"
    assert result.exit_code != 0
    assert "Error" in result.stderr


def test_infinite_loop_times_out() -> None:
    with patch("bzoj.runner.TIMEOUT_SECONDS", 0.2):
        result = run_source("print('started')\nwhile True: pass")
    assert result.status == "Time limit exceeded"
    assert result.stdout == "started\n"


def test_output_is_bounded() -> None:
    result = run_source("while True: print('x' * 8192)")
    assert result.status == "Output limit exceeded"
    assert len(result.stdout.encode()) == MAX_OUTPUT_BYTES


def test_temporary_files_are_cleaned() -> None:
    result = run_source("from pathlib import Path\nPath('test').touch()\nprint(Path.cwd())")
    assert result.status == "Success"
    assert not Path(result.stdout.strip()).exists()


def test_background_child_is_terminated(tmp_path) -> None:
    marker = tmp_path / "child-survived"
    child = f"import time; from pathlib import Path; time.sleep(0.7); Path({str(marker)!r}).touch()"
    source = f"import subprocess, sys\nsubprocess.Popen([sys.executable, '-c', {child!r}])"
    with patch("bzoj.runner.TIMEOUT_SECONDS", 0.2):
        result = run_source(source)
    assert result.status == "Time limit exceeded"
    time.sleep(0.8)
    assert not marker.exists()


def test_rejects_oversized_source() -> None:
    with pytest.raises(ValueError):
        run_source("x" * (MAX_SOURCE_BYTES + 1))


def test_spawn_failure_is_server_error() -> None:
    with patch("bzoj.runner.subprocess.Popen", side_effect=OSError):
        assert run_source("print('hello')").status == "Server error"

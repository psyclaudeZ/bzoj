import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from bzoj.execution import ExecutionError, run_hello_world


def test_runs_in_temporary_directory_and_cleans_up() -> None:
    original_run = subprocess.run
    directories = []

    def record_run(*args, **kwargs):
        directories.append(Path(kwargs["cwd"]))
        assert directories[-1].is_dir()
        return original_run(*args, **kwargs)

    with patch("bzoj.execution.subprocess.run", side_effect=record_run):
        assert run_hello_world() == "hello world"
    assert not directories[0].exists()


@pytest.mark.parametrize("source, message", [
    ("raise RuntimeError('broken')", "Script execution failed."),
    ("import time; time.sleep(10)", "Script timed out."),
])
def test_child_failure_and_timeout(tmp_path, source, message) -> None:
    script = tmp_path / "script.py"
    script.write_text(source, encoding="utf-8")
    with patch("bzoj.execution.SCRIPT", script), patch("bzoj.execution.TIMEOUT_SECONDS", 0.2):
        with pytest.raises(ExecutionError, match=message):
            run_hello_world()

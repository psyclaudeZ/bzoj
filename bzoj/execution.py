"""Execute the bundled demo script in a separate Python process."""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).parent / "scripts" / "hello_world.py"
TIMEOUT_SECONDS = 5


class ExecutionError(Exception):
    """The bundled script could not complete successfully."""


def run_hello_world() -> str:
    try:
        with TemporaryDirectory(prefix="bzoj-hello-") as workdir:
            result = subprocess.run(
                [sys.executable, "-I", str(SCRIPT.resolve())],
                cwd=workdir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=TIMEOUT_SECONDS,
                check=True,
            )
    except subprocess.TimeoutExpired as exc:
        raise ExecutionError("Script timed out.") from exc
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        raise ExecutionError("Script execution failed.") from exc
    return result.stdout.rstrip("\n")

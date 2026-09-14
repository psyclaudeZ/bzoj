"""Execute trusted local Python. Limits provide reliability, not a sandbox."""

from dataclasses import dataclass
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

TIMEOUT_SECONDS = 5
MAX_OUTPUT_BYTES = 64 * 1024
MAX_SOURCE_BYTES = 64 * 1024


@dataclass(frozen=True)
class RunResult:
    status: str
    stdout: str
    stderr: str
    exit_code: int | None
    duration_ms: int


def _kill_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_source(source: str) -> RunResult:
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("Source must be at most 64 KiB.")
    started = time.monotonic()
    output = {"stdout": bytearray(), "stderr": bytearray()}
    size = 0
    status = "Success"
    exit_code = None
    try:
        with TemporaryDirectory(prefix="bzoj-run-") as workdir:
            script = Path(workdir) / "submission.py"
            script.write_text(source, encoding="utf-8")
            with subprocess.Popen(
                [sys.executable, "-I", "-u", str(script)],
                cwd=workdir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            ) as process:
                try:
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
                        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
                        while selector.get_map() or process.poll() is None:
                            remaining = TIMEOUT_SECONDS - (time.monotonic() - started)
                            if remaining <= 0:
                                status = "Time limit exceeded"
                                break
                            for key, _ in selector.select(min(remaining, 0.05)):
                                chunk = os.read(key.fd, 8192)
                                if not chunk:
                                    selector.unregister(key.fileobj)
                                    continue
                                available = MAX_OUTPUT_BYTES - size
                                output[key.data].extend(chunk[:available])
                                size += min(len(chunk), available)
                                if len(chunk) > available:
                                    status = "Output limit exceeded"
                                    break
                            if status != "Success":
                                break
                finally:
                    # Also clean up ordinary descendants after a successful parent exit.
                    _kill_group(process)
                    process.wait()
                exit_code = process.returncode
                if status == "Success" and exit_code != 0:
                    status = "Runtime error"
    except OSError:
        status = "Server error"
        output["stderr"] = bytearray(b"The server could not start or complete execution.")
    return RunResult(
        status=status,
        stdout=output["stdout"].decode("utf-8", errors="replace"),
        stderr=output["stderr"].decode("utf-8", errors="replace"),
        exit_code=exit_code,
        duration_ms=round((time.monotonic() - started) * 1000),
    )

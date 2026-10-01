"""Run both local services and clean up their process groups on exit."""

from contextlib import suppress
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from typing import Sequence


def commands(root: Path) -> Sequence[tuple[list[str], Path]]:
    """Create the two service commands using optional server-only dotenv settings.

    Args:
        root: Repository directory.
    Returns:
        Backend and frontend argument lists with their working directories.
    Raises:
        RuntimeError: Dependencies have not been installed.
    """
    python = root / ".venv" / "bin" / "python"
    npm = shutil.which("npm")
    if not python.is_file() or not (root / "frontend" / "node_modules").is_dir() or npm is None:
        raise RuntimeError("Dependencies are missing. Run `make install` first.")
    backend = [str(python), "-m", "uvicorn", "tavern.app:create_default_app", "--factory",
               "--host", "127.0.0.1", "--port", "8000"]
    if (root / ".env").is_file():
        backend.extend(["--env-file", str(root / ".env")])
    return [(backend, root), ([npm, "run", "dev"], root / "frontend")]


def stop_processes(processes: Sequence[subprocess.Popen[bytes]]) -> None:
    """Stop both services, including children launched by npm.

    Args:
        processes: Service process-group leaders created by this launcher.
    """
    for process in processes:
        if process.poll() is None:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def main(root: Path) -> int:
    """Supervise the two services until interrupted or either exits.

    Args:
        root: Repository directory.
    Returns:
        Zero on Ctrl+C, or a service/setup error code.
    """
    processes: list[subprocess.Popen[bytes]] = []
    try:
        for command, directory in commands(root):
            processes.append(subprocess.Popen(command, cwd=directory, start_new_session=True))
        print("The Last Inn: http://127.0.0.1:5173 · Ctrl+C stops both services", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.2)
        return next((process.returncode for process in processes if process.returncode), 1)
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main(Path(__file__).resolve().parents[1]))

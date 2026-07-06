from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def main() -> int:
    port = os.environ.get("PORT", "10000")
    commands = [
        [sys.executable, "-m", "app.worker"],
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
            "--proxy-headers",
        ],
    ]
    processes = [subprocess.Popen(command) for command in commands]

    def stop_processes(*_: object) -> None:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        deadline = time.time() + 25
        while time.time() < deadline and any(process.poll() is None for process in processes):
            time.sleep(0.2)
        for process in processes:
            if process.poll() is None:
                process.kill()

    signal.signal(signal.SIGTERM, stop_processes)
    signal.signal(signal.SIGINT, stop_processes)

    try:
        while True:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    stop_processes()
                    return return_code
            time.sleep(1)
    finally:
        stop_processes()


if __name__ == "__main__":
    raise SystemExit(main())

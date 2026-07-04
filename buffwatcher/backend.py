from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path


LISTEN_PORT_RE = re.compile(r"LISTEN_PORT=(\d+)")


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundled_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return app_root()


def candidate_backend_paths() -> list[Path]:
    roots = [app_root(), bundled_root(), Path.cwd()]
    candidates: list[Path] = []
    for root in roots:
        candidates.extend(
            [
                root / "vendor" / "mabicat.exe",
                root / "resources" / "mabicat.exe",
                root / "mabicat.exe",
            ]
        )

    temp_root = Path(os.environ.get("TEMP", ""))
    if temp_root:
        candidates.extend(temp_root.glob("*/resources/mabicat.exe"))

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def find_backend(explicit_path: str | None = None) -> Path:
    if explicit_path:
        path = Path(explicit_path)
        if path.is_file():
            return path
        raise FileNotFoundError(f"backend not found: {path}")

    for path in candidate_backend_paths():
        if path.is_file():
            return path

    tried = "\n".join(str(path) for path in candidate_backend_paths()[:12])
    raise FileNotFoundError("mabicat.exe not found. Tried:\n" + tried)


@dataclass
class MabicatBackend:
    executable: Path
    requested_port: str = "auto"
    process: subprocess.Popen[str] | None = None
    port: int | None = None
    _lines: queue.Queue[tuple[str, str]] = field(default_factory=queue.Queue)
    _threads: list[threading.Thread] = field(default_factory=list)

    def start(self, *, timeout_seconds: float = 20) -> int:
        if self.process is not None:
            raise RuntimeError("backend already started")

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        args = [
            str(self.executable),
            "--no-browser",
            "--no-messagebox",
            "--port",
            str(self.requested_port),
        ]
        self.process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )

        self._start_reader("stdout", self.process.stdout)
        self._start_reader("stderr", self.process.stderr)

        deadline = time.monotonic() + timeout_seconds
        buffered: list[str] = []

        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break

            try:
                stream_name, line = self._lines.get(timeout=0.1)
            except queue.Empty:
                continue

            line = line.rstrip()
            if line:
                buffered.append(f"{stream_name}: {line}")
            match = LISTEN_PORT_RE.search(line)
            if match:
                self.port = int(match.group(1))
                return self.port

        exit_code = self.process.poll()
        detail = "\n".join(buffered[-20:]) or "no backend output"
        if exit_code is None:
            self.stop()
            raise TimeoutError("backend did not report LISTEN_PORT in time:\n" + detail)
        raise RuntimeError(f"backend exited with code {exit_code}:\n{detail}")

    def stop(self) -> None:
        process = self.process
        if process is None:
            return

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

        self.process = None

    def _start_reader(self, stream_name: str, stream: object) -> None:
        if stream is None:
            return

        def run() -> None:
            for line in stream:  # type: ignore[operator]
                self._lines.put((stream_name, line))

        thread = threading.Thread(target=run, name=f"mabicat-{stream_name}", daemon=True)
        thread.start()
        self._threads.append(thread)

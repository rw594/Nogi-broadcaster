from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from .backend import MabicatBackend, app_root, find_backend
from .events import DEFAULT_TZ_OFFSET_HOURS
from .live import DEFAULT_HISTORIES, DEFAULT_WS_PORT, cmd_watch_file, cmd_watch_ws
from .single_instance import SingleInstance


def configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)
        except AttributeError:
            pass


def default_record_path() -> Path:
    name = time.strftime("%Y%m%d-%H%M%S-buffwatcher-raw.ndjson.gz")
    return app_root() / "logs" / name


def default_alert_record_path() -> Path:
    name = time.strftime("%Y%m%d-%H%M%S-buffwatcher-alerts.ndjson")
    return app_root() / "logs" / name


def paired_alert_record_path(record_events: str) -> Path:
    if not record_events:
        return default_alert_record_path()
    path = Path(record_events)
    name = path.name
    suffix = "-buffwatcher-raw.ndjson.gz"
    if name.endswith(suffix):
        return path.with_name(name[: -len(suffix)] + "-buffwatcher-alerts.ndjson")
    return default_alert_record_path()


def existing_backend_available(host: str, port: int, path: str) -> bool:
    del path
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def micopunch_is_running() -> bool:
    if os.name != "nt":
        return False
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq MicoPunch.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=creationflags,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "MicoPunch.exe" in result.stdout


def is_transient_backend_traffic_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "could not detect game traffic",
            "newgameserverpacketreader failed",
            "the source string must not be empty",
            "backend did not report listen_port",
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run 洛奇播报小助手 with its own local packet backend."
    )
    parser.add_argument("--config", default=str(app_root() / "buffwatcher.config.local.json"))
    parser.add_argument("--backend", help="Path to mabicat.exe. Defaults to bundled vendor/mabicat.exe.")
    parser.add_argument("--backend-port", default="auto")
    parser.add_argument("--port", type=int, default=DEFAULT_WS_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--path", default="/ws")
    parser.add_argument("--histories", default=DEFAULT_HISTORIES)
    parser.add_argument(
        "--prefer-micopunch-file",
        action="store_true",
        help="If MicoPunch is running, read its raw history file instead of connecting to its websocket backend.",
    )
    parser.add_argument(
        "--block-if-micopunch-running",
        action="store_true",
        help="Exit instead of starting when MicoPunch is already running; start 洛奇播报小助手 first for coexistence.",
    )
    parser.add_argument(
        "--reuse-existing-backend",
        action="store_true",
        help="Use an already-running MicoPunch backend on --port instead of starting the bundled mabicat backend.",
    )
    parser.add_argument("--tz-offset-hours", type=int, default=DEFAULT_TZ_OFFSET_HOURS)
    parser.add_argument("--poll-seconds", type=float, default=0.1)
    parser.add_argument("--reconnect-seconds", type=float, default=3)
    parser.add_argument("--idle-reconnect-seconds", type=float, default=20)
    parser.add_argument(
        "--backend-idle-reconnects",
        type=int,
        default=3,
        help="Restart the bundled backend after this many idle websocket reconnects. Use 0 to disable.",
    )
    parser.add_argument("--status-interval", type=float, default=30.0)
    parser.add_argument("--self-id")
    parser.add_argument("--no-self-filter", action="store_true")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--no-bell", action="store_true")
    parser.add_argument("--verbose-events", action="store_true")
    parser.add_argument(
        "--record-events",
        default="auto",
        help="Write received events to this .ndjson.gz path. Use 'auto' for BuffWatcher/logs.",
    )
    parser.add_argument("--no-record", action="store_true")
    parser.add_argument(
        "--record-alerts",
        default="auto",
        help="Write alert timing diagnostics to this .ndjson path. Use 'auto' for BuffWatcher/logs.",
    )
    parser.add_argument("--no-alert-log", action="store_true")
    parser.add_argument("--max-seconds", type=float, default=0)
    return parser


def main() -> int:
    configure_output()
    args = build_parser().parse_args()
    lock = SingleInstance(app_root() / "buffwatcher.lock")
    if not lock.acquire():
        print("[standalone] 洛奇播报小助手 is already running in this folder.")
        return 2

    backend_path: Path | None = None
    backend: MabicatBackend | None = None

    def start_backend() -> int:
        nonlocal backend
        if backend_path is None:
            raise RuntimeError("backend path is not available")
        attempt = 0
        while True:
            attempt += 1
            backend = MabicatBackend(backend_path, requested_port=args.backend_port)
            try:
                port = backend.start()
            except Exception as exc:
                if backend is not None:
                    backend.stop()
                    backend = None
                if not is_transient_backend_traffic_error(exc):
                    raise
                print(
                    "[standalone] packet backend did not detect game traffic; "
                    f"retrying in 5s (attempt {attempt}). "
                    "Keep Mabinogi connected and move or refresh one BUFF once."
                )
                time.sleep(5)
                continue
            print(f"[standalone] backend port: {port}")
            return port

    def restart_backend() -> int:
        nonlocal backend
        print("[standalone] restarting packet backend...")
        if backend is not None:
            backend.stop()
            backend = None
        return start_backend()

    try:
        print("[standalone] 洛奇播报小助手")
        record_events = ""
        if not args.no_record:
            record_events = str(default_record_path()) if args.record_events == "auto" else args.record_events
        record_alerts = ""
        if not args.no_alert_log:
            if args.record_alerts == "auto":
                record_alerts = str(paired_alert_record_path(record_events))
            else:
                record_alerts = args.record_alerts

        if args.block_if_micopunch_running and micopunch_is_running():
            print(
                "[standalone] MicoPunch is already running. "
                "For coexistence, close MicoPunch, start 洛奇播报小助手 first, "
                "then start MicoPunch."
            )
            return 3

        if args.prefer_micopunch_file and micopunch_is_running():
            print(
                "[standalone] MicoPunch detected; "
                f"using raw file mode from {args.histories}"
            )
            file_args = argparse.Namespace(
                config=str(Path(args.config)),
                histories=args.histories,
                host=args.host,
                port=args.port,
                path=args.path,
                tz_offset_hours=args.tz_offset_hours,
                poll_seconds=args.poll_seconds,
                reconnect_seconds=args.reconnect_seconds,
                idle_reconnect_seconds=args.idle_reconnect_seconds,
                status_interval=args.status_interval,
                self_id=args.self_id,
                no_self_filter=args.no_self_filter,
                play_existing=False,
                no_audio=args.no_audio,
                no_bell=args.no_bell,
                verbose_events=args.verbose_events,
                record_events=record_events,
                record_alerts=record_alerts,
                max_seconds=args.max_seconds,
            )
            return cmd_watch_file(file_args)

        use_existing_backend = (
            args.reuse_existing_backend
            and str(args.backend_port).lower() == "auto"
            and existing_backend_available(args.host, args.port, args.path)
        )
        if use_existing_backend:
            port = args.port
            print(
                "[standalone] existing MicoPunch backend detected; "
                f"using ws://{args.host}:{port}{args.path}"
            )
        else:
            backend_path = find_backend(args.backend)
            print(f"[standalone] backend: {backend_path}")
            print("[standalone] starting packet backend...")
            port = start_backend()

        ws_args = argparse.Namespace(
            config=str(Path(args.config)),
            histories="",
            host=args.host,
            port=port,
            path=args.path,
            tz_offset_hours=args.tz_offset_hours,
            poll_seconds=args.poll_seconds,
            reconnect_seconds=args.reconnect_seconds,
            idle_reconnect_seconds=args.idle_reconnect_seconds,
            status_interval=args.status_interval,
            self_id=args.self_id,
            no_self_filter=args.no_self_filter,
            play_existing=False,
            no_audio=args.no_audio,
            no_bell=args.no_bell,
            verbose_events=args.verbose_events,
            record_events=record_events,
            record_alerts=record_alerts,
            max_seconds=args.max_seconds,
            restart_backend=None if use_existing_backend else restart_backend,
            backend_restart_after_idle_reconnects=(
                0 if use_existing_backend else max(0, args.backend_idle_reconnects)
            ),
            reset_self_on_backend_restart=True,
        )
        return cmd_watch_ws(ws_args)
    finally:
        if backend is not None:
            print("[standalone] stopping packet backend")
            backend.stop()
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())

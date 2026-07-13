from __future__ import annotations

import codecs
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102
LOG_SESSION_DIR_ENV = "NOGI_BROADCASTER_LOG_SESSION_DIR"
PRODUCT_NAME = "洛奇播报小助手"
VERSION_RE = re.compile(r"(?:^|\s)(V\d+(?:\.\d+)+)(?:\s|$)", re.IGNORECASE)


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def package_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parent.parent


def extract_version_label(text: str) -> str:
    match = VERSION_RE.search(text or "")
    if not match:
        return ""
    version = match.group(1)
    if version.startswith("v"):
        return "V" + version[1:]
    return version


def package_title(root: Path | None = None) -> str:
    base = root or package_root()
    for info_path in [base / "package-info.json", base.parent / "package-info.json"]:
        try:
            data = json.loads(info_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        display_name = str(data.get("display_name") or "").strip()
        if display_name:
            return display_name
        version_label = str(data.get("version_label") or "").strip()
        if version_label:
            return f"{PRODUCT_NAME} {version_label}"

    for candidate in [base.parent.name, Path(sys.executable).stem]:
        version_label = extract_version_label(candidate)
        if version_label:
            return f"{PRODUCT_NAME} {version_label}"
    return PRODUCT_NAME


def watcher_dir(root: Path | None = None) -> Path:
    return (root or package_root()) / "BuffWatcher"


def watcher_exe(root: Path | None = None) -> Path:
    return watcher_dir(root) / "BuffWatcher.exe"


def log_dir(root: Path | None = None) -> Path:
    return watcher_dir(root) / "logs"


def create_log_session_dir(
    root: Path | None = None, *, stamp: str | None = None
) -> Path:
    session_stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    path = log_dir(root) / f"{session_stamp}-启动日志"
    path.mkdir(parents=True, exist_ok=True)
    return path


def status_json_path(root: Path | None = None) -> Path:
    return log_dir(root) / "launcher-status.json"


def process_is_running(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_launcher_status(root: Path | None = None) -> dict[str, object] | None:
    path = status_json_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def write_launcher_status(
    root: Path,
    *,
    pid: int,
    log_path: Path,
    started_by: str,
) -> None:
    path = status_json_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "pid": int(pid),
        "log_path": str(log_path),
        "started_by": started_by,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def configure_console() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True, errors="replace")
        sys.stderr.reconfigure(line_buffering=True, errors="replace")
    except TypeError:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except AttributeError:
        pass
    if os.name == "nt":
        try:
            ctypes.windll.kernel32.SetConsoleTitleW(package_title())
        except OSError:
            pass


def run_quiet(args: list[str]) -> None:
    creationflags = CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            check=False,
        )
    except OSError:
        pass


def kill_stale_processes() -> None:
    run_quiet(["taskkill", "/F", "/T", "/IM", "BuffWatcher.exe"])


def create_kill_on_close_job() -> wintypes.HANDLE | None:
    if os.name != "nt":
        return None

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None

    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(
        job,
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        kernel32.CloseHandle(job)
        return None
    return job


def assign_to_job(job: wintypes.HANDLE | None, process: subprocess.Popen[bytes]) -> bool:
    if not job or os.name != "nt":
        return False
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        return bool(kernel32.AssignProcessToJobObject(job, int(process._handle)))
    except OSError:
        return False


def close_handle(handle: wintypes.HANDLE | None) -> None:
    if handle and os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle(handle)
        except OSError:
            pass


def read_new_log_text(
    log_path: Path, offset: int, decoder: codecs.IncrementalDecoder
) -> tuple[int, str]:
    try:
        with log_path.open("rb") as stream:
            stream.seek(offset)
            data = stream.read()
            offset = stream.tell()
    except OSError:
        return offset, ""

    if not data:
        return offset, ""
    return offset, decoder.decode(data)


def tail_log(log_path: Path, process: subprocess.Popen[bytes]) -> None:
    offset = 0
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    while process.poll() is None:
        offset, text = read_new_log_text(log_path, offset, decoder)
        if text:
            print(text, end="")
        time.sleep(0.2)

    for _ in range(5):
        offset, text = read_new_log_text(log_path, offset, decoder)
        if text:
            print(text, end="")
        time.sleep(0.1)

    leftover = decoder.decode(b"", final=True)
    if leftover:
        print(leftover, end="")


def tail_log_for_pid(log_path: Path, pid: int) -> None:
    offset = 0
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    print(f"[launcher] attached to running core pid {pid}")
    print(f"[launcher] log: {log_path}")
    print("[launcher] close this window to stop viewing logs; the plugin keeps running")
    print()
    while process_is_running(pid):
        offset, text = read_new_log_text(log_path, offset, decoder)
        if text:
            print(text, end="")
        time.sleep(0.2)

    for _ in range(5):
        offset, text = read_new_log_text(log_path, offset, decoder)
        if text:
            print(text, end="")
        time.sleep(0.1)

    leftover = decoder.decode(b"", final=True)
    if leftover:
        print(leftover, end="")
    print()
    print("[launcher] core process is no longer running")


def stop_process(process: subprocess.Popen[bytes], job: wintypes.HANDLE | None) -> None:
    close_handle(job)
    if process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass


def main() -> int:
    configure_console()
    root = package_root()
    core_dir = watcher_dir(root)
    core_exe = watcher_exe(root)
    logs = log_dir(root)
    logs.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    session_logs = create_log_session_dir(root, stamp=stamp)
    log_path = session_logs / "console.log"
    status_path = session_logs / "launcher-status.log"

    print("[launcher] 洛奇播报小助手")
    print(f"[launcher] core: {core_exe}")

    status = read_launcher_status(root)
    if status is not None:
        try:
            status_pid = int(status.get("pid", 0))
        except (TypeError, ValueError):
            status_pid = 0
        status_log = Path(str(status.get("log_path", "")))
        if status_pid > 0 and status_log.is_file() and process_is_running(status_pid):
            tail_log_for_pid(status_log, status_pid)
            return 0

    print("[launcher] cleaning old processes...")
    kill_stale_processes()
    time.sleep(0.8)

    if not core_exe.is_file():
        print(f"[launcher] BuffWatcher.exe not found: {core_exe}")
        print("[launcher] press Enter to close")
        input()
        return 1

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env[LOG_SESSION_DIR_ENV] = str(session_logs)
    creationflags = 0
    if os.name == "nt":
        creationflags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

    print("[launcher] starting packet listener in protected child process...")
    print(f"[launcher] log: {log_path}")
    print("[launcher] close this window or press Ctrl+C to stop")
    print()

    process: subprocess.Popen[bytes] | None = None
    job: wintypes.HANDLE | None = None
    try:
        with log_path.open("ab", buffering=0) as log:
            process = subprocess.Popen(
                [
                    str(core_exe),
                    "--no-bell",
                    "--block-if-micopunch-running",
                ],
                cwd=str(core_dir),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                creationflags=creationflags,
            )

            job = create_kill_on_close_job()
            assigned = assign_to_job(job, process)
            write_launcher_status(
                root,
                pid=process.pid,
                log_path=log_path,
                started_by="console",
            )
            with status_path.open("a", encoding="utf-8") as status:
                status.write(
                    f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"started pid {process.pid}, job_assigned={assigned}, log={log_path}\n"
                )

            tail_log(log_path, process)

        code = process.poll() if process is not None else 1
        print()
        print(f"[launcher] 洛奇播报小助手 stopped with code {code}")
        return int(code or 0)
    except KeyboardInterrupt:
        print()
        print("[launcher] stopping...")
        return 0
    finally:
        if process is not None:
            stop_process(process, job)
        else:
            close_handle(job)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys


RUNTIME_DIR_NAME = "程序文件"
LAUNCHER_RELATIVE = Path("BuffWatcherLauncher") / "BuffWatcherLauncher.exe"
PRODUCT_NAME = "洛奇播报小助手"
VERSION_RE = re.compile(r"(?:^|\s)(V\d+(?:\.\d+)+)(?:\s|$)", re.IGNORECASE)


def entry_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def package_title(root: Path | None = None) -> str:
    base = root or entry_root()
    try:
        data = json.loads((base / "package-info.json").read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        data = {}
    display_name = str(data.get("display_name") or "").strip()
    if display_name:
        return display_name
    version_label = str(data.get("version_label") or "").strip()
    if version_label:
        return f"{PRODUCT_NAME} {version_label}"
    match = VERSION_RE.search(Path(sys.executable).stem if getattr(sys, "frozen", False) else base.name)
    if match:
        version = match.group(1)
        if version.startswith("v"):
            version = "V" + version[1:]
        return f"{PRODUCT_NAME} {version}"
    return PRODUCT_NAME


def show_error(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, package_title(), 0x10)
    else:
        print(message, file=sys.stderr)


def is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def find_launcher(root: Path) -> Path | None:
    candidates = [
        root / RUNTIME_DIR_NAME / LAUNCHER_RELATIVE,
        root / LAUNCHER_RELATIVE,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def launch(launcher: Path) -> int:
    launcher_dir = launcher.parent
    if os.name == "nt" and not is_admin():
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            str(launcher),
            None,
            str(launcher_dir),
            1,
        )
        if result <= 32:
            show_error("启动失败：没有获得管理员权限。")
            return 1
        return 0

    subprocess.Popen([str(launcher)], cwd=str(launcher_dir))
    return 0


def main() -> int:
    root = entry_root()
    launcher = find_launcher(root)
    if launcher is None:
        show_error("启动失败：找不到程序文件中的启动器。")
        return 1
    return launch(launcher)

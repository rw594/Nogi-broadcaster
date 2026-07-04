from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request
import zipfile


UPDATE_METADATA_URL = (
    "https://github.com/rw594/Nogi-broadcaster/releases/latest/download/latest.json"
)
VERSION_RE = re.compile(r"v?(\d+(?:\.\d+)+)", re.IGNORECASE)


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    version_code: int
    release_name: str
    download_url: str
    sha256: str
    size: int
    mandatory: bool
    notes: tuple[str, ...]


@dataclass(frozen=True)
class PreparedUpdate:
    temp_dir: Path
    source_root: Path
    script_path: Path


def version_code_from_text(text: str) -> int:
    match = VERSION_RE.search(text or "")
    if not match:
        return 0
    parts = [int(part) for part in match.group(1).split(".")]
    if not parts:
        return 0
    code = parts[0] * 100
    if len(parts) >= 2:
        code += parts[1]
    if len(parts) >= 3:
        code = code * 100 + parts[2]
    return code


def current_version_code(runtime_root: Path, display_title: str = "") -> int:
    for info_path in [runtime_root / "package-info.json", runtime_root.parent / "package-info.json"]:
        try:
            data = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("version_code", "versionCode"):
            try:
                code = int(data.get(key) or 0)
            except (TypeError, ValueError):
                code = 0
            if code > 0:
                return code
        for key in ("version_label", "versionLabel", "display_name", "release_name"):
            code = version_code_from_text(str(data.get(key) or ""))
            if code > 0:
                return code

    for text in (display_title, runtime_root.parent.name):
        code = version_code_from_text(text)
        if code > 0:
            return code
    return 0


def fetch_latest_update(
    runtime_root: Path,
    display_title: str = "",
    *,
    metadata_url: str = UPDATE_METADATA_URL,
    timeout_seconds: float = 8.0,
) -> UpdateInfo | None:
    request = urllib.request.Request(
        metadata_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Nogi-broadcaster-updater",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read(1024 * 1024)
    data = json.loads(payload.decode("utf-8"))
    version = str(data.get("version") or "").strip()
    release_name = str(data.get("releaseName") or data.get("release_name") or "").strip()
    download_url = str(data.get("downloadUrl") or data.get("download_url") or "").strip()
    sha256 = str(data.get("sha256") or "").strip().lower()
    try:
        version_code = int(data.get("versionCode") or data.get("version_code") or 0)
    except (TypeError, ValueError):
        version_code = 0
    if version_code <= 0:
        version_code = version_code_from_text(version or release_name)
    try:
        size = int(data.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    notes_raw = data.get("notes") or ()
    notes = tuple(str(note) for note in notes_raw if str(note).strip())
    info = UpdateInfo(
        version=version,
        version_code=version_code,
        release_name=release_name or (f"V{version}" if version else "新版本"),
        download_url=download_url,
        sha256=sha256,
        size=size,
        mandatory=bool(data.get("mandatory") or False),
        notes=notes,
    )
    if not info.download_url or info.version_code <= 0:
        return None
    if info.version_code <= current_version_code(runtime_root, display_title):
        return None
    return info


def prepare_update(runtime_root: Path, info: UpdateInfo) -> PreparedUpdate:
    temp_dir = Path(tempfile.mkdtemp(prefix="nogi-broadcaster-update-"))
    zip_path = temp_dir / "update.zip"
    extract_root = temp_dir / "payload"
    script_path = temp_dir / "apply_update.ps1"
    _download_file(info.download_url, zip_path)
    if info.sha256:
        actual = _sha256(zip_path)
        if actual.lower() != info.sha256.lower():
            raise RuntimeError("下载文件校验失败，请稍后重试。")
    extract_root.mkdir(parents=True, exist_ok=True)
    _safe_extract(zip_path, extract_root)
    source_root = _find_package_root(extract_root, runtime_root.name)
    _write_update_script(script_path)
    return PreparedUpdate(temp_dir=temp_dir, source_root=source_root, script_path=script_path)


def start_update(
    prepared: PreparedUpdate,
    runtime_root: Path,
    *,
    launcher_pid: int,
    core_pid: int | None,
) -> subprocess.Popen[bytes]:
    package_root = runtime_root.parent
    args = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(prepared.script_path),
        "-Source",
        str(prepared.source_root),
        "-Target",
        str(package_root),
        "-RuntimeDirName",
        runtime_root.name,
        "-LauncherPid",
        str(int(launcher_pid or 0)),
        "-CorePid",
        str(int(core_pid or 0)),
    ]
    creationflags = 0
    if os.name == "nt":
        creationflags = 0x08000000 | 0x00000200
    return subprocess.Popen(
        args,
        cwd=str(prepared.temp_dir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def _download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Nogi-broadcaster-updater"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        with destination.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(zip_path: Path, destination: Path) -> None:
    destination_full = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if target != destination_full and destination_full not in target.parents:
                raise RuntimeError("更新包路径异常，已取消更新。")
        archive.extractall(destination)


def _find_package_root(extract_root: Path, runtime_dir_name: str) -> Path:
    if (extract_root / runtime_dir_name / "BuffWatcher").is_dir():
        return extract_root
    candidates = [
        item
        for item in extract_root.iterdir()
        if item.is_dir() and (item / runtime_dir_name / "BuffWatcher").is_dir()
    ]
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError("更新包结构不符合预期。")


def _write_update_script(path: Path) -> None:
    path.write_text(
        r'''
param(
  [Parameter(Mandatory=$true)][string]$Source,
  [Parameter(Mandatory=$true)][string]$Target,
  [Parameter(Mandatory=$true)][string]$RuntimeDirName,
  [int]$LauncherPid = 0,
  [int]$CorePid = 0
)

$ErrorActionPreference = "Stop"
$log = Join-Path $env:TEMP "nogi-broadcaster-update.log"

function Write-UpdateLog([string]$Message) {
  $line = ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message)
  Add-Content -LiteralPath $log -Value $line -Encoding UTF8
}

function Wait-ForProcessExit([int]$PidValue) {
  if ($PidValue -le 0) { return }
  try {
    $process = Get-Process -Id $PidValue -ErrorAction Stop
  } catch {
    return
  }
  try {
    $process.WaitForExit(30000) | Out-Null
  } catch {
    Start-Sleep -Seconds 3
  }
}

function Show-UpdateError([string]$Message) {
  try {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(($Message + "`n日志：" + $log), "洛奇播报小助手", "OK", "Error") | Out-Null
  } catch {
  }
}

try {
  Write-UpdateLog "update begin"
  $sourceRuntime = Join-Path $Source $RuntimeDirName
  $targetRuntime = Join-Path $Target $RuntimeDirName
  $sourceWatcher = Join-Path $sourceRuntime "BuffWatcher"
  $targetWatcher = Join-Path $targetRuntime "BuffWatcher"
  if (-not (Test-Path -LiteralPath $sourceWatcher)) {
    throw "更新包中找不到 BuffWatcher。"
  }
  if (-not (Test-Path -LiteralPath $targetWatcher)) {
    throw "当前安装目录不符合预期。"
  }

  Wait-ForProcessExit $CorePid
  Wait-ForProcessExit $LauncherPid
  Start-Sleep -Milliseconds 800

  $preserve = Join-Path $env:TEMP ("nogi-broadcaster-preserve-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Force -Path $preserve | Out-Null
  $configPath = Join-Path $targetWatcher "buffwatcher.config.local.json"
  $logsPath = Join-Path $targetWatcher "logs"
  $customPath = Join-Path $targetWatcher "assets\custom"
  if (Test-Path -LiteralPath $configPath) {
    Copy-Item -LiteralPath $configPath -Destination (Join-Path $preserve "buffwatcher.config.local.json") -Force
  }
  if (Test-Path -LiteralPath $logsPath) {
    Copy-Item -LiteralPath $logsPath -Destination (Join-Path $preserve "logs") -Recurse -Force
  }
  if (Test-Path -LiteralPath $customPath) {
    New-Item -ItemType Directory -Force -Path (Join-Path $preserve "assets") | Out-Null
    Copy-Item -LiteralPath $customPath -Destination (Join-Path $preserve "assets\custom") -Recurse -Force
  }

  Get-ChildItem -LiteralPath $Target -Force | Remove-Item -Recurse -Force
  New-Item -ItemType Directory -Force -Path $Target | Out-Null
  Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $Target -Recurse -Force
  }

  $newWatcher = Join-Path (Join-Path $Target $RuntimeDirName) "BuffWatcher"
  if (Test-Path -LiteralPath (Join-Path $preserve "buffwatcher.config.local.json")) {
    Copy-Item -LiteralPath (Join-Path $preserve "buffwatcher.config.local.json") -Destination (Join-Path $newWatcher "buffwatcher.config.local.json") -Force
  }
  if (Test-Path -LiteralPath (Join-Path $preserve "logs")) {
    Copy-Item -LiteralPath (Join-Path $preserve "logs") -Destination $newWatcher -Recurse -Force
  }
  if (Test-Path -LiteralPath (Join-Path $preserve "assets\custom")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $newWatcher "assets") | Out-Null
    Copy-Item -LiteralPath (Join-Path $preserve "assets\custom") -Destination (Join-Path $newWatcher "assets\custom") -Recurse -Force
  }

  $entry = Get-ChildItem -LiteralPath $Target -Filter "洛奇播报小助手*.exe" -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if (-not $entry) {
    throw "更新完成，但找不到启动程序。"
  }
  Write-UpdateLog ("restart " + $entry.FullName)
  Start-Process -FilePath $entry.FullName -WorkingDirectory $Target
  Write-UpdateLog "update complete"
} catch {
  Write-UpdateLog ("update failed: " + $_.Exception.Message)
  Show-UpdateError ("更新失败：" + $_.Exception.Message)
}
'''.lstrip(),
        encoding="utf-8-sig",
    )

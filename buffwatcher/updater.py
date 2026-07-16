from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import tempfile
from typing import Callable
import urllib.parse
import urllib.request
import zipfile

try:
    import certifi
except Exception:  # pragma: no cover - optional runtime dependency
    certifi = None


UPDATE_CHANNEL_ID = "nogi-v13-public"
INSTALL_ROOT_MARKER = "nogi-install-root.json"
ALIYUN_UPDATE_METADATA_URL = (
    "https://nogi-broadcaster-updates.oss-cn-hangzhou.aliyuncs.com/"
    "channels/v13/public/latest.json"
)
GITHUB_UPDATE_METADATA_URL = (
    "https://raw.githubusercontent.com/rw594/Nogi-broadcaster/main/"
    "update-channels/v13/public/latest.json"
)
UPDATE_METADATA_URL = ALIYUN_UPDATE_METADATA_URL
FALLBACK_UPDATE_METADATA_URLS = (
    GITHUB_UPDATE_METADATA_URL,
)
PRODUCT_NAME = "洛奇播报小助手"
VERSION_RE = re.compile(r"v?(\d+(?:\.\d+){1,2})([a-z])?", re.IGNORECASE)
_HTTPS_CONTEXT: ssl.SSLContext | None = None


@dataclass(frozen=True)
class DownloadSource:
    name: str
    url: str


@dataclass(frozen=True)
class UpdateProgress:
    stage: str
    source_name: str = ""
    downloaded: int = 0
    total: int = 0
    detail: str = ""


ProgressCallback = Callable[[UpdateProgress], None]


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
    download_sources: tuple[DownloadSource, ...] = ()

    def available_download_sources(self) -> tuple[DownloadSource, ...]:
        sources = list(self.download_sources)
        if self.download_url and all(
            source.url != self.download_url for source in sources
        ):
            sources.append(
                DownloadSource(
                    name=_download_source_name(self.download_url),
                    url=self.download_url,
                )
            )
        return tuple(sources)


@dataclass(frozen=True)
class PreparedUpdate:
    temp_dir: Path
    source_root: Path
    script_path: Path


def _unsafe_install_roots() -> set[Path]:
    roots: set[Path] = set()
    home = Path.home()
    candidates = [
        home,
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
    ]
    for variable in ("USERPROFILE", "OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        raw = str(os.environ.get(variable) or "").strip()
        if not raw:
            continue
        base = Path(raw)
        candidates.extend(
            [
                base,
                base / "Desktop",
                base / "Documents",
                base / "Downloads",
            ]
        )
    for candidate in candidates:
        try:
            roots.add(candidate.resolve())
        except OSError:
            continue
    return roots


def validate_update_install_layout(runtime_root: Path) -> Path:
    """Return the package root only when it is safe for an in-place update."""

    runtime_root = Path(runtime_root).resolve()
    package_root = runtime_root.parent
    if package_root == Path(package_root.anchor):
        raise RuntimeError("插件位于磁盘根目录，已禁止自动更新。请手动安装到独立文件夹。")
    if package_root in _unsafe_install_roots():
        raise RuntimeError(
            "插件文件直接放在桌面、文档或下载目录中，已禁止自动更新。"
            "请手动下载新版并解压到独立文件夹。"
        )
    if not (runtime_root / "package-info.json").is_file():
        raise RuntimeError("当前安装目录缺少 package-info.json，已禁止自动更新。")
    if not (runtime_root / "BuffWatcher").is_dir():
        raise RuntimeError("当前安装目录缺少 BuffWatcher，已禁止自动更新。")
    if not (package_root / f"{PRODUCT_NAME}.exe").is_file():
        raise RuntimeError("当前安装目录缺少固定启动程序，已禁止自动更新。")
    package_info = _read_package_info(runtime_root)
    if bool(package_info.get("strict_update_channel", False)):
        channel = str(package_info.get("update_channel") or "").strip()
        _validate_install_root_marker(package_root, channel)
    return package_root


def _read_package_info(runtime_root: Path) -> dict:
    for info_path in [
        runtime_root / "package-info.json",
        runtime_root.parent / "package-info.json",
    ]:
        try:
            data = json.loads(info_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def _validate_install_root_marker(package_root: Path, channel: str) -> None:
    if not channel:
        raise RuntimeError("安装包缺少更新通道标识，已禁止自动更新。")
    marker_path = package_root / INSTALL_ROOT_MARKER
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("安装目录缺少 V1.3 安全标记，已禁止自动更新。") from exc
    if not isinstance(marker, dict) or str(marker.get("update_channel") or "").strip() != channel:
        raise RuntimeError("安装目录的更新通道标记不匹配，已禁止自动更新。")


def _download_source_name(url: str) -> str:
    host = (urllib.parse.urlparse(str(url or "")).hostname or "").lower()
    if host.endswith("aliyuncs.com") or host.endswith("alicdn.com"):
        return "阿里云镜像"
    if host == "github.com" or host.endswith("githubusercontent.com"):
        return "GitHub"
    if host == "cdn.jsdelivr.net":
        return "jsDelivr"
    return host or "备用下载源"


def _download_sources_from_metadata(data: dict) -> tuple[DownloadSource, ...]:
    sources: list[DownloadSource] = []
    raw_sources = data.get("downloadUrls") or data.get("download_urls") or ()
    if isinstance(raw_sources, (str, dict)):
        raw_sources = (raw_sources,)
    if isinstance(raw_sources, (list, tuple)):
        for raw in raw_sources:
            if isinstance(raw, str):
                url = raw.strip()
                name = _download_source_name(url)
            elif isinstance(raw, dict):
                url = str(
                    raw.get("url")
                    or raw.get("downloadUrl")
                    or raw.get("download_url")
                    or ""
                ).strip()
                name = str(raw.get("name") or raw.get("label") or "").strip()
                if not name:
                    name = _download_source_name(url)
            else:
                continue
            if url and all(existing.url != url for existing in sources):
                sources.append(DownloadSource(name=name, url=url))

    legacy_url = str(
        data.get("downloadUrl") or data.get("download_url") or ""
    ).strip()
    if legacy_url and all(source.url != legacy_url for source in sources):
        sources.append(
            DownloadSource(
                name=_download_source_name(legacy_url),
                url=legacy_url,
            )
        )
    return tuple(sources)


def _report_progress(
    callback: ProgressCallback | None,
    stage: str,
    *,
    source_name: str = "",
    downloaded: int = 0,
    total: int = 0,
    detail: str = "",
) -> None:
    if callback is None:
        return
    callback(
        UpdateProgress(
            stage=stage,
            source_name=source_name,
            downloaded=max(0, int(downloaded or 0)),
            total=max(0, int(total or 0)),
            detail=str(detail or ""),
        )
    )


def version_code_from_text(text: str) -> int:
    match = VERSION_RE.search(text or "")
    if not match:
        return 0
    parts = [int(part) for part in match.group(1).split(".")]
    if len(parts) < 2:
        return 0
    patch = parts[2] if len(parts) >= 3 else 0
    suffix = match.group(2)
    if suffix and len(parts) == 2:
        patch = ord(suffix.lower()) - ord("a") + 1
    return parts[0] * 10000 + parts[1] * 100 + patch


def current_version_code(runtime_root: Path, display_title: str = "") -> int:
    for info_path in [runtime_root / "package-info.json", runtime_root.parent / "package-info.json"]:
        try:
            data = json.loads(info_path.read_text(encoding="utf-8-sig"))
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


def update_checks_disabled(runtime_root: Path) -> bool:
    if strict_update_channel(runtime_root) and not configured_update_metadata_urls(runtime_root):
        return True
    for info_path in [
        runtime_root / "package-info.json",
        runtime_root.parent / "package-info.json",
    ]:
        try:
            data = json.loads(info_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            bool(data.get("private_build", False))
            and not configured_update_metadata_urls(runtime_root)
        ):
            return True
    return False


def configured_update_metadata_urls(runtime_root: Path) -> tuple[str, ...]:
    urls: list[str] = []
    for info_path in [
        runtime_root / "package-info.json",
        runtime_root.parent / "package-info.json",
    ]:
        try:
            data = json.loads(info_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        raw_values = data.get("update_urls") or data.get("updateUrls") or ()
        if isinstance(raw_values, str):
            raw_values = (raw_values,)
        if isinstance(raw_values, (list, tuple)):
            for raw in raw_values:
                url = str(raw or "").strip()
                if url and url not in urls:
                    urls.append(url)
        legacy_url = str(
            data.get("update_url") or data.get("updateUrl") or ""
        ).strip()
        if legacy_url and legacy_url not in urls:
            urls.append(legacy_url)
    return tuple(urls)


def strict_update_channel(runtime_root: Path) -> bool:
    return bool(_read_package_info(runtime_root).get("strict_update_channel", False))


def configured_update_channel(runtime_root: Path) -> str:
    return str(_read_package_info(runtime_root).get("update_channel") or "").strip()


def _is_private_build(runtime_root: Path) -> bool:
    for info_path in [
        runtime_root / "package-info.json",
        runtime_root.parent / "package-info.json",
    ]:
        try:
            data = json.loads(info_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if bool(data.get("private_build", False)):
            return True
    return False


def fetch_latest_update(
    runtime_root: Path,
    display_title: str = "",
    *,
    metadata_url: str = UPDATE_METADATA_URL,
    timeout_seconds: float = 8.0,
) -> UpdateInfo | None:
    if update_checks_disabled(runtime_root):
        return None
    last_error: Exception | None = None
    errors: list[str] = []
    configured_urls = configured_update_metadata_urls(runtime_root)
    strict_channel = strict_update_channel(runtime_root)
    expected_channel = configured_update_channel(runtime_root) if strict_channel else ""
    if strict_channel and not expected_channel:
        raise RuntimeError("严格更新通道缺少通道标识，已取消检查。")
    private_channel = _is_private_build(runtime_root) and bool(configured_urls)
    authoritative_channel = strict_channel or private_channel
    metadata_urls: list[str] = []
    metadata_candidates = configured_urls if authoritative_channel else (
        *configured_urls,
        metadata_url,
    )
    for candidate_url in metadata_candidates:
        if candidate_url and candidate_url not in metadata_urls:
            metadata_urls.append(candidate_url)
    for candidate_url in metadata_urls:
        try:
            return _fetch_latest_update_from_url(
                runtime_root,
                display_title,
                metadata_url=candidate_url,
                timeout_seconds=timeout_seconds,
                expected_channel=expected_channel,
            )
        except Exception as exc:
            last_error = exc
            errors.append(
                f"metadata {candidate_url}: {type(exc).__name__}: {exc}"
            )
    if authoritative_channel:
        if last_error is not None:
            raise RuntimeError("；".join(errors)) from last_error
        return None
    for candidate_url in FALLBACK_UPDATE_METADATA_URLS:
        try:
            return _fetch_latest_update_from_url(
                runtime_root,
                display_title,
                metadata_url=candidate_url,
                timeout_seconds=timeout_seconds,
                expected_channel="",
            )
        except Exception as exc:
            last_error = exc
            errors.append(f"metadata {candidate_url}: {type(exc).__name__}: {exc}")
    if last_error is not None:
        raise RuntimeError("；".join(errors)) from last_error
    return None


def _fetch_latest_update_from_url(
    runtime_root: Path,
    display_title: str = "",
    *,
    metadata_url: str,
    timeout_seconds: float,
    expected_channel: str = "",
) -> UpdateInfo | None:
    request = urllib.request.Request(
        metadata_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Nogi-broadcaster-updater",
        },
    )
    with _urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read(1024 * 1024)
    data = json.loads(payload.decode("utf-8-sig"))
    if expected_channel:
        manifest_channel = str(data.get("channel") or "").strip()
        if manifest_channel != expected_channel:
            raise RuntimeError(
                f"更新通道标识不匹配（期望 {expected_channel}，实际 {manifest_channel or '空'}）。"
            )
    version = str(data.get("version") or "").strip()
    release_name = str(data.get("releaseName") or data.get("release_name") or "").strip()
    download_sources = _download_sources_from_metadata(data)
    download_url = download_sources[0].url if download_sources else ""
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
        download_sources=download_sources,
    )
    if not info.download_url or info.version_code <= 0:
        return None
    if info.version_code <= current_version_code(runtime_root, display_title):
        return None
    return info


def prepare_update(
    runtime_root: Path,
    info: UpdateInfo,
    *,
    progress_callback: ProgressCallback | None = None,
) -> PreparedUpdate:
    validate_update_install_layout(runtime_root)
    temp_dir = Path(tempfile.mkdtemp(prefix="nogi-broadcaster-update-"))
    zip_path = temp_dir / "update.zip"
    extract_root = temp_dir / "payload"
    script_path = temp_dir / "apply_update.ps1"
    sources = info.available_download_sources()
    if not sources:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError("更新信息中没有可用的下载地址。")

    errors: list[str] = []
    downloaded = False
    try:
        for index, source in enumerate(sources):
            zip_path.unlink(missing_ok=True)
            _report_progress(
                progress_callback,
                "connecting",
                source_name=source.name,
                total=info.size,
            )
            try:
                _download_file(
                    source.url,
                    zip_path,
                    expected_size=info.size,
                    source_name=source.name,
                    progress_callback=progress_callback,
                )
                actual_size = zip_path.stat().st_size
                if info.size and actual_size != info.size:
                    raise RuntimeError(
                        f"文件大小不符（期望 {info.size}，实际 {actual_size}）"
                    )
                _report_progress(
                    progress_callback,
                    "verifying",
                    source_name=source.name,
                    downloaded=actual_size,
                    total=info.size or actual_size,
                )
                if info.sha256:
                    actual = _sha256(zip_path)
                    if actual.lower() != info.sha256.lower():
                        raise RuntimeError("SHA-256 校验失败")
                downloaded = True
                break
            except Exception as exc:
                errors.append(f"{source.name}: {type(exc).__name__}: {exc}")
                next_name = sources[index + 1].name if index + 1 < len(sources) else ""
                _report_progress(
                    progress_callback,
                    "source_failed",
                    source_name=source.name,
                    total=info.size,
                    detail=next_name,
                )
        if not downloaded:
            raise RuntimeError("；".join(errors) or "所有更新下载源均不可用。")

        _report_progress(progress_callback, "extracting")
        extract_root.mkdir(parents=True, exist_ok=True)
        _safe_extract(zip_path, extract_root)
        source_root = _find_package_root(extract_root, runtime_root.name)
        _validate_update_package_compatibility(runtime_root, source_root, info)
        _write_update_script(script_path)
        _report_progress(progress_callback, "ready")
        return PreparedUpdate(
            temp_dir=temp_dir,
            source_root=source_root,
            script_path=script_path,
        )
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def start_update(
    prepared: PreparedUpdate,
    runtime_root: Path,
    *,
    launcher_pid: int,
    core_pid: int | None,
) -> subprocess.Popen[bytes]:
    package_root = validate_update_install_layout(runtime_root)
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


def _download_file(
    url: str,
    destination: Path,
    *,
    expected_size: int = 0,
    source_name: str = "",
    progress_callback: ProgressCallback | None = None,
) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Nogi-broadcaster-updater"},
    )
    with _urlopen(request, timeout=30) as response:
        try:
            response_size = int(response.headers.get("Content-Length") or 0)
        except (AttributeError, TypeError, ValueError):
            response_size = 0
        total = response_size or max(0, int(expected_size or 0))
        downloaded = 0
        last_reported_percent = -1
        with destination.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                percent = int(downloaded * 100 / total) if total > 0 else -1
                if percent != last_reported_percent:
                    last_reported_percent = percent
                    _report_progress(
                        progress_callback,
                        "downloading",
                        source_name=source_name,
                        downloaded=downloaded,
                        total=total,
                    )
        if downloaded == 0:
            raise RuntimeError("下载结果为空")


def _https_context() -> ssl.SSLContext:
    global _HTTPS_CONTEXT
    if _HTTPS_CONTEXT is not None:
        return _HTTPS_CONTEXT
    if certifi is not None:
        context = ssl.create_default_context(cafile=certifi.where())
    else:
        context = ssl.create_default_context()
    if hasattr(ssl, "TLSVersion"):
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    _HTTPS_CONTEXT = context
    return context


def _urlopen(request: urllib.request.Request, *, timeout: float):
    url = str(request.full_url or "")
    if url.lower().startswith("https://"):
        return urllib.request.urlopen(
            request,
            timeout=timeout,
            context=_https_context(),
        )
    return urllib.request.urlopen(request, timeout=timeout)


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


def _validate_update_package_compatibility(
    runtime_root: Path,
    source_root: Path,
    info: UpdateInfo,
) -> None:
    source_runtime = source_root / runtime_root.name
    source_info = _read_package_info(source_runtime)
    try:
        source_version_code = int(source_info.get("version_code") or 0)
    except (TypeError, ValueError):
        source_version_code = 0
    if source_version_code != info.version_code:
        raise RuntimeError("更新包版本码与更新清单不一致，已取消更新。")

    target_info = _read_package_info(runtime_root)
    if not bool(target_info.get("strict_update_channel", False)):
        return
    target_channel = str(target_info.get("update_channel") or "").strip()
    source_channel = str(source_info.get("update_channel") or "").strip()
    if not bool(source_info.get("strict_update_channel", False)):
        raise RuntimeError("更新包未启用严格通道校验，已取消更新。")
    if not target_channel or source_channel != target_channel:
        raise RuntimeError("更新包所属通道与当前安装不一致，已取消更新。")
    _validate_install_root_marker(source_root, source_channel)


def _write_update_script(path: Path) -> None:
    path.write_text(
        r'''
param(
  [Parameter(Mandatory=$true)][string]$Source,
  [Parameter(Mandatory=$true)][string]$Target,
  [Parameter(Mandatory=$true)][string]$RuntimeDirName,
  [int]$LauncherPid = 0,
  [int]$CorePid = 0,
  [switch]$SkipRestart
)

$ErrorActionPreference = "Stop"
$log = Join-Path $env:TEMP "nogi-broadcaster-update.log"

function Write-UpdateLog([string]$Message) {
  $line = ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message)
  Add-Content -LiteralPath $log -Value $line -Encoding UTF8
}

function Get-NormalizedPath([string]$PathValue) {
  return [System.IO.Path]::GetFullPath($PathValue).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
  )
}

function Assert-SafeUpdateTarget([string]$TargetPath, [string]$RuntimePath) {
  $targetFull = Get-NormalizedPath $TargetPath
  $runtimeFull = Get-NormalizedPath $RuntimePath
  $rootFull = Get-NormalizedPath ([System.IO.Path]::GetPathRoot($targetFull))
  if ($targetFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "禁止把磁盘根目录作为更新目标。"
  }

  $unsafe = @(
    $env:USERPROFILE,
    [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop),
    [Environment]::GetFolderPath([Environment+SpecialFolder]::MyDocuments),
    (Join-Path $env:USERPROFILE "Downloads")
  )
  foreach ($oneDriveName in @("OneDrive", "OneDriveConsumer", "OneDriveCommercial")) {
    $oneDrive = [Environment]::GetEnvironmentVariable($oneDriveName)
    if ($oneDrive) {
      $unsafe += $oneDrive
      $unsafe += (Join-Path $oneDrive "Desktop")
      $unsafe += (Join-Path $oneDrive "Documents")
      $unsafe += (Join-Path $oneDrive "Downloads")
    }
  }
  foreach ($unsafePath in $unsafe) {
    if (-not $unsafePath) { continue }
    $unsafeFull = Get-NormalizedPath $unsafePath
    if ($targetFull.Equals($unsafeFull, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "禁止把桌面、文档、下载目录或用户目录作为更新目标。请手动安装到独立文件夹。"
    }
  }

  $expectedRuntime = Get-NormalizedPath (Join-Path $targetFull $RuntimeDirName)
  if (-not $runtimeFull.Equals($expectedRuntime, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "程序目录层级异常，已取消更新。"
  }
  $packageInfoPath = Join-Path $runtimeFull "package-info.json"
  if (-not (Test-Path -LiteralPath $packageInfoPath -PathType Leaf)) {
    throw "当前安装目录缺少 package-info.json，已取消更新。"
  }
  $packageInfo = Get-Content -LiteralPath $packageInfoPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ([bool]$packageInfo.strict_update_channel) {
    $channel = ([string]$packageInfo.update_channel).Trim()
    if ([string]::IsNullOrWhiteSpace($channel)) {
      throw "当前安装目录缺少更新通道标识，已取消更新。"
    }
    $markerPath = Join-Path $targetFull "nogi-install-root.json"
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
      throw "当前安装目录缺少 V1.3 安全标记，已取消更新。"
    }
    $marker = Get-Content -LiteralPath $markerPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (([string]$marker.update_channel).Trim() -ne $channel) {
      throw "安装目录的更新通道标记不匹配，已取消更新。"
    }
  }
  if (-not (Test-Path -LiteralPath (Join-Path $targetFull "洛奇播报小助手.exe") -PathType Leaf)) {
    throw "当前安装目录缺少固定启动程序，已取消更新。"
  }
}

function Assert-ManagedChild([string]$ChildPath, [string]$ParentPath) {
  $childFull = Get-NormalizedPath $ChildPath
  $parentFull = Get-NormalizedPath $ParentPath
  $prefix = $parentFull + [System.IO.Path]::DirectorySeparatorChar
  if (-not $childFull.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "更新文件超出插件目录，已取消更新。"
  }
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

function Get-PackageProcesses([string]$TargetPath) {
  $targetFull = [System.IO.Path]::GetFullPath($TargetPath)
  $separator = [System.IO.Path]::DirectorySeparatorChar.ToString()
  if (-not $targetFull.EndsWith($separator)) {
    $targetFull = $targetFull + $separator
  }
  $matches = @()
  foreach ($process in Get-Process -ErrorAction SilentlyContinue) {
    if ($process.Id -eq $PID) { continue }
    $processPath = $null
    try {
      $processPath = $process.MainModule.FileName
    } catch {
      continue
    }
    if (-not $processPath) { continue }
    try {
      $processFullPath = [System.IO.Path]::GetFullPath($processPath)
    } catch {
      continue
    }
    if ($processFullPath.StartsWith($targetFull, [System.StringComparison]::OrdinalIgnoreCase)) {
      $matches += $process
    }
  }
  return $matches
}

function Stop-PackageProcesses([string]$TargetPath) {
  $processes = @(Get-PackageProcesses $TargetPath)
  foreach ($process in $processes) {
    try {
      Write-UpdateLog ("close process " + $process.Id + " " + $process.ProcessName)
      $process.CloseMainWindow() | Out-Null
    } catch {
    }
  }
  if ($processes.Count -gt 0) {
    Start-Sleep -Milliseconds 1200
  }
  $processes = @(Get-PackageProcesses $TargetPath)
  foreach ($process in $processes) {
    try {
      Write-UpdateLog ("kill process " + $process.Id + " " + $process.ProcessName)
      Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    } catch {
    }
  }
  if ($processes.Count -gt 0) {
    Start-Sleep -Milliseconds 800
  }
}

function Invoke-WithRetry([scriptblock]$Action, [string]$Description, [int]$Attempts = 10) {
  for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
    try {
      & $Action
      return
    } catch {
      Write-UpdateLog ($Description + " attempt " + $attempt + " failed: " + $_.Exception.Message)
      if ($attempt -ge $Attempts) {
        throw
      }
      Stop-PackageProcesses (Join-Path $Target $RuntimeDirName)
      Start-Sleep -Milliseconds (300 * $attempt)
    }
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
  $Source = Get-NormalizedPath $Source
  $Target = Get-NormalizedPath $Target
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
  Assert-SafeUpdateTarget $Target $targetRuntime
  Write-UpdateLog ("source=" + $Source)
  Write-UpdateLog ("target=" + $Target)

  Wait-ForProcessExit $CorePid
  Wait-ForProcessExit $LauncherPid
  Stop-PackageProcesses $targetRuntime
  Start-Sleep -Milliseconds 1200

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

  $managedRuntimeEntries = @(
    "BuffWatcher",
    "BuffWatcherConsole",
    "BuffWatcherLauncher",
    "BuffWatcherSettings",
    "BuffWatcherOverlay",
    "package-info.json"
  )
  foreach ($entryName in $managedRuntimeEntries) {
    $targetEntry = Join-Path $targetRuntime $entryName
    Assert-ManagedChild $targetEntry $targetRuntime
    if (Test-Path -LiteralPath $targetEntry) {
      Invoke-WithRetry {
        Remove-Item -LiteralPath $targetEntry -Recurse -Force
      } ("remove managed entry " + $entryName)
    }
    $sourceEntry = Join-Path $sourceRuntime $entryName
    if (Test-Path -LiteralPath $sourceEntry) {
      Copy-Item -LiteralPath $sourceEntry -Destination $targetRuntime -Recurse -Force
    }
  }

  $productName = [string][char]0x6D1B + [string][char]0x5947 + [string][char]0x64AD + [string][char]0x62A5 + [string][char]0x5C0F + [string][char]0x52A9 + [string][char]0x624B
  $readmeName = [string][char]0x4F7F + [string][char]0x7528 + [string][char]0x65B9 + [string][char]0x6CD5 + "README.txt"
  foreach ($entryName in @(($productName + ".exe"), $readmeName, "Npcap")) {
    $sourceEntry = Join-Path $Source $entryName
    if (-not (Test-Path -LiteralPath $sourceEntry)) { continue }
    $targetEntry = Join-Path $Target $entryName
    Assert-ManagedChild $targetEntry $Target
    if (Test-Path -LiteralPath $targetEntry) {
      Invoke-WithRetry {
        Remove-Item -LiteralPath $targetEntry -Recurse -Force
      } ("remove managed package entry " + $entryName)
    }
    Copy-Item -LiteralPath $sourceEntry -Destination $Target -Recurse -Force
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

  $fixedEntry = Join-Path $Target ($productName + ".exe")
  if (Test-Path -LiteralPath $fixedEntry) {
    $entry = Get-Item -LiteralPath $fixedEntry
  } else {
    $entry = Get-ChildItem -LiteralPath $Target -Filter ($productName + "*.exe") -File |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 1
  }
  if (-not $entry) {
    throw "更新完成，但找不到启动程序。"
  }
  if (-not $SkipRestart) {
    Write-UpdateLog ("restart " + $entry.FullName)
    Start-Process -FilePath $entry.FullName -WorkingDirectory $Target
  }
  Write-UpdateLog "update complete"
} catch {
  Write-UpdateLog ("update failed: " + $_.Exception.Message)
  Show-UpdateError ("更新失败：" + $_.Exception.Message)
}
'''.lstrip(),
        encoding="utf-8-sig",
    )

from __future__ import annotations

import json
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

from buffwatcher.updater import (
    DownloadSource,
    UpdateInfo,
    configured_update_metadata_urls,
    configured_update_channel,
    fetch_latest_update,
    prepare_update,
    strict_update_channel,
    validate_update_install_layout,
    _download_sources_from_metadata,
    _fetch_latest_update_from_url,
    _validate_update_package_compatibility,
    _write_update_script,
)


PRODUCT_NAME = "洛奇播报小助手"


def create_install_layout(runtime_root: Path) -> None:
    (runtime_root / "BuffWatcher").mkdir(parents=True)
    (runtime_root / "package-info.json").write_text("{}", encoding="utf-8")
    (runtime_root.parent / f"{PRODUCT_NAME}.exe").write_bytes(b"launcher")


class UpdaterProgressTests(unittest.TestCase):
    def test_manifest_accepts_named_download_mirrors_and_legacy_url(self) -> None:
        sources = _download_sources_from_metadata(
            {
                "downloadUrls": [
                    {
                        "name": "阿里云镜像",
                        "url": "https://example.oss-cn-shanghai.aliyuncs.com/update.zip",
                    }
                ],
                "downloadUrl": "https://github.com/example/update.zip",
            }
        )

        self.assertEqual(
            [(source.name, source.url) for source in sources],
            [
                (
                    "阿里云镜像",
                    "https://example.oss-cn-shanghai.aliyuncs.com/update.zip",
                ),
                ("GitHub", "https://github.com/example/update.zip"),
            ],
        )

    def test_package_info_can_prepend_aliyun_metadata_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory) / "程序文件"
            runtime_root.mkdir()
            (runtime_root / "package-info.json").write_text(
                json.dumps(
                    {
                        "update_urls": [
                            "https://example.oss-cn-shanghai.aliyuncs.com/latest.json",
                            "https://github.com/example/latest.json",
                        ]
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                configured_update_metadata_urls(runtime_root),
                (
                    "https://example.oss-cn-shanghai.aliyuncs.com/latest.json",
                    "https://github.com/example/latest.json",
                ),
            )

    def test_failed_mirror_falls_back_and_reports_each_stage(self) -> None:
        events = []
        info = UpdateInfo(
            version="1.26",
            version_code=12600,
            release_name="V1.26",
            download_url="https://mirror.invalid/update.zip",
            sha256="",
            size=0,
            mandatory=False,
            notes=(),
            download_sources=(
                DownloadSource("阿里云镜像", "https://mirror.invalid/update.zip"),
                DownloadSource("GitHub", "https://github.com/example/update.zip"),
            ),
        )

        def fake_download(url: str, destination: Path, **_kwargs) -> None:
            if "mirror.invalid" in url:
                raise OSError("mirror unavailable")
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("程序文件/BuffWatcher/payload.txt", "ok")
                archive.writestr(
                    "程序文件/package-info.json",
                    '{"version_code": 12600}',
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory) / "程序文件"
            create_install_layout(runtime_root)
            with patch("buffwatcher.updater._download_file", side_effect=fake_download):
                prepared = prepare_update(
                    runtime_root,
                    info,
                    progress_callback=events.append,
                )
            try:
                self.assertTrue(prepared.source_root.is_dir())
            finally:
                import shutil

                shutil.rmtree(prepared.temp_dir, ignore_errors=True)

        self.assertEqual(
            [event.stage for event in events],
            [
                "connecting",
                "source_failed",
                "connecting",
                "verifying",
                "extracting",
                "ready",
            ],
        )
        self.assertEqual(events[1].source_name, "阿里云镜像")
        self.assertEqual(events[1].detail, "GitHub")

    def test_desktop_root_is_rejected_before_update(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "独立文件夹"):
            validate_update_install_layout(Path.home() / "Desktop" / "程序文件")

    def test_strict_channel_requires_matching_install_root_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package_root = Path(directory) / "package"
            runtime_root = package_root / "程序文件"
            (runtime_root / "BuffWatcher").mkdir(parents=True)
            (runtime_root / "package-info.json").write_text(
                json.dumps(
                    {
                        "strict_update_channel": True,
                        "update_channel": "nogi-v13-public",
                    }
                ),
                encoding="utf-8",
            )
            (package_root / f"{PRODUCT_NAME}.exe").write_bytes(b"launcher")

            with self.assertRaisesRegex(RuntimeError, "V1.3 安全标记"):
                validate_update_install_layout(runtime_root)

            (package_root / "nogi-install-root.json").write_text(
                json.dumps({"update_channel": "wrong-channel"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "通道标记不匹配"):
                validate_update_install_layout(runtime_root)

            (package_root / "nogi-install-root.json").write_text(
                json.dumps({"update_channel": "nogi-v13-public"}),
                encoding="utf-8",
            )
            self.assertEqual(validate_update_install_layout(runtime_root), package_root)

    def test_strict_channel_never_falls_back_outside_configured_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory) / "程序文件"
            runtime_root.mkdir()
            configured = [
                "https://new.example/primary.json",
                "https://new.example/backup.json",
            ]
            (runtime_root / "package-info.json").write_text(
                json.dumps(
                    {
                        "strict_update_channel": True,
                        "update_channel": "nogi-v13-public",
                        "update_urls": configured,
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(strict_update_channel(runtime_root))
            self.assertEqual(configured_update_channel(runtime_root), "nogi-v13-public")

            with patch(
                "buffwatcher.updater._fetch_latest_update_from_url",
                side_effect=[OSError("primary down"), OSError("backup down")],
            ) as fetch:
                with self.assertRaisesRegex(RuntimeError, "primary down"):
                    fetch_latest_update(runtime_root)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(
                [call.kwargs["metadata_url"] for call in fetch.call_args_list],
                configured,
            )
            self.assertTrue(
                all(
                    call.kwargs["expected_channel"] == "nogi-v13-public"
                    for call in fetch.call_args_list
                )
            )

    def test_strict_manifest_rejects_a_different_channel(self) -> None:
        payload = json.dumps(
            {
                "channel": "legacy-channel",
                "version": "1.3a",
                "versionCode": 10301,
                "downloadUrl": "https://example.invalid/update.zip",
            }
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory)
            with patch("buffwatcher.updater._urlopen", return_value=io.BytesIO(payload)):
                with self.assertRaisesRegex(RuntimeError, "更新通道标识不匹配"):
                    _fetch_latest_update_from_url(
                        runtime_root,
                        metadata_url="https://new.example/latest.json",
                        timeout_seconds=1,
                        expected_channel="nogi-v13-public",
                    )

    def test_strict_manifest_accepts_the_next_version_in_the_same_channel(self) -> None:
        payload = json.dumps(
            {
                "channel": "nogi-v13-public",
                "version": "1.3a",
                "versionCode": 10301,
                "releaseName": "V1.3a",
                "downloadUrl": "https://new.example/V1.3a.zip",
                "sha256": "a" * 64,
                "size": 123,
            }
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory)
            (runtime_root / "package-info.json").write_text(
                json.dumps({"version_code": 10300}),
                encoding="utf-8",
            )
            with patch("buffwatcher.updater._urlopen", return_value=io.BytesIO(payload)):
                update = _fetch_latest_update_from_url(
                    runtime_root,
                    metadata_url="https://new.example/latest.json",
                    timeout_seconds=1,
                    expected_channel="nogi-v13-public",
                )
            self.assertIsNotNone(update)
            self.assertEqual(update.version_code, 10301)
            self.assertEqual(update.download_url, "https://new.example/V1.3a.zip")

    def test_update_package_must_stay_in_the_same_strict_channel(self) -> None:
        info = UpdateInfo(
            version="1.3a",
            version_code=10301,
            release_name="V1.3a",
            download_url="https://example.invalid/update.zip",
            sha256="",
            size=0,
            mandatory=False,
            notes=(),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime_root = root / "target" / "程序文件"
            source_root = root / "source"
            source_runtime = source_root / "程序文件"
            runtime_root.mkdir(parents=True)
            source_runtime.mkdir(parents=True)
            (runtime_root / "package-info.json").write_text(
                json.dumps(
                    {
                        "strict_update_channel": True,
                        "update_channel": "nogi-v13-public",
                    }
                ),
                encoding="utf-8",
            )
            (source_runtime / "package-info.json").write_text(
                json.dumps(
                    {
                        "version_code": 10301,
                        "strict_update_channel": True,
                        "update_channel": "nogi-v13-visual",
                    }
                ),
                encoding="utf-8",
            )
            (source_root / "nogi-install-root.json").write_text(
                json.dumps({"update_channel": "nogi-v13-visual"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "所属通道"):
                _validate_update_package_compatibility(runtime_root, source_root, info)

    def test_generated_script_never_clears_every_target_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script_path = Path(directory) / "apply_update.ps1"
            _write_update_script(script_path)
            script = script_path.read_text(encoding="utf-8-sig")

        self.assertNotIn(
            "Get-ChildItem -LiteralPath $Target -Force | Remove-Item",
            script,
        )
        self.assertIn("$managedRuntimeEntries", script)
        self.assertIn("Assert-SafeUpdateTarget", script)
        self.assertIn("nogi-install-root.json", script)

    @unittest.skipUnless(os.name == "nt", "PowerShell updater is Windows-only")
    def test_update_preserves_unmanaged_files_in_package_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "payload"
            target = root / "dedicated-package"
            source_runtime = source / "程序文件"
            target_runtime = target / "程序文件"
            source_watcher = source_runtime / "BuffWatcher"
            target_watcher = target_runtime / "BuffWatcher"

            source_watcher.mkdir(parents=True)
            (source_watcher / "new.txt").write_text("new", encoding="utf-8")
            (source_runtime / "package-info.json").write_text(
                json.dumps(
                    {
                        "version_code": 10301,
                        "strict_update_channel": True,
                        "update_channel": "nogi-v13-public",
                    }
                ),
                encoding="utf-8",
            )
            (source / "nogi-install-root.json").write_text(
                json.dumps({"update_channel": "nogi-v13-public"}),
                encoding="utf-8",
            )
            (source / f"{PRODUCT_NAME}.exe").write_bytes(b"new-launcher")

            target_watcher.mkdir(parents=True)
            (target_watcher / "old.txt").write_text("old", encoding="utf-8")
            (target_watcher / "buffwatcher.config.local.json").write_text(
                "saved-config",
                encoding="utf-8",
            )
            (target_watcher / "logs").mkdir()
            (target_watcher / "logs" / "saved.log").write_text(
                "saved-log",
                encoding="utf-8",
            )
            (target_watcher / "assets" / "custom").mkdir(parents=True)
            (target_watcher / "assets" / "custom" / "saved.png").write_bytes(
                b"saved-icon"
            )
            (target_runtime / "package-info.json").write_text(
                json.dumps(
                    {
                        "version_code": 10300,
                        "strict_update_channel": True,
                        "update_channel": "nogi-v13-public",
                    }
                ),
                encoding="utf-8",
            )
            (target / "nogi-install-root.json").write_text(
                json.dumps({"update_channel": "nogi-v13-public"}),
                encoding="utf-8",
            )
            (target / f"{PRODUCT_NAME}.exe").write_bytes(b"old-launcher")
            (target / "personal.txt").write_text("keep", encoding="utf-8")
            (target / "personal-folder").mkdir()
            (target / "personal-folder" / "keep.txt").write_text(
                "keep",
                encoding="utf-8",
            )

            script_path = root / "apply_update.ps1"
            _write_update_script(script_path)
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    "-Source",
                    str(source),
                    "-Target",
                    str(target),
                    "-RuntimeDirName",
                    "程序文件",
                    "-SkipRestart",
                ],
                check=True,
                timeout=30,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual((target / "personal.txt").read_text(), "keep")
            self.assertEqual(
                (target / "personal-folder" / "keep.txt").read_text(),
                "keep",
            )
            self.assertFalse((target_watcher / "old.txt").exists())
            self.assertEqual((target_watcher / "new.txt").read_text(), "new")
            self.assertEqual(
                (target_watcher / "buffwatcher.config.local.json").read_text(),
                "saved-config",
            )
            self.assertEqual(
                (target_watcher / "logs" / "saved.log").read_text(),
                "saved-log",
            )
            self.assertEqual(
                (target_watcher / "assets" / "custom" / "saved.png").read_bytes(),
                b"saved-icon",
            )


if __name__ == "__main__":
    unittest.main()

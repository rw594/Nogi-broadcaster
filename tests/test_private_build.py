from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buffwatcher.updater import fetch_latest_update, update_checks_disabled


class PrivateBuildTests(unittest.TestCase):
    def test_private_visual_package_never_contacts_public_updater(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory) / "程序文件"
            runtime_root.mkdir()
            (runtime_root / "package-info.json").write_text(
                json.dumps(
                    {
                        "version_code": 12405,
                        "private_build": True,
                        "visual_overlay": True,
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(update_checks_disabled(runtime_root))
            with patch("buffwatcher.updater._urlopen") as urlopen:
                self.assertIsNone(fetch_latest_update(runtime_root))
                urlopen.assert_not_called()

    def test_private_visual_package_with_its_own_channel_can_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory) / "程序文件"
            runtime_root.mkdir()
            (runtime_root / "package-info.json").write_text(
                json.dumps(
                    {
                        "version_code": 1250201,
                        "private_build": True,
                        "visual_overlay": True,
                        "update_urls": [
                            "https://example.oss-cn-hangzhou.aliyuncs.com/visual/latest.json"
                        ],
                    }
                ),
                encoding="utf-8",
            )

            self.assertFalse(update_checks_disabled(runtime_root))

    def test_private_visual_channel_never_falls_back_to_public_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory) / "程序文件"
            runtime_root.mkdir()
            private_url = (
                "https://example.oss-cn-hangzhou.aliyuncs.com/visual/latest.json"
            )
            (runtime_root / "package-info.json").write_text(
                json.dumps(
                    {
                        "version_code": 1250201,
                        "private_build": True,
                        "visual_overlay": True,
                        "update_urls": [private_url],
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "buffwatcher.updater._urlopen",
                side_effect=OSError("visual channel unavailable"),
            ) as urlopen:
                with self.assertRaises(RuntimeError):
                    fetch_latest_update(runtime_root)

            self.assertEqual(urlopen.call_count, 1)
            request = urlopen.call_args.args[0]
            self.assertEqual(request.full_url, private_url)


if __name__ == "__main__":
    unittest.main()

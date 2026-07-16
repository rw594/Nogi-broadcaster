from __future__ import annotations

import json
from pathlib import Path
import unittest

from buffwatcher.config_migration import _apply_policy_migrations
from buffwatcher.hamster_buffs import (
    HAMSTER_ADRENALINE_CCID,
    HAMSTER_ADRENALINE_NAME,
    HAMSTER_BUFF_DURATION_SECONDS,
    HAMSTER_DEFAULT_WARNING_SECONDS,
    HAMSTER_PET_RACE_IDS,
    HAMSTER_REMINDER_MERGE_VERSION,
    HAMSTER_SETTINGS_NAME,
    HAMSTER_SUMMON_SKILL_ID,
    HAMSTER_SUPERCHARGED_CCID,
    HAMSTER_SUPERCHARGED_NAME,
    ensure_hamster_buff_items,
)
from buffwatcher.settings_gui import BUFF_GROUPS


class HamsterBuffConfigTests(unittest.TestCase):
    def test_observed_ids_and_release_defaults_are_recorded(self) -> None:
        path = Path(__file__).resolve().parents[1] / "buffwatcher.config.defaults.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        items = {item.get("name"): item for item in data["buffs"]}

        supercharged = items[HAMSTER_SUPERCHARGED_NAME]
        adrenaline = items[HAMSTER_ADRENALINE_NAME]
        self.assertEqual(HAMSTER_PET_RACE_IDS, (490500, 490501))
        self.assertEqual(HAMSTER_SUMMON_SKILL_ID, 50279)
        self.assertEqual(supercharged["ccid"], HAMSTER_SUPERCHARGED_CCID)
        self.assertEqual(adrenaline["ccid"], HAMSTER_ADRENALINE_CCID)
        self.assertTrue(supercharged["enabled"])
        self.assertTrue(supercharged["ended_alert"])
        self.assertTrue(supercharged["remaining_enabled"])
        self.assertEqual(
            supercharged["alerts"][0]["remaining_seconds"],
            HAMSTER_DEFAULT_WARNING_SECONDS,
        )
        self.assertFalse(adrenaline["enabled"])
        self.assertFalse(adrenaline["ended_alert"])
        for item in (supercharged, adrenaline):
            self.assertEqual(item["duration_seconds"], HAMSTER_BUFF_DURATION_SECONDS)
            self.assertEqual(item["warn_seconds"], HAMSTER_DEFAULT_WARNING_SECONDS)
            self.assertTrue(item["ended_on_remove_only"])
        self.assertEqual(adrenaline["alerts"], [])
        self.assertEqual(
            data["hamster_reminder_merge_version"],
            HAMSTER_REMINDER_MERGE_VERSION,
        )
        self.assertNotIn("whale_override_silence_enabled", adrenaline)
        self.assertNotIn("suppress_ended_if_active_ccids", adrenaline)

    def test_combined_settings_row_is_in_other_group_with_plain_name(self) -> None:
        groups = dict(BUFF_GROUPS)

        self.assertNotIn("宠物增益", groups)
        self.assertIn(HAMSTER_SETTINGS_NAME, groups["其他"])
        self.assertNotIn(HAMSTER_SUPERCHARGED_NAME, groups["其他"])
        self.assertNotIn(HAMSTER_ADRENALINE_NAME, groups["其他"])
        self.assertEqual(HAMSTER_SETTINGS_NAME, "陈睿")

    def test_migration_adds_default_enabled_supercharged_and_silent_adrenaline(self) -> None:
        data = {"buffs": []}

        self.assertTrue(_apply_policy_migrations(data))

        items = {item.get("name"): item for item in data["buffs"]}
        self.assertTrue(items[HAMSTER_SUPERCHARGED_NAME]["enabled"])
        self.assertTrue(items[HAMSTER_SUPERCHARGED_NAME]["ended_alert"])
        self.assertTrue(items[HAMSTER_SUPERCHARGED_NAME]["alerts"])
        self.assertFalse(items[HAMSTER_ADRENALINE_NAME]["enabled"])

    def test_old_adrenaline_choices_move_to_supercharged_then_go_silent(self) -> None:
        data = {
            "buffs": [
                {
                    "name": HAMSTER_ADRENALINE_NAME,
                    "ccid": HAMSTER_ADRENALINE_CCID,
                    "enabled": True,
                    "ended_alert": True,
                    "warn_seconds": 17,
                    "alerts": [{"remaining_seconds": 17}],
                }
            ]
        }

        ensure_hamster_buff_items(data)

        items = {item["name"]: item for item in data["buffs"]}
        supercharged = items[HAMSTER_SUPERCHARGED_NAME]
        adrenaline = items[HAMSTER_ADRENALINE_NAME]
        self.assertTrue(supercharged["enabled"])
        self.assertTrue(supercharged["ended_alert"])
        self.assertEqual(supercharged["warn_seconds"], 17)
        self.assertEqual(supercharged["alerts"][0]["remaining_seconds"], 17)
        self.assertFalse(adrenaline["enabled"])
        self.assertFalse(adrenaline["ended_alert"])
        self.assertEqual(adrenaline["alerts"], [])
        self.assertEqual(
            data["hamster_reminder_merge_version"],
            HAMSTER_REMINDER_MERGE_VERSION,
        )

    def test_old_disabled_master_turns_both_subswitches_off(self) -> None:
        data = {
            "buffs": [
                {
                    "name": HAMSTER_SUPERCHARGED_NAME,
                    "ccid": HAMSTER_SUPERCHARGED_CCID,
                    "enabled": False,
                    "ended_alert": True,
                    "alerts": [{"remaining_seconds": 30}],
                }
            ]
        }

        ensure_hamster_buff_items(data)

        item = data["buffs"][0]
        self.assertFalse(item["enabled"])
        self.assertFalse(item["ended_alert"])
        self.assertEqual(item["alerts"], [])

    def test_old_enabled_master_keeps_selected_subswitches(self) -> None:
        data = {
            "buffs": [
                {
                    "name": HAMSTER_SUPERCHARGED_NAME,
                    "ccid": HAMSTER_SUPERCHARGED_CCID,
                    "enabled": True,
                    "ended_alert": False,
                    "alerts": [{"remaining_seconds": 30}],
                }
            ]
        }

        ensure_hamster_buff_items(data)

        item = data["buffs"][0]
        self.assertTrue(item["enabled"])
        self.assertFalse(item["ended_alert"])
        self.assertEqual(item["alerts"][0]["remaining_seconds"], 30)
        self.assertEqual(
            item["alerts"][0]["sound"],
            "assets/audio/xiaoyi/hamster_supercharged_remaining.wav",
        )
if __name__ == "__main__":
    unittest.main()

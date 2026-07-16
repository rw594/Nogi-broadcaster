from __future__ import annotations

import unittest

from buffwatcher.alerting import AlertEngine, BossHpAlertSpec
from buffwatcher.music_overlay import (
    MIRACLE_ORB_BLUE,
    MIRACLE_ORB_ORANGE,
    MIRACLE_ORB_RED,
    MusicOverlayApp,
)
from buffwatcher.overlay_bridge import (
    MiracleOrbHpOverlaySettings,
    command_for_miracle_orb_hp_states,
)


BU3_MAX_HP = 1_967_880_100


def boss_spec() -> BossHpAlertSpec:
    return BossHpAlertSpec(
        name="布三",
        short_name="布本3王",
        max_hp_values=(BU3_MAX_HP,),
        current_hp_stat_id=28,
        max_hp_stat_id=30,
        alerts=[],
    )


def stats(at_ms: int, entity_id: str, current_hp: float, max_hp: float) -> dict:
    return {
        "EventId": 17,
        "At": at_ms,
        "Id": entity_id,
        "Stats": [
            {"StatId": 28, "Value": current_hp},
            {"StatId": 30, "Value": max_hp},
        ],
    }


class MiracleOrbHpTrackingTests(unittest.TestCase):
    def make_engine(self, boss_percent: float = 60.0) -> AlertEngine:
        engine = AlertEngine([], boss_hp_alert_specs=[boss_spec()])
        engine.set_self_entity_id("self")
        engine.process_event(
            stats(1_000, "boss", BU3_MAX_HP * boss_percent / 100.0, BU3_MAX_HP)
        )
        return engine

    def spawn_group(self, engine: AlertEngine) -> None:
        for index, race_id in enumerate((7604, 7605, 7606)):
            engine.process_event(
                {
                    "EventId": 1,
                    "At": 2_000 + index * 10,
                    "Id": f"orb-{race_id}",
                    "OwnerId": "boss",
                    "RaceId": race_id,
                }
            )

    def test_group_activates_only_after_all_three_spawn_and_switches_focus(self) -> None:
        engine = self.make_engine()
        for index, race_id in enumerate((7604, 7605)):
            engine.process_event(
                {
                    "EventId": 1,
                    "At": 2_000 + index * 10,
                    "Id": f"orb-{race_id}",
                    "OwnerId": "boss",
                    "RaceId": race_id,
                }
            )
        self.assertFalse(any(state.active for state in engine.miracle_orb_hp_states.values()))

        engine.process_event(
            {
                "EventId": 1,
                "At": 2_020,
                "Id": "orb-7606",
                "OwnerId": "boss",
                "RaceId": 7606,
            }
        )
        self.assertEqual(
            [state.race_id for state in engine.miracle_orb_hp_states.values()],
            [7604, 7605, 7606],
        )
        self.assertTrue(all(state.active for state in engine.miracle_orb_hp_states.values()))

        for race_id, percent in ((7604, 80), (7605, 34), (7606, 14)):
            engine.process_event(
                stats(3_000 + race_id, f"orb-{race_id}", percent, 100)
            )
        engine.process_event(
            {
                "EventId": 3,
                "At": 4_000,
                "Id": "self",
                "TargetId": "orb-7605",
                "Damage": 9_999,
            }
        )
        self.assertIsNone(engine.miracle_orb_selected_entity_id)
        engine.process_event(
            {
                "EventId": 3,
                "At": 4_050,
                "Id": "self",
                "TargetId": "orb-7605",
                "Damage": 10_000,
            }
        )
        self.assertEqual(engine.miracle_orb_selected_entity_id, "orb-7605")
        engine.process_event(
            {
                "EventId": 3,
                "At": 4_100,
                "Id": "self",
                "TargetId": "orb-7606",
                "Damage": 12_000,
            }
        )
        self.assertEqual(engine.miracle_orb_selected_entity_id, "orb-7606")

        command = command_for_miracle_orb_hp_states(
            MiracleOrbHpOverlaySettings(enabled=True),
            engine.miracle_orb_hp_states,
            engine.miracle_orb_selected_entity_id,
        )
        self.assertEqual(command["type"], "miracle_orb_hp_snapshot")
        self.assertEqual([item["race_id"] for item in command["items"]], [7605, 7604, 7606])
        self.assertEqual(command["selected"]["race_id"], 7606)

        engine.process_event({"EventId": 2, "At": 5_000, "Id": "orb-7606"})
        self.assertIsNone(engine.miracle_orb_selected_entity_id)
        self.assertNotIn("orb-7606", engine.miracle_orb_hp_states)

    def test_30_percent_five_laser_phase_does_not_activate_tracker(self) -> None:
        engine = self.make_engine(30.0)
        self.spawn_group(engine)
        self.assertEqual(engine.miracle_orb_hp_states, {})

    def test_broad_50_to_65_percent_window_no_longer_accepts_lookalikes(self) -> None:
        engine = self.make_engine(64.0)
        self.spawn_group(engine)
        self.assertEqual(engine.miracle_orb_hp_states, {})

    def test_completed_group_clears_and_same_owner_cannot_rearm(self) -> None:
        engine = self.make_engine()
        self.spawn_group(engine)
        for race_id in (7604, 7605, 7606):
            engine.process_event(stats(3_000 + race_id, f"orb-{race_id}", 0, 100))
        self.assertEqual(engine.miracle_orb_hp_states, {})
        self.assertIn("boss", engine.miracle_orb_completed_owner_ids)

        self.spawn_group(engine)
        self.assertEqual(engine.miracle_orb_hp_states, {})

    def test_boss_resuming_below_60_percent_ends_the_phase(self) -> None:
        engine = self.make_engine()
        self.spawn_group(engine)
        engine.process_event(stats(5_000, "boss", BU3_MAX_HP * 0.599, BU3_MAX_HP))
        self.assertEqual(engine.miracle_orb_hp_states, {})
        self.assertIn("boss", engine.miracle_orb_completed_owner_ids)

    def test_threshold_colors_match_requested_rgb_values(self) -> None:
        self.assertEqual(MusicOverlayApp._miracle_orb_hp_color(35.0), MIRACLE_ORB_BLUE)
        self.assertEqual(MusicOverlayApp._miracle_orb_hp_color(34.99), MIRACLE_ORB_ORANGE)
        self.assertEqual(MusicOverlayApp._miracle_orb_hp_color(15.0), MIRACLE_ORB_ORANGE)
        self.assertEqual(MusicOverlayApp._miracle_orb_hp_color(14.99), MIRACLE_ORB_RED)

    def test_debuff_row_anchor_adapts_between_1080p_and_4k(self) -> None:
        self.assertEqual(MusicOverlayApp._responsive_debuff_center_y(1080), 772)
        self.assertEqual(MusicOverlayApp._responsive_debuff_center_y(2160), 1685)

    def test_focus_bar_anchor_also_adapts_to_game_ui_scaling(self) -> None:
        self.assertEqual(
            MusicOverlayApp._responsive_center_y(
                1080, low_ratio=0.785, high_ratio=0.855
            ),
            848,
        )
        self.assertEqual(
            MusicOverlayApp._responsive_center_y(
                2160, low_ratio=0.785, high_ratio=0.855
            ),
            1847,
        )


if __name__ == "__main__":
    unittest.main()

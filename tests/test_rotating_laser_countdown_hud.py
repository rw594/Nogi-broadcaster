from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from buffwatcher.alerting import AlertEngine, BossLaserAlertSpec, load_all_specs
from buffwatcher.music_overlay import (
    ROTATING_LASER_COUNTDOWN_COLOR,
    RotatingLaserCountdownOverlayItem,
)
from buffwatcher.overlay_bridge import (
    RotatingLaserCountdownOverlaySettings,
    command_for_rotating_laser_countdown,
)


BU3_MAX_HP = 1_967_880_100
BU4_MAX_HP = 3_449_779_200


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


def laser_event(at_ms: int, entity_id: str, op: str, duration_ms: int = 5_000) -> dict:
    return {
        "EventId": 0,
        "At": at_ms,
        "Id": entity_id,
        "Op": op,
        "Msg": [
            {"V": "0"},
            {"V": "0"},
            {"V": "0"},
            {"V": str(duration_ms)},
            {"V": "278"},
            {"V": "1"},
        ],
    }


class RotatingLaserCountdownTrackingTests(unittest.TestCase):
    def make_engine(self) -> AlertEngine:
        engine = AlertEngine(
            [],
            boss_laser_alert_specs=[
                BossLaserAlertSpec(
                    name="布三/布四旋转激光",
                    max_hp_values=(BU3_MAX_HP,),
                    voice_enabled=False,
                )
            ],
        )
        engine.process_event(stats(1_000, "boss", BU3_MAX_HP, BU3_MAX_HP))
        for index, race_id in enumerate((7604, 7605, 7606, 7607, 7608)):
            engine.process_event(
                {
                    "EventId": 1,
                    "At": 2_000 + index,
                    "Id": f"laser-{race_id}",
                    "OwnerId": "boss",
                    "RaceId": race_id,
                }
            )
        return engine

    def test_real_afdb_starts_countdown_and_duplicates_do_not_restart_it(self) -> None:
        engine = self.make_engine()
        state = engine.boss_laser_alert_states_by_max_hp[BU3_MAX_HP]

        engine.process_event(laser_event(10_000, "laser-7604", "0xafdb", 5_000))
        engine.process_event(laser_event(10_018, "laser-7605", "0xafdb", 5_000))

        movement = state.movement_countdown
        self.assertIsNotNone(movement)
        assert movement is not None
        self.assertEqual(movement.start_at_ms, 10_000)
        self.assertEqual(movement.end_at_ms, 15_000)
        self.assertEqual(
            movement.stardust_entity_ids,
            {"laser-7604", "laser-7605"},
        )

        command = command_for_rotating_laser_countdown(
            RotatingLaserCountdownOverlaySettings(enabled=True),
            engine.boss_laser_alert_states_by_max_hp,
            now_ms=10_100,
        )
        self.assertEqual(command["type"], "rotating_laser_countdown_snapshot")
        self.assertEqual(command["duration_ms"], 5_000)
        self.assertEqual(command["end_at_ms"], 15_000)

    def test_each_new_segment_uses_its_dynamic_duration(self) -> None:
        engine = self.make_engine()
        state = engine.boss_laser_alert_states_by_max_hp[BU3_MAX_HP]
        engine.process_event(laser_event(10_000, "laser-7604", "0xafda", 5_000))
        engine.process_event(laser_event(20_000, "laser-7604", "0xafdb", 12_345))

        movement = state.movement_countdown
        self.assertIsNotNone(movement)
        assert movement is not None
        self.assertEqual(movement.start_at_ms, 20_000)
        self.assertEqual(movement.end_at_ms, 32_345)

        engine.advance_time(32_345)
        self.assertIsNone(state.movement_countdown)

    def test_long_60_percent_movement_packet_is_not_a_laser_countdown(self) -> None:
        engine = self.make_engine()
        state = engine.boss_laser_alert_states_by_max_hp[BU3_MAX_HP]
        engine.process_event(laser_event(10_000, "laser-7604", "0xafdb", 154_000))
        self.assertIsNone(state.movement_countdown)

    def test_advance_time_expires_a_countdown_without_a_stop_packet(self) -> None:
        engine = self.make_engine()
        state = engine.boss_laser_alert_states_by_max_hp[BU3_MAX_HP]
        engine.process_event(laser_event(10_000, "laser-7604", "0xafda", 5_000))
        engine.advance_time(15_000)
        self.assertIsNone(state.movement_countdown)

    def test_overlay_text_is_one_decimal_and_requested_orange(self) -> None:
        item = RotatingLaserCountdownOverlayItem(
            boss_entity_id="boss",
            start_at_ms=10_000,
            end_at_ms=15_000,
            duration_ms=5_000,
        )
        self.assertEqual(item.text(10_051), "4.9")
        self.assertEqual(ROTATING_LASER_COUNTDOWN_COLOR, "#ff9d30")

    def test_visual_switch_keeps_laser_packets_without_enabling_voice(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "buffs": [],
                        "experimental_bu34_rotating_laser_visual_countdown": {
                            "enabled": True
                        },
                    }
                ),
                encoding="utf-8",
            )
            loaded = load_all_specs(path)

        self.assertEqual(len(loaded.boss_laser_alerts), 1)
        self.assertFalse(loaded.boss_laser_alerts[0].voice_enabled)
        self.assertEqual(
            loaded.boss_laser_alerts[0].max_hp_values,
            (1_967_880_100, 3_449_779_200),
        )

    def test_bu4_current_afe8_and_legacy_afe7_share_the_five_second_warning(self) -> None:
        for cast_op in ("0xafe7", "0xafe8"):
            with self.subTest(cast_op=cast_op):
                engine = AlertEngine(
                    [],
                    boss_laser_alert_specs=[
                        BossLaserAlertSpec(
                            name="布3/布4激光前倒计时",
                            max_hp_values=(BU3_MAX_HP, BU4_MAX_HP),
                        )
                    ],
                )
                engine.process_event(stats(1_000, "boss", BU4_MAX_HP, BU4_MAX_HP))
                for index, race_id in enumerate((7616, 7617, 7618, 7619, 7620)):
                    engine.process_event(
                        {
                            "EventId": 1,
                            "At": 1_100 + index,
                            "Id": f"laser-{race_id}",
                            "OwnerId": "boss",
                            "RaceId": race_id,
                        }
                    )

                event = {
                    "EventId": 0,
                    "At": 10_000,
                    "Id": "laser-7616",
                    "Op": cast_op,
                    "Msg": [
                        {"V": "52401"},
                        {"V": "0"},
                        {"V": "25156"},
                        {"V": "500"},
                        {"V": "36745"},
                        {"V": "1"},
                    ],
                }
                alerts = engine.process_event(event)

                self.assertEqual(len(alerts), 1)
                self.assertEqual(alerts[0].kind, "boss_laser")
                self.assertEqual(alerts[0].detail["start_at_ms"], 10_000)
                self.assertEqual(alerts[0].detail["impact_at_ms"], 15_000)
                self.assertEqual(alerts[0].detail["cast_seconds"], 5.0)

                duplicate = dict(event, At=10_010, Id="laser-7617")
                self.assertEqual(engine.process_event(duplicate), [])


if __name__ == "__main__":
    unittest.main()

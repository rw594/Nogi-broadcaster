from __future__ import annotations

import unittest

from buffwatcher.alerting import AlertEngine, BuffSpec, MissingMagicShieldSpec


SELF_ID = "4503599639695197"


def hp_event(at_ms: int, hp: float) -> dict:
    return {
        "EventId": 17,
        "At": at_ms,
        "Id": SELF_ID,
        "Stats": [{"StatId": 28, "Value": hp}],
    }


class MagicShieldDeathTests(unittest.TestCase):
    @staticmethod
    def _engine() -> AlertEngine:
        magic_shield = BuffSpec(
            name="魔法盾",
            ccid=59,
            self_filter=True,
            ended_alert=False,
        )
        engine = AlertEngine(
            [magic_shield],
            magic_shield_missing=MissingMagicShieldSpec(
                delay_seconds=3,
                repeat_seconds=5,
                message="魔法盾忘开啦",
            ),
        )
        engine.set_self_entity_id(SELF_ID)
        engine.battle_timer_active = True
        engine.magic_shield_state_observed = True
        return engine

    def test_stale_positive_hp_after_death_does_not_resume_missing_alerts(self) -> None:
        engine = self._engine()
        engine.process_event(hp_event(1_000, 7_354.2812))
        engine._resync_magic_shield_missing_schedule(1_000)
        self.assertEqual(engine.magic_shield_missing_next_due_ms, 4_000)

        engine.process_event({"EventId": 15, "At": 2_000, "Id": SELF_ID})
        self.assertTrue(engine.self_player_dead)
        self.assertIsNone(engine.magic_shield_missing_next_due_ms)

        # Real battle logs repeat the same positive HP snapshot while the character
        # is still lying dead. It must not be interpreted as a revival.
        engine.process_event(hp_event(2_100, 7_354.2812))
        engine.process_event(hp_event(8_000, 7_354.2812))
        self.assertTrue(engine.self_player_dead)
        self.assertFalse(
            any(
                alert.kind == "missing_magic_shield"
                for alert in engine.advance_time(10_000)
            )
        )

    def test_real_hp_transition_resumes_detection_with_a_fresh_delay(self) -> None:
        engine = self._engine()
        engine.process_event(hp_event(1_000, 7_354.2812))
        engine.process_event({"EventId": 15, "At": 2_000, "Id": SELF_ID})
        engine.process_event(hp_event(2_100, 7_354.2812))

        engine.process_event(hp_event(8_000, 4_529.8027))
        self.assertFalse(engine.self_player_dead)
        self.assertEqual(engine.magic_shield_missing_next_due_ms, 11_000)
        self.assertFalse(engine.advance_time(10_999))
        alerts = engine.advance_time(11_000)
        self.assertEqual([alert.kind for alert in alerts], ["missing_magic_shield"])

    def test_death_snapshot_magic_shield_apply_does_not_fake_a_revival(self) -> None:
        engine = self._engine()
        engine.process_event(hp_event(1_000, 7_354.2812))
        engine.process_event({"EventId": 15, "At": 2_000, "Id": SELF_ID})

        engine.process_event(
            {"EventId": 4, "At": 2_001, "Id": SELF_ID, "CCId": 59}
        )

        self.assertTrue(engine.self_player_dead)
        self.assertIsNone(engine.magic_shield_missing_next_due_ms)


if __name__ == "__main__":
    unittest.main()

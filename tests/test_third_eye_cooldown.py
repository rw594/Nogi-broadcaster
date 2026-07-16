from __future__ import annotations

import unittest

from buffwatcher.alerting import AlertEngine, BuffSpec
from buffwatcher.config_migration import _apply_policy_migrations
from buffwatcher.settings_gui import (
    SPECIAL_END_ONLY_DEFAULTS,
    THIRD_EYE_NAME,
    find_or_create_special_end_only,
)


THIRD_EYE_CCID = 521


def third_eye_event(event_id: int, at_ms: int) -> dict:
    event = {
        "EventId": event_id,
        "At": at_ms,
        "CCId": THIRD_EYE_CCID,
    }
    if event_id == 4:
        event["ExtraData"] = {"DUR": 120_000}
    return event


class ThirdEyeCooldownTests(unittest.TestCase):
    @staticmethod
    def _engine(cooldown_seconds: int) -> tuple[AlertEngine, object]:
        spec = BuffSpec(
            name="第三只眼",
            ccid=THIRD_EYE_CCID,
            self_filter=False,
            ended_on_remove_only=True,
            ended_grace_seconds=0,
            cooldown_alert=True,
            cooldown_delay_seconds=cooldown_seconds,
            cooldown_from_apply=True,
            cooldown_message="三眼 就绪",
        )
        engine = AlertEngine([spec])
        return engine, engine.states[THIRD_EYE_CCID]

    def test_300_second_cooldown_stays_anchored_to_first_apply(self) -> None:
        engine, state = self._engine(300)

        engine.process_event(third_eye_event(4, 1_000))
        self.assertEqual(state.cooldown_anchor_at_ms, 1_000)
        self.assertEqual(state.cooldown_pending_at_ms, 301_000)

        # Periodic EventId=4 refresh packets must not restart the cooldown.
        engine.process_event(third_eye_event(4, 11_000))
        self.assertEqual(state.cooldown_anchor_at_ms, 1_000)
        self.assertEqual(state.cooldown_pending_at_ms, 301_000)

        # The remove packet still drives the end reminder, but not cooldown timing.
        engine.process_event(third_eye_event(5, 121_119))
        self.assertEqual(state.cooldown_pending_at_ms, 301_000)
        self.assertFalse(any(alert.kind == "cooldown" for alert in engine.advance_time(300_999)))

        alerts = engine.advance_time(301_000)
        cooldown_alerts = [alert for alert in alerts if alert.kind == "cooldown"]
        self.assertEqual(len(cooldown_alerts), 1)
        self.assertEqual(cooldown_alerts[0].at_ms, 301_000)
        self.assertEqual(cooldown_alerts[0].message, "三眼 就绪")

    def test_240_second_equipment_option_uses_the_same_apply_anchor(self) -> None:
        engine, state = self._engine(240)

        engine.process_event(third_eye_event(4, 5_000))
        engine.process_event(third_eye_event(4, 15_000))
        engine.process_event(third_eye_event(5, 125_000))

        self.assertEqual(state.cooldown_pending_at_ms, 245_000)
        alerts = engine.advance_time(245_000)
        self.assertEqual([alert.kind for alert in alerts], ["cooldown"])

    def test_settings_offer_only_300_or_240_and_default_to_300(self) -> None:
        rules = SPECIAL_END_ONLY_DEFAULTS[THIRD_EYE_NAME]

        self.assertEqual(rules["cooldown_seconds"], 300)
        self.assertEqual(rules["cooldown_choices"], (300, 240))
        item = find_or_create_special_end_only({}, THIRD_EYE_NAME)
        self.assertEqual(item["cooldown_delay_seconds"], 300)
        self.assertTrue(item["cooldown_from_apply"])

    def test_migration_converts_old_end_plus_180_but_preserves_240_choice(self) -> None:
        old_data = {
            "buffs": [
                {
                    "name": THIRD_EYE_NAME,
                    "ccid": THIRD_EYE_CCID,
                    "cooldown_delay_seconds": 180,
                }
            ]
        }
        self.assertTrue(_apply_policy_migrations(old_data))
        self.assertEqual(old_data["buffs"][0]["cooldown_delay_seconds"], 300)
        self.assertTrue(old_data["buffs"][0]["cooldown_from_apply"])

        equipment_data = {
            "buffs": [
                {
                    "name": THIRD_EYE_NAME,
                    "ccid": THIRD_EYE_CCID,
                    "cooldown_delay_seconds": 240,
                    "cooldown_from_apply": True,
                }
            ]
        }
        # Shared policy migration adds newly supported, disabled hamster buffs.
        self.assertTrue(_apply_policy_migrations(equipment_data))
        self.assertFalse(_apply_policy_migrations(equipment_data))
        self.assertEqual(equipment_data["buffs"][0]["cooldown_delay_seconds"], 240)


if __name__ == "__main__":
    unittest.main()

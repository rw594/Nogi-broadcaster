from __future__ import annotations

import unittest

from buffwatcher.alerting import AlertEngine, BuffSpec
from buffwatcher.config_migration import _apply_policy_migrations
from buffwatcher.settings_gui import (
    SELF_BUFF_CIRCLE_NAME,
    SPECIAL_END_ONLY_DEFAULTS,
    find_or_create_special_end_only,
)


MAGIC_CIRCLE_CCID = 10133
MAGIC_CIRCLE_SKILL_ID = 10103
SELF_ID = "4503599639695197"


def skill_event(event_id: int, at_ms: int, *, entity_id: str = SELF_ID) -> dict:
    return {
        "EventId": event_id,
        "At": at_ms,
        "Id": entity_id,
        "SkillId": MAGIC_CIRCLE_SKILL_ID,
    }


def circle_apply(at_ms: int) -> dict:
    return {
        "EventId": 4,
        "At": at_ms,
        "Id": SELF_ID,
        "CCId": MAGIC_CIRCLE_CCID,
        "ExtraData": {"MCED": 130_000, "MCEID": 0},
    }


class MagicCircleCooldownTests(unittest.TestCase):
    @staticmethod
    def _engine() -> tuple[AlertEngine, object]:
        spec = BuffSpec(
            name=SELF_BUFF_CIRCLE_NAME,
            ccid=MAGIC_CIRCLE_CCID,
            skill_id=MAGIC_CIRCLE_SKILL_ID,
            linked_ccids={10137, 10138},
            self_filter=True,
            ended_alert=False,
            cooldown_alert=True,
            cooldown_delay_seconds=140,
            cooldown_from_skill_use=True,
            cooldown_message="魔法阵 就绪",
        )
        engine = AlertEngine([spec])
        return engine, engine.states[MAGIC_CIRCLE_CCID]

    def test_only_self_e12_starts_cooldown(self) -> None:
        engine, state = self._engine()

        # No character identity yet: do not trust a skill packet as ours.
        engine.process_event(skill_event(12, 500))
        self.assertIsNone(state.cooldown_anchor_at_ms)

        engine.set_self_entity_id(SELF_ID)
        state = engine.states[MAGIC_CIRCLE_CCID]
        for event_id in (10, 11, 13):
            engine.process_event(skill_event(event_id, 600 + event_id))
        engine.process_event(skill_event(12, 800, entity_id="someone-else"))
        self.assertIsNone(state.cooldown_anchor_at_ms)

        engine.process_event(skill_event(12, 1_000))
        self.assertEqual(state.cooldown_anchor_at_ms, 1_000)
        self.assertEqual(state.cooldown_pending_at_ms, 141_000)

    def test_buff_apply_and_end_do_not_move_e12_anchor(self) -> None:
        engine, state = self._engine()
        engine.set_self_entity_id(SELF_ID)
        state = engine.states[MAGIC_CIRCLE_CCID]

        # Mirrors the observed order: buff components arrived 0-6 ms before E12.
        engine.process_event(circle_apply(1_000))
        engine.process_event(skill_event(12, 1_006))
        self.assertEqual(state.cooldown_pending_at_ms, 141_006)

        # A subsequent component/refresh and the effect ending must not turn this
        # back into the legacy "effect end + delay" calculation.
        linked_refresh = circle_apply(1_010)
        linked_refresh["CCId"] = 10138
        engine.process_event(linked_refresh)
        engine.process_event(
            {
                "EventId": 5,
                "At": 131_000,
                "Id": SELF_ID,
                "CCId": MAGIC_CIRCLE_CCID,
            }
        )
        self.assertEqual(state.cooldown_pending_at_ms, 141_006)
        self.assertFalse(engine.advance_time(141_005))

        alerts = engine.advance_time(141_006)
        self.assertEqual([alert.kind for alert in alerts], ["cooldown"])
        self.assertEqual(alerts[0].message, "魔法阵 就绪")

    def test_defaults_and_migration_use_e12_plus_140(self) -> None:
        rules = SPECIAL_END_ONLY_DEFAULTS[SELF_BUFF_CIRCLE_NAME]
        self.assertEqual(rules["cooldown_seconds"], 140)
        self.assertTrue(rules["cooldown_fixed"])
        self.assertTrue(rules["cooldown_from_skill_use"])

        item = find_or_create_special_end_only({}, SELF_BUFF_CIRCLE_NAME)
        self.assertEqual(item["cooldown_delay_seconds"], 140)
        self.assertTrue(item["cooldown_from_skill_use"])

        legacy_data = {
            "buffs": [
                {
                    "name": SELF_BUFF_CIRCLE_NAME,
                    "ccid": MAGIC_CIRCLE_CCID,
                    "cooldown_delay_seconds": 15,
                }
            ]
        }
        self.assertTrue(_apply_policy_migrations(legacy_data))
        migrated = legacy_data["buffs"][0]
        self.assertEqual(migrated["cooldown_delay_seconds"], 140)
        self.assertTrue(migrated["cooldown_from_skill_use"])

        manually_edited_data = {
            "buffs": [
                {
                    "name": SELF_BUFF_CIRCLE_NAME,
                    "ccid": MAGIC_CIRCLE_CCID,
                    "cooldown_delay_seconds": 150,
                    "cooldown_from_skill_use": True,
                }
            ]
        }
        self.assertTrue(_apply_policy_migrations(manually_edited_data))
        self.assertEqual(
            manually_edited_data["buffs"][0]["cooldown_delay_seconds"], 140
        )

    def test_ground_target_e12_uses_same_skill_id_and_anchor(self) -> None:
        engine, _state = self._engine()
        engine.set_self_entity_id(SELF_ID)
        state = engine.states[MAGIC_CIRCLE_CCID]

        event = skill_event(12, 2_000)
        event["TargetId"] = "3458764574063724604"
        engine.process_event(event)

        self.assertEqual(state.cooldown_anchor_at_ms, 2_000)
        self.assertEqual(state.cooldown_pending_at_ms, 142_000)
        self.assertEqual(
            [alert.kind for alert in engine.advance_time(142_000)], ["cooldown"]
        )

    def test_pall_of_ruination_uses_self_e12_plus_fixed_180_seconds(self) -> None:
        spec = BuffSpec(
            name="崩坏波动",
            ccid=803,
            skill_id=59005,
            self_filter=True,
            ended_alert=False,
            cooldown_alert=False,
            cooldown_delay_seconds=180,
            cooldown_from_skill_use=True,
        )
        engine = AlertEngine([spec])
        engine.set_self_entity_id(SELF_ID)
        engine.process_event(
            {
                "EventId": 12,
                "At": 5_000,
                "Id": SELF_ID,
                "SkillId": 59005,
                "TargetId": "",
            }
        )
        state = engine.states[803]

        self.assertEqual(state.cooldown_anchor_at_ms, 5_000)
        self.assertEqual(state.spec.cooldown_delay_seconds, 180)
        self.assertIsNone(state.cooldown_pending_at_ms)


if __name__ == "__main__":
    unittest.main()

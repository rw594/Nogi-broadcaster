from __future__ import annotations

import unittest

from buffwatcher.alerting import (
    AlertEngine,
    BossHpAlertSpec,
    BuffSpec,
    KeyEnemyDebuffAlertSpec,
    MissingMagicShieldSpec,
)


IGNIS_PLUME_TRACKER_CCID = -59060
IGNIS_PLUME_SKILL_ID = 59060
AQUA_VOLLEY_TRACKER_CCID = -59061
AQUA_VOLLEY_SKILL_ID = 59061
SELF_ID = "4503599639695197"


class ShortCooldownHudTests(unittest.TestCase):
    def test_self_e12_is_the_only_ignis_plume_cooldown_anchor(self) -> None:
        spec = BuffSpec(
            name="爆炎箭",
            ccid=IGNIS_PLUME_TRACKER_CCID,
            skill_id=IGNIS_PLUME_SKILL_ID,
            self_filter=True,
            ended_alert=False,
            cooldown_alert=False,
            cooldown_delay_seconds=6,
            cooldown_from_skill_use=True,
        )
        engine = AlertEngine([spec])

        engine.process_event(
            {
                "EventId": 12,
                "At": 500,
                "Id": SELF_ID,
                "SkillId": IGNIS_PLUME_SKILL_ID,
            }
        )
        self.assertIsNone(
            engine.states[IGNIS_PLUME_TRACKER_CCID].cooldown_anchor_at_ms
        )

        engine.set_self_entity_id(SELF_ID)
        for event_id in (10, 11, 13):
            engine.process_event(
                {
                    "EventId": event_id,
                    "At": 1_000 + event_id,
                    "Id": SELF_ID,
                    "SkillId": IGNIS_PLUME_SKILL_ID,
                }
            )
        engine.process_event(
            {
                "EventId": 12,
                "At": 2_000,
                "Id": "someone-else",
                "SkillId": IGNIS_PLUME_SKILL_ID,
            }
        )
        self.assertIsNone(
            engine.states[IGNIS_PLUME_TRACKER_CCID].cooldown_anchor_at_ms
        )

        engine.process_event(
            {
                "EventId": 12,
                "At": 3_000,
                "Id": SELF_ID,
                "TargetId": "4767482434595472",
                "SkillId": IGNIS_PLUME_SKILL_ID,
            }
        )
        state = engine.states[IGNIS_PLUME_TRACKER_CCID]
        self.assertEqual(state.cooldown_anchor_at_ms, 3_000)
        self.assertEqual(state.spec.cooldown_delay_seconds, 6)
        self.assertIsNone(state.cooldown_pending_at_ms)

        engine.process_event(
            {
                "EventId": 12,
                "At": 9_200,
                "Id": SELF_ID,
                "TargetId": "4767482434595472",
                "SkillId": IGNIS_PLUME_SKILL_ID,
            }
        )
        self.assertEqual(state.cooldown_anchor_at_ms, 9_200)

    def test_self_e12_starts_the_aqua_volley_ten_second_cooldown(self) -> None:
        spec = BuffSpec(
            name="水流箭",
            ccid=AQUA_VOLLEY_TRACKER_CCID,
            skill_id=AQUA_VOLLEY_SKILL_ID,
            self_filter=True,
            ended_alert=False,
            cooldown_alert=False,
            cooldown_delay_seconds=10,
            cooldown_from_skill_use=True,
        )
        engine = AlertEngine([spec])
        engine.set_self_entity_id(SELF_ID)

        for event_id in (10, 11, 13):
            engine.process_event(
                {
                    "EventId": event_id,
                    "At": 1_000 + event_id,
                    "Id": SELF_ID,
                    "SkillId": AQUA_VOLLEY_SKILL_ID,
                }
            )
        engine.process_event(
            {
                "EventId": 12,
                "At": 2_000,
                "Id": "someone-else",
                "SkillId": AQUA_VOLLEY_SKILL_ID,
            }
        )
        state = engine.states[AQUA_VOLLEY_TRACKER_CCID]
        self.assertIsNone(state.cooldown_anchor_at_ms)

        engine.process_event(
            {
                "EventId": 12,
                "At": 3_000,
                "Id": SELF_ID,
                "TargetId": "4767482434902725",
                "SkillId": AQUA_VOLLEY_SKILL_ID,
            }
        )
        self.assertEqual(state.cooldown_anchor_at_ms, 3_000)
        self.assertEqual(state.spec.cooldown_delay_seconds, 10)
        self.assertIsNone(state.cooldown_pending_at_ms)

    def test_training_dummy_only_activates_the_short_cooldown_test_scope(self) -> None:
        boss_max_hp = 104_041_810
        engine = AlertEngine(
            [],
            boss_hp_alert_specs=[
                BossHpAlertSpec(name="boss", max_hp_values=(boss_max_hp,))
            ],
            key_enemy_debuff_alert=KeyEnemyDebuffAlertSpec(
                complete_enabled=True,
                max_hp_values=(boss_max_hp,),
            ),
            magic_shield_missing=MissingMagicShieldSpec(
                delay_seconds=1,
                repeat_seconds=1,
            ),
        )
        appeared = {
            "EventId": 1,
            "At": 1_000,
            "Id": "training-dummy",
            "RaceId": 4860,
            "Name": "instance-name",
        }
        stats = {
            "EventId": 17,
            "At": 2_000,
            "Id": "training-dummy",
            "Stats": [
                {"StatId": 11, "Value": 1},
                {"StatId": 12, "Value": 1},
                {"StatId": 13, "Value": 1},
                {"StatId": 14, "Value": 1},
                {"StatId": 28, "Value": 99_996_120},
                {"StatId": 30, "Value": 100_000_000},
            ],
        }

        self.assertTrue(engine.is_short_cooldown_test_target_event(appeared))
        self.assertFalse(engine.is_boss_hp_event(appeared))
        self.assertFalse(engine.is_key_enemy_debuff_event(appeared))
        self.assertEqual(engine.process_event(appeared), [])
        self.assertTrue(engine.short_cooldown_test_target_active)

        self.assertTrue(engine.is_short_cooldown_test_target_event(stats))
        self.assertFalse(engine.is_boss_hp_event(stats))
        self.assertFalse(engine.is_key_enemy_debuff_event(stats))
        self.assertEqual(engine.process_event(stats), [])
        self.assertFalse(engine.key_enemy_debuff_entity_states)
        self.assertFalse(
            any(state.active for state in engine.boss_hp_alert_states_by_max_hp.values())
        )
        self.assertIsNone(engine.magic_shield_missing_next_due_ms)
        self.assertFalse(
            any(
                alert.kind == "missing_magic_shield"
                for alert in engine.advance_time(20_000)
            )
        )

        removed = {
            "EventId": 2,
            "At": 21_000,
            "Id": "training-dummy",
        }
        self.assertTrue(engine.is_short_cooldown_test_target_event(removed))
        engine.process_event(removed)
        self.assertFalse(engine.short_cooldown_test_target_active)

    def test_training_dummy_stats_are_a_fallback_when_spawn_was_missed(self) -> None:
        engine = AlertEngine([])
        stats = {
            "EventId": 17,
            "At": 2_000,
            "Id": "training-dummy",
            "Stats": [
                {"StatId": 11, "Value": 1},
                {"StatId": 12, "Value": 1},
                {"StatId": 13, "Value": 1},
                {"StatId": 14, "Value": 1},
                {"StatId": 30, "Value": 100_000_000},
            ],
        }

        self.assertTrue(engine.is_short_cooldown_test_target_event(stats))
        engine.process_event(stats)
        self.assertTrue(engine.short_cooldown_test_target_active)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from buffwatcher.alerting import (
    AlertEngine,
    DEATH_MARK_DAMAGE_CCID,
    DEATH_MARK_PULL_CCID,
    KeyEnemyDebuffAlertSpec,
)
from buffwatcher.config_migration import _apply_policy_migrations


BOSS_ID = "boss"
BOSS_MAX_HP = 1_143_352_700


class DeathMarkDebuffIdentityTests(unittest.TestCase):
    def _engine(self, *, minimum: float = 60) -> AlertEngine:
        engine = AlertEngine(
            [],
            key_enemy_debuff_alert=KeyEnemyDebuffAlertSpec(
                complete_enabled=True,
                expiry_enabled=True,
                damage_bonus_min=minimum,
                max_hp_values=(BOSS_MAX_HP,),
            ),
        )
        engine.process_event(
            {
                "EventId": 17,
                "At": 1_000,
                "Id": BOSS_ID,
                "Stats": [
                    {"StatId": 28, "Value": BOSS_MAX_HP},
                    {"StatId": 30, "Value": BOSS_MAX_HP},
                ],
            }
        )
        return engine

    def test_pull_ccid_is_hard_excluded_from_all_death_mark_tracking(self) -> None:
        engine = self._engine()
        event = {
            "EventId": 4,
            "At": 2_000,
            "Id": BOSS_ID,
            "CCId": DEATH_MARK_PULL_CCID,
            "ExtraData": {
                "MCDDMBPV": 62,
                "MCDDMBTPV": 62,
                "DUR": 300_000,
            },
        }

        self.assertFalse(engine.is_key_enemy_debuff_event(event))
        engine.process_event(event)
        state = engine.key_enemy_debuff_entity_states[BOSS_ID]
        self.assertFalse(state.requirements["damage_bonus"].active)
        self.assertFalse(state.expiry_requirements["damage_bonus"].active)

    def test_damage_ccid_requires_the_damage_bonus_field(self) -> None:
        engine = self._engine()
        event = {
            "EventId": 4,
            "At": 2_000,
            "Id": BOSS_ID,
            "CCId": DEATH_MARK_DAMAGE_CCID,
            "ExtraData": {
                "MCDDMBPV": 99,
                "MCDDMBTPV": 99,
                "DUR": 300_000,
            },
        }

        self.assertTrue(engine.is_key_enemy_debuff_event(event))
        engine.process_event(event)
        state = engine.key_enemy_debuff_entity_states[BOSS_ID]
        self.assertFalse(state.requirements["damage_bonus"].active)
        self.assertFalse(state.expiry_requirements["damage_bonus"].active)

    def test_real_damage_signal_tracks_expiry_below_completion_threshold(self) -> None:
        engine = self._engine(minimum=60)
        event = {
            "EventId": 4,
            "At": 2_000,
            "Id": BOSS_ID,
            "CCId": DEATH_MARK_DAMAGE_CCID,
            "ExtraData": {"DAMAGE_BONUS": 56.25, "DUR": 300_000},
        }

        engine.process_event(event)
        state = engine.key_enemy_debuff_entity_states[BOSS_ID]
        self.assertFalse(state.requirements["damage_bonus"].active)
        self.assertTrue(state.expiry_requirements["damage_bonus"].active)

        lower_threshold_engine = self._engine(minimum=50)
        lower_threshold_engine.process_event(event)
        lower_state = lower_threshold_engine.key_enemy_debuff_entity_states[BOSS_ID]
        self.assertTrue(lower_state.requirements["damage_bonus"].active)
        self.assertTrue(lower_state.expiry_requirements["damage_bonus"].active)

    def test_config_migration_labels_pull_as_unrelated_and_disables_it(self) -> None:
        data = {
            "buffs": [
                {"name": "cc_426", "ccid": DEATH_MARK_DAMAGE_CCID},
                {
                    "name": "死亡锁定",
                    "ccid": DEATH_MARK_PULL_CCID,
                    "enabled": True,
                },
            ]
        }

        self.assertTrue(_apply_policy_migrations(data))
        by_ccid = {item["ccid"]: item for item in data["buffs"]}
        self.assertEqual(by_ccid[DEATH_MARK_DAMAGE_CCID]["name"], "死亡锁定增伤")
        self.assertEqual(
            by_ccid[DEATH_MARK_PULL_CCID]["name"],
            "牵引吸怪（非死亡锁定增伤）",
        )
        self.assertFalse(by_ccid[DEATH_MARK_PULL_CCID]["enabled"])


if __name__ == "__main__":
    unittest.main()

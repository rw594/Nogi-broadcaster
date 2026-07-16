from __future__ import annotations

import unittest

from buffwatcher.alerting import (
    AlertEngine,
    AlertRule,
    EventTrigger,
    StatDropEffectSpec,
    StatValueMatch,
)


BOSS_MAX_HP = 3_449_779_200
SAFEHOUSE_MAX_HP = 69_906_070


def stats_event(at_ms: int, entity_id: str, values: dict[int, float]) -> dict:
    return {
        "EventId": 17,
        "At": at_ms,
        "Id": entity_id,
        "Stats": [
            {"StatId": stat_id, "Value": value}
            for stat_id, value in values.items()
        ],
    }


class SafehouseTimerSyncTests(unittest.TestCase):
    @staticmethod
    def _engine() -> AlertEngine:
        safehouse = StatDropEffectSpec(
            name="布四安全屋",
            trigger=EventTrigger(event_id=-1),
            start_stat_matches=(
                StatValueMatch(stat_id=28, value=BOSS_MAX_HP),
                StatValueMatch(stat_id=30, value=BOSS_MAX_HP),
            ),
            start_offset_seconds=70,
            timer_sync_stat_matches=(
                StatValueMatch(stat_id=11, value=3),
                StatValueMatch(stat_id=28, value=SAFEHOUSE_MAX_HP),
                StatValueMatch(stat_id=30, value=SAFEHOUSE_MAX_HP),
            ),
            timer_sync_event_id=17,
            timer_sync_initial_min_delay_seconds=4,
            timer_sync_initial_max_delay_seconds=12,
            timer_sync_min_interval_seconds=61,
            timer_sync_max_interval_seconds=64,
            repeat_timer=True,
            self_filter=False,
            timer_enabled=True,
            duration_seconds=63,
            alerts=[
                AlertRule(
                    remaining_seconds=7,
                    sound="safehouse.wav",
                    message="安全屋",
                )
            ],
            ended_alert=False,
        )
        return AlertEngine([], stat_drop_effect_specs=[safehouse])

    def test_active_safehouse_sync_entity_bypasses_live_self_filter(self) -> None:
        engine = self._engine()
        engine.process_event(
            stats_event(0, "boss", {28: BOSS_MAX_HP, 30: BOSS_MAX_HP})
        )

        sync_event = stats_event(
            8_000,
            "safehouse-1",
            {11: 3, 28: SAFEHOUSE_MAX_HP, 30: SAFEHOUSE_MAX_HP},
        )

        self.assertTrue(engine.is_stat_drop_effect_event(sync_event))
        self.assertTrue(engine.is_unfiltered_stat_drop_effect_event(sync_event))

        engine.process_event(sync_event)
        state = engine.stat_drop_effect_states[0]
        self.assertEqual(state.timer_sync_last_at_ms, 8_000)
        self.assertEqual(state.end_ms, 71_000)
        self.assertFalse(engine.advance_time(63_999))
        alerts = engine.advance_time(64_000)
        self.assertEqual([alert.name for alert in alerts], ["布四安全屋"])

    def test_safehouse_fingerprint_does_not_bypass_filter_outside_battle(self) -> None:
        engine = self._engine()
        sync_event = stats_event(
            8_000,
            "safehouse-1",
            {11: 3, 28: SAFEHOUSE_MAX_HP, 30: SAFEHOUSE_MAX_HP},
        )

        self.assertFalse(engine.is_unfiltered_stat_drop_effect_event(sync_event))


if __name__ == "__main__":
    unittest.main()

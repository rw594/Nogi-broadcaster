from __future__ import annotations

import unittest

from buffwatcher.alerting import AlertEngine
from buffwatcher.astrology_cards import (
    ASTROLOGY_CARD_TRACKER_CONFIG_KEY,
    ASTROLOGY_CORE_COOLDOWN_DEFAULTS,
    ASTROLOGY_SKILLS,
    ASTROLOGY_SUIT_ATTACK,
    ASTROLOGY_SUIT_INTERFERENCE,
    ASTROLOGY_SUIT_LUCK,
    ASTROLOGY_SUIT_SUPPORT,
    AstrologyCardTracker,
    ensure_astrology_card_tracker_config,
    load_astrology_card_tracker_settings,
)


SELF_ID = "4503599639695197"


def configured_data() -> dict:
    return {
        ASTROLOGY_CARD_TRACKER_CONFIG_KEY: {
            "tracked_skills": {"27202": True, "27203": True},
            "counter_threshold": 6,
            "deck": ["命运之轮", "倒吊者", "命运之轮", "月亮", "恶魔"],
            "skill_suits": {
                "27202": ASTROLOGY_SUIT_LUCK,
                "27203": ASTROLOGY_SUIT_ATTACK,
                "27201": ASTROLOGY_SUIT_INTERFERENCE,
                "27200": ASTROLOGY_SUIT_LUCK,
                "27204": ASTROLOGY_SUIT_SUPPORT,
                "27206": ASTROLOGY_SUIT_INTERFERENCE,
                "27205": ASTROLOGY_SUIT_SUPPORT,
                "27210": ASTROLOGY_SUIT_ATTACK,
            },
        }
    }


def e12(at_ms: int, skill_id: int, *, entity_id: str = SELF_ID) -> dict:
    return {
        "EventId": 12,
        "At": at_ms,
        "Id": entity_id,
        "SkillId": skill_id,
    }


def critical_damage(
    at_ms: int,
    skill_id: int,
    *,
    entity_id: str = SELF_ID,
) -> dict:
    return {
        "EventId": 3,
        "At": at_ms,
        "Id": entity_id,
        "SkillId": skill_id,
        "IsCritical": True,
    }


class AstrologyCardConfigTests(unittest.TestCase):
    def test_config_has_five_card_slots_and_all_eight_requested_skill_ids(self) -> None:
        data: dict = {}

        item = ensure_astrology_card_tracker_config(data)

        self.assertEqual(len(item["deck"]), 5)
        self.assertEqual(
            set(item["skill_suits"]),
            {str(int(skill["skill_id"])) for skill in ASTROLOGY_SKILLS.values()},
        )
        self.assertEqual(
            [int(skill["skill_id"]) for skill in ASTROLOGY_SKILLS.values()],
            [27202, 27203, 27201, 27200, 27204, 27206, 27205, 27210],
        )
        self.assertEqual(
            item["tracked_skills"],
            {"27202": False, "27203": False},
        )
        self.assertNotIn("enabled", item)
        self.assertEqual(
            item["base_cooldown_seconds"],
            {"27202": 9, "27203": 12},
        )

    def test_incomplete_config_does_not_guess_card_state(self) -> None:
        data: dict = {}
        ensure_astrology_card_tracker_config(data)
        tracker = AstrologyCardTracker(load_astrology_card_tracker_settings(data))

        self.assertFalse(tracker.configured)
        self.assertIsNone(
            tracker.process_event(e12(1_000, 27202), self_entity_id=SELF_ID)
        )
        self.assertEqual(tracker.counter, 0)
        self.assertIsNone(tracker.held_card)

    def test_deck_ends_at_first_empty_slot_and_may_have_four_cards(self) -> None:
        data = configured_data()
        data[ASTROLOGY_CARD_TRACKER_CONFIG_KEY]["deck"] = [
            "命运之轮",
            "倒吊者",
            "月亮",
            "恶魔",
            "",
        ]

        settings = load_astrology_card_tracker_settings(data)
        tracker = AstrologyCardTracker(settings)

        self.assertTrue(settings.configured)
        self.assertEqual(settings.deck, ("命运之轮", "倒吊者", "月亮", "恶魔"))
        self.assertEqual(
            [tracker._draw_next_card() for _ in range(5)],
            ["命运之轮", "倒吊者", "月亮", "恶魔", "命运之轮"],
        )

    def test_slots_after_first_empty_slot_are_not_part_of_the_deck(self) -> None:
        data = configured_data()
        data[ASTROLOGY_CARD_TRACKER_CONFIG_KEY]["deck"] = [
            "命运之轮",
            "倒吊者",
            "",
            "月亮",
            "恶魔",
        ]

        settings = load_astrology_card_tracker_settings(data)

        self.assertEqual(settings.deck, ("命运之轮", "倒吊者"))

    def test_release_defaults_use_the_requested_core_cooldowns(self) -> None:
        self.assertEqual(ASTROLOGY_CORE_COOLDOWN_DEFAULTS, {27202: 9.0, 27203: 12.0})


class AstrologyCardTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = load_astrology_card_tracker_settings(configured_data())
        self.tracker = AstrologyCardTracker(self.settings)

    def send(self, at_ms: int, skill_id: int):
        return self.tracker.process_event(
            e12(at_ms, skill_id),
            self_entity_id=SELF_ID,
        )

    def test_controlled_hanged_man_sequence_freezes_then_restarts_full_count(self) -> None:
        for index in range(6):
            update = self.send(1_000 + index, 27202)
        self.assertEqual(update.action, "acquired")
        self.assertEqual(self.tracker.held_card, "命运之轮")

        self.assertTrue(self.tracker.skill_can_consume_current_card(27202))
        self.assertFalse(self.tracker.skill_can_consume_current_card(27201))
        update = self.send(2_000, 27202)
        self.assertEqual(update.action, "wheel_pass")
        self.assertEqual(self.tracker.held_card, "倒吊者")

        for at_ms, skill_id in ((3_000, 27202), (3_100, 27203), (3_200, 27204)):
            update = self.send(at_ms, skill_id)
            self.assertEqual(update.action, "held_mismatch")
            self.assertEqual(self.tracker.counter, 0)
            self.assertEqual(self.tracker.held_card, "倒吊者")

        update = self.send(4_000, 27201)
        self.assertEqual(update.action, "consumed")
        self.assertIsNone(self.tracker.held_card)
        self.assertEqual(self.tracker.counter, 0)

        for index, skill_id in enumerate((27202, 27203, 27206, 27204, 27205), 1):
            update = self.send(5_000 + index, skill_id)
            self.assertEqual(update.action, "counted")
            self.assertEqual(self.tracker.counter, index)
            self.assertIsNone(self.tracker.held_card)

        update = self.send(6_000, 27210)
        self.assertEqual(update.action, "acquired")
        self.assertEqual(self.tracker.held_card, "命运之轮")
        self.assertEqual(self.tracker.counter, 0)

    def test_non_self_e12_is_ignored(self) -> None:
        update = self.tracker.process_event(
            e12(1_000, 27202, entity_id="other"),
            self_entity_id=SELF_ID,
        )

        self.assertIsNone(update)
        self.assertEqual(self.tracker.counter, 0)

    def test_core_skill_e12_starts_a_fresh_configured_base_cooldown(self) -> None:
        data = configured_data()
        data[ASTROLOGY_CARD_TRACKER_CONFIG_KEY]["base_cooldown_seconds"] = {
            "27202": 3.5,
            "27203": 6.2,
        }
        tracker = AstrologyCardTracker(load_astrology_card_tracker_settings(data))

        update = tracker.process_event(e12(10_000, 27202), self_entity_id=SELF_ID)

        self.assertEqual(update.cooldown_ready_at_ms, 13_500)
        self.assertEqual(tracker.skill_cooldown_ready_at_ms(27202), 13_500)
        self.assertAlmostEqual(
            tracker.skill_cooldown_remaining_seconds(27202, at_ms=12_000),
            1.5,
        )
        self.assertFalse(tracker.skill_is_ready(27202, at_ms=13_499))
        self.assertTrue(tracker.skill_is_ready(27202, at_ms=13_500))

        update = tracker.process_event(e12(20_000, 27203), self_entity_id=SELF_ID)
        self.assertEqual(update.cooldown_ready_at_ms, 26_200)

    def test_starry_field_critical_reduces_current_cooldown_once(self) -> None:
        data = configured_data()
        data[ASTROLOGY_CARD_TRACKER_CONFIG_KEY]["base_cooldown_seconds"] = {
            "27202": 9,
            "27203": 12,
        }
        tracker = AstrologyCardTracker(load_astrology_card_tracker_settings(data))
        tracker.process_event(e12(10_000, 27202), self_entity_id=SELF_ID)

        update = tracker.process_event(
            critical_damage(10_010, 27202), self_entity_id=SELF_ID
        )

        self.assertEqual(update.action, "critical_reduction")
        self.assertEqual(update.cooldown_ready_at_ms, 17_000)
        self.assertEqual(tracker.skill_cooldown_ready_at_ms(27202), 17_000)
        self.assertIsNone(
            tracker.process_event(
                critical_damage(10_020, 27202), self_entity_id=SELF_ID
            )
        )
        self.assertEqual(tracker.skill_cooldown_ready_at_ms(27202), 17_000)

    def test_whirling_assault_three_hits_reduce_current_cooldown_only_once(self) -> None:
        data = configured_data()
        data[ASTROLOGY_CARD_TRACKER_CONFIG_KEY]["base_cooldown_seconds"] = {
            "27202": 9,
            "27203": 12,
        }
        tracker = AstrologyCardTracker(load_astrology_card_tracker_settings(data))
        tracker.process_event(e12(20_000, 27203), self_entity_id=SELF_ID)

        first = tracker.process_event(
            critical_damage(20_010, 27203), self_entity_id=SELF_ID
        )
        second = tracker.process_event(
            critical_damage(20_020, 27203), self_entity_id=SELF_ID
        )
        third = tracker.process_event(
            critical_damage(20_030, 27203), self_entity_id=SELF_ID
        )

        self.assertEqual(first.action, "critical_reduction")
        self.assertEqual(first.cooldown_ready_at_ms, 30_000)
        self.assertIsNone(second)
        self.assertIsNone(third)
        self.assertEqual(tracker.skill_cooldown_ready_at_ms(27203), 30_000)

    def test_matching_held_card_makes_cooling_skill_available(self) -> None:
        tracker = AstrologyCardTracker(self.settings)
        tracker.process_event(e12(1_000, 27202), self_entity_id=SELF_ID)
        self.assertFalse(tracker.skill_is_available(27202, at_ms=1_001))
        tracker.held_card = "命运之轮"
        self.assertTrue(tracker.skill_is_available(27202, at_ms=1_001))

    def test_disabled_tracker_ignores_events_even_when_fully_configured(self) -> None:
        data = configured_data()
        data[ASTROLOGY_CARD_TRACKER_CONFIG_KEY]["tracked_skills"] = {
            "27202": False,
            "27203": False,
        }
        tracker = AstrologyCardTracker(load_astrology_card_tracker_settings(data))

        self.assertFalse(tracker.configured)
        self.assertIsNone(
            tracker.process_event(e12(1_000, 27202), self_entity_id=SELF_ID)
        )

    def test_alert_engine_resets_card_cycle_when_self_identity_changes(self) -> None:
        engine = AlertEngine([], astrology_card_tracker_settings=self.settings)
        engine.set_self_entity_id(SELF_ID)
        engine.short_cooldown_test_target_entity_ids.add("test-dummy")
        for index in range(6):
            engine.process_event(e12(1_000 + index, 27202))
        self.assertEqual(engine.astrology_card_tracker.held_card, "命运之轮")

        engine.set_self_entity_id("new-self")

        self.assertIsNone(engine.astrology_card_tracker.held_card)
        self.assertEqual(engine.astrology_card_tracker.counter, 0)
        self.assertEqual(engine.astrology_card_tracker.next_card_number, 1)

    def test_alert_engine_tracks_only_inside_supported_encounter_context(self) -> None:
        engine = AlertEngine([], astrology_card_tracker_settings=self.settings)
        engine.set_self_entity_id(SELF_ID)

        engine.process_event(e12(1_000, 27202))
        self.assertEqual(engine.astrology_card_tracker.counter, 0)
        self.assertIsNone(
            engine.astrology_card_tracker.skill_cooldown_ready_at_ms(27202)
        )

        engine.short_cooldown_test_target_entity_ids.add("test-dummy")
        engine.process_event(e12(2_000, 27202))
        self.assertEqual(engine.astrology_card_tracker.counter, 1)
        self.assertEqual(
            engine.astrology_card_tracker.skill_cooldown_ready_at_ms(27202),
            11_000,
        )

        engine.short_cooldown_test_target_entity_ids.clear()
        engine.process_event(e12(3_000, 27202))
        self.assertEqual(engine.astrology_card_tracker.counter, 0)
        self.assertIsNone(
            engine.astrology_card_tracker.skill_cooldown_ready_at_ms(27202)
        )


if __name__ == "__main__":
    unittest.main()

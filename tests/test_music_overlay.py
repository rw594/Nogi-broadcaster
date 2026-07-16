from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from buffwatcher.alerting import (
    BRONNTANAS_MAX_HP,
    BossHpAlertSpec,
    BossHpAlertState,
    BuffSpec,
    BuffState,
    KeyEnemyDebuffAlertSpec,
    KeyEnemyDebuffEntityState,
    load_all_specs,
)
from buffwatcher.music_overlay import (
    ASTROLOGY_CELL_SIZE,
    AstrologyOverlayItem,
    BRONNTANAS_HP_WARNING_COLOR,
    BronntanasHpOverlayItem,
    CARD_BACKGROUND,
    DebuffOverlayRequirement,
    MusicOverlayApp,
    OtherSkillOverlayItem,
    OverlayCondition,
    PRIMARY_TEXT,
    PROGRESS_FILL_COLOR,
    PROGRESS_TRACK_COLOR,
    TOAST_CONTENT_HEIGHT,
    TOAST_ICON_GAP,
    TOAST_ICON_SIZE,
    decode_ipc_command,
    format_remaining_countdown,
)
from buffwatcher.overlay_bridge import (
    AstrologyOverlaySettings,
    BronntanasHpOverlaySession,
    BronntanasHpOverlaySettings,
    DEFAULT_DEBUFF_OVERLAY_ITEMS,
    DEFAULT_OTHER_SKILL_OVERLAY_ITEMS,
    MusicOverlaySettings,
    OtherSkillOverlaySettings,
    ShortCooldownOverlaySettings,
    command_for_astrology_tracker,
    command_for_bronntanas_hp_state,
    command_for_key_enemy_debuff_states,
    command_for_music_state,
    command_for_other_skill_states,
    command_for_short_cooldown_states,
    load_music_overlay_settings,
    music_overlay_is_safely_covered_by_tuan,
    next_life_temperature_missing_latch,
)
from buffwatcher.astrology_cards import (
    ASTROLOGY_CARD_TRACKER_CONFIG_KEY,
    ASTROLOGY_SUIT_ATTACK,
    AstrologyCardTracker,
    load_astrology_card_tracker_settings,
)
from buffwatcher.hamster_buffs import HAMSTER_SUPERCHARGED_CCID


class MusicOverlayTests(unittest.TestCase):
    def test_bronntanas_hp_hud_tracks_hp_even_when_voice_row_is_disabled(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "boss_hp_alerts": [
                            {
                                "name": "布本2王",
                                "enabled": False,
                                "max_hp_values": [BRONNTANAS_MAX_HP],
                                "alerts": [
                                    {"threshold_percent": 50, "sound": "unused.wav"}
                                ],
                            }
                        ],
                        "experimental_bronntanas_hp_visual_overlay": {
                            "enabled": True
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            loaded = load_all_specs(config)

        matching = [
            spec
            for spec in loaded.boss_hp_alerts
            if BRONNTANAS_MAX_HP in {int(round(value)) for value in spec.max_hp_values}
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].alerts, [])

    def test_settings_are_opt_in_and_load_visual_hud_options(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "experimental_music_visual_overlay": {
                            "enabled": True,
                            "show_before_seconds": 5,
                            "condition_controls_version": 1,
                            "conditions": {
                                "192": {
                                    "enabled": True,
                                    "icon": "assets/custom/visual_hud/music.png",
                                    "show_before_seconds": 8,
                                    "ring_sound_enabled": True,
                                },
                                "193": {"enabled": False},
                                "680": {"enabled": True},
                                "874": {"enabled": True},
                            },
                            "ring_sound_enabled": False,
                            "tuan_silence_enabled": False,
                        },
                        "experimental_other_skill_visual_overlay": {
                            "enabled": True,
                            "conditions": {
                                "magic_circle": {"enabled": True},
                                "life_temperature": {"enabled": False},
                            },
                        },
                        "experimental_short_cooldown_visual_overlay": {
                            "enabled": True,
                            "conditions": {
                                "ignis_plume": {
                                    "enabled": True,
                                    "icon": "assets/custom/ignis.png",
                                }
                            },
                        },
                        "combat_astrology_card_tracker": {
                            "tracked_skills": {"27202": True, "27203": False}
                        },
                        "experimental_bronntanas_hp_visual_overlay": {
                            "enabled": True,
                            "icon": "assets/custom/bronntanas.png",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            settings = load_music_overlay_settings(config)

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.show_before_seconds, 5.0)
        self.assertTrue(settings.condition_is_enabled(192))
        self.assertFalse(settings.condition_is_enabled(193))
        self.assertTrue(settings.condition_is_enabled(680))
        self.assertFalse(settings.condition_is_enabled(874))
        self.assertEqual(settings.width, 300)
        self.assertEqual(settings.refresh_ms, 30)
        self.assertFalse(settings.ring_sound_enabled)
        self.assertFalse(settings.muted)
        self.assertFalse(settings.tuan_silence_enabled)
        self.assertEqual(settings.show_before_seconds_for(192), 8.0)
        self.assertTrue(settings.ring_sound_is_enabled(192))
        self.assertEqual(settings.show_before_seconds_for(680), 5.0)
        self.assertFalse(settings.ring_sound_is_enabled(680))
        self.assertEqual(
            settings.icon_path(192), "assets/custom/visual_hud/music.png"
        )
        self.assertTrue(settings.other_skill_hud.enabled)
        self.assertTrue(
            settings.other_skill_hud.condition_is_enabled("magic_circle")
        )
        self.assertFalse(
            settings.other_skill_hud.condition_is_enabled("life_temperature")
        )
        self.assertTrue(settings.short_cooldown_hud.enabled)
        self.assertTrue(
            settings.short_cooldown_hud.condition_is_enabled("ignis_plume")
        )
        self.assertEqual(
            settings.short_cooldown_hud.icon_path("ignis_plume"),
            "assets/custom/ignis.png",
        )
        self.assertEqual(settings.astrology_hud.enabled_skill_ids, {27202})
        self.assertTrue(settings.bronntanas_hp_hud.enabled)
        self.assertEqual(
            settings.bronntanas_hp_hud.icon_path,
            "assets/custom/bronntanas.png",
        )
        self.assertTrue(settings.process_is_enabled())

    def test_bronntanas_hp_hud_starts_at_52_and_finishes_two_seconds_after_50(
        self,
    ) -> None:
        settings = BronntanasHpOverlaySettings(enabled=True)
        session = BronntanasHpOverlaySession()
        state = BossHpAlertState(
            spec=BossHpAlertSpec(name="布隆塔纳斯"),
            tracked_entity_id="boss-1",
            active=True,
            last_seen_at_ms=1_000,
            last_current_hp=53,
            last_max_hp=100,
        )

        self.assertEqual(
            command_for_bronntanas_hp_state(
                settings, state, session, now_ms=1_000
            ),
            {"type": "bronntanas_hp_clear"},
        )
        state.last_current_hp = 52
        command = command_for_bronntanas_hp_state(
            settings, state, session, now_ms=1_100
        )
        self.assertEqual(command["type"], "bronntanas_hp_snapshot")
        self.assertEqual(command["percent"], 52.0)
        self.assertFalse(command["warning"])

        state.last_current_hp = 50
        state.last_seen_at_ms = 2_000
        command = command_for_bronntanas_hp_state(
            settings, state, session, now_ms=2_000
        )
        self.assertTrue(command["warning"])
        self.assertEqual(command["dismiss_at_ms"], 4_000)
        self.assertEqual(
            command_for_bronntanas_hp_state(
                settings, state, session, now_ms=3_999
            )["type"],
            "bronntanas_hp_snapshot",
        )
        self.assertEqual(
            command_for_bronntanas_hp_state(
                settings, state, session, now_ms=4_000
            ),
            {"type": "bronntanas_hp_clear"},
        )
        self.assertTrue(session.completed)
        state.active = False
        self.assertEqual(
            command_for_bronntanas_hp_state(
                settings, state, session, now_ms=4_100
            ),
            {"type": "bronntanas_hp_clear"},
        )
        state.active = True
        state.last_current_hp = -0.04
        state.last_seen_at_ms = 4_200
        self.assertEqual(
            command_for_bronntanas_hp_state(
                settings, state, session, now_ms=4_200
            ),
            {"type": "bronntanas_hp_clear"},
        )
        state.tracked_entity_id = "boss-2"
        state.last_current_hp = 51
        state.last_seen_at_ms = 5_000
        command = command_for_bronntanas_hp_state(
            settings, state, session, now_ms=5_000
        )
        self.assertEqual(command["type"], "bronntanas_hp_snapshot")
        self.assertFalse(command["warning"])

    def test_bronntanas_hp_hud_warns_when_display_rounds_to_50_percent(
        self,
    ) -> None:
        settings = BronntanasHpOverlaySettings(enabled=True)
        session = BronntanasHpOverlaySession()
        state = BossHpAlertState(
            spec=BossHpAlertSpec(name="布隆塔纳斯"),
            tracked_entity_id="boss-1",
            active=True,
            last_seen_at_ms=1_000,
            last_current_hp=50.004,
            last_max_hp=100,
        )

        command = command_for_bronntanas_hp_state(
            settings, state, session, now_ms=1_000
        )
        self.assertEqual(command["type"], "bronntanas_hp_snapshot")
        self.assertEqual(f'{command["percent"]:.2f}', "50.00")
        self.assertTrue(command["warning"])

    def test_bronntanas_hp_hud_draws_two_decimals_and_red_warning(self) -> None:
        class RecordingCanvas:
            def __init__(self) -> None:
                self.rectangles: list[tuple[tuple, dict]] = []
                self.texts: list[tuple[tuple, dict]] = []

            def delete(self, *_args) -> None:
                return None

            def create_rectangle(self, *args, **kwargs) -> None:
                self.rectangles.append((args, kwargs))

            def create_text(self, *args, **kwargs) -> None:
                self.texts.append((args, kwargs))

            def create_image(self, *_args, **_kwargs) -> None:
                return None

        app = MusicOverlayApp.__new__(MusicOverlayApp)
        app.canvas = RecordingCanvas()
        app.settings = MusicOverlaySettings(
            bronntanas_hp_hud=BronntanasHpOverlaySettings(enabled=True)
        )
        app.last_bounds = (0, 0, 2048, 1152)
        app._load_icon = lambda *_args, **_kwargs: None
        normal = BronntanasHpOverlayItem(
            "boss-1", 50.08, False, None, "bronntanas.png"
        )

        app._draw([], [], 1_000, bronntanas_hp_item=normal)

        number = next(
            kwargs for _args, kwargs in app.canvas.texts
            if kwargs.get("text") == "50.08%"
        )
        self.assertEqual(number["fill"], "#ffffff")

        app.canvas.texts.clear()
        warning = BronntanasHpOverlayItem(
            "boss-1", 50.0, True, 3_000, "bronntanas.png"
        )
        app._draw([], [], 1_000, bronntanas_hp_item=warning)
        number = next(
            kwargs for _args, kwargs in app.canvas.texts
            if kwargs.get("text") == "50.00%"
        )
        self.assertEqual(number["fill"], BRONNTANAS_HP_WARNING_COLOR)
        self.assertFalse(
            any(kwargs.get("text") == "⚠️" for _args, kwargs in app.canvas.texts)
        )

    def test_astrology_snapshot_keeps_symmetric_slots_and_cooldown_deadlines(self) -> None:
        data = {
            ASTROLOGY_CARD_TRACKER_CONFIG_KEY: {
                "tracked_skills": {"27202": True, "27203": True},
                "counter_threshold": 6,
                "deck": ["力量", "皇帝", "女皇", "正义", "审判"],
                "skill_suits": {
                    str(skill_id): ASTROLOGY_SUIT_ATTACK
                    for skill_id in (27202, 27203, 27201, 27200, 27204, 27206, 27205, 27210)
                },
                "base_cooldown_seconds": {"27202": 3.5, "27203": 6.2},
            }
        }
        tracker = AstrologyCardTracker(load_astrology_card_tracker_settings(data))
        tracker.process_event(
            {"EventId": 12, "At": 10_000, "Id": "self", "SkillId": 27202},
            self_entity_id="self",
        )

        command = command_for_astrology_tracker(
            AstrologyOverlaySettings(enabled_skill_ids=frozenset({27202, 27203})),
            tracker,
            self_identity_confirmed=True,
            tracking_context_active=True,
        )

        self.assertEqual(command["type"], "astrology_snapshot")
        self.assertEqual(
            [(item["skill_id"], item["slot"]) for item in command["items"]],
            [(27202, -1), (27203, 1)],
        )
        self.assertEqual(command["items"][0]["cooldown_ready_at_ms"], 13_500)
        self.assertIsNone(command["items"][1]["cooldown_ready_at_ms"])

        command = command_for_astrology_tracker(
            AstrologyOverlaySettings(enabled_skill_ids=frozenset({27203})),
            tracker,
            self_identity_confirmed=True,
            tracking_context_active=True,
        )
        self.assertEqual(command["items"][0]["slot"], 0)

    def test_astrology_hud_stays_clear_until_identity_and_context_are_ready(self) -> None:
        data = {
            ASTROLOGY_CARD_TRACKER_CONFIG_KEY: {
                "tracked_skills": {"27202": True, "27203": False},
                "counter_threshold": 6,
                "deck": ["力量"],
                "skill_suits": {
                    str(skill_id): ASTROLOGY_SUIT_ATTACK
                    for skill_id in (27202, 27203, 27201, 27200, 27204, 27206, 27205, 27210)
                },
                "base_cooldown_seconds": {"27202": 3.5, "27203": 6.2},
            }
        }
        tracker = AstrologyCardTracker(load_astrology_card_tracker_settings(data))
        settings = AstrologyOverlaySettings(enabled_skill_ids=frozenset({27202}))

        self.assertEqual(
            command_for_astrology_tracker(
                settings,
                tracker,
                self_identity_confirmed=False,
                tracking_context_active=True,
            ),
            {"type": "astrology_clear"},
        )
        self.assertEqual(
            command_for_astrology_tracker(
                settings,
                tracker,
                self_identity_confirmed=True,
                tracking_context_active=False,
            ),
            {"type": "astrology_clear"},
        )

    def test_new_card_bypass_cast_replaces_the_superseded_cooldown_deadline(self) -> None:
        data = {
            ASTROLOGY_CARD_TRACKER_CONFIG_KEY: {
                "tracked_skills": {"27202": True, "27203": False},
                "counter_threshold": 6,
                "deck": ["力量"],
                "skill_suits": {
                    str(skill_id): ASTROLOGY_SUIT_ATTACK
                    for skill_id in (27202, 27203, 27201, 27200, 27204, 27206, 27205, 27210)
                },
                "base_cooldown_seconds": {"27202": 3.5, "27203": 6.2},
            }
        }
        tracker = AstrologyCardTracker(load_astrology_card_tracker_settings(data))
        for index in range(5):
            tracker.process_event(
                {
                    "EventId": 12,
                    "At": 20_000 + index,
                    "Id": "self",
                    "SkillId": 27201,
                },
                self_entity_id="self",
            )
        settings = AstrologyOverlaySettings(enabled_skill_ids=frozenset({27202}))

        tracker.process_event(
            {"EventId": 12, "At": 22_126, "Id": "self", "SkillId": 27202},
            self_entity_id="self",
        )
        old_command = command_for_astrology_tracker(
            settings,
            tracker,
            self_identity_confirmed=True,
            tracking_context_active=True,
        )
        tracker.process_event(
            {"EventId": 12, "At": 23_742, "Id": "self", "SkillId": 27202},
            self_entity_id="self",
        )
        new_command = command_for_astrology_tracker(
            settings,
            tracker,
            self_identity_confirmed=True,
            tracking_context_active=True,
        )

        app = MusicOverlayApp.__new__(MusicOverlayApp)
        app.astrology_items = ()
        app._upsert_astrology_snapshot(old_command)
        app._upsert_astrology_snapshot(new_command)
        self.assertEqual(app.astrology_items[0].cooldown_ready_at_ms, 27_242)
        self.assertFalse(app.astrology_items[0].card_ready)
        self.assertEqual(app._visible_astrology_items(25_626), ())
        self.assertEqual(len(app._visible_astrology_items(27_242)), 1)

    def test_active_music_state_becomes_a_scheduled_toast(self) -> None:
        state = BuffState(
            spec=BuffSpec(name="活跃曲", ccid=192),
            active=True,
            end_ms=123_456,
            last_timing_source="music_login_server_clock",
        )
        command = command_for_music_state(
            state,
            MusicOverlaySettings(
                enabled=True,
                condition_icons={192: "assets/custom/visual_hud/music.png"},
                condition_show_before_seconds={192: 7.5},
                condition_ring_sound_enabled={192: False},
            ),
        )

        self.assertEqual(command["type"], "upsert")
        self.assertEqual(command["ccid"], 192)
        self.assertEqual(command["end_ms"], 123_456)
        self.assertEqual(command["show_before_ms"], 7_500)
        self.assertFalse(command["ring_sound_enabled"])
        self.assertEqual(command["timing_source"], "music_login_server_clock")
        self.assertEqual(
            command["icon_path"], "assets/custom/visual_hud/music.png"
        )

    def test_disabled_or_inactive_condition_is_removed(self) -> None:
        disabled = MusicOverlaySettings(
            enabled=True,
            condition_enabled={192: False, 193: False, 680: True},
        )
        state = BuffState(
            spec=BuffSpec(name="活跃曲", ccid=192),
            active=True,
            end_ms=123_456,
        )
        self.assertEqual(command_for_music_state(state, disabled)["type"], "remove")
        state.active = False
        self.assertEqual(
            command_for_music_state(state, MusicOverlaySettings(enabled=True))["type"],
            "remove",
        )

    def test_life_temperature_is_not_a_music_countdown_condition(self) -> None:
        settings = MusicOverlaySettings(enabled=True)

        self.assertFalse(settings.condition_is_enabled(874))
        self.assertEqual(
            [item[0] for item in DEFAULT_OTHER_SKILL_OVERLAY_ITEMS][-1],
            "life_temperature",
        )

    def test_other_skill_snapshot_requires_key_boss_and_tracks_ready_states(self) -> None:
        boss_spec = KeyEnemyDebuffAlertSpec()
        boss = KeyEnemyDebuffEntityState(
            spec=boss_spec,
            tracked_entity_id="boss-1",
            active=True,
        )
        magic = BuffState(
            spec=BuffSpec(
                name="魔法阵",
                ccid=10133,
                cooldown_delay_seconds=140,
                cooldown_from_skill_use=True,
            ),
            cooldown_anchor_at_ms=1_000,
        )
        pall = BuffState(
            spec=BuffSpec(
                name="崩坏波动",
                ccid=803,
                cooldown_delay_seconds=180,
                cooldown_from_skill_use=True,
            ),
            cooldown_anchor_at_ms=100_000,
        )
        manus = BuffState(
            spec=BuffSpec(name="马纽斯秘药", ccid=835),
            active=False,
            last_event_at_ms=50_000,
        )
        purification = BuffState(
            spec=BuffSpec(name="净化之浪", ccid=645),
            active=True,
            last_event_at_ms=50_000,
        )
        hamster_supercharged = BuffState(
            spec=BuffSpec(name="超燃咚咚", ccid=HAMSTER_SUPERCHARGED_CCID),
            active=False,
            last_event_at_ms=60_000,
        )
        settings = OtherSkillOverlaySettings(
            enabled=True,
            condition_enabled={
                key: True
                for key, _name, _icon, _enabled in DEFAULT_OTHER_SKILL_OVERLAY_ITEMS
            },
        )
        states = {
            10133: magic,
            803: pall,
            835: manus,
            645: purification,
            HAMSTER_SUPERCHARGED_CCID: hamster_supercharged,
        }

        command = command_for_other_skill_states(
            settings,
            states,
            {"boss-1": boss},
            now_ms=141_000,
            life_temperature_missing=True,
        )

        self.assertEqual(command["type"], "other_skill_snapshot")
        self.assertEqual(
            [item["key"] for item in command["items"]],
            [
                "magic_circle",
                "manus_potion",
                "hamster_supercharged",
                "life_temperature",
            ],
        )
        hamster_supercharged.active = True
        active_command = command_for_other_skill_states(
            settings,
            states,
            {"boss-1": boss},
            now_ms=141_000,
            life_temperature_missing=True,
        )
        self.assertNotIn(
            "hamster_supercharged",
            [item["key"] for item in active_command["items"]],
        )
        boss.active = False
        self.assertEqual(
            command_for_other_skill_states(
                settings,
                states,
                {"boss-1": boss},
                now_ms=141_000,
                life_temperature_missing=True,
            )["type"],
            "other_skill_clear",
        )

    def test_life_temperature_missing_latches_until_five_stacks(self) -> None:
        state = BuffState(
            spec=BuffSpec(name="生命的温度", ccid=874),
            active=True,
            stacks=3,
            last_event_at_ms=1_000,
        )
        self.assertFalse(next_life_temperature_missing_latch(False, state))
        state.active = False
        self.assertTrue(next_life_temperature_missing_latch(False, state))
        state.active = True
        state.stacks = 4
        self.assertTrue(next_life_temperature_missing_latch(True, state))
        state.stacks = 5
        self.assertFalse(next_life_temperature_missing_latch(True, state))

    def test_short_cooldown_snapshot_uses_each_skill_custom_cooldown(self) -> None:
        boss = KeyEnemyDebuffEntityState(
            spec=KeyEnemyDebuffAlertSpec(),
            tracked_entity_id="boss-1",
            active=True,
        )
        ignis = BuffState(
            spec=BuffSpec(
                name="爆炎箭",
                ccid=-59060,
                cooldown_delay_seconds=6,
                cooldown_from_skill_use=True,
            ),
            cooldown_anchor_at_ms=1_000,
        )
        aqua = BuffState(
            spec=BuffSpec(
                name="水流箭",
                ccid=-59061,
                cooldown_delay_seconds=10,
                cooldown_from_skill_use=True,
            ),
            cooldown_anchor_at_ms=1_000,
        )
        settings = ShortCooldownOverlaySettings(enabled=True)

        self.assertEqual(
            command_for_short_cooldown_states(
                settings,
                {-59060: ignis, -59061: aqua},
                {"boss-1": boss},
                now_ms=6_999,
            )["type"],
            "short_cooldown_clear",
        )
        command = command_for_short_cooldown_states(
            settings,
            {-59060: ignis, -59061: aqua},
            {"boss-1": boss},
            now_ms=7_000,
        )
        self.assertEqual(command["type"], "short_cooldown_snapshot")
        self.assertEqual([item["name"] for item in command["items"]], ["爆炎箭"])

        command = command_for_short_cooldown_states(
            settings,
            {-59060: ignis, -59061: aqua},
            {"boss-1": boss},
            now_ms=11_000,
        )
        self.assertEqual(
            [item["name"] for item in command["items"]], ["爆炎箭", "水流箭"]
        )

        command = command_for_short_cooldown_states(
            settings,
            {-59060: ignis, -59061: aqua},
            None,
            now_ms=11_000,
            test_target_active=True,
        )
        self.assertEqual(command["type"], "short_cooldown_snapshot")
        self.assertEqual(
            [item["name"] for item in command["items"]], ["爆炎箭", "水流箭"]
        )

        ignis.cooldown_anchor_at_ms = 8_000
        self.assertEqual(
            command_for_short_cooldown_states(
                settings,
                {-59060: ignis, -59061: aqua},
                {"boss-1": boss},
                now_ms=8_000,
            )["type"],
            "short_cooldown_clear",
        )
        boss.active = False
        self.assertEqual(
            command_for_short_cooldown_states(
                settings,
                {-59060: ignis, -59061: aqua},
                {"boss-1": boss},
                now_ms=20_000,
            )["type"],
            "short_cooldown_clear",
        )

    def test_short_cooldown_icon_is_centered_in_its_own_screen_row(self) -> None:
        class RecordingCanvas:
            def __init__(self) -> None:
                self.rectangles: list[tuple[tuple, dict]] = []

            def delete(self, *_args) -> None:
                return None

            def create_rectangle(self, *args, **kwargs) -> None:
                self.rectangles.append((args, kwargs))

            def create_text(self, *_args, **_kwargs) -> None:
                return None

            def create_image(self, *_args, **_kwargs) -> None:
                return None

        app = MusicOverlayApp.__new__(MusicOverlayApp)
        app.canvas = RecordingCanvas()
        app.settings = MusicOverlaySettings(
            short_cooldown_hud=ShortCooldownOverlaySettings(enabled=True)
        )
        app.last_bounds = (0, 0, 1920, 1080)
        app._load_icon = lambda _path: None
        items = (OtherSkillOverlayItem("ignis_plume", "爆炎箭", "ignis.png"),)

        app._draw([], [], 1_000, (), items)

        self.assertEqual(len(app.canvas.rectangles), 1)
        cell = app.canvas.rectangles[0][0]
        self.assertEqual(cell[0], (1920 - 48) // 2)
        self.assertEqual(cell[1], round(1080 * 0.715) - 48 // 2)
        self.assertEqual(cell[2] - cell[0], 48)
        self.assertEqual(cell[3] - cell[1], 48)

    def test_other_skill_icons_draw_as_a_left_aligned_vertical_column(self) -> None:
        class RecordingCanvas:
            def __init__(self) -> None:
                self.rectangles: list[tuple[tuple, dict]] = []

            def delete(self, *_args) -> None:
                return None

            def create_rectangle(self, *args, **kwargs) -> None:
                self.rectangles.append((args, kwargs))

            def create_text(self, *_args, **_kwargs) -> None:
                return None

            def create_image(self, *_args, **_kwargs) -> None:
                return None

        app = MusicOverlayApp.__new__(MusicOverlayApp)
        app.canvas = RecordingCanvas()
        app.settings = MusicOverlaySettings(
            other_skill_hud=OtherSkillOverlaySettings(
                enabled=True,
                left_offset_px=8,
                center_y_ratio=0.28,
                gap_px=6,
            )
        )
        app.last_bounds = (0, 0, 1920, 1080)
        app._load_icon = lambda _path: None
        items = (
            OtherSkillOverlayItem("magic_circle", "魔法阵", "magic.png"),
            OtherSkillOverlayItem("manus_potion", "马纽斯秘药", "manus.png"),
        )

        app._draw([], [], 1_000, items)

        cells = [args for args, _kwargs in app.canvas.rectangles]
        self.assertEqual(len(cells), 2)
        self.assertTrue(all(cell[0] == 8 for cell in cells))
        self.assertEqual(cells[1][1] - cells[0][1], 54)

    def test_astrology_icons_use_large_symmetric_slots_or_single_center(self) -> None:
        class RecordingCanvas:
            def __init__(self) -> None:
                self.rectangles: list[tuple[tuple, dict]] = []

            def delete(self, *_args) -> None:
                return None

            def create_rectangle(self, *args, **kwargs) -> None:
                self.rectangles.append((args, kwargs))

            def create_text(self, *_args, **_kwargs) -> None:
                return None

            def create_image(self, *_args, **_kwargs) -> None:
                return None

        app = MusicOverlayApp.__new__(MusicOverlayApp)
        app.canvas = RecordingCanvas()
        app.settings = MusicOverlaySettings(
            astrology_hud=AstrologyOverlaySettings(
                enabled_skill_ids=frozenset({27202, 27203})
            )
        )
        app.last_bounds = (0, 0, 2048, 1152)
        app._load_icon = lambda *_args, **_kwargs: None
        left = AstrologyOverlayItem(
            "starry_field", "星辉领域", 27202, "starry.png", -1, None, False
        )
        right = AstrologyOverlayItem(
            "whirling_assault", "疾旋突袭", 27203, "whirl.png", 1, None, False
        )

        app._draw([], [], 1_000, (), (), (left, right))

        cells = [args for args, _kwargs in app.canvas.rectangles]
        self.assertEqual(len(cells), 2)
        self.assertEqual(cells[0][2] - cells[0][0], ASTROLOGY_CELL_SIZE)
        self.assertEqual(
            (cells[0][0] + cells[0][2]) // 2,
            2048 // 2 - 136,
        )
        self.assertEqual(
            (cells[1][0] + cells[1][2]) // 2,
            2048 // 2 + 136,
        )

        app.canvas.rectangles.clear()
        centered = AstrologyOverlayItem(
            "starry_field", "星辉领域", 27202, "starry.png", 0, None, False
        )
        app._draw([], [], 1_000, (), (), (centered,))
        cell = app.canvas.rectangles[0][0]
        self.assertEqual((cell[0] + cell[2]) // 2, 2048 // 2)

    def test_new_hud_defaults_enable_march_and_use_icon_height_progress(self) -> None:
        settings = MusicOverlaySettings(enabled=True)

        self.assertTrue(settings.condition_is_enabled(193))
        self.assertEqual(TOAST_CONTENT_HEIGHT, TOAST_ICON_SIZE)
        self.assertNotEqual(PROGRESS_FILL_COLOR, PRIMARY_TEXT)

    def test_toast_draws_no_outer_card_and_places_progress_beside_icon(self) -> None:
        class RecordingCanvas:
            def __init__(self) -> None:
                self.rectangles: list[tuple[tuple, dict]] = []

            def delete(self, *_args) -> None:
                return None

            def create_rectangle(self, *args, **kwargs) -> None:
                self.rectangles.append((args, kwargs))

            def create_text(self, *_args, **_kwargs) -> None:
                return None

            def create_image(self, *_args, **_kwargs) -> None:
                return None

        app = MusicOverlayApp.__new__(MusicOverlayApp)
        app.canvas = RecordingCanvas()
        app.settings = MusicOverlaySettings(
            enabled=True,
            width=300,
            toast_height=72,
            top_offset_px=72,
        )
        app.last_bounds = (0, 0, 1920, 1080)
        app._load_icon = lambda _path: None
        condition = OverlayCondition(
            ccid=874,
            name="生命的温度",
            entity_name="自己",
            end_ms=10_000,
            show_before_ms=10_000,
            visible_since_ms=5_000,
            toast_lifetime_ms=10_000,
        )

        app._draw([condition], [], 5_000)

        self.assertFalse(
            any(
                kwargs.get("fill") == CARD_BACKGROUND
                for _args, kwargs in app.canvas.rectangles
            )
        )
        icon = app.canvas.rectangles[0][0]
        track = next(
            args
            for args, kwargs in app.canvas.rectangles
            if kwargs.get("fill") == PROGRESS_TRACK_COLOR
        )
        self.assertEqual(icon[2] - icon[0], TOAST_ICON_SIZE)
        self.assertEqual(icon[3] - icon[1], TOAST_CONTENT_HEIGHT)
        self.assertEqual(track[3] - track[1], TOAST_CONTENT_HEIGHT)
        self.assertEqual(track[0], icon[2] + TOAST_ICON_GAP)
        self.assertEqual(track[2], (1920 + 300) // 2)

    def test_tuan_cover_removes_only_unextended_music_hud(self) -> None:
        music = BuffState(
            spec=BuffSpec(name="活跃曲", ccid=192),
            active=True,
            end_ms=10_000,
        )
        tuan = BuffState(
            spec=BuffSpec(name="徒安之歌", ccid=1124),
            active=True,
            end_ms=10_001,
        )
        states = {192: music, 1124: tuan}

        self.assertTrue(
            music_overlay_is_safely_covered_by_tuan(
                music, states, now_ms=5_000
            )
        )
        music.music_toan_extended = True
        self.assertFalse(
            music_overlay_is_safely_covered_by_tuan(
                music, states, now_ms=5_000
            )
        )
        music.music_toan_extended = False
        tuan.end_ms = music.end_ms
        self.assertFalse(
            music_overlay_is_safely_covered_by_tuan(
                music, states, now_ms=5_000
            )
        )

    def test_key_enemy_snapshot_contains_all_nine_requirements_in_display_order(self) -> None:
        spec = KeyEnemyDebuffAlertSpec(
            visual_hud_enabled=True,
            visual_expiry_enabled=True,
            expiry_seconds=30,
        )
        state = KeyEnemyDebuffEntityState(
            spec=spec,
            tracked_entity_id="boss-1",
            active=True,
            last_seen_at_ms=100,
        )
        state.requirements["bernak_magic"].active = True
        state.requirements["bernak_magic"].end_ms = 40_000
        state.expiry_requirements["bernak_magic"].active = True
        state.expiry_requirements["bernak_magic"].end_ms = 40_000

        command = command_for_key_enemy_debuff_states(spec, {"boss-1": state})

        self.assertEqual(command["type"], "debuff_snapshot")
        self.assertEqual(command["entity_id"], "boss-1")
        self.assertEqual(command["expiry_threshold_ms"], 30_000)
        self.assertEqual(len(command["requirements"]), 9)
        self.assertEqual(
            [item["key"] for item in command["requirements"]],
            [item[0] for item in DEFAULT_DEBUFF_OVERLAY_ITEMS],
        )
        self.assertTrue(command["requirements"][0]["complete"])
        self.assertFalse(command["requirements"][1]["complete"])

    def test_debuff_requirement_is_solid_when_missing_and_flashes_near_expiry(self) -> None:
        missing = DebuffOverlayRequirement(
            key="rabbit",
            name="兔子增伤",
            icon_path="rabbit.png",
            complete=False,
            complete_end_ms=None,
            expiry_active=False,
            expiry_end_ms=None,
        )
        expiring = DebuffOverlayRequirement(
            key="rabbit",
            name="兔子增伤",
            icon_path="rabbit.png",
            complete=True,
            complete_end_ms=20_000,
            expiry_active=True,
            expiry_end_ms=20_000,
        )

        self.assertEqual(
            missing.visual_status(
                10_000,
                visual_expiry_enabled=True,
                expiry_threshold_ms=5_000,
            ),
            "missing",
        )
        self.assertIsNone(
            expiring.visual_status(
                14_999,
                visual_expiry_enabled=True,
                expiry_threshold_ms=5_000,
            )
        )
        self.assertEqual(
            expiring.visual_status(
                15_000,
                visual_expiry_enabled=True,
                expiry_threshold_ms=5_000,
            ),
            "expiring",
        )
        self.assertIsNone(
            expiring.visual_status(
                15_000,
                visual_expiry_enabled=False,
                expiry_threshold_ms=5_000,
            )
        )
        self.assertEqual(
            expiring.visual_status(
                20_000,
                visual_expiry_enabled=True,
                expiry_threshold_ms=5_000,
            ),
            "missing",
        )
    def test_toast_appears_only_during_its_configured_window(self) -> None:
        condition = OverlayCondition(
            ccid=192,
            name="活跃曲",
            entity_name="自己",
            end_ms=10_000,
            show_before_ms=5_000,
        )
        self.assertFalse(condition.should_show(4_999))
        self.assertTrue(condition.should_show(5_000))
        condition.mark_visible(5_000)
        self.assertAlmostEqual(condition.progress(7_500), 0.5)
        self.assertFalse(condition.should_show(10_000))

    def test_remaining_display_uses_tenths_only_in_final_two_seconds(self) -> None:
        self.assertEqual(format_remaining_countdown(14_999), "15")
        self.assertEqual(format_remaining_countdown(2_001), "3")
        self.assertEqual(format_remaining_countdown(2_000), "2.0")
        self.assertEqual(format_remaining_countdown(1_999), "1.9")
        self.assertEqual(format_remaining_countdown(101), "0.1")
        self.assertEqual(format_remaining_countdown(-1), "0.0")

    def test_utf8_ipc_preserves_chinese_condition_and_entity_names(self) -> None:
        payload = json.dumps(
            {
                "type": "upsert",
                "ccid": 874,
                "name": "生命的温度",
                "entity_name": "自己",
            },
            ensure_ascii=False,
        ).encode("utf-8")

        command = decode_ipc_command(payload)

        self.assertIsNotNone(command)
        self.assertEqual(command["name"], "生命的温度")
        self.assertEqual(command["entity_name"], "自己")


if __name__ == "__main__":
    unittest.main()

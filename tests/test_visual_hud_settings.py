from __future__ import annotations

import unittest
from pathlib import Path

from buffwatcher.overlay_bridge import (
    DEFAULT_DEBUFF_OVERLAY_ITEMS,
    DEFAULT_OTHER_SKILL_OVERLAY_ITEMS,
    DEFAULT_OVERLAY_ICONS,
    DEFAULT_SHORT_COOLDOWN_OVERLAY_ITEMS,
)
from buffwatcher.settings_gui import (
    AstrologyCardTrackerRow,
    BRONNTANAS_HP_HUD_CONFIG_KEY,
    BRONNTANAS_HP_HUD_DEFAULT_ICON,
    MIRACLE_ORB_HP_HUD_CONFIG_KEY,
    ROTATING_LASER_COUNTDOWN_HUD_CONFIG_KEY,
    OTHER_SKILL_HUD_CONDITION_DEFAULTS,
    SETTINGS_TAB_ASTROLOGY,
    SETTINGS_TAB_SHORT_COOLDOWN,
    SETTINGS_TAB_DUNGEON,
    SETTINGS_TAB_GENERAL,
    SETTINGS_TAB_VISUAL_HUD,
    SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS,
    VISUAL_HUD_DEFAULT_ICONS,
    VISUAL_HUD_DEFAULT_SHOW_BEFORE_SECONDS,
    SettingsApp,
    find_or_create_boss_laser_alert,
    find_or_create_bronntanas_hp_hud,
    find_or_create_miracle_orb_hp_hud,
    find_or_create_rotating_laser_countdown_hud,
    find_or_create_other_skill_hud,
    find_or_create_short_cooldown_hud,
    find_or_create_short_cooldown_tracker,
    find_or_create_visual_hud,
    key_enemy_debuff_defaults,
    other_skill_hud_icon,
    parse_key_enemy_debuff_threshold_values,
    settings_tab_titles,
    short_cooldown_hud_icon,
    visual_hud_icon,
)
from scripts.make_visual_private_config import configure_visual_private
from buffwatcher.config_migration import _apply_policy_migrations


class VisualHudSettingsTests(unittest.TestCase):
    def test_requested_settings_sections_do_not_restore_explanatory_copy(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "buffwatcher"
            / "settings_gui.py"
        ).read_text(encoding="utf-8")
        forbidden_copy = (
            "每项 HUD 的提前提醒时间和铃声开关均与语音播报相互独立。",
            "支持 PNG、GIF 图片；留空时使用后备音符或爱心。",
            "仅在已定义的关键 Boss 战中，于屏幕左侧常驻显示满足条件的图标",
            "在已定义的关键 Boss 战或测试木头人（RaceId 4860）出现时显示。",
            "依次填写卡组中的 1–5 号牌和当前技能花色",
            "以上为不含暴击减少冷却的基础数值。",
            "卡牌选项：幸运型",
            "到期图标慢闪；提前时间沿用",
            "Boss血量达到52%后显示精确血量",
            "60%阶段显示7604、7605、7606三只神迹球血量",
            "每轮旋转激光开始移动时，读取服务器下发的本轮移动时长",
            "计时起点：魔法阵为技能施放成功",
        )
        for text in forbidden_copy:
            with self.subTest(text=text):
                self.assertNotIn(text, source)

    def test_astrology_save_writes_the_two_independent_switches(self) -> None:
        class Value:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        app = SettingsApp.__new__(SettingsApp)
        app.data = {"combat_astrology_card_tracker": {}}
        app.astrology_card_tracker = AstrologyCardTrackerRow(
            item=app.data["combat_astrology_card_tracker"],
            enabled_skills={27202: Value(True), 27203: Value(False)},
            counter_threshold=Value("6"),
            deck=[Value(name) for name in ("审判", "女皇", "皇帝", "力量", "正义")],
            skill_suits={
                skill_id: Value("攻击型")
                for skill_id in (27202, 27203, 27201, 27200, 27204, 27206, 27205, 27210)
            },
            base_cooldown_seconds={27202: Value("3.5"), 27203: Value("6.2")},
        )

        app.apply_astrology_card_tracker_to_data()

        saved = app.data["combat_astrology_card_tracker"]
        self.assertEqual(saved["tracked_skills"], {"27202": True, "27203": False})
        self.assertNotIn("enabled", saved)

    def test_generic_and_visual_builds_expose_the_expected_tabs(self) -> None:
        self.assertEqual(
            settings_tab_titles({}),
            (SETTINGS_TAB_GENERAL, SETTINGS_TAB_DUNGEON),
        )

    def test_pall_tracker_is_added_only_to_the_visual_private_config(self) -> None:
        generic = {"buffs": []}
        self.assertTrue(_apply_policy_migrations(generic))
        self.assertTrue(any(item.get("ccid") == 1186 for item in generic["buffs"]))
        self.assertTrue(any(item.get("ccid") == 1225 for item in generic["buffs"]))
        self.assertFalse(any(item.get("ccid") == 803 for item in generic["buffs"]))
        self.assertFalse(
            any(item.get("ccid") == -59060 for item in generic["buffs"])
        )

        visual = {
            "buffs": [],
            "experimental_music_visual_overlay": {},
        }
        self.assertTrue(_apply_policy_migrations(visual))
        pall = next(item for item in visual["buffs"] if item.get("ccid") == 803)
        self.assertEqual(pall["skill_id"], 59005)
        self.assertEqual(pall["cooldown_delay_seconds"], 180)
        ignis = next(
            item for item in visual["buffs"] if item.get("ccid") == -59060
        )
        self.assertEqual(ignis["skill_id"], 59060)
        self.assertEqual(ignis["cooldown_delay_seconds"], 6)
        self.assertTrue(ignis["cooldown_from_skill_use"])
        self.assertEqual(
            settings_tab_titles(visual),
            (
                SETTINGS_TAB_GENERAL,
                SETTINGS_TAB_DUNGEON,
                SETTINGS_TAB_VISUAL_HUD,
                SETTINGS_TAB_SHORT_COOLDOWN,
                SETTINGS_TAB_ASTROLOGY,
            ),
        )

    def test_private_rebuild_preserves_every_existing_local_hud_choice(self) -> None:
        data = {
            "music_tuan_silence_enabled": True,
            "experimental_music_visual_overlay": {
                "enabled": False,
                "tuan_silence_enabled": True,
                "conditions": {
                    "192": {
                        "enabled": False,
                        "icon": "assets/custom/my-vivace.png",
                        "show_before_seconds": 6.5,
                        "ring_sound_enabled": True,
                    },
                    "874": {"enabled": True},
                },
            },
            "key_enemy_debuff_alert": {"visual_hud_enabled": False},
            BRONNTANAS_HP_HUD_CONFIG_KEY: {"enabled": False},
        }

        configure_visual_private(data, preserve_existing=True)

        overlay = data["experimental_music_visual_overlay"]
        self.assertFalse(overlay["enabled"])
        self.assertTrue(overlay["tuan_silence_enabled"])
        self.assertFalse(overlay["conditions"]["192"]["enabled"])
        self.assertTrue(overlay["conditions"]["192"]["ring_sound_enabled"])
        self.assertEqual(overlay["conditions"]["192"]["show_before_seconds"], 6.5)
        self.assertEqual(
            overlay["conditions"]["192"]["icon"], "assets/custom/my-vivace.png"
        )
        self.assertIn("193", overlay["conditions"])
        self.assertNotIn("874", overlay["conditions"])
        self.assertFalse(data["experimental_other_skill_visual_overlay"]["enabled"])
        self.assertFalse(
            data["experimental_other_skill_visual_overlay"]["conditions"]
            ["life_temperature"]["enabled"]
        )
        self.assertFalse(data["key_enemy_debuff_alert"]["visual_hud_enabled"])
        self.assertTrue(data["music_tuan_silence_enabled"])
        self.assertTrue(
            data["experimental_short_cooldown_visual_overlay"]["enabled"]
        )
        self.assertFalse(data[BRONNTANAS_HP_HUD_CONFIG_KEY]["enabled"])
        self.assertTrue(data[MIRACLE_ORB_HP_HUD_CONFIG_KEY]["enabled"])
        self.assertTrue(
            data[ROTATING_LASER_COUNTDOWN_HUD_CONFIG_KEY]["enabled"]
        )

    def test_bronntanas_hp_hud_is_visual_only_and_defaults_on(self) -> None:
        generic: dict = {}
        self.assertNotIn(BRONNTANAS_HP_HUD_CONFIG_KEY, generic)

        visual = {"buffs": []}
        configure_visual_private(visual, preserve_existing=False)
        item = find_or_create_bronntanas_hp_hud(visual)

        self.assertTrue(item["enabled"])
        self.assertEqual(item["activation_percent"], 52.0)
        self.assertEqual(item["warning_percent"], 50.0)
        self.assertEqual(item["dismiss_after_seconds"], 2.0)
        self.assertEqual(item["icon"], BRONNTANAS_HP_HUD_DEFAULT_ICON)
        self.assertTrue(
            (Path(__file__).resolve().parents[1] / item["icon"]).is_file()
        )

    def test_miracle_orb_hp_hud_is_visual_only_and_defaults_on(self) -> None:
        generic: dict = {}
        self.assertNotIn(MIRACLE_ORB_HP_HUD_CONFIG_KEY, generic)

        visual = {"buffs": []}
        configure_visual_private(visual, preserve_existing=False)
        item = find_or_create_miracle_orb_hp_hud(visual)

        self.assertTrue(item["enabled"])
        self.assertEqual(item["left_x_ratio"], 0.108)
        self.assertEqual(item["top_y_ratio"], 0.125)
        self.assertEqual(item["focus_center_y_ratio"], 0.855)

    def test_rotating_laser_countdown_is_visual_only_and_defaults_on(self) -> None:
        generic: dict = {}
        self.assertNotIn(ROTATING_LASER_COUNTDOWN_HUD_CONFIG_KEY, generic)

        visual = {"buffs": []}
        configure_visual_private(visual, preserve_existing=False)
        item = find_or_create_rotating_laser_countdown_hud(visual)

        self.assertTrue(item["enabled"])
        self.assertEqual(item["center_y_ratio"], 0.89)

        item["enabled"] = False
        configure_visual_private(visual, preserve_existing=True)
        self.assertFalse(
            visual[ROTATING_LASER_COUNTDOWN_HUD_CONFIG_KEY]["enabled"]
        )

    def test_astrology_release_and_local_defaults_are_kept_separate(self) -> None:
        release = {"buffs": []}
        configure_visual_private(release, preserve_existing=False)
        release_astrology = release["combat_astrology_card_tracker"]
        self.assertEqual(
            release_astrology["tracked_skills"],
            {"27202": False, "27203": False},
        )
        self.assertEqual(
            release_astrology["base_cooldown_seconds"],
            {"27202": 9, "27203": 12},
        )

        local = {
            "buffs": [],
            "combat_astrology_card_tracker": {
                "enabled": True,
                "base_cooldown_seconds": {"27202": 3.5, "27203": 6.2},
            },
        }
        configure_visual_private(local, preserve_existing=True)
        local_astrology = local["combat_astrology_card_tracker"]
        self.assertNotIn("enabled", local_astrology)
        self.assertEqual(
            local_astrology["tracked_skills"],
            {"27202": True, "27203": True},
        )
        self.assertEqual(
            local_astrology["base_cooldown_seconds"],
            {"27202": 3.5, "27203": 6.2},
        )

    def test_music_visual_hud_contains_only_three_music_skills(self) -> None:
        data: dict = {}

        item = find_or_create_visual_hud(data)

        self.assertTrue(item["enabled"])
        self.assertEqual(
            item["show_before_seconds"], VISUAL_HUD_DEFAULT_SHOW_BEFORE_SECONDS
        )
        self.assertEqual(item["show_before_seconds"], 15.0)
        self.assertEqual(visual_hud_icon(item, 192), VISUAL_HUD_DEFAULT_ICONS[192])
        self.assertEqual(visual_hud_icon(item, 874), "")
        self.assertEqual(VISUAL_HUD_DEFAULT_ICONS, DEFAULT_OVERLAY_ICONS)
        project_root = Path(__file__).resolve().parents[1]
        for icon in VISUAL_HUD_DEFAULT_ICONS.values():
            self.assertTrue((project_root / icon).is_file(), icon)
        for ccid, condition in item["conditions"].items():
            self.assertEqual(condition["show_before_seconds"], 15.0)
            self.assertFalse(condition["ring_sound_enabled"])
        self.assertTrue(item["conditions"]["193"]["enabled"])
        self.assertFalse(item["tuan_silence_enabled"])

    def test_other_skill_hud_defaults_off_and_life_temperature_is_individually_off(self) -> None:
        data: dict = {}

        item = find_or_create_other_skill_hud(data)

        self.assertFalse(item["enabled"])
        self.assertEqual(
            list(item["conditions"]),
            list(OTHER_SKILL_HUD_CONDITION_DEFAULTS),
        )
        self.assertFalse(item["conditions"]["life_temperature"]["enabled"])
        self.assertTrue(item["conditions"]["magic_circle"]["enabled"])
        self.assertTrue(item["conditions"]["hamster_supercharged"]["enabled"])
        self.assertEqual(item["conditions"]["hamster_supercharged"]["name"], "陈睿")
        self.assertEqual(
            other_skill_hud_icon(item, "hamster_supercharged"),
            "assets/icon/visual-overlay/other-skills/hamster-supercharged.png",
        )
        self.assertNotIn("hamster_adrenaline", item["conditions"])
        self.assertEqual(
            other_skill_hud_icon(item, "pall_of_ruination"),
            "assets/icon/visual-overlay/other-skills/pall-of-ruination.png",
        )
        self.assertEqual(
            [value[0] for value in DEFAULT_OTHER_SKILL_OVERLAY_ITEMS],
            list(OTHER_SKILL_HUD_CONDITION_DEFAULTS),
        )
        project_root = Path(__file__).resolve().parents[1]
        for defaults in OTHER_SKILL_HUD_CONDITION_DEFAULTS.values():
            self.assertTrue((project_root / defaults["icon"]).is_file())

    def test_short_cooldown_hud_defaults_include_both_packaged_icons(self) -> None:
        data: dict = {}

        item = find_or_create_short_cooldown_hud(data)

        self.assertTrue(item["enabled"])
        self.assertTrue(item["conditions"]["ignis_plume"]["enabled"])
        self.assertTrue(item["conditions"]["aqua_volley"]["enabled"])
        self.assertEqual(
            short_cooldown_hud_icon(item, "ignis_plume"),
            "assets/icon/visual-overlay/short-cooldown/ignis-plume.png",
        )
        self.assertEqual(
            short_cooldown_hud_icon(item, "aqua_volley"),
            "assets/icon/visual-overlay/short-cooldown/aqua-volley.png",
        )
        self.assertEqual(
            [value[0] for value in DEFAULT_SHORT_COOLDOWN_OVERLAY_ITEMS],
            list(SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS),
        )
        project_root = Path(__file__).resolve().parents[1]
        for condition in item["conditions"].values():
            self.assertTrue((project_root / condition["icon"]).is_file())

        ignis = find_or_create_short_cooldown_tracker(data, "ignis_plume")
        aqua = find_or_create_short_cooldown_tracker(data, "aqua_volley")
        self.assertEqual(ignis["skill_id"], 59060)
        self.assertEqual(ignis["cooldown_delay_seconds"], 6)
        self.assertEqual(aqua["skill_id"], 59061)
        self.assertEqual(aqua["cooldown_delay_seconds"], 10)

    def test_short_cooldown_custom_times_survive_policy_migration(self) -> None:
        data = {
            "buffs": [
                {
                    "name": "爆炎箭",
                    "ccid": -59060,
                    "cooldown_delay_seconds": 7.5,
                },
                {
                    "name": "水流箭",
                    "ccid": -59061,
                    "cooldown_delay_seconds": 12,
                },
            ],
            "experimental_short_cooldown_visual_overlay": {},
        }

        self.assertTrue(_apply_policy_migrations(data))
        trackers = {item["name"]: item for item in data["buffs"]}
        self.assertEqual(trackers["爆炎箭"]["cooldown_delay_seconds"], 7.5)
        self.assertEqual(trackers["水流箭"]["cooldown_delay_seconds"], 12)
        self.assertEqual(
            data["experimental_short_cooldown_visual_overlay"]
            ["default_icons_version"],
            2,
        )

    def test_legacy_muted_value_migrates_to_ring_toggle(self) -> None:
        data = {
            "experimental_music_visual_overlay": {
                "muted": True,
                "show_before_seconds": 9.5,
            }
        }

        item = find_or_create_visual_hud(data)

        self.assertFalse(item["ring_sound_enabled"])
        self.assertFalse(item["muted"])
        for condition in item["conditions"].values():
            self.assertFalse(condition["ring_sound_enabled"])
            self.assertEqual(condition["show_before_seconds"], 9.5)
        self.assertEqual(visual_hud_icon(item, 192), VISUAL_HUD_DEFAULT_ICONS[192])

    def test_existing_tuan_silence_choice_is_preserved(self) -> None:
        data = {
            "experimental_music_visual_overlay": {
                "tuan_silence_enabled": True,
            }
        }

        item = find_or_create_visual_hud(data)

        self.assertTrue(item["tuan_silence_enabled"])

    def test_custom_icon_is_preserved_while_old_empty_icons_are_migrated(self) -> None:
        data = {
            "experimental_music_visual_overlay": {
                "conditions": {
                    "192": {
                        "icon": "assets/custom/my-vivace.png",
                        "show_before_seconds": 6.5,
                        "ring_sound_enabled": False,
                    },
                    "680": {"icon": ""},
                }
            }
        }

        item = find_or_create_visual_hud(data)

        self.assertEqual(visual_hud_icon(item, 192), "assets/custom/my-vivace.png")
        self.assertEqual(visual_hud_icon(item, 680), VISUAL_HUD_DEFAULT_ICONS[680])
        self.assertEqual(item["conditions"]["192"]["show_before_seconds"], 6.5)
        self.assertFalse(item["conditions"]["192"]["ring_sound_enabled"])
        self.assertEqual(item["conditions"]["680"]["show_before_seconds"], 15.0)
        self.assertFalse(item["conditions"]["680"]["ring_sound_enabled"])

    def test_debuff_complete_defaults_require_explicit_setup(self) -> None:
        defaults = key_enemy_debuff_defaults()

        self.assertFalse(defaults["complete_enabled"])
        self.assertFalse(defaults["visual_hud_enabled"])
        self.assertTrue(defaults["visual_expiry_enabled"])
        for key in (
            "physical_break_min",
            "magic_break_min",
            "damage_bonus_min",
            "rabbit_stacks_min",
        ):
            self.assertIsNone(defaults[key])
        project_root = Path(__file__).resolve().parents[1]
        self.assertEqual(len(DEFAULT_DEBUFF_OVERLAY_ITEMS), 9)
        for _key, _name, icon in DEFAULT_DEBUFF_OVERLAY_ITEMS:
            self.assertTrue((project_root / icon).is_file(), icon)

    def test_debuff_complete_thresholds_must_all_be_filled_before_enabling(self) -> None:
        incomplete = {
            "physical_break_min": "30",
            "magic_break_min": "41",
            "damage_bonus_min": "",
            "rabbit_stacks_min": "4",
        }
        with self.assertRaisesRegex(ValueError, "必须完整填写四项"):
            parse_key_enemy_debuff_threshold_values(
                incomplete,
                require_complete=True,
            )

        complete = dict(incomplete, damage_bonus_min="61")
        self.assertEqual(
            parse_key_enemy_debuff_threshold_values(
                complete,
                require_complete=True,
            ),
            {
                "physical_break_min": 30,
                "magic_break_min": 41,
                "damage_bonus_min": 61,
                "rabbit_stacks_min": 4,
            },
        )

    def test_visual_release_defaults_are_empty_but_local_values_are_preserved(self) -> None:
        release = {"key_enemy_debuff_alert": {}}
        configure_visual_private(release, preserve_existing=False)
        release_debuff = release["key_enemy_debuff_alert"]
        self.assertFalse(release_debuff["complete_enabled"])
        self.assertFalse(release_debuff["visual_hud_enabled"])
        self.assertIsNone(release_debuff["physical_break_min"])
        self.assertIsNone(release_debuff["magic_break_min"])
        self.assertIsNone(release_debuff["damage_bonus_min"])
        self.assertIsNone(release_debuff["rabbit_stacks_min"])

        local = {
            "key_enemy_debuff_alert": {
                "complete_enabled": True,
                "visual_hud_enabled": True,
                "physical_break_min": 30,
                "magic_break_min": 41,
                "damage_bonus_min": 62,
                "rabbit_stacks_min": 4,
            }
        }
        configure_visual_private(local, preserve_existing=True)
        local_debuff = local["key_enemy_debuff_alert"]
        self.assertTrue(local_debuff["complete_enabled"])
        self.assertTrue(local_debuff["visual_hud_enabled"])
        self.assertEqual(local_debuff["physical_break_min"], 30)
        self.assertEqual(local_debuff["magic_break_min"], 41)
        self.assertEqual(local_debuff["damage_bonus_min"], 62)
        self.assertEqual(local_debuff["rabbit_stacks_min"], 4)

    def test_boss_laser_settings_remove_the_obsolete_warning_note(self) -> None:
        data = {
            "boss_laser_alerts": [
                {
                    "name": "布3/布4激光预警",
                    "note": "***请勿过度依赖***",
                }
            ]
        }

        item = find_or_create_boss_laser_alert(data)

        self.assertNotIn("note", item)
        self.assertEqual(item["name"], "布3/布4激光前倒计时")
        self.assertEqual(len(data["boss_laser_alerts"]), 1)


if __name__ == "__main__":
    unittest.main()

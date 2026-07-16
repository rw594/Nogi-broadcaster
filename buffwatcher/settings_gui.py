from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import (
    BooleanVar,
    DoubleVar,
    IntVar,
    StringVar,
    Tk,
    filedialog,
    messagebox,
    ttk,
)

from .alerting import (
    DEFAULT_ENDED_SOUND,
    DEFAULT_WARN_SOUND,
    make_timed_sound_sequence,
    normalize_volume,
    play_sound,
)
from .astrology_cards import (
    ASTROLOGY_CARD_OPTIONS,
    ASTROLOGY_CARD_TRACKER_CONFIG_KEY,
    ASTROLOGY_CORE_COOLDOWN_DEFAULTS,
    ASTROLOGY_COUNTER_CHOICES,
    ASTROLOGY_DEFAULT_COUNTER_THRESHOLD,
    ASTROLOGY_MAX_COOLDOWN_SECONDS,
    ASTROLOGY_MIN_COOLDOWN_SECONDS,
    ASTROLOGY_SKILLS,
    ASTROLOGY_SUIT_OPTIONS,
    ASTROLOGY_UNSET_LABEL,
    default_astrology_card_tracker_config,
    ensure_astrology_card_tracker_config,
)
from .backend import app_root
from .config_migration import migrate_config_file
from .console_launcher import package_title
from .hamster_buffs import (
    HAMSTER_BUFF_DURATION_SECONDS,
    HAMSTER_BUFF_NAMES,
    HAMSTER_DEFAULT_WARNING_SECONDS,
    HAMSTER_SETTINGS_NAME,
    HAMSTER_SUPERCHARGED_NAME,
    ensure_hamster_buff_items,
)
from .theme import ROOT_BACKGROUND, SETTINGS_COLORS


BUFF_GROUPS = [
    ("乐曲类", ["战争序曲", "活跃曲", "行进曲"]),
    ("药水类", ["物攻水", "魔攻水", "法速水", "炼金水", "马纽斯秘药"]),
    ("特性类", ["状态支援", "坚定意志", "逆光剑", "致命穿透", "超越生命"]),
    (
        "阿尔卡纳特定",
        [
            "负载转移",
            "圣域之主",
            "活力之歌",
            "生命的温度",
            "枪手之眼",
            "星辰交汇-物理",
            "星辰交汇-魔法",
            "星辰交汇-炼金",
        ],
    ),
    ("其他", ["净化之浪", HAMSTER_SETTINGS_NAME]),
]
BUFF_ORDER = [name for _group, names in BUFF_GROUPS for name in names]
MUSIC_STRONG_REMINDER_ENABLED = False
MUSIC_STRONG_REMINDER_REPEAT_SECONDS = 5.0
MUSIC_STRONG_REMINDER_PREFIX_SOUND = "assets/audio/xiaoyi/music_strong_beep.wav"
MUSIC_TUAN_SILENCE_LABEL = "检测到徒安之歌时，静默播报"
MUSIC_TUAN_SILENCE_DEFAULT = False
VISUAL_HUD_TUAN_SILENCE_LABEL = "检测到徒安之歌时，屏蔽视觉提醒"
SETTINGS_TAB_GENERAL = "常规提醒"
SETTINGS_TAB_DUNGEON = "副本机制提醒"
SETTINGS_TAB_VISUAL_HUD = "可视化HUD"
SETTINGS_TAB_SHORT_COOLDOWN = "短CD技能冷却提示"
SETTINGS_TAB_ASTROLOGY = "战斗占星追踪"

VISUAL_HUD_CONFIG_KEY = "experimental_music_visual_overlay"
VISUAL_HUD_DEFAULT_SHOW_BEFORE_SECONDS = 15.0
VISUAL_HUD_MIN_SHOW_BEFORE_SECONDS = 0.1
VISUAL_HUD_MAX_SHOW_BEFORE_SECONDS = 9999.0
VISUAL_HUD_MUSIC_CCIDS = (192, 193, 680)
VISUAL_HUD_DEFAULT_ICONS_VERSION = 1
VISUAL_HUD_DEFAULT_ICONS = {
    192: "assets/icon/visual-overlay/vivace.png",
    193: "assets/icon/visual-overlay/march-song.png",
    680: "assets/icon/visual-overlay/battlefield-overture.png",
}
VISUAL_HUD_CONDITION_DEFAULTS = {
    192: {
        "enabled": True,
        "name": "活跃曲",
        "icon": VISUAL_HUD_DEFAULT_ICONS[192],
        "show_before_seconds": VISUAL_HUD_DEFAULT_SHOW_BEFORE_SECONDS,
        "ring_sound_enabled": False,
    },
    193: {
        "enabled": True,
        "name": "行进曲",
        "icon": VISUAL_HUD_DEFAULT_ICONS[193],
        "show_before_seconds": VISUAL_HUD_DEFAULT_SHOW_BEFORE_SECONDS,
        "ring_sound_enabled": False,
    },
    680: {
        "enabled": True,
        "name": "战争序曲",
        "icon": VISUAL_HUD_DEFAULT_ICONS[680],
        "show_before_seconds": VISUAL_HUD_DEFAULT_SHOW_BEFORE_SECONDS,
        "ring_sound_enabled": False,
    },
}
OTHER_SKILL_HUD_CONFIG_KEY = "experimental_other_skill_visual_overlay"
OTHER_SKILL_HUD_DEFAULT_ICONS_VERSION = 2
OTHER_SKILL_HUD_CONDITION_DEFAULTS = {
    "magic_circle": {
        "enabled": True,
        "name": "魔法阵",
        "icon": "assets/icon/visual-overlay/other-skills/magic-circle.png",
    },
    "pall_of_ruination": {
        "enabled": True,
        "name": "崩坏波动",
        "icon": "assets/icon/visual-overlay/other-skills/pall-of-ruination.png",
    },
    "manus_potion": {
        "enabled": True,
        "name": "马纽斯秘药",
        "icon": "assets/icon/visual-overlay/other-skills/manus-potion.png",
    },
    "purification_wave": {
        "enabled": True,
        "name": "净化之浪",
        "icon": "assets/icon/visual-overlay/other-skills/purification-wave.png",
    },
    "hamster_supercharged": {
        "enabled": True,
        "name": HAMSTER_SETTINGS_NAME,
        "icon": "assets/icon/visual-overlay/other-skills/hamster-supercharged.png",
    },
    "life_temperature": {
        "enabled": False,
        "name": "生命的温度",
        "icon": "assets/icon/visual-overlay/life-temperature.png",
    },
}
SHORT_COOLDOWN_HUD_CONFIG_KEY = "experimental_short_cooldown_visual_overlay"
BRONNTANAS_HP_HUD_CONFIG_KEY = "experimental_bronntanas_hp_visual_overlay"
BRONNTANAS_HP_HUD_SECTION_NAME = "布本二王50%机制血量监控"
BRONNTANAS_HP_HUD_DEFAULT_ICON = (
    "assets/icon/visual-overlay/boss/bronntanas.png"
)
MIRACLE_ORB_HP_HUD_CONFIG_KEY = (
    "experimental_bu3_miracle_orb_hp_visual_overlay"
)
MIRACLE_ORB_HP_HUD_SECTION_NAME = "布三60%神迹球血量追踪"
ROTATING_LASER_COUNTDOWN_HUD_CONFIG_KEY = (
    "experimental_bu34_rotating_laser_visual_countdown"
)
ROTATING_LASER_COUNTDOWN_HUD_SECTION_NAME = (
    "布三/布四旋转激光移动倒计时"
)
SHORT_COOLDOWN_HUD_DEFAULT_ICONS_VERSION = 2
SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS = {
    "ignis_plume": {
        "enabled": True,
        "name": "爆炎箭",
        "icon": "assets/icon/visual-overlay/short-cooldown/ignis-plume.png",
        "tracker_ccid": -59060,
        "skill_id": 59060,
        "cooldown_seconds": 6,
    },
    "aqua_volley": {
        "enabled": True,
        "name": "水流箭",
        "icon": "assets/icon/visual-overlay/short-cooldown/aqua-volley.png",
        "tracker_ccid": -59061,
        "skill_id": 59061,
        "cooldown_seconds": 10,
    },
}


def settings_tab_titles(data: dict) -> tuple[str, ...]:
    titles = [SETTINGS_TAB_GENERAL, SETTINGS_TAB_DUNGEON]
    if any(
        key in data
        for key in (
            VISUAL_HUD_CONFIG_KEY,
            OTHER_SKILL_HUD_CONFIG_KEY,
            SHORT_COOLDOWN_HUD_CONFIG_KEY,
        )
    ):
        titles.append(SETTINGS_TAB_VISUAL_HUD)
    if SHORT_COOLDOWN_HUD_CONFIG_KEY in data:
        titles.append(SETTINGS_TAB_SHORT_COOLDOWN)
    if ASTROLOGY_CARD_TRACKER_CONFIG_KEY in data:
        titles.append(SETTINGS_TAB_ASTROLOGY)
    return tuple(titles)

PROGRESS_ORDER = [
    "托亚灵进度",
]

FOOD_EFFECT_NAME = "庆典料理"
FOOD_DEFAULT_WARNING_SECONDS = 60
SAFEHOUSE_NAME = "布四安全屋"
SAFEHOUSE_INTERVAL_SECONDS = 63
SAFEHOUSE_FIRST_OCCURRENCE_SECONDS = 7
SAFEHOUSE_FIRST_ALERTED_OCCURRENCE_SECONDS = (
    SAFEHOUSE_FIRST_OCCURRENCE_SECONDS + SAFEHOUSE_INTERVAL_SECONDS
)
SAFEHOUSE_BOSS_MAX_HP = 3449779200
SAFEHOUSE_DEFAULT_LEAD_SECONDS = 7
SAFEHOUSE_MIN_LEAD_SECONDS = 5
SAFEHOUSE_MAX_LEAD_SECONDS = 15
SAFEHOUSE_TRIGGER_DEDUPE_SECONDS = 10
SAFEHOUSE_DEFAULT_SOUND = "assets/audio/xiaoyi/safehouse_warning.wav"
SAFEHOUSE_ENTITY_STAT_ID = 11
SAFEHOUSE_ENTITY_STAT_VALUE = 3
SAFEHOUSE_ENTITY_HP = 69906070
SAFEHOUSE_SYNC_EVENT_ID = 17
SAFEHOUSE_SYNC_INITIAL_MIN_SECONDS = 4
SAFEHOUSE_SYNC_INITIAL_MAX_SECONDS = 12
SAFEHOUSE_SYNC_EXPECTED_TOLERANCE_SECONDS = 2
SAFEHOUSE_SYNC_MIN_INTERVAL_SECONDS = 61
SAFEHOUSE_SYNC_MAX_INTERVAL_SECONDS = 64
MAGIC_SHIELD_NAME = "魔法盾"
MAGIC_SHIELD_DEFAULT_ENDED_GRACE_SECONDS = 0.0
MAGIC_SHIELD_MAX_ENDED_GRACE_SECONDS = 10.0
MAGIC_SHIELD_DEFAULT_ENDED_SOUND = "assets/audio/xiaoyi/magic_shield_ended.wav"
MAGIC_SHIELD_DEFAULT_ENDED_MESSAGE = "魔法盾关闭"
MAGIC_SHIELD_MISSING_ALERT_NAME = "魔法盾漏开提醒"
MAGIC_SHIELD_DEFAULT_MISSING_DELAY_SECONDS = 5.0
MAGIC_SHIELD_MAX_MISSING_DELAY_SECONDS = 30.0
MAGIC_SHIELD_DEFAULT_MISSING_REPEAT_SECONDS = 5.0
MAGIC_SHIELD_DEFAULT_MISSING_SOUND = "assets/audio/xiaoyi/magic_shield_missing.wav"
MAGIC_SHIELD_DEFAULT_MISSING_MESSAGE = "魔法盾忘开啦"
BOSS_HP_SECTION_NAME = "Boss血量机制提醒"
BOSS_HP_DEFAULT_SOUND = "assets/audio/xiaoyi/boss_mechanic_warning.wav"
BOSS_HP_DEFAULT_MESSAGE = "注意机制"
BOSS_HP_CURRENT_STAT_ID = 28
BOSS_HP_MAX_STAT_ID = 30
BOSS_HP_SAFEHOUSE_COUNTDOWN_SOUND_DIR = "assets/audio/xiaoyi/safehouse_countdown"
BOSS_HP_SAFEHOUSE_COUNTDOWN_MESSAGE = "{message}，安全屋{seconds}秒"
BOSS_HP_SAFEHOUSE_COUNTDOWN_MAX_SECONDS = 70
BOSS_RED_ORB_NAME = "布三红球危险倒数"
BOSS_RED_ORB_SOUND = "assets/audio/xiaoyi/red_orb_countdown/danger_red_orb.wav"
BOSS_RED_ORB_SAFE_SOUND = "assets/audio/xiaoyi/red_orb_countdown/safe_complete.wav"
BOSS_RED_ORB_MESSAGE = "危险红球，5，4，3，2，1，0"
BOSS_RED_ORB_COUNTDOWN_5_SOUND = "assets/audio/xiaoyi/red_orb_countdown/count_05.wav"
BOSS_RED_ORB_COUNTDOWN_4_SOUND = "assets/audio/xiaoyi/red_orb_countdown/count_04.wav"
BOSS_RED_ORB_COUNTDOWN_3_SOUND = "assets/audio/xiaoyi/red_orb_countdown/count_03.wav"
BOSS_RED_ORB_COUNTDOWN_2_SOUND = "assets/audio/xiaoyi/red_orb_countdown/count_02.wav"
BOSS_RED_ORB_COUNTDOWN_1_SOUND = "assets/audio/xiaoyi/red_orb_countdown/count_01.wav"
BOSS_RED_ORB_COUNTDOWN_0_SOUND = "assets/audio/xiaoyi/red_orb_countdown/count_00.wav"
BOSS_RED_ORB_BOSS_MAX_HP_VALUES = [1967880100]
BOSS_RED_ORB_RACE_IDS = [7604, 7605, 7606, 7607]
BOSS_RED_ORB_COUNTDOWN_OP = "0x6d62"
BOSS_RED_ORB_COUNTDOWN_MARKER = "280"
BOSS_RED_ORB_START_STEP = "4"
BOSS_RED_ORB_CONFIRM_STEP = "5"
BOSS_RED_ORB_PAIR_WINDOW_MS = 250
BOSS_RED_ORB_HIGH_HP_EXPLOSION_DELAY_SECONDS = 15.0
BOSS_RED_ORB_LOW_HP_EXPLOSION_DELAY_SECONDS = 20.0
BOSS_RED_ORB_EXPLOSION_DELAY_SECONDS = BOSS_RED_ORB_HIGH_HP_EXPLOSION_DELAY_SECONDS
BOSS_RED_ORB_LEAD_SECONDS = 3.0
BOSS_RED_ORB_CONTACT_CHECK_SECONDS = 12.0
BOSS_RED_ORB_SAFE_MIN_CONTACT_TICKS = 8
BOSS_RED_ORB_SAFE_LAST_CONTACT_BEFORE_SECONDS = 12.0
BOSS_RED_ORB_CONTACT_GROUP_MS = 120
BOSS_RED_ORB_HP_SPLIT_PERCENT = 60.0
BOSS_RED_ORB_HIGH_HP_REQUIRED_CONTACT_TICKS = 8
BOSS_RED_ORB_HIGH_HP_EARLY_CHECK_SECONDS = 5.0
BOSS_RED_ORB_HIGH_HP_EARLY_MAX_CONTACT_TICKS = 2
BOSS_RED_ORB_HIGH_HP_FINAL_CHECK_SECONDS = 8.0
BOSS_RED_ORB_LOW_HP_REQUIRED_CONTACT_TICKS = 10
BOSS_RED_ORB_LOW_HP_EARLY_CHECK_SECONDS = 10.0
BOSS_RED_ORB_LOW_HP_EARLY_MAX_CONTACT_TICKS = 5
BOSS_RED_ORB_LOW_HP_FINAL_CHECK_SECONDS = 11.0
BOSS_RED_ORB_LATE_CONFIRM_OP = "0x6d66"
BOSS_RED_ORB_LATE_CONFIRM_START_SECONDS = 12.0
BOSS_RED_ORB_LATE_CONFIRM_END_SECONDS = 14.75
BOSS_RED_ORB_STALE_SECONDS = 25.0
BOSS_LASER_ALERT_NAME = "布3/布4激光前倒计时"
BOSS_LASER_ALERT_LEGACY_NAMES = {
    BOSS_LASER_ALERT_NAME,
    "布3/布4激光预警",
}
BOSS_LASER_ALERT_SOUND = "assets/audio/xiaoyi/laser_warning_prefix.wav"
BOSS_LASER_ALERT_MESSAGE = "激光 四 三 二 一 零"
BOSS_LASER_BOSS_MAX_HP_VALUES = [1967880100, SAFEHOUSE_BOSS_MAX_HP]
BOSS_LASER_STARDUST_RACE_IDS = [
    7604,
    7605,
    7606,
    7607,
    7608,
    7616,
    7617,
    7618,
    7619,
    7620,
]
BOSS_LASER_CAST_OP = "0xafe7"
BOSS_LASER_SKILL_ID = 52401
BOSS_LASER_CAST_SECONDS = 5.0
BOSS_LASER_CLUSTER_WINDOW_MS = 250
BOSS_LASER_STALE_SECONDS = 8.0
BOSS_LASER_COUNTDOWN_4_SOUND = "assets/audio/xiaoyi/red_orb_countdown/count_04.wav"
BOSS_LASER_COUNTDOWN_3_SOUND = "assets/audio/xiaoyi/red_orb_countdown/count_03.wav"
BOSS_LASER_COUNTDOWN_2_SOUND = "assets/audio/xiaoyi/red_orb_countdown/count_02.wav"
BOSS_LASER_COUNTDOWN_1_SOUND = "assets/audio/xiaoyi/red_orb_countdown/count_01.wav"
BOSS_LASER_COUNTDOWN_0_SOUND = "assets/audio/xiaoyi/red_orb_countdown/count_00.wav"
KEY_ENEMY_DEBUFF_SECTION_NAME = "关键敌人DEBUFF提醒"
KEY_ENEMY_DEBUFF_COMPLETE_SOUND = "assets/audio/xiaoyi/debuffs_ready.wav"
KEY_ENEMY_DEBUFF_EXPIRY_SOUND = "assets/audio/xiaoyi/debuffs_renew.wav"
KEY_ENEMY_DEBUFF_COMPLETE_MESSAGE = "BUFF齐啦"
KEY_ENEMY_DEBUFF_EXPIRY_MESSAGE = "破防该续啦"
KEY_ENEMY_DEBUFF_DEFAULT_EXPIRY_SECONDS = 30
KEY_ENEMY_DEBUFF_PHYSICAL_BREAK_MIN = 30
KEY_ENEMY_DEBUFF_MAGIC_BREAK_MIN = 41
KEY_ENEMY_DEBUFF_DAMAGE_BONUS_MIN = 61
KEY_ENEMY_DEBUFF_RABBIT_STACKS_MIN = 4
KAILAHE_PHASE_1_MAX_HP = 80032160
KAILAHE_PHASE_2_MAX_HP = 104041810
KEY_ENEMY_GUNNER_EYE_NAME = "枪手之眼"
KEY_ENEMY_GUNNER_EYE_CCID = 1122
KEY_ENEMY_GUNNER_EYE_DEFAULT_SECONDS = 5
KEY_ENEMY_GUNNER_EYE_REMAINING_SOUND = "assets/audio/xiaoyi/gunner_eye_remaining.wav"
KEY_ENEMY_GUNNER_EYE_ENDED_SOUND = "assets/audio/xiaoyi/gunner_eye_ended.wav"
KEY_ENEMY_GUNNER_EYE_REMAINING_MESSAGE = "枪手之眼"
KEY_ENEMY_GUNNER_EYE_ENDED_MESSAGE = "枪手之眼 结束"
ASTROLOGY_SOUND = "assets/audio/xiaoyi/astrology.wav"
ASTROLOGY_MESSAGE = "占星"
ASTROLOGY_BUFFS = [
    {"name": "星辰交汇-物理", "ccid": 1016},
    {"name": "星辰交汇-魔法", "ccid": 1045},
    {"name": "星辰交汇-炼金", "ccid": 1046},
]
ASTROLOGY_BUFF_NAMES = {item["name"] for item in ASTROLOGY_BUFFS}
KEY_ENEMY_DEBUFF_BOSS_MAX_HP_VALUES = [
    698517000,
    850368600,
    1143352700,
    1967880100,
    SAFEHOUSE_BOSS_MAX_HP,
    KAILAHE_PHASE_1_MAX_HP,
    KAILAHE_PHASE_2_MAX_HP,
]
BOSS_HP_DEFAULTS = [
    {
        "entity_id": "4767482429251739",
        "name": "枯木之佩塔克",
        "short_name": "布本1王",
        "max_hp_values": [698517000, 850368600],
        "thresholds": [88, 73, 58, 38, 28, 18],
    },
    {
        "entity_id": "4767482429265858",
        "name": "布隆塔纳斯",
        "short_name": "布本2王",
        "max_hp_values": [1143352700],
        "thresholds": [93, 78, 63, 53, 43, 23],
    },
    {
        "entity_id": "4767482429308981",
        "name": "雷内恩的米耶尔",
        "short_name": "布本3王",
        "max_hp_values": [1967880100],
        "thresholds": [83, 63, 43, 33, 15],
    },
    {
        "entity_id": "",
        "name": "布本四王",
        "short_name": "布本4王",
        "max_hp_values": [SAFEHOUSE_BOSS_MAX_HP],
        "thresholds": [83, 68, 53, 38],
        "safehouse_countdown_enabled": True,
        "safehouse_countdown_effect_name": SAFEHOUSE_NAME,
        "safehouse_countdown_sound_dir": BOSS_HP_SAFEHOUSE_COUNTDOWN_SOUND_DIR,
        "safehouse_countdown_message_template": BOSS_HP_SAFEHOUSE_COUNTDOWN_MESSAGE,
        "safehouse_countdown_min_seconds": 0,
        "safehouse_countdown_max_seconds": BOSS_HP_SAFEHOUSE_COUNTDOWN_MAX_SECONDS,
    },
    {
        "entity_id": "",
        "name": "凯莱赫-1阶段",
        "short_name": "雪女1阶段",
        "max_hp_values": [KAILAHE_PHASE_1_MAX_HP],
        "thresholds": [],
        "hidden": True,
        "track_only": True,
    },
    {
        "entity_id": "",
        "name": "凯莱赫-2阶段",
        "short_name": "雪女2阶段",
        "max_hp_values": [KAILAHE_PHASE_2_MAX_HP],
        "thresholds": [],
        "hidden": True,
        "track_only": True,
    },
]
AZURE_WOUND_NAME = "湛蓝内伤"
AZURE_WOUND_CCID = 1098
AZURE_WOUND_STACK_FIELD = "MCSTCT"
AZURE_WOUND_MAX_STACKS = 10
AZURE_WOUND_DEFAULT_DANGER_STACKS = 7
AZURE_WOUND_DEFAULT_DANGER_SOUND = "assets/audio/xiaoyi/azure_internal_wound_danger.wav"
AZURE_WOUND_DEFAULT_CLEAR_SOUND = "assets/audio/xiaoyi/azure_internal_wound_cleared.wav"
AZURE_WOUND_CLEAR_MIN_ACTIVE_SECONDS = 28
DEMI_GOD_NAME = "半神化"
SELF_BUFF_CIRCLE_NAME = "魔法阵"
THIRD_EYE_NAME = "第三只眼"
SPECIAL_END_ONLY_ORDER = [SELF_BUFF_CIRCLE_NAME, DEMI_GOD_NAME, THIRD_EYE_NAME]
SPECIAL_END_ONLY_DEFAULTS = {
    SELF_BUFF_CIRCLE_NAME: {
        "cooldown_seconds": 140,
        "cooldown_fixed": True,
        "cooldown_from_skill_use": True,
        "cooldown_enabled": True,
        "ended_enabled": False,
        "cooldown_sound": "assets/audio/xiaoyi/self_buff_magic_circle_cooldown.wav",
        "ended_sound": "assets/audio/xiaoyi/self_buff_magic_circle_ended.wav",
        "ended_message": "魔法阵 结束",
        "cooldown_message": "魔法阵 就绪",
    },
    DEMI_GOD_NAME: {
        "cooldown_seconds": 15,
        "cooldown_min": 15,
        "cooldown_max": 600,
        "cooldown_enabled": False,
        "ended_enabled": True,
        "cooldown_sound": "assets/audio/xiaoyi/demigod_cooldown.wav",
        "ended_sound": "assets/audio/xiaoyi/demigod_ended.wav",
        "ended_message": "半神 结束",
        "cooldown_message": "半神 就绪",
        "ended_on_remove_only": True,
        "ended_grace_seconds": 0,
        "sbt_ended_lead_seconds": 0,
        "use_dynamic_sbt_adjust": False,
    },
    THIRD_EYE_NAME: {
        "cooldown_seconds": 300,
        "cooldown_min": 240,
        "cooldown_max": 300,
        "cooldown_choices": (300, 240),
        "cooldown_from_apply": True,
        "cooldown_enabled": True,
        "ended_enabled": True,
        "cooldown_sound": "assets/audio/xiaoyi/third_eye_cooldown.wav",
        "ended_sound": "assets/audio/xiaoyi/third_eye_ended.wav",
        "ended_message": "三眼 结束",
        "cooldown_message": "三眼 就绪",
        "ended_on_remove_only": True,
        "ended_grace_seconds": 0,
        "sbt_ended_lead_seconds": 0,
        "use_dynamic_sbt_adjust": False,
    },
}
NAME_ALIASES = {
    "状态支援：逆转": "状态支援",
    "自我增益魔法阵": SELF_BUFF_CIRCLE_NAME,
}
REMAINING_LOCKED_NAMES = {MAGIC_SHIELD_NAME, *ASTROLOGY_BUFF_NAMES}

FOOD_DROP_RULES = [
    {"stat_id": 48, "min_drop": 20, "max_drop": 40},
    {"stat_id": 50, "min_drop": 10, "max_drop": 30},
    {"stat_id": 52, "min_drop": 10, "max_drop": 30},
    {"stat_id": 54, "min_drop": 10, "max_drop": 30},
    {"stat_id": 56, "min_drop": 10, "max_drop": 30},
    {"stat_id": 86, "min_drop": 8, "max_drop": 25},
    {"stat_id": 87, "min_drop": 8, "max_drop": 20},
    {"stat_id": 88, "min_drop": 30, "max_drop": 50},
    {"stat_id": 94, "min_drop": 8, "max_drop": 20},
]

DEFAULT_RULES = {
    "战争序曲": {"remaining_enabled": True, "seconds": 20},
    "活跃曲": {"remaining_enabled": True, "seconds": 20},
    "行进曲": {"remaining_enabled": True, "seconds": 20},
    "坚定意志": {"enabled": False, "remaining_enabled": False, "seconds": 30},
    "逆光剑": {"enabled": False, "remaining_enabled": False, "seconds": 30},
    "致命穿透": {"enabled": False, "remaining_enabled": False, "seconds": 30},
    "超越生命": {"enabled": False, "remaining_enabled": False, "seconds": 30},
    "负载转移": {"remaining_enabled": True, "seconds": 30},
    "半神化": {"remaining_enabled": False, "seconds": 0},
    "魔法盾": {"remaining_enabled": False, "seconds": 0},
    "圣域之主": {"remaining_enabled": True, "seconds": 10},
    "马纽斯秘药": {"remaining_enabled": False, "seconds": 0},
    "魔攻水": {"remaining_enabled": True, "seconds": 60},
    "物攻水": {"remaining_enabled": True, "seconds": 60},
    "法速水": {"remaining_enabled": True, "seconds": 60},
    "炼金水": {"remaining_enabled": True, "seconds": 60},
    "净化之浪": {"remaining_enabled": True, "seconds": 10},
    HAMSTER_SUPERCHARGED_NAME: {
        "enabled": True,
        "remaining_enabled": True,
        "seconds": HAMSTER_DEFAULT_WARNING_SECONDS,
    },
    "活力之歌": {"remaining_enabled": True, "seconds": 30},
    "状态支援": {"remaining_enabled": True, "seconds": 30},
    "生命的温度": {"remaining_enabled": True, "seconds": 10},
    "托亚灵进度": {"remaining_enabled": True, "seconds": 5},
    "枪手之眼": {"enabled": False, "remaining_enabled": False, "seconds": 5},
    "星辰交汇-物理": {"enabled": False, "remaining_enabled": False, "seconds": 0},
    "星辰交汇-魔法": {"enabled": False, "remaining_enabled": False, "seconds": 0},
    "星辰交汇-炼金": {"enabled": False, "remaining_enabled": False, "seconds": 0},
}


@dataclass
class BuffRow:
    item: dict
    enabled: BooleanVar
    remaining_enabled: BooleanVar
    seconds: IntVar
    remaining_sound: StringVar
    ended_sound: StringVar
    seconds_widget: tk.Spinbox
    remaining_toggle: tk.Checkbutton
    remaining_sound_entry: tk.Entry
    remaining_choose: tk.Button
    remaining_test: tk.Button


@dataclass
class FoodTimerRow:
    item: dict
    timer_enabled: BooleanVar
    duration_seconds: IntVar
    remaining_enabled: BooleanVar
    remaining_seconds: IntVar
    remaining_sound: StringVar
    ended_sound: StringVar
    duration_widget: tk.Spinbox
    remaining_widget: tk.Spinbox


@dataclass
class SafeHouseRow:
    item: dict
    enabled: BooleanVar
    lead_seconds: IntVar
    warning_sound: StringVar
    lead_widget: tk.Spinbox
    warning_sound_entry: tk.Entry
    warning_choose: tk.Button
    warning_test: tk.Button


@dataclass
class BossHpAlertRow:
    item: dict
    enabled: BooleanVar
    thresholds: StringVar
    sound: StringVar
    toggle: tk.Checkbutton
    thresholds_entry: tk.Entry
    sound_entry: tk.Entry
    choose: tk.Button
    test: tk.Button


@dataclass
class BossRedOrbRow:
    item: dict
    enabled: BooleanVar
    sound: StringVar
    toggle: tk.Checkbutton
    sound_entry: tk.Entry
    choose: tk.Button
    test: tk.Button
    voice_pack: tk.Button


@dataclass
class BossLaserAlertRow:
    item: dict
    enabled: BooleanVar
    sound: StringVar
    toggle: tk.Checkbutton
    sound_entry: tk.Entry
    choose: tk.Button
    test: tk.Button
    voice_pack: tk.Button


@dataclass
class KeyEnemyDebuffRow:
    item: dict
    complete_enabled: BooleanVar
    expiry_enabled: BooleanVar
    visual_hud_enabled: BooleanVar
    visual_expiry_enabled: BooleanVar
    expiry_seconds: IntVar
    physical_break_min: StringVar
    magic_break_min: StringVar
    damage_bonus_min: StringVar
    rabbit_stacks_min: StringVar
    complete_sound: StringVar
    expiry_sound: StringVar
    complete_toggle: tk.Checkbutton
    expiry_toggle: tk.Checkbutton
    visual_hud_toggle: tk.Checkbutton | None
    visual_expiry_toggle: tk.Checkbutton | None
    expiry_seconds_widget: tk.Spinbox
    physical_widget: tk.Entry
    magic_widget: tk.Entry
    damage_bonus_widget: tk.Entry
    rabbit_stacks_widget: tk.Entry
    complete_sound_entry: tk.Entry
    expiry_sound_entry: tk.Entry
    complete_choose: tk.Button
    expiry_choose: tk.Button
    complete_test: tk.Button
    expiry_test: tk.Button


@dataclass
class MagicShieldDelayRow:
    item: dict
    enabled: BooleanVar
    ended_enabled: BooleanVar
    missing_enabled: BooleanVar
    ended_sound: StringVar
    missing_sound: StringVar
    ended_grace_seconds: DoubleVar
    missing_delay_seconds: DoubleVar
    ended_toggle: tk.Checkbutton
    missing_toggle: tk.Checkbutton
    ended_sound_entry: tk.Entry
    missing_sound_entry: tk.Entry
    ended_choose: tk.Button
    missing_choose: tk.Button
    ended_test: tk.Button
    missing_test: tk.Button
    delay_widget: tk.Spinbox
    missing_delay_widget: tk.Spinbox


@dataclass
class AzureWoundRow:
    item: dict
    enabled: BooleanVar
    danger_stacks: IntVar
    danger_sound: StringVar
    clear_enabled: BooleanVar
    clear_sound: StringVar
    danger_widget: tk.Spinbox
    danger_sound_entry: tk.Entry
    danger_choose: tk.Button
    danger_test: tk.Button
    clear_toggle: tk.Checkbutton
    clear_sound_entry: tk.Entry
    clear_choose: tk.Button
    clear_test: tk.Button


@dataclass
class SpecialEndOnlyRow:
    item: dict
    enabled: BooleanVar
    ended_enabled: BooleanVar
    ended_sound: StringVar
    cooldown_enabled: BooleanVar
    cooldown_seconds: IntVar
    cooldown_sound: StringVar
    cooldown_widget: tk.Widget
    ended_toggle: tk.Checkbutton
    ended_sound_entry: tk.Entry
    ended_choose: tk.Button
    ended_test: tk.Button
    cooldown_toggle: tk.Checkbutton
    cooldown_sound_entry: tk.Entry
    cooldown_choose: tk.Button
    cooldown_test: tk.Button


@dataclass
class VisualHudRow:
    item: dict
    enabled: BooleanVar
    tuan_silence_enabled: BooleanVar
    condition_enabled: dict[int, BooleanVar]
    condition_show_before_seconds: dict[int, DoubleVar]
    condition_ring_sound_enabled: dict[int, BooleanVar]
    condition_icons: dict[int, StringVar]
    condition_toggles: dict[int, tk.Checkbutton]
    show_before_widgets: dict[int, tk.Spinbox]
    ring_toggles: dict[int, tk.Checkbutton]
    icon_entries: dict[int, tk.Entry]
    icon_choose_buttons: dict[int, tk.Button]
    icon_reset_buttons: dict[int, tk.Button]


@dataclass
class OtherSkillHudRow:
    item: dict
    enabled: BooleanVar
    condition_enabled: dict[str, BooleanVar]
    condition_icons: dict[str, StringVar]
    condition_toggles: dict[str, tk.Checkbutton]
    icon_entries: dict[str, tk.Entry]
    icon_choose_buttons: dict[str, tk.Button]
    icon_reset_buttons: dict[str, tk.Button]


@dataclass
class ShortCooldownHudRow:
    item: dict
    condition_enabled: dict[str, BooleanVar]
    cooldown_seconds: dict[str, StringVar]
    condition_icons: dict[str, StringVar]
    condition_toggles: dict[str, tk.Checkbutton]
    cooldown_widgets: dict[str, tk.Spinbox]
    icon_entries: dict[str, tk.Entry]
    icon_choose_buttons: dict[str, tk.Button]
    icon_reset_buttons: dict[str, tk.Button]


@dataclass
class AstrologyCardTrackerRow:
    item: dict
    enabled_skills: dict[int, BooleanVar]
    counter_threshold: StringVar
    deck: list[StringVar]
    skill_suits: dict[int, StringVar]
    base_cooldown_seconds: dict[int, StringVar]


def load_config(path: Path) -> dict:
    return migrate_config_file(path)


def save_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_item_name(name: object) -> object:
    if not isinstance(name, str):
        return name
    for old_name, new_name in NAME_ALIASES.items():
        if name == old_name:
            return new_name
        prefix = old_name + "/"
        if name.startswith(prefix):
            return new_name + name[len(old_name):]
    return name


def normalize_config_names(data: dict) -> None:
    for section in ("buffs", "progresses", "stat_drop_effects"):
        for item in data.get(section, []):
            item["name"] = normalize_item_name(item.get("name"))


def clamp_float(value: object, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, tk.TclError):
        return minimum
    return max(minimum, min(maximum, number))


def find_or_create_visual_hud(data: dict) -> dict:
    item = data.get(VISUAL_HUD_CONFIG_KEY)
    if not isinstance(item, dict):
        item = {}
        data[VISUAL_HUD_CONFIG_KEY] = item

    had_legacy_show_before_seconds = "show_before_seconds" in item
    try:
        condition_controls_version = int(item.get("condition_controls_version", 0))
    except (TypeError, ValueError):
        condition_controls_version = 0
    item.setdefault("enabled", True)
    item.setdefault("show_before_seconds", VISUAL_HUD_DEFAULT_SHOW_BEFORE_SECONDS)
    if "ring_sound_enabled" not in item:
        item["ring_sound_enabled"] = (
            not bool(item.get("muted")) if "muted" in item else False
        )
    legacy_show_before_seconds = clamp_float(
        item.get("show_before_seconds", VISUAL_HUD_DEFAULT_SHOW_BEFORE_SECONDS),
        VISUAL_HUD_MIN_SHOW_BEFORE_SECONDS,
        VISUAL_HUD_MAX_SHOW_BEFORE_SECONDS,
    )
    legacy_ring_sound_enabled = bool(item["ring_sound_enabled"])
    item.setdefault("entity_name", "自己")
    item.setdefault("tuan_silence_enabled", False)
    item.setdefault("arrival_sound", MUSIC_STRONG_REMINDER_PREFIX_SOUND)
    item.setdefault("three_second_sound", MUSIC_STRONG_REMINDER_PREFIX_SOUND)

    conditions = item.get("conditions")
    if not isinstance(conditions, dict):
        conditions = {}
        item["conditions"] = conditions
    conditions.pop(str(874), None)
    try:
        default_icons_version = int(item.get("default_icons_version", 0))
    except (TypeError, ValueError):
        default_icons_version = 0
    adopt_new_default_icons = (
        default_icons_version < VISUAL_HUD_DEFAULT_ICONS_VERSION
    )
    for ccid, defaults in VISUAL_HUD_CONDITION_DEFAULTS.items():
        key = str(ccid)
        condition = conditions.get(key)
        if not isinstance(condition, dict):
            condition = {}
            conditions[key] = condition
        condition.setdefault("enabled", defaults["enabled"])
        condition.setdefault("name", defaults["name"])
        condition.setdefault(
            "show_before_seconds",
            (
                legacy_show_before_seconds
                if condition_controls_version < 1
                and had_legacy_show_before_seconds
                else defaults["show_before_seconds"]
            ),
        )
        condition.setdefault("ring_sound_enabled", legacy_ring_sound_enabled)
        if adopt_new_default_icons and not str(condition.get("icon") or "").strip():
            condition["icon"] = defaults["icon"]
        else:
            condition.setdefault("icon", defaults["icon"])
    item["default_icons_version"] = VISUAL_HUD_DEFAULT_ICONS_VERSION
    item["condition_controls_version"] = 1
    item["ring_sound_enabled"] = False
    item["muted"] = False
    return item


def find_or_create_bronntanas_hp_hud(data: dict) -> dict:
    item = data.get(BRONNTANAS_HP_HUD_CONFIG_KEY)
    if not isinstance(item, dict):
        item = {}
        data[BRONNTANAS_HP_HUD_CONFIG_KEY] = item
    item.setdefault("enabled", True)
    item["icon"] = str(
        item.get("icon") or BRONNTANAS_HP_HUD_DEFAULT_ICON
    ).strip() or BRONNTANAS_HP_HUD_DEFAULT_ICON
    item["activation_percent"] = 52.0
    item["warning_percent"] = 50.0
    item["dismiss_after_seconds"] = 2.0
    item["center_y_ratio"] = 0.89
    return item


def find_or_create_miracle_orb_hp_hud(data: dict) -> dict:
    item = data.get(MIRACLE_ORB_HP_HUD_CONFIG_KEY)
    if not isinstance(item, dict):
        item = {}
        data[MIRACLE_ORB_HP_HUD_CONFIG_KEY] = item
    item.setdefault("enabled", True)
    item["left_x_ratio"] = 0.108
    item["top_y_ratio"] = 0.125
    item["focus_center_y_ratio"] = 0.855
    return item


def find_or_create_rotating_laser_countdown_hud(data: dict) -> dict:
    item = data.get(ROTATING_LASER_COUNTDOWN_HUD_CONFIG_KEY)
    if not isinstance(item, dict):
        item = {}
        data[ROTATING_LASER_COUNTDOWN_HUD_CONFIG_KEY] = item
    item.setdefault("enabled", True)
    item["center_y_ratio"] = 0.89
    return item


def visual_hud_icon(item: dict, ccid: int) -> str:
    conditions = item.get("conditions")
    if not isinstance(conditions, dict):
        return ""
    condition = conditions.get(str(ccid))
    if not isinstance(condition, dict):
        return ""
    return str(condition.get("icon") or "").strip()


def find_or_create_other_skill_hud(data: dict) -> dict:
    item = data.get(OTHER_SKILL_HUD_CONFIG_KEY)
    if not isinstance(item, dict):
        item = {}
        data[OTHER_SKILL_HUD_CONFIG_KEY] = item
    item.setdefault("enabled", False)
    item.setdefault("left_offset_px", 8)
    item.setdefault("center_y_ratio", 0.28)
    item.setdefault("gap_px", 6)
    conditions = item.get("conditions")
    if not isinstance(conditions, dict):
        conditions = {}
        item["conditions"] = conditions
    conditions.pop("hamster_adrenaline", None)
    try:
        icon_version = int(item.get("default_icons_version", 0))
    except (TypeError, ValueError):
        icon_version = 0
    adopt_default_icons = icon_version < OTHER_SKILL_HUD_DEFAULT_ICONS_VERSION
    for key, defaults in OTHER_SKILL_HUD_CONDITION_DEFAULTS.items():
        condition = conditions.get(key)
        if not isinstance(condition, dict):
            condition = {}
            conditions[key] = condition
        condition.setdefault("enabled", defaults["enabled"])
        condition.setdefault("name", defaults["name"])
        if adopt_default_icons and not str(condition.get("icon") or "").strip():
            condition["icon"] = defaults["icon"]
        else:
            condition.setdefault("icon", defaults["icon"])
    item["default_icons_version"] = OTHER_SKILL_HUD_DEFAULT_ICONS_VERSION
    return item


def other_skill_hud_icon(item: dict, key: str) -> str:
    conditions = item.get("conditions")
    if not isinstance(conditions, dict):
        return ""
    condition = conditions.get(str(key))
    if not isinstance(condition, dict):
        return ""
    return str(condition.get("icon") or "").strip()


def find_or_create_short_cooldown_hud(data: dict) -> dict:
    item = data.get(SHORT_COOLDOWN_HUD_CONFIG_KEY)
    if not isinstance(item, dict):
        item = {}
        data[SHORT_COOLDOWN_HUD_CONFIG_KEY] = item
    item.setdefault("enabled", True)
    item.setdefault("center_y_ratio", 0.715)
    item.setdefault("gap_px", 6)
    conditions = item.get("conditions")
    if not isinstance(conditions, dict):
        conditions = {}
        item["conditions"] = conditions
    try:
        icon_version = int(item.get("default_icons_version", 0))
    except (TypeError, ValueError):
        icon_version = 0
    adopt_default_icons = icon_version < SHORT_COOLDOWN_HUD_DEFAULT_ICONS_VERSION
    for key, defaults in SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS.items():
        condition = conditions.get(key)
        if not isinstance(condition, dict):
            condition = {}
            conditions[key] = condition
        condition.setdefault("enabled", defaults["enabled"])
        condition.setdefault("name", defaults["name"])
        if adopt_default_icons and not str(condition.get("icon") or "").strip():
            condition["icon"] = defaults["icon"]
        else:
            condition.setdefault("icon", defaults["icon"])
    item["default_icons_version"] = SHORT_COOLDOWN_HUD_DEFAULT_ICONS_VERSION
    return item


def short_cooldown_hud_icon(item: dict, key: str) -> str:
    conditions = item.get("conditions")
    if not isinstance(conditions, dict):
        return ""
    condition = conditions.get(str(key))
    if not isinstance(condition, dict):
        return ""
    return str(condition.get("icon") or "").strip()


def find_or_create_short_cooldown_tracker(data: dict, key: str) -> dict:
    defaults = SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS[key]
    buffs = data.setdefault("buffs", [])
    tracker_ccid = int(defaults["tracker_ccid"])
    tracker = next(
        (
            item
            for item in buffs
            if isinstance(item, dict)
            and (
                str(item.get("ccid")) == str(tracker_ccid)
                or item.get("name") == defaults["name"]
            )
        ),
        None,
    )
    if tracker is None:
        tracker = {}
        buffs.append(tracker)
    required = {
        "name": defaults["name"],
        "ccid": tracker_ccid,
        "enabled": True,
        "skill_id": int(defaults["skill_id"]),
        "self_filter": True,
        "warn_seconds": 0,
        "critical_seconds": 0,
        "alerts": [],
        "ended_alert": False,
        "cooldown_alert": False,
        "cooldown_from_skill_use": True,
        "audio_volume": 100,
    }
    tracker.update(required)
    try:
        cooldown_seconds = float(tracker.get("cooldown_delay_seconds"))
    except (TypeError, ValueError):
        cooldown_seconds = 0.0
    if cooldown_seconds <= 0:
        tracker["cooldown_delay_seconds"] = defaults["cooldown_seconds"]
    return tracker


def short_cooldown_hud_cooldown_seconds(data: dict, key: str) -> float:
    tracker = find_or_create_short_cooldown_tracker(data, key)
    return float(tracker["cooldown_delay_seconds"])


def relpath(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def first_alert(item: dict) -> dict | None:
    alerts = item.get("alerts") or []
    if not alerts:
        return None
    return alerts[0]


def find_or_create_food_effect(data: dict) -> dict:
    effects = data.setdefault("stat_drop_effects", [])
    for item in effects:
        if item.get("name") == FOOD_EFFECT_NAME:
            if not item.get("drop_rules") or not all(
                "max_drop" in rule for rule in item.get("drop_rules", [])
            ):
                item["drop_rules"] = FOOD_DROP_RULES
            item.setdefault("allow_unseen_drop", True)
            return item

    item = {
        "name": FOOD_EFFECT_NAME,
        "enabled": True,
        "trigger": {
            "event_id": 0,
            "op": "0xae04",
            "message_matches": [{"index": 0, "type": "int", "value": "5038"}],
        },
        "drop_rules": FOOD_DROP_RULES,
        "min_drop_count": 6,
        "allow_unseen_drop": True,
        "timer_enabled": False,
        "duration_seconds": 0,
        "alerts": [],
        "warn_sound": DEFAULT_WARN_SOUND,
        "ended_alert": rules.get("ended_enabled", True),
        "ended_sound": DEFAULT_ENDED_SOUND,
        "ended_message": "{name} 结束",
    }
    effects.append(item)
    return item


def safehouse_defaults() -> dict:
    return {
        "name": SAFEHOUSE_NAME,
        "enabled": True,
        "trigger": {
            "event_id": -1,
        },
        "start_stat_matches": [
            {"stat_id": 28, "value": SAFEHOUSE_BOSS_MAX_HP},
            {"stat_id": 30, "value": SAFEHOUSE_BOSS_MAX_HP},
        ],
        "stop_stat_matches": [
            {"stat_id": 28, "max_value": 0},
        ],
        "start_offset_seconds": SAFEHOUSE_FIRST_ALERTED_OCCURRENCE_SECONDS,
        "timer_sync_stat_matches": [
            {"stat_id": SAFEHOUSE_ENTITY_STAT_ID, "value": SAFEHOUSE_ENTITY_STAT_VALUE},
            {"stat_id": 28, "value": SAFEHOUSE_ENTITY_HP},
            {"stat_id": 30, "value": SAFEHOUSE_ENTITY_HP},
        ],
        "timer_sync_event_id": SAFEHOUSE_SYNC_EVENT_ID,
        "timer_sync_initial_min_delay_seconds": SAFEHOUSE_SYNC_INITIAL_MIN_SECONDS,
        "timer_sync_initial_max_delay_seconds": SAFEHOUSE_SYNC_INITIAL_MAX_SECONDS,
        "timer_sync_expected_tolerance_seconds": (
            SAFEHOUSE_SYNC_EXPECTED_TOLERANCE_SECONDS
        ),
        "timer_sync_min_interval_seconds": SAFEHOUSE_SYNC_MIN_INTERVAL_SECONDS,
        "timer_sync_max_interval_seconds": SAFEHOUSE_SYNC_MAX_INTERVAL_SECONDS,
        "trigger_dedupe_seconds": SAFEHOUSE_TRIGGER_DEDUPE_SECONDS,
        "ignore_trigger_while_active": False,
        "trigger_rearm_tolerance_seconds": 0,
        "repeat_timer": True,
        "self_filter": False,
        "drop_rules": [],
        "min_drop_count": 1,
        "allow_unseen_drop": False,
        "timer_enabled": True,
        "duration_seconds": SAFEHOUSE_INTERVAL_SECONDS,
        "alerts": [
            {
                "remaining_seconds": SAFEHOUSE_DEFAULT_LEAD_SECONDS,
                "sound": SAFEHOUSE_DEFAULT_SOUND,
                "message": "安全屋",
            }
        ],
        "warn_sound": SAFEHOUSE_DEFAULT_SOUND,
        "ended_alert": False,
        "ended_sound": DEFAULT_ENDED_SOUND,
        "ended_message": "{name} 结束",
        "audio_volume": 100,
        "observed": {
            "source_file": "20260524-003416-buffwatcher-raw.ndjson.gz",
            "note": "Boss entities with StatId 28 and StatId 30 both equal to 3449779200 mark the fight start. Safehouse timing is resynced only by full safehouse entities within the expected 61-64 second cadence window, excluding HP-mechanic entities.",
        },
    }


def find_or_create_safehouse_effect(data: dict) -> dict:
    effects = data.setdefault("stat_drop_effects", [])
    defaults = safehouse_defaults()
    for item in effects:
        if item.get("name") != SAFEHOUSE_NAME:
            continue
        item.setdefault("enabled", True)
        item["trigger"] = defaults["trigger"]
        item.pop("start_trigger", None)
        item["start_stat_matches"] = defaults["start_stat_matches"]
        item["stop_stat_matches"] = defaults["stop_stat_matches"]
        item["start_offset_seconds"] = SAFEHOUSE_FIRST_ALERTED_OCCURRENCE_SECONDS
        item["timer_sync_stat_matches"] = defaults["timer_sync_stat_matches"]
        item["timer_sync_event_id"] = SAFEHOUSE_SYNC_EVENT_ID
        item["timer_sync_initial_min_delay_seconds"] = (
            SAFEHOUSE_SYNC_INITIAL_MIN_SECONDS
        )
        item["timer_sync_initial_max_delay_seconds"] = (
            SAFEHOUSE_SYNC_INITIAL_MAX_SECONDS
        )
        item["timer_sync_expected_tolerance_seconds"] = (
            SAFEHOUSE_SYNC_EXPECTED_TOLERANCE_SECONDS
        )
        item["timer_sync_min_interval_seconds"] = SAFEHOUSE_SYNC_MIN_INTERVAL_SECONDS
        item["timer_sync_max_interval_seconds"] = SAFEHOUSE_SYNC_MAX_INTERVAL_SECONDS
        item["trigger_dedupe_seconds"] = SAFEHOUSE_TRIGGER_DEDUPE_SECONDS
        item["ignore_trigger_while_active"] = False
        item["trigger_rearm_tolerance_seconds"] = 0
        item["repeat_timer"] = True
        item["self_filter"] = False
        item["drop_rules"] = []
        item["min_drop_count"] = 1
        item["allow_unseen_drop"] = False
        item["timer_enabled"] = True
        item["duration_seconds"] = SAFEHOUSE_INTERVAL_SECONDS
        item.setdefault("alerts", defaults["alerts"])
        item.setdefault("warn_sound", SAFEHOUSE_DEFAULT_SOUND)
        item["ended_alert"] = False
        item.setdefault("ended_sound", DEFAULT_ENDED_SOUND)
        item.setdefault("ended_message", MAGIC_SHIELD_DEFAULT_ENDED_MESSAGE)
        return item

    effects.append(defaults)
    return defaults


def boss_hp_alert_item(defaults: dict) -> dict:
    item = {
        "name": defaults["name"],
        "short_name": defaults["short_name"],
        "entity_id": defaults["entity_id"],
        "max_hp_values": list(defaults.get("max_hp_values", [])),
        "enabled": True,
        "current_hp_stat_id": BOSS_HP_CURRENT_STAT_ID,
        "max_hp_stat_id": BOSS_HP_MAX_STAT_ID,
        "warn_sound": BOSS_HP_DEFAULT_SOUND,
        "alerts": [
            {
                "threshold_percent": threshold,
                "sound": BOSS_HP_DEFAULT_SOUND,
                "message": BOSS_HP_DEFAULT_MESSAGE,
            }
            for threshold in defaults["thresholds"]
        ],
        "audio_volume": 100,
        "safehouse_countdown_enabled": bool(
            defaults.get("safehouse_countdown_enabled", False)
        ),
        "safehouse_countdown_effect_name": defaults.get(
            "safehouse_countdown_effect_name", ""
        ),
        "safehouse_countdown_sound_dir": defaults.get(
            "safehouse_countdown_sound_dir", BOSS_HP_SAFEHOUSE_COUNTDOWN_SOUND_DIR
        ),
        "safehouse_countdown_message_template": defaults.get(
            "safehouse_countdown_message_template",
            BOSS_HP_SAFEHOUSE_COUNTDOWN_MESSAGE,
        ),
        "safehouse_countdown_min_seconds": int(
            defaults.get("safehouse_countdown_min_seconds", 0)
        ),
        "safehouse_countdown_max_seconds": int(
            defaults.get(
                "safehouse_countdown_max_seconds",
                BOSS_HP_SAFEHOUSE_COUNTDOWN_MAX_SECONDS,
            )
        ),
    }
    if defaults.get("hidden"):
        item["hidden"] = True
    if defaults.get("track_only"):
        item["track_only"] = True
    return item


def find_or_create_boss_hp_alerts(data: dict) -> list[dict]:
    items = data.setdefault("boss_hp_alerts", [])
    by_entity = {
        str(item.get("entity_id", item.get("id", ""))): item
        for item in items
        if item.get("entity_id") or item.get("id")
    }
    by_short_name = {
        str(item.get("short_name", "")): item
        for item in items
        if item.get("short_name")
    }
    result: list[dict] = []
    for defaults in BOSS_HP_DEFAULTS:
        entity_id = defaults["entity_id"]
        item = by_short_name.get(defaults["short_name"]) or by_entity.get(entity_id)
        if item is None:
            item = boss_hp_alert_item(defaults)
            items.append(item)
        item["entity_id"] = entity_id
        item["name"] = defaults["name"]
        item["short_name"] = defaults["short_name"]
        item["max_hp_values"] = list(defaults.get("max_hp_values", []))
        item.setdefault("enabled", True)
        item.setdefault("current_hp_stat_id", BOSS_HP_CURRENT_STAT_ID)
        item.setdefault("max_hp_stat_id", BOSS_HP_MAX_STAT_ID)
        item.setdefault("warn_sound", BOSS_HP_DEFAULT_SOUND)
        item.setdefault("audio_volume", 100)
        for key in (
            "safehouse_countdown_enabled",
            "safehouse_countdown_effect_name",
            "safehouse_countdown_sound_dir",
            "safehouse_countdown_message_template",
            "safehouse_countdown_min_seconds",
            "safehouse_countdown_max_seconds",
        ):
            if key in defaults:
                item.setdefault(key, defaults[key])
        if not item.get("alerts"):
            item["alerts"] = boss_hp_alert_item(defaults)["alerts"]
        for alert in item.get("alerts", []):
            if alert.get("threshold_percent") is None:
                alert["threshold_percent"] = alert.get("mechanic_threshold_percent", 0)
            alert.setdefault("sound", item.get("warn_sound", BOSS_HP_DEFAULT_SOUND))
            alert.setdefault("message", BOSS_HP_DEFAULT_MESSAGE)
        if defaults.get("hidden"):
            item["hidden"] = True
            item["track_only"] = bool(defaults.get("track_only", False))
            item["alerts"] = []
            item["enabled"] = True
            continue
        result.append(item)
    return result


def boss_hp_thresholds(item: dict) -> list[float]:
    values = []
    for alert in item.get("alerts", []):
        if alert.get("threshold_percent") is None:
            continue
        values.append(clamp_float(alert.get("threshold_percent"), 0.0, 100.0))
    return sorted(set(values), reverse=True)


def boss_red_orb_defaults() -> dict:
    return {
        "name": BOSS_RED_ORB_NAME,
        "enabled": True,
        "entity_id": "",
        "max_hp_values": BOSS_RED_ORB_BOSS_MAX_HP_VALUES,
        "orb_race_ids": BOSS_RED_ORB_RACE_IDS,
        "countdown_op": BOSS_RED_ORB_COUNTDOWN_OP,
        "countdown_marker": BOSS_RED_ORB_COUNTDOWN_MARKER,
        "start_step": BOSS_RED_ORB_START_STEP,
        "confirm_step": BOSS_RED_ORB_CONFIRM_STEP,
        "pair_window_ms": BOSS_RED_ORB_PAIR_WINDOW_MS,
        "explosion_delay_seconds": BOSS_RED_ORB_EXPLOSION_DELAY_SECONDS,
        "high_hp_explosion_delay_seconds": BOSS_RED_ORB_HIGH_HP_EXPLOSION_DELAY_SECONDS,
        "low_hp_explosion_delay_seconds": BOSS_RED_ORB_LOW_HP_EXPLOSION_DELAY_SECONDS,
        "lead_seconds": BOSS_RED_ORB_LEAD_SECONDS,
        "contact_check_seconds": BOSS_RED_ORB_CONTACT_CHECK_SECONDS,
        "safe_min_contact_ticks": BOSS_RED_ORB_SAFE_MIN_CONTACT_TICKS,
        "safe_last_contact_before_seconds": (
            BOSS_RED_ORB_SAFE_LAST_CONTACT_BEFORE_SECONDS
        ),
        "contact_group_ms": BOSS_RED_ORB_CONTACT_GROUP_MS,
        "hp_split_percent": BOSS_RED_ORB_HP_SPLIT_PERCENT,
        "high_hp_required_contact_ticks": BOSS_RED_ORB_HIGH_HP_REQUIRED_CONTACT_TICKS,
        "high_hp_early_check_seconds": BOSS_RED_ORB_HIGH_HP_EARLY_CHECK_SECONDS,
        "high_hp_early_max_contact_ticks": (
            BOSS_RED_ORB_HIGH_HP_EARLY_MAX_CONTACT_TICKS
        ),
        "high_hp_final_check_seconds": BOSS_RED_ORB_HIGH_HP_FINAL_CHECK_SECONDS,
        "low_hp_required_contact_ticks": BOSS_RED_ORB_LOW_HP_REQUIRED_CONTACT_TICKS,
        "low_hp_early_check_seconds": BOSS_RED_ORB_LOW_HP_EARLY_CHECK_SECONDS,
        "low_hp_early_max_contact_ticks": BOSS_RED_ORB_LOW_HP_EARLY_MAX_CONTACT_TICKS,
        "low_hp_final_check_seconds": BOSS_RED_ORB_LOW_HP_FINAL_CHECK_SECONDS,
        "late_confirm_op": BOSS_RED_ORB_LATE_CONFIRM_OP,
        "late_confirm_start_seconds": BOSS_RED_ORB_LATE_CONFIRM_START_SECONDS,
        "late_confirm_end_seconds": BOSS_RED_ORB_LATE_CONFIRM_END_SECONDS,
        "stale_seconds": BOSS_RED_ORB_STALE_SECONDS,
        "sound": BOSS_RED_ORB_SOUND,
        "safe_sound": BOSS_RED_ORB_SAFE_SOUND,
        "countdown_sounds": {
            "5": BOSS_RED_ORB_COUNTDOWN_5_SOUND,
            "4": BOSS_RED_ORB_COUNTDOWN_4_SOUND,
            "3": BOSS_RED_ORB_COUNTDOWN_3_SOUND,
            "2": BOSS_RED_ORB_COUNTDOWN_2_SOUND,
            "1": BOSS_RED_ORB_COUNTDOWN_1_SOUND,
            "0": BOSS_RED_ORB_COUNTDOWN_0_SOUND,
        },
        "message": BOSS_RED_ORB_MESSAGE,
        "audio_volume": 100,
        "note": "",
    }


def find_or_create_boss_red_orb_alert(data: dict) -> dict:
    items = data.setdefault("boss_red_orb_alerts", [])
    for item in items:
        if item.get("name") == BOSS_RED_ORB_NAME or item.get("max_hp_values") == BOSS_RED_ORB_BOSS_MAX_HP_VALUES:
            break
    else:
        item = boss_red_orb_defaults()
        items.append(item)

    defaults = boss_red_orb_defaults()
    item["name"] = BOSS_RED_ORB_NAME
    item.setdefault("enabled", defaults["enabled"])
    item["entity_id"] = defaults["entity_id"]
    item["max_hp_values"] = defaults["max_hp_values"]
    item["orb_race_ids"] = defaults["orb_race_ids"]
    item["countdown_op"] = defaults["countdown_op"]
    item["countdown_marker"] = defaults["countdown_marker"]
    item["start_step"] = defaults["start_step"]
    item["confirm_step"] = defaults["confirm_step"]
    item["pair_window_ms"] = defaults["pair_window_ms"]
    item["explosion_delay_seconds"] = defaults["explosion_delay_seconds"]
    item["high_hp_explosion_delay_seconds"] = defaults[
        "high_hp_explosion_delay_seconds"
    ]
    item["low_hp_explosion_delay_seconds"] = defaults[
        "low_hp_explosion_delay_seconds"
    ]
    item["lead_seconds"] = defaults["lead_seconds"]
    item["contact_check_seconds"] = defaults["contact_check_seconds"]
    item["safe_min_contact_ticks"] = defaults["safe_min_contact_ticks"]
    item["safe_last_contact_before_seconds"] = defaults[
        "safe_last_contact_before_seconds"
    ]
    item["contact_group_ms"] = defaults["contact_group_ms"]
    item["hp_split_percent"] = defaults["hp_split_percent"]
    item["high_hp_required_contact_ticks"] = defaults[
        "high_hp_required_contact_ticks"
    ]
    item["high_hp_early_check_seconds"] = defaults["high_hp_early_check_seconds"]
    item["high_hp_early_max_contact_ticks"] = defaults[
        "high_hp_early_max_contact_ticks"
    ]
    item["high_hp_final_check_seconds"] = defaults["high_hp_final_check_seconds"]
    item["low_hp_required_contact_ticks"] = defaults["low_hp_required_contact_ticks"]
    item["low_hp_early_check_seconds"] = defaults["low_hp_early_check_seconds"]
    item["low_hp_early_max_contact_ticks"] = defaults[
        "low_hp_early_max_contact_ticks"
    ]
    item["low_hp_final_check_seconds"] = defaults["low_hp_final_check_seconds"]
    item["late_confirm_op"] = defaults["late_confirm_op"]
    item["late_confirm_start_seconds"] = defaults["late_confirm_start_seconds"]
    item["late_confirm_end_seconds"] = defaults["late_confirm_end_seconds"]
    item["stale_seconds"] = defaults["stale_seconds"]
    item.setdefault("sound", defaults["sound"])
    item.setdefault("safe_sound", defaults["safe_sound"])
    item.setdefault("countdown_sounds", defaults["countdown_sounds"])
    item["message"] = defaults["message"]
    item.setdefault("audio_volume", 100)
    item["note"] = defaults["note"]
    return item


def boss_laser_alert_defaults() -> dict:
    return {
        "name": BOSS_LASER_ALERT_NAME,
        "enabled": False,
        "entity_id": "",
        "max_hp_values": list(BOSS_LASER_BOSS_MAX_HP_VALUES),
        "current_hp_stat_id": BOSS_HP_CURRENT_STAT_ID,
        "max_hp_stat_id": BOSS_HP_MAX_STAT_ID,
        "stardust_race_ids": list(BOSS_LASER_STARDUST_RACE_IDS),
        "cast_op": BOSS_LASER_CAST_OP,
        "skill_id": BOSS_LASER_SKILL_ID,
        "cast_seconds": BOSS_LASER_CAST_SECONDS,
        "cluster_window_ms": BOSS_LASER_CLUSTER_WINDOW_MS,
        "stale_seconds": BOSS_LASER_STALE_SECONDS,
        "sound": BOSS_LASER_ALERT_SOUND,
        "countdown_sounds": {
            "4": BOSS_LASER_COUNTDOWN_4_SOUND,
            "3": BOSS_LASER_COUNTDOWN_3_SOUND,
            "2": BOSS_LASER_COUNTDOWN_2_SOUND,
            "1": BOSS_LASER_COUNTDOWN_1_SOUND,
            "0": BOSS_LASER_COUNTDOWN_0_SOUND,
        },
        "message": BOSS_LASER_ALERT_MESSAGE,
        "audio_volume": 100,
    }


def find_or_create_boss_laser_alert(data: dict) -> dict:
    items = data.setdefault("boss_laser_alerts", [])
    for item in items:
        if item.get("name") in BOSS_LASER_ALERT_LEGACY_NAMES:
            break
    else:
        item = boss_laser_alert_defaults()
        items.append(item)

    defaults = boss_laser_alert_defaults()
    item["name"] = BOSS_LASER_ALERT_NAME
    item.setdefault("enabled", defaults["enabled"])
    item["entity_id"] = defaults["entity_id"]
    item["max_hp_values"] = defaults["max_hp_values"]
    item["current_hp_stat_id"] = defaults["current_hp_stat_id"]
    item["max_hp_stat_id"] = defaults["max_hp_stat_id"]
    item["stardust_race_ids"] = defaults["stardust_race_ids"]
    item["cast_op"] = defaults["cast_op"]
    item["skill_id"] = defaults["skill_id"]
    item["cast_seconds"] = defaults["cast_seconds"]
    item["cluster_window_ms"] = defaults["cluster_window_ms"]
    item["stale_seconds"] = defaults["stale_seconds"]
    item.setdefault("sound", defaults["sound"])
    item.setdefault("countdown_sounds", defaults["countdown_sounds"])
    item["message"] = defaults["message"]
    item.setdefault("audio_volume", 100)
    item.pop("note", None)
    return item


def music_strong_reminder_defaults() -> dict:
    return {
        "enabled": MUSIC_STRONG_REMINDER_ENABLED,
        "repeat_seconds": MUSIC_STRONG_REMINDER_REPEAT_SECONDS,
        "prefix_sound": MUSIC_STRONG_REMINDER_PREFIX_SOUND,
    }


def find_or_create_music_strong_reminder(data: dict) -> dict:
    item = data.get("music_strong_reminder")
    if not isinstance(item, dict):
        item = {}
        data["music_strong_reminder"] = item
    defaults = music_strong_reminder_defaults()
    item.setdefault("enabled", defaults["enabled"])
    item["repeat_seconds"] = defaults["repeat_seconds"]
    item.setdefault("prefix_sound", defaults["prefix_sound"])
    return item


def astrology_buff_defaults(name: str, ccid: int) -> dict:
    return {
        "name": name,
        "ccid": ccid,
        "enabled": False,
        "alerts": [],
        "warn_seconds": 0,
        "critical_seconds": 0,
        "warn_sound": ASTROLOGY_SOUND,
        "ended_alert": True,
        "ended_sound": ASTROLOGY_SOUND,
        "ended_message": ASTROLOGY_MESSAGE,
        "ended_on_remove_only": True,
        "ended_grace_seconds": 0,
        "sbt_ended_lead_seconds": 0,
        "use_dynamic_sbt_adjust": False,
        "audio_volume": 100,
    }


def find_or_create_astrology_buffs(data: dict) -> list[dict]:
    buffs = data.setdefault("buffs", [])
    result: list[dict] = []
    for spec in ASTROLOGY_BUFFS:
        name = spec["name"]
        ccid = spec["ccid"]
        item = next(
            (
                existing
                for existing in buffs
                if existing.get("name") == name or existing.get("ccid") == ccid
            ),
            None,
        )
        defaults = astrology_buff_defaults(name, ccid)
        if item is None:
            item = defaults.copy()
            buffs.append(item)
        item["name"] = name
        item["ccid"] = ccid
        item.setdefault("enabled", defaults["enabled"])
        item["alerts"] = []
        item["warn_seconds"] = 0
        item["critical_seconds"] = 0
        item.setdefault("warn_sound", ASTROLOGY_SOUND)
        item.setdefault("ended_alert", True)
        item.setdefault("ended_sound", ASTROLOGY_SOUND)
        item["ended_message"] = ASTROLOGY_MESSAGE
        item["ended_on_remove_only"] = True
        item["ended_grace_seconds"] = 0
        item["sbt_ended_lead_seconds"] = 0
        item["use_dynamic_sbt_adjust"] = False
        item.setdefault("audio_volume", 100)
        result.append(item)
    return result


def key_enemy_debuff_defaults() -> dict:
    return {
        "name": KEY_ENEMY_DEBUFF_SECTION_NAME,
        "complete_enabled": False,
        "expiry_enabled": True,
        "visual_hud_enabled": False,
        "visual_expiry_enabled": True,
        "expiry_seconds": KEY_ENEMY_DEBUFF_DEFAULT_EXPIRY_SECONDS,
        "complete_sound": KEY_ENEMY_DEBUFF_COMPLETE_SOUND,
        "complete_message": KEY_ENEMY_DEBUFF_COMPLETE_MESSAGE,
        "expiry_sound": KEY_ENEMY_DEBUFF_EXPIRY_SOUND,
        "expiry_message": KEY_ENEMY_DEBUFF_EXPIRY_MESSAGE,
        "physical_break_min": None,
        "magic_break_min": None,
        "damage_bonus_min": None,
        "rabbit_stacks_min": None,
        "max_hp_values": list(KEY_ENEMY_DEBUFF_BOSS_MAX_HP_VALUES),
        "current_hp_stat_id": BOSS_HP_CURRENT_STAT_ID,
        "max_hp_stat_id": BOSS_HP_MAX_STAT_ID,
        "audio_volume": 100,
        "watched_debuffs": [key_enemy_gunner_eye_defaults()],
    }


KEY_ENEMY_DEBUFF_THRESHOLD_FIELDS = (
    ("physical_break_min", "物理破坏", 0, 999),
    ("magic_break_min", "魔法破坏", 0, 999),
    ("damage_bonus_min", "死亡锁定增伤", 0, 999),
    ("rabbit_stacks_min", "兔子层数", 1, 10),
)


def key_enemy_debuff_threshold_text(value: object) -> str:
    if value is None or not str(value).strip():
        return ""
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return str(value).strip()
    return str(number)


def parse_key_enemy_debuff_threshold_values(
    values: dict[str, object],
    *,
    require_complete: bool,
) -> dict[str, int | None]:
    parsed: dict[str, int | None] = {}
    missing: list[str] = []
    for key, label, minimum, maximum in KEY_ENEMY_DEBUFF_THRESHOLD_FIELDS:
        raw = str(values.get(key, "") or "").strip()
        if not raw:
            parsed[key] = None
            missing.append(label)
            continue
        try:
            number = int(raw)
        except ValueError as exc:
            raise ValueError(f"“{label}”必须填写整数。") from exc
        if not minimum <= number <= maximum:
            raise ValueError(f"“{label}”必须填写 {minimum}–{maximum} 之间的整数。")
        parsed[key] = number
    if require_complete and missing:
        raise ValueError(
            "启用破防上齐提醒前，必须完整填写四项预期破防数值："
            + "、".join(label for _key, label, _min, _max in KEY_ENEMY_DEBUFF_THRESHOLD_FIELDS)
            + "。"
        )
    return parsed


def key_enemy_gunner_eye_defaults() -> dict:
    return {
        "name": KEY_ENEMY_GUNNER_EYE_NAME,
        "ccids": [KEY_ENEMY_GUNNER_EYE_CCID],
        "enabled": False,
        "remaining_enabled": False,
        "remaining_seconds": KEY_ENEMY_GUNNER_EYE_DEFAULT_SECONDS,
        "remaining_sound": KEY_ENEMY_GUNNER_EYE_REMAINING_SOUND,
        "remaining_message": KEY_ENEMY_GUNNER_EYE_REMAINING_MESSAGE,
        "ended_enabled": False,
        "ended_sound": KEY_ENEMY_GUNNER_EYE_ENDED_SOUND,
        "ended_message": KEY_ENEMY_GUNNER_EYE_ENDED_MESSAGE,
    }


def find_or_create_key_enemy_gunner_eye(item: dict) -> dict:
    defaults = key_enemy_gunner_eye_defaults()
    watched = item.setdefault("watched_debuffs", [])
    if not isinstance(watched, list):
        watched = []
        item["watched_debuffs"] = watched
    for entry in watched:
        if not isinstance(entry, dict):
            continue
        if entry.get("name") == KEY_ENEMY_GUNNER_EYE_NAME:
            break
        raw_ccids = entry.get("ccids", entry.get("ccid", []))
        if isinstance(raw_ccids, (int, str)):
            raw_ccids = [raw_ccids]
        if KEY_ENEMY_GUNNER_EYE_CCID in {
            int(ccid) for ccid in raw_ccids if str(ccid).strip().isdigit()
        }:
            break
    else:
        entry = defaults.copy()
        watched.append(entry)

    legacy_disabled = entry.get("enabled") is False
    for key, value in defaults.items():
        entry.setdefault(key, value)
    entry["name"] = KEY_ENEMY_GUNNER_EYE_NAME
    entry["ccids"] = [KEY_ENEMY_GUNNER_EYE_CCID]
    if legacy_disabled:
        entry["remaining_enabled"] = False
        entry["ended_enabled"] = False
    else:
        entry.setdefault("remaining_enabled", defaults["remaining_enabled"])
        entry.setdefault("ended_enabled", defaults["ended_enabled"])
    entry["remaining_message"] = KEY_ENEMY_GUNNER_EYE_REMAINING_MESSAGE
    entry["ended_message"] = KEY_ENEMY_GUNNER_EYE_ENDED_MESSAGE
    return entry


def find_or_create_key_enemy_debuff_alert(data: dict) -> dict:
    defaults = key_enemy_debuff_defaults()
    item = data.get("key_enemy_debuff_alert")
    if not isinstance(item, dict):
        item = {}
        data["key_enemy_debuff_alert"] = item

    item["name"] = KEY_ENEMY_DEBUFF_SECTION_NAME
    for key, value in defaults.items():
        item.setdefault(key, value)
    item["max_hp_values"] = list(KEY_ENEMY_DEBUFF_BOSS_MAX_HP_VALUES)
    item["current_hp_stat_id"] = BOSS_HP_CURRENT_STAT_ID
    item["max_hp_stat_id"] = BOSS_HP_MAX_STAT_ID
    item.setdefault("audio_volume", 100)
    find_or_create_key_enemy_gunner_eye(item)
    return item


def format_thresholds(values: list[float]) -> str:
    parts = []
    for value in values:
        if float(value).is_integer():
            parts.append(str(int(value)))
        else:
            parts.append(f"{value:g}")
    return ", ".join(parts)


def parse_thresholds_text(text: str) -> list[float]:
    normalized = text.replace("%", " ").replace("，", ",").replace("、", ",")
    for separator in (";", "；", "\n", "\t", " "):
        normalized = normalized.replace(separator, ",")
    values: list[float] = []
    seen: set[float] = set()
    for raw in normalized.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            value = max(0.0, min(100.0, float(raw)))
        except ValueError:
            continue
        key = round(value, 3)
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
    return sorted(values, reverse=True)


def azure_wound_defaults() -> dict:
    return {
        "name": AZURE_WOUND_NAME,
        "ccid": AZURE_WOUND_CCID,
        "enabled": True,
        "stack_field": AZURE_WOUND_STACK_FIELD,
        "max_stacks": AZURE_WOUND_MAX_STACKS,
        "warn_seconds": 0,
        "critical_seconds": 0,
        "alerts": [],
        "warn_sound": AZURE_WOUND_DEFAULT_DANGER_SOUND,
        "stack_alert": {
            "enabled": True,
            "stacks": AZURE_WOUND_DEFAULT_DANGER_STACKS,
            "sound": AZURE_WOUND_DEFAULT_DANGER_SOUND,
            "message": "{name} 达到危险层数",
        },
        "clear_after_stack_alert": True,
        "clear_sound": AZURE_WOUND_DEFAULT_CLEAR_SOUND,
        "clear_message": "{name} 已清除",
        "clear_grace_seconds": 1.5,
        "clear_after_stack_min_active_seconds": AZURE_WOUND_CLEAR_MIN_ACTIVE_SECONDS,
        "ended_alert": False,
        "audio_volume": 100,
        "observed": {
            "source_file": "20260521-231251-buffwatcher-raw.ndjson.gz",
            "note": "玩家自身 debuff；EventId 4 / CCId 1098，ExtraData.MCSTCT 为层数，最高按 10 层处理；短时间内的 EventId 5 后紧接新 EventId 4 视为叠层刷新，最终 EventId 5 视为自然清除候选。",
        },
    }


def find_or_create_azure_wound(data: dict) -> dict:
    buffs = data.setdefault("buffs", [])
    defaults = azure_wound_defaults()
    for item in buffs:
        if item.get("name") != AZURE_WOUND_NAME:
            continue
        item.setdefault("ccid", AZURE_WOUND_CCID)
        item.setdefault("stack_field", AZURE_WOUND_STACK_FIELD)
        item.setdefault("max_stacks", AZURE_WOUND_MAX_STACKS)
        item.setdefault("warn_sound", AZURE_WOUND_DEFAULT_DANGER_SOUND)
        item.setdefault("stack_alert", defaults["stack_alert"])
        item.setdefault("clear_after_stack_alert", True)
        item.setdefault("clear_sound", AZURE_WOUND_DEFAULT_CLEAR_SOUND)
        item.setdefault("clear_message", "{name} 已清除")
        item.setdefault("clear_grace_seconds", 1.5)
        item.setdefault(
            "clear_after_stack_min_active_seconds",
            AZURE_WOUND_CLEAR_MIN_ACTIVE_SECONDS,
        )
        item["ended_alert"] = False
        item["alerts"] = []
        return item

    buffs.append(defaults)
    return defaults


def special_defaults(name: str) -> dict:
    rules = SPECIAL_END_ONLY_DEFAULTS[name]
    if name == SELF_BUFF_CIRCLE_NAME:
        ccid = 10133
        skill_id = 10103
        linked_ccids = [10138, 10137]
    elif name == DEMI_GOD_NAME:
        ccid = 78
        skill_id = None
        linked_ccids = []
    else:
        ccid = 521
        skill_id = None
        linked_ccids = []
    item = {
        "name": name,
        "ccid": ccid,
        "enabled": True,
        "warn_seconds": 0,
        "critical_seconds": 0,
        "alerts": [],
        "ended_alert": bool(rules.get("ended_enabled", True)),
        "ended_sound": rules["ended_sound"],
        "ended_message": rules["ended_message"],
        "cooldown_alert": rules["cooldown_enabled"],
        "cooldown_delay_seconds": rules["cooldown_seconds"],
        "cooldown_sound": rules["cooldown_sound"],
        "cooldown_message": rules["cooldown_message"],
        "audio_volume": 100,
    }
    if rules.get("cooldown_from_apply"):
        item["cooldown_from_apply"] = True
    if rules.get("cooldown_from_skill_use"):
        item["cooldown_from_skill_use"] = True
    if rules.get("ended_on_remove_only"):
        item["ended_on_remove_only"] = True
    if "ended_grace_seconds" in rules:
        item["ended_grace_seconds"] = rules["ended_grace_seconds"]
    if "sbt_ended_lead_seconds" in rules:
        item["sbt_ended_lead_seconds"] = rules["sbt_ended_lead_seconds"]
    if "use_dynamic_sbt_adjust" in rules:
        item["use_dynamic_sbt_adjust"] = rules["use_dynamic_sbt_adjust"]
    if skill_id is not None:
        item["skill_id"] = skill_id
    if linked_ccids:
        item["linked_ccids"] = linked_ccids
    return item


def find_or_create_special_end_only(data: dict, name: str) -> dict:
    buffs = data.setdefault("buffs", [])
    defaults = special_defaults(name)
    rules = SPECIAL_END_ONLY_DEFAULTS[name]
    for item in buffs:
        if item.get("name") != name:
            continue
        item.setdefault("enabled", True)
        item.setdefault("alerts", [])
        item.setdefault("warn_seconds", 0)
        item.setdefault("critical_seconds", 0)
        item.setdefault("ended_alert", rules.get("ended_enabled", True))
        item.setdefault("ended_sound", rules["ended_sound"])
        item.setdefault("ended_message", rules["ended_message"])
        item.setdefault("cooldown_alert", rules["cooldown_enabled"])
        item.setdefault("cooldown_delay_seconds", rules["cooldown_seconds"])
        if rules.get("cooldown_from_apply"):
            item["cooldown_from_apply"] = True
            try:
                cooldown_seconds = int(float(item.get("cooldown_delay_seconds")))
            except (TypeError, ValueError):
                cooldown_seconds = None
            if cooldown_seconds not in rules["cooldown_choices"]:
                item["cooldown_delay_seconds"] = rules["cooldown_seconds"]
        if rules.get("cooldown_from_skill_use"):
            item["cooldown_from_skill_use"] = True
            item.pop("cooldown_from_apply", None)
        if rules.get("cooldown_fixed"):
            item["cooldown_delay_seconds"] = rules["cooldown_seconds"]
        item.setdefault("cooldown_sound", rules["cooldown_sound"])
        item.setdefault("cooldown_message", rules["cooldown_message"])
        if rules.get("ended_on_remove_only"):
            item.setdefault("ended_on_remove_only", True)
        if "ended_grace_seconds" in rules:
            item.setdefault("ended_grace_seconds", rules["ended_grace_seconds"])
        if "sbt_ended_lead_seconds" in rules:
            item.setdefault("sbt_ended_lead_seconds", rules["sbt_ended_lead_seconds"])
        if "use_dynamic_sbt_adjust" in rules:
            item.setdefault("use_dynamic_sbt_adjust", rules["use_dynamic_sbt_adjust"])
        if name == SELF_BUFF_CIRCLE_NAME:
            item.setdefault("skill_id", 10103)
            item.setdefault("linked_ccids", [10138, 10137])
        return item

    buffs.append(defaults)
    return defaults


def food_alert(item: dict) -> dict | None:
    alerts = item.get("alerts") or []
    if not alerts:
        return None
    return alerts[0]


def food_remaining_seconds(item: dict) -> int:
    alert = food_alert(item)
    if alert:
        return int(alert.get("remaining_seconds", FOOD_DEFAULT_WARNING_SECONDS))
    return FOOD_DEFAULT_WARNING_SECONDS


def food_remaining_sound(item: dict) -> str:
    alert = food_alert(item)
    if alert:
        return alert.get("sound", DEFAULT_WARN_SOUND)
    return item.get("warn_sound", DEFAULT_WARN_SOUND)


def safehouse_alert(item: dict) -> dict | None:
    alerts = item.get("alerts") or []
    if not alerts:
        return None
    return alerts[0]


def safehouse_lead_seconds(item: dict) -> int:
    alert = safehouse_alert(item)
    if alert:
        try:
            value = int(float(alert.get("remaining_seconds", SAFEHOUSE_DEFAULT_LEAD_SECONDS)))
        except (TypeError, ValueError):
            value = SAFEHOUSE_DEFAULT_LEAD_SECONDS
    else:
        value = SAFEHOUSE_DEFAULT_LEAD_SECONDS
    return max(SAFEHOUSE_MIN_LEAD_SECONDS, min(SAFEHOUSE_MAX_LEAD_SECONDS, value))


def safehouse_warning_sound(item: dict) -> str:
    alert = safehouse_alert(item)
    if alert:
        return alert.get("sound", SAFEHOUSE_DEFAULT_SOUND)
    return item.get("warn_sound", SAFEHOUSE_DEFAULT_SOUND)


def item_is_progress(item: dict) -> bool:
    return "stat_id" in item


def item_remaining_locked(item: dict) -> bool:
    return item.get("name") in REMAINING_LOCKED_NAMES


def item_remaining_enabled(item: dict) -> bool:
    if item_remaining_locked(item):
        return False
    if "remaining_enabled" in item:
        return bool(item.get("remaining_enabled", False))
    return bool(item.get("alerts") or [])


def item_seconds(item: dict) -> int:
    if item_remaining_locked(item):
        return 0
    if "remaining_seconds" in item:
        return int(float(item.get("remaining_seconds", 30)))
    alert = first_alert(item)
    if alert:
        if item_is_progress(item):
            return int(float(alert.get("remaining_progress", 5)))
        return int(alert.get("remaining_seconds", 30))
    return int(DEFAULT_RULES.get(item.get("name"), {"seconds": 30})["seconds"])


def item_remaining_sound(item: dict) -> str:
    alert = first_alert(item)
    if alert:
        return alert.get("sound", DEFAULT_WARN_SOUND)
    if "remaining_sound" in item:
        return item.get("remaining_sound", DEFAULT_WARN_SOUND)
    return item.get("warn_sound", DEFAULT_WARN_SOUND)


def item_ended_sound(item: dict) -> str:
    if item_is_progress(item):
        return "无结束提醒"
    return item.get("ended_sound", DEFAULT_ENDED_SOUND)


def magic_shield_ended_grace_seconds(item: dict) -> float:
    return clamp_float(
        item.get("ended_grace_seconds", MAGIC_SHIELD_DEFAULT_ENDED_GRACE_SECONDS),
        0.0,
        MAGIC_SHIELD_MAX_ENDED_GRACE_SECONDS,
    )


def magic_shield_missing_defaults() -> dict:
    return {
        "enabled": False,
        "delay_seconds": MAGIC_SHIELD_DEFAULT_MISSING_DELAY_SECONDS,
        "repeat_seconds": MAGIC_SHIELD_DEFAULT_MISSING_REPEAT_SECONDS,
        "sound": MAGIC_SHIELD_DEFAULT_MISSING_SOUND,
        "message": MAGIC_SHIELD_DEFAULT_MISSING_MESSAGE,
    }


def ensure_magic_shield_missing_alert(item: dict) -> dict:
    current = item.get("missing_shield_alert")
    if not isinstance(current, dict):
        current = {}
        item["missing_shield_alert"] = current
    for key, value in magic_shield_missing_defaults().items():
        current.setdefault(key, value)
    return current


def magic_shield_missing_delay_seconds(item: dict) -> float:
    alert = ensure_magic_shield_missing_alert(item)
    return clamp_float(
        alert.get("delay_seconds", MAGIC_SHIELD_DEFAULT_MISSING_DELAY_SECONDS),
        0.0,
        MAGIC_SHIELD_MAX_MISSING_DELAY_SECONDS,
    )


def magic_shield_missing_sound(item: dict) -> str:
    alert = ensure_magic_shield_missing_alert(item)
    return alert.get("sound", MAGIC_SHIELD_DEFAULT_MISSING_SOUND)


def find_or_create_magic_shield(data: dict) -> dict:
    buffs = data.setdefault("buffs", [])
    for item in buffs:
        if item.get("name") != MAGIC_SHIELD_NAME:
            continue
        item.setdefault("ccid", 59)
        item.setdefault("enabled", True)
        item.setdefault("alerts", [])
        item.setdefault("warn_seconds", 0)
        item.setdefault("critical_seconds", 0)
        item.setdefault("ended_alert", True)
        item.setdefault("ended_sound", MAGIC_SHIELD_DEFAULT_ENDED_SOUND)
        item.setdefault("ended_message", MAGIC_SHIELD_DEFAULT_ENDED_MESSAGE)
        item.setdefault(
            "ended_grace_seconds", MAGIC_SHIELD_DEFAULT_ENDED_GRACE_SECONDS
        )
        ensure_magic_shield_missing_alert(item)
        return item

    item = {
        "name": MAGIC_SHIELD_NAME,
        "ccid": 59,
        "enabled": True,
        "alerts": [],
        "warn_seconds": 0,
        "critical_seconds": 0,
        "ended_alert": True,
        "ended_sound": MAGIC_SHIELD_DEFAULT_ENDED_SOUND,
        "ended_message": MAGIC_SHIELD_DEFAULT_ENDED_MESSAGE,
        "ended_grace_seconds": MAGIC_SHIELD_DEFAULT_ENDED_GRACE_SECONDS,
        "audio_volume": 100,
        "missing_shield_alert": magic_shield_missing_defaults(),
    }
    buffs.append(item)
    return item


def alert_message(name: str) -> str:
    if name == "托亚灵进度":
        return "托亚灵震爆 即将发生"
    return "{name}"


class SettingsApp:
    def __init__(self, root: Tk, config_path: Path) -> None:
        self.root = root
        self.config_path = config_path.resolve()
        self.config_dir = self.config_path.parent
        self.data = load_config(self.config_path)
        normalize_config_names(self.data)
        self.rows: list[BuffRow] = []
        self.food_timer: FoodTimerRow | None = None
        self.safehouse: SafeHouseRow | None = None
        self.boss_hp_rows: list[BossHpAlertRow] = []
        self.bronntanas_hp_hud_enabled: BooleanVar | None = None
        self.miracle_orb_hp_hud_enabled: BooleanVar | None = None
        self.rotating_laser_countdown_hud_enabled: BooleanVar | None = None
        self.key_enemy_debuff: KeyEnemyDebuffRow | None = None
        self.gunner_eye_row: BuffRow | None = None
        self.music_strong_enabled: BooleanVar | None = None
        self.music_tuan_silence_enabled: BooleanVar | None = None
        self.visual_hud: VisualHudRow | None = None
        self.other_skill_hud: OtherSkillHudRow | None = None
        self.short_cooldown_hud: ShortCooldownHudRow | None = None
        self.astrology_card_tracker: AstrologyCardTrackerRow | None = None
        self.boss_red_orb: BossRedOrbRow | None = None
        self.boss_laser: BossLaserAlertRow | None = None
        self.magic_shield_delay: MagicShieldDelayRow | None = None
        self.azure_wound: AzureWoundRow | None = None
        self.special_end_only_rows: list[SpecialEndOnlyRow] = []
        self.notebook: ttk.Notebook | None = None
        self.tab_frames: dict[str, tk.Frame] = {}
        self.tab_scroll_canvases: dict[str, tk.Canvas] = {}
        self.tab_scroll_contents: dict[str, tk.Frame] = {}
        self.tab_scroll_windows: dict[str, int] = {}
        self.scroll_canvas: tk.Canvas | None = None
        self.scroll_content: tk.Frame | None = None
        self.scroll_window: int | None = None
        self.volume_row: tk.Frame | None = None
        self.volume = IntVar(value=normalize_volume(self.data.get("audio_volume", 100)))

        root.title(f"{package_title()} 设置")
        root.minsize(900, 520)
        root.configure(bg=ROOT_BACKGROUND)
        self._set_default_geometry()
        self._set_window_icon()
        try:
            root.attributes("-alpha", 0.96)
        except tk.TclError:
            pass

        self._build()

    def _set_default_geometry(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1280, max(960, screen_w - 160))
        height = min(780, max(560, screen_h - 180))
        self.root.geometry(f"{int(width)}x{int(height)}")

    def _build(self) -> None:
        colors = self._colors()
        outer = tk.Frame(self.root, bg=colors["panel"], bd=1, relief="solid")
        outer.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        title = tk.Frame(outer, bg=colors["title"], height=42)
        title.grid(row=0, column=0, sticky="ew")
        title.grid_propagate(False)
        tk.Label(
            title,
            text="BUFF 提醒设置",
            bg=colors["title"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 13, "bold"),
            anchor="w",
        ).pack(side="left", padx=18)

        self._configure_notebook_style()
        notebook = ttk.Notebook(outer, style="Settings.TNotebook")
        notebook.grid(row=1, column=0, sticky="nsew", padx=18, pady=(14, 10))
        self.notebook = notebook
        general_main = self._create_scrollable_tab(notebook, SETTINGS_TAB_GENERAL)
        dungeon_main = self._create_scrollable_tab(notebook, SETTINGS_TAB_DUNGEON)
        self.visual_hud_available = (
            SETTINGS_TAB_VISUAL_HUD in settings_tab_titles(self.data)
        )
        visual_main = (
            self._create_scrollable_tab(notebook, SETTINGS_TAB_VISUAL_HUD)
            if self.visual_hud_available
            else None
        )
        short_cooldown_main = (
            self._create_scrollable_tab(notebook, SETTINGS_TAB_SHORT_COOLDOWN)
            if SETTINGS_TAB_SHORT_COOLDOWN in settings_tab_titles(self.data)
            else None
        )
        astrology_main = (
            self._create_scrollable_tab(notebook, SETTINGS_TAB_ASTROLOGY)
            if SETTINGS_TAB_ASTROLOGY in settings_tab_titles(self.data)
            else None
        )
        notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        ensure_hamster_buff_items(self.data)
        find_or_create_astrology_buffs(self.data)
        key_enemy_item = find_or_create_key_enemy_debuff_alert(self.data)
        gunner_eye_item = find_or_create_key_enemy_gunner_eye(key_enemy_item)
        gunner_eye_item["_key_enemy_watched_debuff"] = True
        items_by_name = {
            item.get("name"): item
            for item in self.data.get("buffs", [])
            if item.get("name") in BUFF_ORDER
            or item.get("name") == HAMSTER_SUPERCHARGED_NAME
        }
        hamster_item = items_by_name.get(HAMSTER_SUPERCHARGED_NAME)
        if hamster_item is not None:
            items_by_name[HAMSTER_SETTINGS_NAME] = hamster_item
        items_by_name[KEY_ENEMY_GUNNER_EYE_NAME] = gunner_eye_item
        progress_by_name = {
            item.get("name"): item
            for item in self.data.get("progresses", [])
            if item.get("name") in PROGRESS_ORDER
        }

        content_row = 0
        for group_name, names in BUFF_GROUPS:
            self._build_buff_group(
                general_main,
                content_row,
                group_name,
                names,
                items_by_name,
                seconds_header="秒",
            )
            content_row += 1

        self._build_buff_group(
            general_main,
            content_row,
            "托亚灵震爆",
            PROGRESS_ORDER,
            progress_by_name,
            seconds_header="进度%",
            progress_mode=True,
        )
        content_row += 1

        self._build_magic_shield_delay(general_main, content_row)
        content_row += 1
        self._build_key_enemy_debuff_alert(general_main, content_row)
        content_row += 1
        self._build_special_end_only(general_main, content_row)
        content_row += 1
        self._build_food_timer(general_main, content_row)

        dungeon_row = 0
        self._build_azure_wound(dungeon_main, dungeon_row)
        dungeon_row += 1
        self._build_safehouse(dungeon_main, dungeon_row)
        dungeon_row += 1
        self._build_boss_hp_alerts(dungeon_main, dungeon_row)
        dungeon_row += 1
        if BRONNTANAS_HP_HUD_CONFIG_KEY in self.data:
            self._build_bronntanas_hp_hud(dungeon_main, dungeon_row)
            dungeon_row += 1
        if MIRACLE_ORB_HP_HUD_CONFIG_KEY in self.data:
            self._build_miracle_orb_hp_hud(dungeon_main, dungeon_row)
            dungeon_row += 1
        if ROTATING_LASER_COUNTDOWN_HUD_CONFIG_KEY in self.data:
            self._build_rotating_laser_countdown_hud(dungeon_main, dungeon_row)
            dungeon_row += 1
        self._build_boss_red_orb(dungeon_main, dungeon_row)
        dungeon_row += 1
        self._build_boss_laser(dungeon_main, dungeon_row)

        if visual_main is not None:
            visual_row = 0
            self._build_visual_hud(visual_main, visual_row)
            visual_row += 1
            self._build_other_skill_hud(visual_main, visual_row)
            visual_row += 1
            self._build_visual_debuff_expiry(visual_main, visual_row)

        if short_cooldown_main is not None:
            self._build_short_cooldown_hud(short_cooldown_main, 0)

        if astrology_main is not None:
            self._build_astrology_card_tracker(astrology_main, 0)

        volume_row = self._row_frame(outer)
        self.volume_row = volume_row
        volume_row.grid(row=2, column=0, sticky="ew", padx=18, pady=(2, 14))
        volume_row.columnconfigure(1, weight=1)
        tk.Label(
            volume_row,
            text="提醒音量",
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            width=12,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(12, 4), pady=8)
        tk.Scale(
            volume_row,
            from_=0,
            to=100,
            variable=self.volume,
            orient="horizontal",
            bg=colors["row"],
            fg=colors["text"],
            troughcolor=colors["input"],
            activebackground=colors["accent"],
            highlightthickness=0,
            bd=0,
        ).grid(row=0, column=1, sticky="ew", padx=8)
        self.volume_label = tk.Label(
            volume_row,
            width=5,
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.volume_label.grid(row=0, column=2, sticky="e", padx=(4, 12))
        self._button(volume_row, "恢复默认规则", self.restore_defaults).grid(
            row=0, column=3, padx=(6, 0), pady=7
        )
        self._button(volume_row, "保存并关闭", self.save_and_close).grid(
            row=0, column=4, padx=(8, 0), pady=7
        )
        self._button(volume_row, "保存", self.save, primary=True).grid(
            row=0, column=5, padx=(8, 12), pady=7
        )
        self.volume.trace_add("write", lambda *_: self._sync_volume_label())
        self._sync_volume_label()

    def _configure_notebook_style(self) -> None:
        colors = self._colors()
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Settings.TNotebook",
            background=colors["content"],
            borderwidth=0,
            tabmargins=(0, 0, 0, 0),
        )
        style.configure(
            "Settings.TNotebook.Tab",
            background=colors["button"],
            foreground=colors["text"],
            padding=(15, 6),
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        style.map(
            "Settings.TNotebook.Tab",
            background=[
                ("selected", colors["title"]),
                ("active", colors["accent"]),
            ],
            foreground=[("selected", colors["accent_dark"])],
            padding=[("selected", (22, 10))],
            font=[("selected", ("Microsoft YaHei UI", 11, "bold"))],
        )

    def _create_scrollable_tab(
        self,
        notebook: ttk.Notebook,
        title: str,
    ) -> tk.Frame:
        colors = self._colors()
        tab = tk.Frame(notebook, bg=colors["content"], bd=0)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        notebook.add(tab, text=title)

        scroll_host = tk.Frame(tab, bg=colors["content"], bd=1, relief="solid")
        scroll_host.grid(row=0, column=0, sticky="nsew")
        scroll_host.columnconfigure(0, weight=1)
        scroll_host.rowconfigure(0, weight=1)
        canvas = tk.Canvas(
            scroll_host,
            bg=colors["content"],
            highlightthickness=0,
            bd=0,
        )
        vbar = tk.Scrollbar(scroll_host, orient="vertical", command=canvas.yview)
        hbar = tk.Scrollbar(scroll_host, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")

        content = tk.Frame(canvas, bg=colors["content"], bd=0)
        content.columnconfigure(0, weight=1)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        tab_id = str(tab)
        self.tab_frames[title] = tab
        self.tab_scroll_canvases[tab_id] = canvas
        self.tab_scroll_contents[tab_id] = content
        self.tab_scroll_windows[tab_id] = window_id
        content.bind(
            "<Configure>",
            lambda _event, c=canvas, w=content, i=window_id: self._sync_scroll_region_for(
                c, w, i
            ),
        )
        canvas.bind(
            "<Configure>",
            lambda _event, c=canvas, w=content, i=window_id: self._sync_scroll_region_for(
                c, w, i
            ),
        )
        if self.scroll_canvas is None:
            self.scroll_canvas = canvas
            self.scroll_content = content
            self.scroll_window = window_id
        return content

    # Settings copy rule: unless the user explicitly requests it, new sections
    # contain only titles, controls, field labels, and units—no explanatory text.
    def _build_visual_hud(self, parent: tk.Frame, row_index: int) -> None:
        colors = self._colors()
        item = find_or_create_visual_hud(self.data)
        enabled = BooleanVar(value=bool(item.get("enabled", True)))
        tuan_silence_enabled = BooleanVar(
            value=bool(item.get("tuan_silence_enabled", False))
        )
        conditions = item["conditions"]
        condition_enabled = {
            ccid: BooleanVar(value=bool(conditions[str(ccid)].get("enabled", True)))
            for ccid in VISUAL_HUD_CONDITION_DEFAULTS
        }
        condition_show_before_seconds = {
            ccid: DoubleVar(
                value=clamp_float(
                    conditions[str(ccid)].get(
                        "show_before_seconds",
                        VISUAL_HUD_DEFAULT_SHOW_BEFORE_SECONDS,
                    ),
                    VISUAL_HUD_MIN_SHOW_BEFORE_SECONDS,
                    VISUAL_HUD_MAX_SHOW_BEFORE_SECONDS,
                )
            )
            for ccid in VISUAL_HUD_CONDITION_DEFAULTS
        }
        condition_ring_sound_enabled = {
            ccid: BooleanVar(
                value=bool(
                    conditions[str(ccid)].get("ring_sound_enabled", False)
                )
            )
            for ccid in VISUAL_HUD_CONDITION_DEFAULTS
        }
        condition_icons = {
            ccid: StringVar(value=visual_hud_icon(item, ccid))
            for ccid in VISUAL_HUD_CONDITION_DEFAULTS
        }

        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col, weight in [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),
            (4, 1),
            (5, 1),
            (6, 0),
            (7, 0),
        ]:
            section.columnconfigure(col, weight=weight)

        tk.Label(
            section,
            text="音乐技能HUD提醒",
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 2), columnspan=6)
        master_toggle = tk.Checkbutton(
            section,
            variable=enabled,
            text="启用音乐技能HUD提醒",
            bg=colors["row"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row"],
            bd=0,
            highlightthickness=0,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        master_toggle.grid(
            row=0, column=6, columnspan=2, sticky="e", padx=12, pady=(9, 2)
        )
        tk.Checkbutton(
            section,
            variable=tuan_silence_enabled,
            text=VISUAL_HUD_TUAN_SILENCE_LABEL,
            bg=colors["row_alt"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row_alt"],
            bd=0,
            highlightthickness=0,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).grid(
            row=1,
            column=0,
            columnspan=8,
            sticky="w",
            padx=12,
            pady=(5, 4),
        )
        headers = ("项目", "HUD", "提前提醒（秒）", "铃声", "图标", "", "", "")
        for column, text in enumerate(headers):
            tk.Label(
                section,
                text=text,
                bg=colors["row_alt"],
                fg=colors["muted"],
                font=("Microsoft YaHei UI", 9, "bold"),
                anchor="w",
            ).grid(row=2, column=column, sticky="ew", padx=5, pady=(6, 4))

        condition_toggles: dict[int, tk.Checkbutton] = {}
        show_before_widgets: dict[int, tk.Spinbox] = {}
        ring_toggles: dict[int, tk.Checkbutton] = {}
        icon_entries: dict[int, tk.Entry] = {}
        icon_choose_buttons: dict[int, tk.Button] = {}
        icon_reset_buttons: dict[int, tk.Button] = {}

        def add_condition_row(local_row: int, label: str, ccid: int) -> None:
            row_bg = colors["row"] if local_row % 2 else colors["row_alt"]
            tk.Label(
                section,
                text=label,
                bg=row_bg,
                fg=colors["text"],
                font=("Microsoft YaHei UI", 9, "bold"),
                anchor="w",
            ).grid(row=local_row, column=0, sticky="ew", padx=(12, 5), pady=5)
            toggle = tk.Checkbutton(
                section,
                variable=condition_enabled[ccid],
                text="ON",
                bg=row_bg,
                fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=row_bg,
                bd=0,
                highlightthickness=0,
            )
            toggle.grid(row=local_row, column=1, sticky="ew", padx=5, pady=5)
            show_before = tk.Spinbox(
                section,
                from_=VISUAL_HUD_MIN_SHOW_BEFORE_SECONDS,
                to=VISUAL_HUD_MAX_SHOW_BEFORE_SECONDS,
                increment=0.5,
                textvariable=condition_show_before_seconds[ccid],
                width=8,
                bg=colors["input"],
                fg=colors["text"],
                buttonbackground=colors["button"],
                relief="solid",
                bd=1,
                justify="center",
            )
            show_before.grid(
                row=local_row, column=2, sticky="ew", padx=5, pady=5, ipady=4
            )
            ring_toggle = tk.Checkbutton(
                section,
                variable=condition_ring_sound_enabled[ccid],
                text="ON",
                bg=row_bg,
                fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=row_bg,
                bd=0,
                highlightthickness=0,
            )
            ring_toggle.grid(
                row=local_row, column=3, sticky="ew", padx=5, pady=5
            )
            entry = tk.Entry(
                section,
                textvariable=condition_icons[ccid],
                bg=colors["input"],
                fg=colors["text"],
                relief="solid",
                bd=1,
            )
            entry.grid(
                row=local_row,
                column=4,
                columnspan=2,
                sticky="ew",
                padx=5,
                pady=5,
                ipady=5,
            )
            choose = self._button(
                section,
                "选择图片",
                lambda condition_ccid=ccid: self.choose_visual_hud_icon(
                    condition_ccid
                ),
            )
            choose.grid(row=local_row, column=6, padx=5, pady=5)
            reset = self._button(
                section,
                "恢复默认图标",
                lambda condition_ccid=ccid: self.reset_visual_hud_icon(
                    condition_ccid
                ),
            )
            reset.grid(row=local_row, column=7, padx=(5, 12), pady=5)
            condition_toggles[ccid] = toggle
            show_before_widgets[ccid] = show_before
            ring_toggles[ccid] = ring_toggle
            icon_entries[ccid] = entry
            icon_choose_buttons[ccid] = choose
            icon_reset_buttons[ccid] = reset

        for local_row, ccid, label in (
            (3, 192, "活跃曲图标"),
            (4, 680, "战争序曲图标"),
            (5, 193, "行进曲图标"),
        ):
            add_condition_row(local_row, label.removesuffix("图标"), ccid)

        self.visual_hud = VisualHudRow(
            item=item,
            enabled=enabled,
            tuan_silence_enabled=tuan_silence_enabled,
            condition_enabled=condition_enabled,
            condition_show_before_seconds=condition_show_before_seconds,
            condition_ring_sound_enabled=condition_ring_sound_enabled,
            condition_icons=condition_icons,
            condition_toggles=condition_toggles,
            show_before_widgets=show_before_widgets,
            ring_toggles=ring_toggles,
            icon_entries=icon_entries,
            icon_choose_buttons=icon_choose_buttons,
            icon_reset_buttons=icon_reset_buttons,
        )
        enabled.trace_add("write", lambda *_args: self._sync_visual_hud_state())
        for variable in condition_enabled.values():
            variable.trace_add("write", lambda *_args: self._sync_visual_hud_state())
        self._sync_visual_hud_state()

    def _build_other_skill_hud(self, parent: tk.Frame, row_index: int) -> None:
        colors = self._colors()
        item = find_or_create_other_skill_hud(self.data)
        enabled = BooleanVar(value=bool(item.get("enabled", False)))
        conditions = item["conditions"]
        condition_enabled = {
            key: BooleanVar(value=bool(conditions[key].get("enabled", False)))
            for key in OTHER_SKILL_HUD_CONDITION_DEFAULTS
        }
        condition_icons = {
            key: StringVar(value=other_skill_hud_icon(item, key))
            for key in OTHER_SKILL_HUD_CONDITION_DEFAULTS
        }

        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        section.columnconfigure(0, weight=0)
        section.columnconfigure(1, weight=0)
        section.columnconfigure(2, weight=1)
        section.columnconfigure(3, weight=0)
        section.columnconfigure(4, weight=0)

        tk.Label(
            section,
            text="其他技能HUD提醒",
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(9, 2))
        master_toggle = tk.Checkbutton(
            section,
            variable=enabled,
            text="启用其他技能HUD提醒",
            bg=colors["row"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row"],
            bd=0,
            highlightthickness=0,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        master_toggle.grid(
            row=0, column=3, columnspan=2, sticky="e", padx=12, pady=(9, 2)
        )
        for column, text in enumerate(("项目", "HUD", "图标", "", "")):
            tk.Label(
                section,
                text=text,
                bg=colors["row_alt"],
                fg=colors["muted"],
                font=("Microsoft YaHei UI", 9, "bold"),
                anchor="w",
            ).grid(row=1, column=column, sticky="ew", padx=5, pady=(6, 4))

        condition_toggles: dict[str, tk.Checkbutton] = {}
        icon_entries: dict[str, tk.Entry] = {}
        icon_choose_buttons: dict[str, tk.Button] = {}
        icon_reset_buttons: dict[str, tk.Button] = {}
        for index, (key, defaults) in enumerate(
            OTHER_SKILL_HUD_CONDITION_DEFAULTS.items(), start=2
        ):
            row_bg = colors["row"] if index % 2 else colors["row_alt"]
            tk.Label(
                section,
                text=defaults["name"],
                bg=row_bg,
                fg=colors["text"],
                font=("Microsoft YaHei UI", 9, "bold"),
                anchor="w",
            ).grid(row=index, column=0, sticky="ew", padx=(12, 5), pady=5)
            toggle = tk.Checkbutton(
                section,
                variable=condition_enabled[key],
                text="ON",
                bg=row_bg,
                fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=row_bg,
                bd=0,
                highlightthickness=0,
            )
            toggle.grid(row=index, column=1, sticky="ew", padx=5, pady=5)
            entry = tk.Entry(
                section,
                textvariable=condition_icons[key],
                bg=colors["input"],
                fg=colors["text"],
                relief="solid",
                bd=1,
            )
            entry.grid(row=index, column=2, sticky="ew", padx=5, pady=5, ipady=5)
            choose = self._button(
                section,
                "选择图片",
                lambda condition_key=key: self.choose_other_skill_hud_icon(
                    condition_key
                ),
            )
            choose.grid(row=index, column=3, padx=5, pady=5)
            reset = self._button(
                section,
                "恢复默认图标",
                lambda condition_key=key: self.reset_other_skill_hud_icon(
                    condition_key
                ),
            )
            reset.grid(row=index, column=4, padx=(5, 12), pady=5)
            condition_toggles[key] = toggle
            icon_entries[key] = entry
            icon_choose_buttons[key] = choose
            icon_reset_buttons[key] = reset

        self.other_skill_hud = OtherSkillHudRow(
            item=item,
            enabled=enabled,
            condition_enabled=condition_enabled,
            condition_icons=condition_icons,
            condition_toggles=condition_toggles,
            icon_entries=icon_entries,
            icon_choose_buttons=icon_choose_buttons,
            icon_reset_buttons=icon_reset_buttons,
        )
        enabled.trace_add("write", lambda *_args: self._sync_other_skill_hud_state())
        for variable in condition_enabled.values():
            variable.trace_add(
                "write", lambda *_args: self._sync_other_skill_hud_state()
            )
        self._sync_other_skill_hud_state()

    def _build_short_cooldown_hud(
        self, parent: tk.Frame, row_index: int
    ) -> None:
        colors = self._colors()
        item = find_or_create_short_cooldown_hud(self.data)
        conditions = item["conditions"]
        master_enabled = bool(item.get("enabled", True))
        condition_enabled = {
            key: BooleanVar(
                value=master_enabled and bool(conditions[key].get("enabled", True))
            )
            for key in SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS
        }
        cooldown_seconds = {
            key: StringVar(
                value=f"{short_cooldown_hud_cooldown_seconds(self.data, key):g}"
            )
            for key in SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS
        }
        condition_icons = {
            key: StringVar(value=short_cooldown_hud_icon(item, key))
            for key in SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS
        }

        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 10))
        section.columnconfigure(0, weight=0)
        section.columnconfigure(1, weight=0)
        section.columnconfigure(2, weight=0)
        section.columnconfigure(3, weight=1)
        section.columnconfigure(4, weight=0)
        section.columnconfigure(5, weight=0)

        tk.Label(
            section,
            text="短CD技能冷却提示",
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=6, sticky="ew", padx=12, pady=(9, 2))
        for column, text in enumerate(
            ("项目", "HUD", "冷却时间（秒）", "图标", "", "")
        ):
            tk.Label(
                section,
                text=text,
                bg=colors["row_alt"],
                fg=colors["muted"],
                font=("Microsoft YaHei UI", 9, "bold"),
                anchor="w",
            ).grid(row=1, column=column, sticky="ew", padx=5, pady=(6, 4))

        condition_toggles: dict[str, tk.Checkbutton] = {}
        cooldown_widgets: dict[str, tk.Spinbox] = {}
        icon_entries: dict[str, tk.Entry] = {}
        icon_choose_buttons: dict[str, tk.Button] = {}
        icon_reset_buttons: dict[str, tk.Button] = {}
        for row_offset, (key, defaults) in enumerate(
            SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS.items(), start=2
        ):
            tk.Label(
                section,
                text=defaults["name"],
                bg=colors["row"],
                fg=colors["text"],
                font=("Microsoft YaHei UI", 9, "bold"),
                anchor="w",
            ).grid(
                row=row_offset,
                column=0,
                sticky="ew",
                padx=(12, 5),
                pady=5,
            )
            toggle = tk.Checkbutton(
                section,
                variable=condition_enabled[key],
                text="ON",
                bg=colors["row"],
                fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=colors["row"],
                bd=0,
                highlightthickness=0,
            )
            toggle.grid(row=row_offset, column=1, sticky="ew", padx=5, pady=5)
            cooldown_widget = tk.Spinbox(
                section,
                from_=0.1,
                to=9999,
                increment=1,
                textvariable=cooldown_seconds[key],
                width=10,
                bg=colors["input"],
                fg=colors["text"],
                buttonbackground=colors["button"],
                relief="solid",
                bd=1,
                justify="center",
            )
            cooldown_widget.grid(
                row=row_offset, column=2, sticky="ew", padx=5, pady=5, ipady=4
            )
            icon_entry = tk.Entry(
                section,
                textvariable=condition_icons[key],
                bg=colors["input"],
                fg=colors["text"],
                relief="solid",
                bd=1,
            )
            icon_entry.grid(
                row=row_offset, column=3, sticky="ew", padx=5, pady=5, ipady=5
            )
            choose = self._button(
                section,
                "选择图片",
                lambda condition_key=key: self.choose_short_cooldown_hud_icon(
                    condition_key
                ),
            )
            choose.grid(row=row_offset, column=4, padx=5, pady=5)
            reset = self._button(
                section,
                "恢复默认图标",
                lambda condition_key=key: self.reset_short_cooldown_hud_icon(
                    condition_key
                ),
            )
            reset.grid(row=row_offset, column=5, padx=(5, 12), pady=5)
            condition_toggles[key] = toggle
            cooldown_widgets[key] = cooldown_widget
            icon_entries[key] = icon_entry
            icon_choose_buttons[key] = choose
            icon_reset_buttons[key] = reset

        self.short_cooldown_hud = ShortCooldownHudRow(
            item=item,
            condition_enabled=condition_enabled,
            cooldown_seconds=cooldown_seconds,
            condition_icons=condition_icons,
            condition_toggles=condition_toggles,
            cooldown_widgets=cooldown_widgets,
            icon_entries=icon_entries,
            icon_choose_buttons=icon_choose_buttons,
            icon_reset_buttons=icon_reset_buttons,
        )
        for variable in condition_enabled.values():
            variable.trace_add(
                "write", lambda *_args: self._sync_short_cooldown_hud_state()
            )
        self._sync_short_cooldown_hud_state()

    def _build_astrology_card_tracker(
        self, parent: tk.Frame, row_index: int
    ) -> None:
        colors = self._colors()
        item = ensure_astrology_card_tracker_config(self.data)
        enabled_skills = {
            skill_id: BooleanVar(
                value=bool(item["tracked_skills"].get(str(skill_id), False))
            )
            for skill_id in ASTROLOGY_CORE_COOLDOWN_DEFAULTS
        }
        counter_threshold = StringVar(value=str(item["counter_threshold"]))
        deck = [
            StringVar(value=card or ASTROLOGY_UNSET_LABEL)
            for card in item["deck"]
        ]
        skill_suits = {
            int(skill_id): StringVar(value=suit or ASTROLOGY_UNSET_LABEL)
            for skill_id, suit in item["skill_suits"].items()
        }
        base_cooldown_seconds = {
            int(skill_id): StringVar(value=f"{float(seconds):g}")
            for skill_id, seconds in item["base_cooldown_seconds"].items()
        }

        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 10))
        section.columnconfigure(0, weight=0)
        section.columnconfigure(1, weight=1)
        section.columnconfigure(2, weight=0)
        section.columnconfigure(3, weight=1)

        tk.Label(
            section,
            text="战斗占星卡牌追踪",
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=4, sticky="ew", padx=12, pady=(9, 2))
        for column, skill_id, text in (
            (0, 27202, "启用星辉领域冷却追踪"),
            (2, 27203, "启用疾旋突袭冷却追踪"),
        ):
            tk.Checkbutton(
                section,
                variable=enabled_skills[skill_id],
                text=text,
                bg=colors["row_alt"],
                fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=colors["row_alt"],
                bd=0,
                highlightthickness=0,
                font=("Microsoft YaHei UI", 9, "bold"),
                anchor="w",
            ).grid(
                row=1,
                column=column,
                columnspan=2,
                sticky="ew",
                padx=12,
                pady=(4, 5),
            )

        tk.Label(
            section,
            text="获得每张牌所需计数",
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 9, "bold"),
            anchor="w",
        ).grid(row=2, column=0, sticky="w", padx=(12, 5), pady=5)
        ttk.Combobox(
            section,
            textvariable=counter_threshold,
            values=tuple(str(value) for value in ASTROLOGY_COUNTER_CHOICES),
            state="readonly",
            width=12,
        ).grid(row=2, column=1, sticky="w", padx=5, pady=5)

        core_skills = {
            int(item["skill_id"]): item
            for key, item in ASTROLOGY_SKILLS.items()
            if key in ("starry_field", "whirling_assault")
        }
        for column, skill_id in ((0, 27202), (2, 27203)):
            skill = core_skills[skill_id]
            tk.Label(
                section,
                text=f"{skill['name']}基础冷却（秒）",
                bg=colors["row"],
                fg=colors["text"],
                font=("Microsoft YaHei UI", 9, "bold"),
                anchor="w",
            ).grid(row=3, column=column, sticky="w", padx=(12, 5), pady=5)
            tk.Spinbox(
                section,
                from_=ASTROLOGY_MIN_COOLDOWN_SECONDS,
                to=ASTROLOGY_MAX_COOLDOWN_SECONDS,
                increment=0.1,
                textvariable=base_cooldown_seconds[skill_id],
                width=12,
                bg=colors["input"],
                fg=colors["text"],
                buttonbackground=colors["button"],
                highlightthickness=0,
                bd=1,
            ).grid(row=3, column=column + 1, sticky="w", padx=5, pady=5)

        for column, text in ((0, "卡组顺序"), (1, "卡牌"), (2, "技能"), (3, "当前花色")):
            tk.Label(
                section,
                text=text,
                bg=colors["row_alt"],
                fg=colors["muted"],
                font=("Microsoft YaHei UI", 9, "bold"),
                anchor="w",
            ).grid(row=4, column=column, sticky="ew", padx=5, pady=(6, 4))

        card_values = (ASTROLOGY_UNSET_LABEL,) + ASTROLOGY_CARD_OPTIONS
        suit_values = (ASTROLOGY_UNSET_LABEL,) + ASTROLOGY_SUIT_OPTIONS
        skills = list(ASTROLOGY_SKILLS.values())
        max_rows = max(len(deck), len(skills))
        for index in range(max_rows):
            grid_row = 5 + index
            if index < len(deck):
                tk.Label(
                    section,
                    text=f"{index + 1}号牌",
                    bg=colors["row"],
                    fg=colors["text"],
                    font=("Microsoft YaHei UI", 9, "bold"),
                    anchor="w",
                ).grid(row=grid_row, column=0, sticky="ew", padx=(12, 5), pady=5)
                ttk.Combobox(
                    section,
                    textvariable=deck[index],
                    values=card_values,
                    state="readonly",
                    width=18,
                ).grid(row=grid_row, column=1, sticky="ew", padx=5, pady=5)

            if index < len(skills):
                skill = skills[index]
                skill_id = int(skill["skill_id"])
                tk.Label(
                    section,
                    text=f"{skill['name']}  ({skill_id})",
                    bg=colors["row"],
                    fg=colors["text"],
                    font=("Microsoft YaHei UI", 9, "bold"),
                    anchor="w",
                ).grid(row=grid_row, column=2, sticky="ew", padx=(16, 5), pady=5)
                ttk.Combobox(
                    section,
                    textvariable=skill_suits[skill_id],
                    values=suit_values,
                    state="readonly",
                    width=14,
                ).grid(row=grid_row, column=3, sticky="ew", padx=(5, 12), pady=5)

        self.astrology_card_tracker = AstrologyCardTrackerRow(
            item=item,
            enabled_skills=enabled_skills,
            counter_threshold=counter_threshold,
            deck=deck,
            skill_suits=skill_suits,
            base_cooldown_seconds=base_cooldown_seconds,
        )

    def _build_visual_debuff_expiry(
        self,
        parent: tk.Frame,
        row_index: int,
    ) -> None:
        if self.key_enemy_debuff is None:
            return
        colors = self._colors()
        row = self.key_enemy_debuff
        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 10))
        section.columnconfigure(0, weight=1)

        tk.Label(
            section,
            text="可视化DEBUFF提醒",
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 3))
        visual_hud_toggle = tk.Checkbutton(
            section,
            variable=row.visual_hud_enabled,
            text="可视化DEBUFF上齐提醒",
            bg=colors["row_alt"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row_alt"],
            bd=0,
            highlightthickness=0,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        visual_hud_toggle.grid(
            row=1, column=0, sticky="ew", padx=12, pady=(5, 2)
        )
        row.visual_hud_toggle = visual_hud_toggle

        toggle = tk.Checkbutton(
            section,
            variable=row.visual_expiry_enabled,
            text="可视化DEBUFF到期提醒",
            bg=colors["row_alt"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row_alt"],
            bd=0,
            highlightthickness=0,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        toggle.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 9))
        row.visual_expiry_toggle = toggle

    def _sync_scroll_region_for(
        self,
        canvas: tk.Canvas,
        content: tk.Frame,
        window_id: int,
    ) -> None:
        width = max(canvas.winfo_width(), content.winfo_reqwidth())
        canvas.itemconfigure(window_id, width=width)
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_notebook_tab_changed(self, _event: tk.Event | None = None) -> None:
        if self.notebook is None:
            return
        tab_id = str(self.notebook.select())
        canvas = self.tab_scroll_canvases.get(tab_id)
        content = self.tab_scroll_contents.get(tab_id)
        window_id = self.tab_scroll_windows.get(tab_id)
        if canvas is None or content is None or window_id is None:
            return
        self.scroll_canvas = canvas
        self.scroll_content = content
        self.scroll_window = window_id
        self._sync_scroll_region_for(canvas, content, window_id)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.notebook is not None:
            selected = str(self.notebook.select())
            canvas = self.tab_scroll_canvases.get(selected)
        else:
            canvas = self.scroll_canvas
        if canvas is None:
            return
        delta = getattr(event, "delta", 0)
        if delta == 0:
            return
        steps = int(-delta / 120)
        if steps == 0:
            steps = -1 if delta > 0 else 1
        if getattr(event, "state", 0) & 0x0001:
            canvas.xview_scroll(steps, "units")
        else:
            canvas.yview_scroll(steps, "units")

    def _build_buff_group(
        self,
        parent: tk.Frame,
        row_index: int,
        title: str,
        names: list[str],
        items_by_name: dict[str, dict],
        *,
        seconds_header: str,
        progress_mode: bool = False,
    ) -> None:
        colors = self._colors()
        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col, weight in [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),
            (4, 1),
            (5, 0),
            (6, 0),
            (7, 1),
            (8, 0),
            (9, 0),
        ]:
            section.columnconfigure(col, weight=weight)

        is_music_group = title == "乐曲类"
        title_columnspan = 1 if is_music_group else 10
        tk.Label(
            section,
            text=title,
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=(9, 6),
            columnspan=title_columnspan,
        )
        if is_music_group:
            music_strong = find_or_create_music_strong_reminder(self.data)
            self.music_strong_enabled = BooleanVar(
                value=bool(music_strong.get("enabled", False))
            )
            self.music_tuan_silence_enabled = BooleanVar(
                value=bool(
                    self.data.get(
                        "music_tuan_silence_enabled",
                        MUSIC_TUAN_SILENCE_DEFAULT,
                    )
                )
            )
            tk.Checkbutton(
                section,
                variable=self.music_strong_enabled,
                text="\u5f3a\u63d0\u9192\u6a21\u5f0f",
                bg=colors["row"],
                fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=colors["row"],
                bd=0,
                highlightthickness=0,
                font=("Microsoft YaHei UI", 9, "bold"),
            ).grid(row=0, column=0, columnspan=10, sticky="w", padx=12, pady=(9, 6))

            tk.Checkbutton(
                section,
                variable=self.music_tuan_silence_enabled,
                text=MUSIC_TUAN_SILENCE_LABEL,
                bg=colors["row_alt"],
                fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=colors["row_alt"],
                bd=0,
                highlightthickness=0,
                font=("Microsoft YaHei UI", 9, "bold"),
            ).grid(
                row=1,
                column=0,
                columnspan=10,
                sticky="w",
                padx=12,
                pady=(5, 4),
            )

        headers = (
            ["项目", "", "剩余进度提醒", seconds_header, "提醒音源", "", "", "", "", ""]
            if progress_mode
            else ["项目", "结束提醒", "剩余提醒", seconds_header, "提醒音源", "", "", "结束音源", "", ""]
        )
        header_row = 2 if is_music_group else 1
        for col, text in enumerate(headers):
            tk.Label(
                section,
                text=text,
                bg=colors["row"],
                fg=colors["muted"],
                font=("Microsoft YaHei UI", 9, "bold"),
            ).grid(row=header_row, column=col, sticky="w", padx=5, pady=(4, 8))

        local_row = header_row + 1
        for name in names:
            item = items_by_name.get(name)
            if item is None:
                continue
            local_row += self._add_buff_row(section, local_row, item)

    def _add_buff_row(self, parent: tk.Frame, row_index: int, item: dict) -> int:
        colors = self._colors()
        name = item["name"]
        display_name = "托亚灵震爆" if name == "托亚灵进度" else name
        if name == HAMSTER_SUPERCHARGED_NAME:
            display_name = HAMSTER_SETTINGS_NAME
        is_progress = item_is_progress(item)
        enabled = BooleanVar(
            value=(
                True
                if is_progress
                else bool(
                    item.get("enabled", True)
                    and item.get("ended_alert", True)
                )
            )
        )
        remaining_enabled = BooleanVar(value=item_remaining_enabled(item))
        seconds = IntVar(value=max(0, item_seconds(item)))
        remaining_sound = StringVar(value=item_remaining_sound(item))
        ended_sound = StringVar(value=item_ended_sound(item))

        row_bg = colors["row"] if row_index % 2 else colors["row_alt"]
        tk.Label(
            parent,
            text=display_name,
            width=18,
            bg=row_bg,
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=row_index, column=0, sticky="ew", padx=5, pady=3, ipady=7)
        ended_toggle = tk.Checkbutton(
            parent,
            variable=enabled,
            text="ON",
            bg=row_bg,
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=row_bg,
            bd=0,
            highlightthickness=0,
        )
        if not is_progress:
            ended_toggle.grid(row=row_index, column=1, sticky="ew", padx=5, pady=3)
        remaining_toggle = tk.Checkbutton(
            parent,
            variable=remaining_enabled,
            text="ON",
            bg=row_bg,
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=row_bg,
            bd=0,
            highlightthickness=0,
        )
        remaining_toggle.grid(row=row_index, column=2, sticky="ew", padx=5, pady=3)
        seconds_widget = tk.Spinbox(
            parent,
            from_=0,
            to=100 if is_progress else 9999,
            textvariable=seconds,
            width=6,
            bg=colors["input"],
            fg=colors["text"],
            buttonbackground=colors["button"],
            relief="solid",
            bd=1,
            justify="center",
        )
        seconds_widget.grid(row=row_index, column=3, sticky="ew", padx=5, pady=3, ipady=4)
        sound_entry = tk.Entry(
            parent,
            textvariable=remaining_sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        )
        sound_entry.grid(row=row_index, column=4, sticky="ew", padx=5, pady=3, ipady=5)
        remaining_choose = self._button(
            parent,
            "选择",
            lambda r=len(self.rows): self.choose_sound(r, "remaining"),
        )
        remaining_choose.grid(row=row_index, column=5, padx=5, pady=3)
        remaining_test = self._button(
            parent,
            "试听",
            lambda r=len(self.rows): self.test_sound(r, "remaining"),
        )
        remaining_test.grid(row=row_index, column=6, padx=5, pady=3)
        ended_sound_entry = tk.Entry(
            parent,
            textvariable=ended_sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        )
        ended_choose = self._button(parent, "选择", lambda r=len(self.rows): self.choose_sound(r, "ended"))
        ended_test = self._button(parent, "试听", lambda r=len(self.rows): self.test_sound(r, "ended"))
        if not is_progress:
            ended_sound_entry.grid(row=row_index, column=7, sticky="ew", padx=5, pady=3, ipady=5)
            ended_choose.grid(row=row_index, column=8, padx=5, pady=3)
            ended_test.grid(row=row_index, column=9, padx=5, pady=3)

        row = BuffRow(
            item,
            enabled,
            remaining_enabled,
            seconds,
            remaining_sound,
            ended_sound,
            seconds_widget,
            remaining_toggle,
            sound_entry,
            remaining_choose,
            remaining_test,
        )
        self.rows.append(row)
        if name == KEY_ENEMY_GUNNER_EYE_NAME:
            self.gunner_eye_row = row
        remaining_enabled.trace_add("write", lambda *_args, buff_row=row: self._sync_seconds_state(buff_row))
        self._sync_seconds_state(row)
        return 1

    def _build_magic_shield_delay(self, parent: tk.Frame, row_index: int) -> None:
        colors = self._colors()
        item = find_or_create_magic_shield(self.data)
        missing_alert = ensure_magic_shield_missing_alert(item)

        enabled = BooleanVar(value=bool(item.get("enabled", True)))
        ended_enabled = BooleanVar(value=bool(item.get("ended_alert", True)))
        missing_enabled = BooleanVar(value=bool(missing_alert.get("enabled", False)))
        ended_sound = StringVar(
            value=item.get("ended_sound", MAGIC_SHIELD_DEFAULT_ENDED_SOUND)
        )
        missing_sound = StringVar(value=magic_shield_missing_sound(item))
        ended_grace_seconds = DoubleVar(value=magic_shield_ended_grace_seconds(item))
        missing_delay_seconds = DoubleVar(
            value=magic_shield_missing_delay_seconds(item)
        )
        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col, weight in [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 1),
            (4, 0),
            (5, 0),
            (6, 0),
            (7, 0),
        ]:
            section.columnconfigure(col, weight=weight)

        tk.Label(
            section,
            text="魔法盾提醒",
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 6), columnspan=8)

        headers = ["项目", "启用", "提醒开关", "音源", "", "", "延迟", ""]
        for col, text in enumerate(headers):
            tk.Label(
                section,
                text=text,
                bg=colors["row"],
                fg=colors["muted"],
                font=("Microsoft YaHei UI", 9, "bold"),
            ).grid(row=1, column=col, sticky="w", padx=5, pady=(4, 6))

        row_bg = colors["row_alt"]
        tk.Label(
            section,
            text="魔法盾结束提醒",
            bg=row_bg,
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=5, pady=3, ipady=7)
        tk.Checkbutton(
            section,
            variable=enabled,
            text="ON",
            bg=row_bg,
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=row_bg,
            bd=0,
            highlightthickness=0,
        ).grid(row=2, column=1, sticky="ew", padx=5, pady=3)
        ended_toggle = tk.Checkbutton(
            section,
            variable=ended_enabled,
            text="ON",
            bg=row_bg,
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=row_bg,
            bd=0,
            highlightthickness=0,
        )
        ended_toggle.grid(row=2, column=2, sticky="ew", padx=5, pady=3)
        ended_entry = tk.Entry(
            section,
            textvariable=ended_sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        )
        ended_entry.grid(row=2, column=3, sticky="ew", padx=5, pady=3, ipady=5)
        ended_choose = self._button(
            section,
            "选择",
            self.choose_magic_shield_sound,
        )
        ended_choose.grid(row=2, column=4, padx=5, pady=3)
        ended_test = self._button(section, "试听", self.test_magic_shield_sound)
        ended_test.grid(row=2, column=5, padx=5, pady=3)
        delay_widget = tk.Spinbox(
            section,
            from_=0.0,
            to=MAGIC_SHIELD_MAX_ENDED_GRACE_SECONDS,
            increment=0.1,
            format="%.1f",
            textvariable=ended_grace_seconds,
            width=7,
            bg=colors["input"],
            fg=colors["text"],
            buttonbackground=colors["button"],
            relief="solid",
            bd=1,
            justify="center",
        )
        delay_widget.grid(row=2, column=6, sticky="ew", padx=5, pady=3, ipady=4)
        tk.Label(
            section,
            text="秒",
            bg=row_bg,
            fg=colors["muted"],
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).grid(row=2, column=7, sticky="w", padx=(0, 12), pady=3)

        tk.Label(
            section,
            text=MAGIC_SHIELD_MISSING_ALERT_NAME,
            bg=row_bg,
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=3, column=0, sticky="ew", padx=5, pady=3, ipady=7)
        tk.Label(
            section,
            text="随上方",
            bg=row_bg,
            fg=colors["muted"],
            font=("Microsoft YaHei UI", 9),
            anchor="center",
        ).grid(row=3, column=1, sticky="ew", padx=5, pady=3)
        missing_toggle = tk.Checkbutton(
            section,
            variable=missing_enabled,
            text="ON",
            bg=row_bg,
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=row_bg,
            bd=0,
            highlightthickness=0,
        )
        missing_toggle.grid(row=3, column=2, sticky="ew", padx=5, pady=3)
        missing_entry = tk.Entry(
            section,
            textvariable=missing_sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        )
        missing_entry.grid(row=3, column=3, sticky="ew", padx=5, pady=3, ipady=5)
        missing_choose = self._button(
            section,
            "选择",
            self.choose_magic_shield_missing_sound,
        )
        missing_choose.grid(row=3, column=4, padx=5, pady=3)
        missing_test = self._button(
            section,
            "试听",
            self.test_magic_shield_missing_sound,
        )
        missing_test.grid(row=3, column=5, padx=5, pady=3)
        missing_delay_widget = tk.Spinbox(
            section,
            from_=0.0,
            to=MAGIC_SHIELD_MAX_MISSING_DELAY_SECONDS,
            increment=0.5,
            format="%.1f",
            textvariable=missing_delay_seconds,
            width=7,
            bg=colors["input"],
            fg=colors["text"],
            buttonbackground=colors["button"],
            relief="solid",
            bd=1,
            justify="center",
        )
        missing_delay_widget.grid(row=3, column=6, sticky="ew", padx=5, pady=3, ipady=4)
        tk.Label(
            section,
            text="秒",
            bg=row_bg,
            fg=colors["muted"],
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).grid(row=3, column=7, sticky="w", padx=(0, 12), pady=3)

        self.magic_shield_delay = MagicShieldDelayRow(
            item=item,
            enabled=enabled,
            ended_enabled=ended_enabled,
            missing_enabled=missing_enabled,
            ended_sound=ended_sound,
            missing_sound=missing_sound,
            ended_grace_seconds=ended_grace_seconds,
            missing_delay_seconds=missing_delay_seconds,
            ended_toggle=ended_toggle,
            missing_toggle=missing_toggle,
            ended_sound_entry=ended_entry,
            missing_sound_entry=missing_entry,
            ended_choose=ended_choose,
            missing_choose=missing_choose,
            ended_test=ended_test,
            missing_test=missing_test,
            delay_widget=delay_widget,
            missing_delay_widget=missing_delay_widget,
        )
        enabled.trace_add("write", lambda *_args: self._sync_magic_shield_state())
        ended_enabled.trace_add("write", lambda *_args: self._sync_magic_shield_state())
        missing_enabled.trace_add("write", lambda *_args: self._sync_magic_shield_state())
        self._sync_magic_shield_state()

    def _build_azure_wound(self, parent: tk.Frame, row_index: int) -> None:
        colors = self._colors()
        item = find_or_create_azure_wound(self.data)
        stack_alert = item.get("stack_alert") or {}
        try:
            danger_value = int(
                stack_alert.get("stacks", AZURE_WOUND_DEFAULT_DANGER_STACKS)
            )
        except (TypeError, ValueError):
            danger_value = AZURE_WOUND_DEFAULT_DANGER_STACKS
        danger_value = max(1, min(AZURE_WOUND_MAX_STACKS, danger_value))

        enabled = BooleanVar(value=bool(item.get("enabled", True)))
        danger_stacks = IntVar(value=danger_value)
        danger_sound = StringVar(
            value=stack_alert.get(
                "sound", item.get("warn_sound", AZURE_WOUND_DEFAULT_DANGER_SOUND)
            )
        )
        clear_enabled = BooleanVar(value=bool(item.get("clear_after_stack_alert", True)))
        clear_sound = StringVar(
            value=item.get("clear_sound", AZURE_WOUND_DEFAULT_CLEAR_SOUND)
        )

        section = tk.Frame(parent, bg=colors["row_alt"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col, weight in [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),
            (4, 1),
            (5, 0),
            (6, 0),
            (7, 1),
            (8, 0),
            (9, 0),
        ]:
            section.columnconfigure(col, weight=weight)

        tk.Label(
            section,
            text="湛蓝内伤",
            bg=colors["row_alt"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 6), columnspan=10)

        tk.Checkbutton(
            section,
            variable=enabled,
            text="启用监控",
            bg=colors["row_alt"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row_alt"],
            bd=0,
            highlightthickness=0,
        ).grid(row=1, column=0, sticky="w", padx=12, pady=6)
        tk.Label(
            section,
            text="危险层级",
            bg=colors["row_alt"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
        ).grid(row=1, column=1, sticky="e", padx=5, pady=6)
        danger_widget = tk.Spinbox(
            section,
            from_=1,
            to=AZURE_WOUND_MAX_STACKS,
            textvariable=danger_stacks,
            width=7,
            bg=colors["input"],
            fg=colors["text"],
            buttonbackground=colors["button"],
            relief="solid",
            bd=1,
            justify="center",
        )
        danger_widget.grid(row=1, column=2, sticky="ew", padx=5, pady=6, ipady=4)
        danger_entry = tk.Entry(
            section,
            textvariable=danger_sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        )
        danger_entry.grid(row=1, column=3, sticky="ew", padx=5, pady=6, columnspan=4, ipady=5)
        danger_choose = self._button(
            section, "危险音源", lambda: self.choose_azure_wound_sound("danger")
        )
        danger_choose.grid(row=1, column=7, sticky="ew", padx=5, pady=6)
        danger_test = self._button(
            section, "试听", lambda: self.test_azure_wound_sound("danger")
        )
        danger_test.grid(row=1, column=8, sticky="ew", padx=(5, 12), pady=6, columnspan=2)

        clear_toggle = tk.Checkbutton(
            section,
            variable=clear_enabled,
            text="消除提示",
            bg=colors["row_alt"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row_alt"],
            bd=0,
            highlightthickness=0,
        )
        clear_toggle.grid(row=2, column=0, sticky="w", padx=12, pady=(4, 10))
        clear_entry = tk.Entry(
            section,
            textvariable=clear_sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        )
        clear_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=(4, 10), columnspan=6, ipady=5)
        clear_choose = self._button(
            section, "消除音源", lambda: self.choose_azure_wound_sound("clear")
        )
        clear_choose.grid(row=2, column=7, sticky="ew", padx=5, pady=(4, 10))
        clear_test = self._button(
            section, "试听", lambda: self.test_azure_wound_sound("clear")
        )
        clear_test.grid(row=2, column=8, sticky="ew", padx=(5, 12), pady=(4, 10), columnspan=2)

        self.azure_wound = AzureWoundRow(
            item=item,
            enabled=enabled,
            danger_stacks=danger_stacks,
            danger_sound=danger_sound,
            clear_enabled=clear_enabled,
            clear_sound=clear_sound,
            danger_widget=danger_widget,
            danger_sound_entry=danger_entry,
            danger_choose=danger_choose,
            danger_test=danger_test,
            clear_toggle=clear_toggle,
            clear_sound_entry=clear_entry,
            clear_choose=clear_choose,
            clear_test=clear_test,
        )
        enabled.trace_add("write", lambda *_args: self._sync_azure_wound_state())
        clear_enabled.trace_add("write", lambda *_args: self._sync_azure_wound_state())
        self._sync_azure_wound_state()

    def _build_safehouse(self, parent: tk.Frame, row_index: int) -> None:
        colors = self._colors()
        item = find_or_create_safehouse_effect(self.data)
        enabled = BooleanVar(value=bool(item.get("enabled", True)))
        lead_seconds = IntVar(value=safehouse_lead_seconds(item))
        warning_sound = StringVar(value=safehouse_warning_sound(item))

        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col, weight in [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),
            (4, 1),
            (5, 0),
            (6, 0),
        ]:
            section.columnconfigure(col, weight=weight)

        tk.Label(
            section,
            text=SAFEHOUSE_NAME,
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 6), columnspan=7)

        tk.Checkbutton(
            section,
            variable=enabled,
            text="启用预警",
            bg=colors["row"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row"],
            bd=0,
            highlightthickness=0,
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(4, 10))
        tk.Label(
            section,
            text="提前秒数",
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
        ).grid(row=1, column=1, sticky="e", padx=5, pady=(4, 10))
        lead_widget = tk.Spinbox(
            section,
            from_=SAFEHOUSE_MIN_LEAD_SECONDS,
            to=SAFEHOUSE_MAX_LEAD_SECONDS,
            textvariable=lead_seconds,
            width=7,
            bg=colors["input"],
            fg=colors["text"],
            buttonbackground=colors["button"],
            relief="solid",
            bd=1,
            justify="center",
        )
        lead_widget.grid(row=1, column=2, sticky="ew", padx=5, pady=(4, 10), ipady=4)
        warning_entry = tk.Entry(
            section,
            textvariable=warning_sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        )
        warning_entry.grid(row=1, column=3, sticky="ew", padx=5, pady=(4, 10), columnspan=2, ipady=5)
        warning_choose = self._button(
            section, "预警音源", self.choose_safehouse_sound
        )
        warning_choose.grid(row=1, column=5, sticky="ew", padx=5, pady=(4, 10))
        warning_test = self._button(section, "试听", self.test_safehouse_sound)
        warning_test.grid(row=1, column=6, sticky="ew", padx=(5, 12), pady=(4, 10))

        self.safehouse = SafeHouseRow(
            item=item,
            enabled=enabled,
            lead_seconds=lead_seconds,
            warning_sound=warning_sound,
            lead_widget=lead_widget,
            warning_sound_entry=warning_entry,
            warning_choose=warning_choose,
            warning_test=warning_test,
        )
        enabled.trace_add("write", lambda *_args: self._sync_safehouse_state())
        self._sync_safehouse_state()

    def _build_boss_hp_alerts(self, parent: tk.Frame, row_index: int) -> None:
        colors = self._colors()
        items = find_or_create_boss_hp_alerts(self.data)
        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col, weight in [(0, 0), (1, 0), (2, 1), (3, 1), (4, 0), (5, 0)]:
            section.columnconfigure(col, weight=weight)

        tk.Label(
            section,
            text=BOSS_HP_SECTION_NAME,
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 6), columnspan=6)

        headers = ["Boss", "启用", "血量阈值(%)", "音源", "", ""]
        for col, text in enumerate(headers):
            tk.Label(
                section,
                text=text,
                bg=colors["row"],
                fg=colors["muted"],
                font=("Microsoft YaHei UI", 9, "bold"),
            ).grid(row=1, column=col, sticky="w", padx=5, pady=(4, 6))

        self.boss_hp_rows = []
        for offset, item in enumerate(items, start=2):
            row_bg = colors["row_alt"] if offset % 2 == 0 else colors["row"]
            enabled = BooleanVar(value=bool(item.get("enabled", True)))
            thresholds = StringVar(value=format_thresholds(boss_hp_thresholds(item)))
            sound = StringVar(value=item.get("warn_sound", BOSS_HP_DEFAULT_SOUND))
            tk.Label(
                section,
                text=f"{item.get('short_name', '')} {item.get('name', '')}".strip(),
                bg=row_bg,
                fg=colors["text"],
                font=("Microsoft YaHei UI", 10, "bold"),
                anchor="w",
            ).grid(row=offset, column=0, sticky="ew", padx=5, pady=3, ipady=7)
            toggle = tk.Checkbutton(
                section,
                variable=enabled,
                text="ON",
                bg=row_bg,
                fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=row_bg,
                bd=0,
                highlightthickness=0,
            )
            toggle.grid(row=offset, column=1, sticky="ew", padx=5, pady=3)
            thresholds_entry = tk.Entry(
                section,
                textvariable=thresholds,
                bg=colors["input"],
                fg=colors["text"],
                relief="solid",
                bd=1,
            )
            thresholds_entry.grid(row=offset, column=2, sticky="ew", padx=5, pady=3, ipady=5)
            sound_entry = tk.Entry(
                section,
                textvariable=sound,
                bg=colors["input"],
                fg=colors["text"],
                relief="solid",
                bd=1,
            )
            sound_entry.grid(row=offset, column=3, sticky="ew", padx=5, pady=3, ipady=5)
            row = BossHpAlertRow(
                item=item,
                enabled=enabled,
                thresholds=thresholds,
                sound=sound,
                toggle=toggle,
                thresholds_entry=thresholds_entry,
                sound_entry=sound_entry,
                choose=self._button(section, "选择", lambda r=len(self.boss_hp_rows): self.choose_boss_hp_sound(r)),
                test=self._button(section, "试听", lambda r=len(self.boss_hp_rows): self.test_boss_hp_sound(r)),
            )
            row.choose.grid(row=offset, column=4, padx=5, pady=3)
            row.test.grid(row=offset, column=5, padx=(5, 12), pady=3)
            self.boss_hp_rows.append(row)
            enabled.trace_add("write", lambda *_args, boss_row=row: self._sync_boss_hp_state(boss_row))
            self._sync_boss_hp_state(row)

    def _build_bronntanas_hp_hud(
        self, parent: tk.Frame, row_index: int
    ) -> None:
        colors = self._colors()
        item = find_or_create_bronntanas_hp_hud(self.data)
        enabled = BooleanVar(value=bool(item.get("enabled", True)))
        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        section.columnconfigure(0, weight=1)
        tk.Label(
            section,
            text=BRONNTANAS_HP_HUD_SECTION_NAME,
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 5))
        tk.Checkbutton(
            section,
            variable=enabled,
            text="启用布本二王50%机制血量监控",
            bg=colors["row"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row"],
            bd=0,
            highlightthickness=0,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(4, 9))
        self.bronntanas_hp_hud_enabled = enabled

    def _build_miracle_orb_hp_hud(
        self, parent: tk.Frame, row_index: int
    ) -> None:
        colors = self._colors()
        item = find_or_create_miracle_orb_hp_hud(self.data)
        enabled = BooleanVar(value=bool(item.get("enabled", True)))
        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        section.columnconfigure(0, weight=1)
        tk.Label(
            section,
            text=MIRACLE_ORB_HP_HUD_SECTION_NAME,
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 5))
        tk.Checkbutton(
            section,
            variable=enabled,
            text="启用布三60%神迹球血量追踪",
            bg=colors["row"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row"],
            bd=0,
            highlightthickness=0,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(4, 9))
        self.miracle_orb_hp_hud_enabled = enabled

    def _build_rotating_laser_countdown_hud(
        self, parent: tk.Frame, row_index: int
    ) -> None:
        colors = self._colors()
        item = find_or_create_rotating_laser_countdown_hud(self.data)
        enabled = BooleanVar(value=bool(item.get("enabled", True)))
        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        section.columnconfigure(0, weight=1)
        tk.Label(
            section,
            text=ROTATING_LASER_COUNTDOWN_HUD_SECTION_NAME,
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 11, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 4))
        tk.Checkbutton(
            section,
            text="启用",
            variable=enabled,
            bg=colors["row"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row"],
            bd=0,
            highlightthickness=0,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(2, 9))
        self.rotating_laser_countdown_hud_enabled = enabled

    def _build_key_enemy_debuff_alert(self, parent: tk.Frame, row_index: int) -> None:
        colors = self._colors()
        item = find_or_create_key_enemy_debuff_alert(self.data)
        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col, weight in [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),
            (4, 1),
            (5, 0),
            (6, 0),
            (7, 0),
        ]:
            section.columnconfigure(col, weight=weight)

        tk.Label(
            section,
            text=KEY_ENEMY_DEBUFF_SECTION_NAME,
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 6), columnspan=8)

        complete_enabled = BooleanVar(
            value=bool(item.get("complete_enabled", item.get("enabled", False)))
        )
        expiry_enabled = BooleanVar(value=bool(item.get("expiry_enabled", True)))
        visual_hud_enabled = BooleanVar(
            value=bool(item.get("visual_hud_enabled", False))
        )
        visual_expiry_enabled = BooleanVar(
            value=bool(item.get("visual_expiry_enabled", True))
        )
        expiry_seconds = IntVar(
            value=int(
                clamp_float(
                    item.get(
                        "expiry_seconds",
                        KEY_ENEMY_DEBUFF_DEFAULT_EXPIRY_SECONDS,
                    ),
                    0,
                    600,
                )
            )
        )
        physical_break_min = StringVar(
            value=key_enemy_debuff_threshold_text(item.get("physical_break_min"))
        )
        magic_break_min = StringVar(
            value=key_enemy_debuff_threshold_text(item.get("magic_break_min"))
        )
        damage_bonus_min = StringVar(
            value=key_enemy_debuff_threshold_text(item.get("damage_bonus_min"))
        )
        rabbit_stacks_min = StringVar(
            value=key_enemy_debuff_threshold_text(item.get("rabbit_stacks_min"))
        )
        complete_sound = StringVar(
            value=item.get("complete_sound", KEY_ENEMY_DEBUFF_COMPLETE_SOUND)
        )
        expiry_sound = StringVar(
            value=item.get("expiry_sound", KEY_ENEMY_DEBUFF_EXPIRY_SOUND)
        )

        row_bg = colors["row_alt"]
        tk.Label(
            section,
            text="DEBUFF上齐提醒",
            bg=row_bg,
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=5, pady=3, ipady=7)
        complete_toggle = tk.Checkbutton(
            section,
            variable=complete_enabled,
            text="ON",
            bg=row_bg,
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=row_bg,
            bd=0,
            highlightthickness=0,
        )
        complete_toggle.grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        complete_entry = tk.Entry(
            section,
            textvariable=complete_sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        )
        complete_entry.grid(row=1, column=2, columnspan=3, sticky="ew", padx=5, pady=3, ipady=5)
        complete_choose = self._button(
            section,
            "选择",
            lambda: self.choose_key_enemy_debuff_sound("complete"),
        )
        complete_choose.grid(row=1, column=5, padx=5, pady=3)
        complete_test = self._button(
            section,
            "试听",
            lambda: self.test_key_enemy_debuff_sound("complete"),
        )
        complete_test.grid(row=1, column=6, padx=5, pady=3)

        tk.Label(
            section,
            text="注意：使用前请先在下方设置队伍的预期破保数额。如实际破保数额未达到设定的数额，将无法触发上齐提醒",
            bg=row_bg,
            fg=colors["muted"],
            font=("Microsoft YaHei UI", 9),
            anchor="w",
            justify="left",
            wraplength=760,
        ).grid(row=2, column=0, columnspan=8, sticky="ew", padx=8, pady=(0, 7))

        row_bg = colors["row"]
        tk.Label(
            section,
            text="破防DEBUFF续期提醒",
            bg=row_bg,
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=3, column=0, sticky="ew", padx=5, pady=3, ipady=7)
        expiry_toggle = tk.Checkbutton(
            section,
            variable=expiry_enabled,
            text="ON",
            bg=row_bg,
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=row_bg,
            bd=0,
            highlightthickness=0,
        )
        expiry_toggle.grid(row=3, column=1, sticky="ew", padx=5, pady=3)
        expiry_seconds_widget = tk.Spinbox(
            section,
            from_=0,
            to=600,
            textvariable=expiry_seconds,
            width=6,
            bg=colors["input"],
            fg=colors["text"],
            buttonbackground=colors["button"],
            relief="solid",
            bd=1,
            justify="center",
        )
        expiry_seconds_widget.grid(row=3, column=2, sticky="ew", padx=5, pady=3, ipady=4)
        tk.Label(
            section,
            text="秒",
            bg=row_bg,
            fg=colors["muted"],
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).grid(row=3, column=3, sticky="w", padx=5, pady=3)
        expiry_entry = tk.Entry(
            section,
            textvariable=expiry_sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        )
        expiry_entry.grid(row=3, column=4, sticky="ew", padx=5, pady=3, ipady=5)
        expiry_choose = self._button(
            section,
            "选择",
            lambda: self.choose_key_enemy_debuff_sound("expiry"),
        )
        expiry_choose.grid(row=3, column=5, padx=5, pady=3)
        expiry_test = self._button(
            section,
            "试听",
            lambda: self.test_key_enemy_debuff_sound("expiry"),
        )
        expiry_test.grid(row=3, column=6, padx=5, pady=3)

        threshold_row = tk.Frame(section, bg=colors["row_alt"])
        threshold_row.grid(row=4, column=0, columnspan=8, sticky="ew", padx=5, pady=(3, 8))
        for col in range(8):
            threshold_row.columnconfigure(col, weight=0)
        labels = [
            ("物理破坏 >=", physical_break_min, 0, 999),
            ("魔法破坏 >=", magic_break_min, 0, 999),
            ("死亡锁定增伤 >=", damage_bonus_min, 0, 999),
            ("兔子层数 >=", rabbit_stacks_min, 1, 10),
        ]
        widgets: list[tk.Entry] = []
        for index, (label, variable, _minimum, _maximum) in enumerate(labels):
            base_col = index * 2
            tk.Label(
                threshold_row,
                text=label,
                bg=colors["row_alt"],
                fg=colors["text"],
                font=("Microsoft YaHei UI", 9, "bold"),
            ).grid(row=0, column=base_col, sticky="w", padx=(8, 4), pady=7)
            widget = tk.Entry(
                threshold_row,
                textvariable=variable,
                width=6,
                bg=colors["input"],
                fg=colors["text"],
                relief="solid",
                bd=1,
                justify="center",
            )
            widget.grid(row=0, column=base_col + 1, sticky="w", padx=(0, 12), pady=7)
            widgets.append(widget)

        self.key_enemy_debuff = KeyEnemyDebuffRow(
            item=item,
            complete_enabled=complete_enabled,
            expiry_enabled=expiry_enabled,
            visual_hud_enabled=visual_hud_enabled,
            visual_expiry_enabled=visual_expiry_enabled,
            expiry_seconds=expiry_seconds,
            physical_break_min=physical_break_min,
            magic_break_min=magic_break_min,
            damage_bonus_min=damage_bonus_min,
            rabbit_stacks_min=rabbit_stacks_min,
            complete_sound=complete_sound,
            expiry_sound=expiry_sound,
            complete_toggle=complete_toggle,
            expiry_toggle=expiry_toggle,
            visual_hud_toggle=None,
            visual_expiry_toggle=None,
            expiry_seconds_widget=expiry_seconds_widget,
            physical_widget=widgets[0],
            magic_widget=widgets[1],
            damage_bonus_widget=widgets[2],
            rabbit_stacks_widget=widgets[3],
            complete_sound_entry=complete_entry,
            expiry_sound_entry=expiry_entry,
            complete_choose=complete_choose,
            expiry_choose=expiry_choose,
            complete_test=complete_test,
            expiry_test=expiry_test,
        )
        complete_enabled.trace_add(
            "write",
            lambda *_args: self._on_key_enemy_debuff_activation_changed(
                complete_enabled
            ),
        )
        expiry_enabled.trace_add("write", lambda *_args: self._sync_key_enemy_debuff_state())
        visual_hud_enabled.trace_add(
            "write",
            lambda *_args: self._on_key_enemy_debuff_activation_changed(
                visual_hud_enabled
            ),
        )
        visual_expiry_enabled.trace_add(
            "write", lambda *_args: self._sync_key_enemy_debuff_state()
        )
        self._sync_key_enemy_debuff_state()

    def _build_boss_red_orb(self, parent: tk.Frame, row_index: int) -> None:
        colors = self._colors()
        item = find_or_create_boss_red_orb_alert(self.data)
        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col, weight in [(0, 0), (1, 0), (2, 1), (3, 0), (4, 0), (5, 0)]:
            section.columnconfigure(col, weight=weight)

        tk.Label(
            section,
            text=BOSS_RED_ORB_NAME,
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 6), columnspan=6)

        enabled = BooleanVar(value=bool(item.get("enabled", True)))
        sound = StringVar(value=item.get("sound", BOSS_RED_ORB_SOUND))
        tk.Label(
            section,
            text=BOSS_RED_ORB_MESSAGE,
            bg=colors["row_alt"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=5, pady=(3, 9), ipady=7)
        toggle = tk.Checkbutton(
            section,
            variable=enabled,
            text="ON",
            bg=colors["row_alt"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row_alt"],
            bd=0,
            highlightthickness=0,
        )
        toggle.grid(row=1, column=1, sticky="ew", padx=5, pady=(3, 9))
        sound_entry = tk.Entry(
            section,
            textvariable=sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        )
        sound_entry.grid(row=1, column=2, sticky="ew", padx=5, pady=(3, 9), ipady=5)
        choose = self._button(section, "选择", self.choose_boss_red_orb_sound)
        choose.grid(row=1, column=3, padx=5, pady=(3, 9))
        test = self._button(section, "试听", self.test_boss_red_orb_sound)
        test.grid(row=1, column=4, padx=5, pady=(3, 9))
        voice_pack = self._button(
            section, "\u8bed\u97f3\u5305", self.choose_boss_red_orb_voice_pack
        )
        voice_pack.grid(row=1, column=5, padx=(5, 12), pady=(3, 9))
        self.boss_red_orb = BossRedOrbRow(
            item=item,
            enabled=enabled,
            sound=sound,
            toggle=toggle,
            sound_entry=sound_entry,
            choose=choose,
            test=test,
            voice_pack=voice_pack,
        )
        enabled.trace_add("write", lambda *_args: self._sync_boss_red_orb_state())
        self._sync_boss_red_orb_state()

    def _build_boss_laser(self, parent: tk.Frame, row_index: int) -> None:
        colors = self._colors()
        item = find_or_create_boss_laser_alert(self.data)
        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col, weight in [(0, 0), (1, 0), (2, 1), (3, 0), (4, 0), (5, 0)]:
            section.columnconfigure(col, weight=weight)

        tk.Label(
            section,
            text=BOSS_LASER_ALERT_NAME,
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(12, 8), pady=(9, 6))
        enabled = BooleanVar(value=bool(item.get("enabled", False)))
        sound = StringVar(value=item.get("sound", BOSS_LASER_ALERT_SOUND))
        tk.Label(
            section,
            text=BOSS_LASER_ALERT_MESSAGE,
            bg=colors["row_alt"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=5, pady=(3, 9), ipady=7)
        toggle = tk.Checkbutton(
            section,
            variable=enabled,
            text="ON",
            bg=colors["row_alt"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row_alt"],
            bd=0,
            highlightthickness=0,
        )
        toggle.grid(row=1, column=1, sticky="ew", padx=5, pady=(3, 9))
        sound_entry = tk.Entry(
            section,
            textvariable=sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        )
        sound_entry.grid(row=1, column=2, sticky="ew", padx=5, pady=(3, 9), ipady=5)
        choose = self._button(section, "选择", self.choose_boss_laser_sound)
        choose.grid(row=1, column=3, padx=5, pady=(3, 9))
        test = self._button(section, "试听", self.test_boss_laser_sound)
        test.grid(row=1, column=4, padx=5, pady=(3, 9))
        voice_pack = self._button(
            section, "\u8bed\u97f3\u5305", self.choose_boss_laser_voice_pack
        )
        voice_pack.grid(row=1, column=5, padx=(5, 12), pady=(3, 9))
        self.boss_laser = BossLaserAlertRow(
            item=item,
            enabled=enabled,
            sound=sound,
            toggle=toggle,
            sound_entry=sound_entry,
            choose=choose,
            test=test,
            voice_pack=voice_pack,
        )
        enabled.trace_add("write", lambda *_args: self._sync_boss_laser_state())
        self._sync_boss_laser_state()

    def _build_special_end_only(self, parent: tk.Frame, row_index: int) -> None:
        colors = self._colors()
        section = tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col, weight in [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 1),
            (4, 0),
            (5, 0),
            (6, 0),
            (7, 0),
            (8, 1),
            (9, 0),
            (10, 0),
        ]:
            section.columnconfigure(col, weight=weight)

        tk.Label(
            section,
            text="结束与冷却提醒",
            bg=colors["row"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 6), columnspan=11)

        headers = [
            "项目",
            "启用",
            "结束提醒",
            "结束音源",
            "",
            "",
            "冷却提醒",
            "冷却时长",
            "冷却音源",
            "",
            "",
        ]
        for col, text in enumerate(headers):
            tk.Label(
                section,
                text=text,
                bg=colors["row"],
                fg=colors["muted"],
                font=("Microsoft YaHei UI", 9, "bold"),
            ).grid(row=1, column=col, sticky="w", padx=5, pady=(4, 6))

        for offset, name in enumerate(SPECIAL_END_ONLY_ORDER, start=2):
            item = find_or_create_special_end_only(self.data, name)
            rules = SPECIAL_END_ONLY_DEFAULTS[name]
            enabled = BooleanVar(value=bool(item.get("enabled", True)))
            ended_enabled = BooleanVar(value=bool(item.get("ended_alert", True)))
            ended_sound = StringVar(value=item.get("ended_sound", rules["ended_sound"]))
            cooldown_enabled = BooleanVar(
                value=bool(item.get("cooldown_alert", rules["cooldown_enabled"]))
            )
            try:
                cooldown_value = int(
                    float(item.get("cooldown_delay_seconds", rules["cooldown_seconds"]))
                )
            except (TypeError, ValueError):
                cooldown_value = int(rules["cooldown_seconds"])
            if rules.get("cooldown_fixed"):
                cooldown_value = int(rules["cooldown_seconds"])
            elif "cooldown_choices" in rules:
                if cooldown_value not in rules["cooldown_choices"]:
                    cooldown_value = int(rules["cooldown_seconds"])
            else:
                cooldown_value = max(
                    int(rules["cooldown_min"]),
                    min(int(rules["cooldown_max"]), cooldown_value),
                )
            cooldown_seconds = IntVar(value=cooldown_value)
            cooldown_sound = StringVar(
                value=item.get("cooldown_sound", rules["cooldown_sound"])
            )
            row_bg = colors["row_alt"] if offset % 2 else colors["row"]

            tk.Label(
                section,
                text=name,
                bg=row_bg,
                fg=colors["text"],
                font=("Microsoft YaHei UI", 10, "bold"),
                anchor="w",
            ).grid(row=offset, column=0, sticky="ew", padx=5, pady=3, ipady=7)
            tk.Checkbutton(
                section,
                variable=enabled,
                text="ON",
                bg=row_bg,
                fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=row_bg,
                bd=0,
                highlightthickness=0,
            ).grid(row=offset, column=1, sticky="ew", padx=5, pady=3)
            ended_toggle = tk.Checkbutton(
                section,
                variable=ended_enabled,
                text="ON",
                bg=row_bg,
                fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=row_bg,
                bd=0,
                highlightthickness=0,
            )
            ended_toggle.grid(row=offset, column=2, sticky="ew", padx=5, pady=3)
            ended_entry = tk.Entry(
                section,
                textvariable=ended_sound,
                bg=colors["input"],
                fg=colors["text"],
                relief="solid",
                bd=1,
            )
            ended_entry.grid(row=offset, column=3, sticky="ew", padx=5, pady=3, ipady=5)
            ended_choose = self._button(
                section,
                "选择",
                lambda r=len(self.special_end_only_rows): self.choose_special_sound(
                    r, "ended"
                ),
            )
            ended_choose.grid(row=offset, column=4, padx=5, pady=3)
            ended_test = self._button(
                section,
                "试听",
                lambda r=len(self.special_end_only_rows): self.test_special_sound(
                    r, "ended"
                ),
            )
            ended_test.grid(row=offset, column=5, padx=5, pady=3)
            cooldown_toggle = tk.Checkbutton(
                section,
                variable=cooldown_enabled,
                text="ON",
                bg=row_bg,
                fg=colors["text"],
                selectcolor=colors["accent"],
                activebackground=row_bg,
                bd=0,
                highlightthickness=0,
            )
            cooldown_toggle.grid(row=offset, column=6, sticky="ew", padx=5, pady=3)
            if rules.get("cooldown_fixed"):
                cooldown_widget = tk.Label(
                    section,
                    text=f"{rules['cooldown_seconds']} 秒（固定）",
                    bg=row_bg,
                    fg=colors["text"],
                    font=("Microsoft YaHei UI", 9),
                    anchor="center",
                )
            elif "cooldown_choices" in rules:
                cooldown_widget = tk.OptionMenu(
                    section,
                    cooldown_seconds,
                    *rules["cooldown_choices"],
                )
                cooldown_widget.configure(
                    width=7,
                    bg=colors["input"],
                    fg=colors["text"],
                    activebackground=colors["button"],
                    activeforeground=colors["text"],
                    relief="solid",
                    bd=1,
                    highlightthickness=0,
                )
                cooldown_widget["menu"].configure(
                    bg=colors["input"],
                    fg=colors["text"],
                    activebackground=colors["accent"],
                )
            else:
                cooldown_widget = tk.Spinbox(
                    section,
                    from_=rules["cooldown_min"],
                    to=rules["cooldown_max"],
                    textvariable=cooldown_seconds,
                    width=7,
                    bg=colors["input"],
                    fg=colors["text"],
                    buttonbackground=colors["button"],
                    relief="solid",
                    bd=1,
                    justify="center",
                )
            cooldown_widget.grid(row=offset, column=7, sticky="ew", padx=5, pady=3, ipady=4)
            cooldown_entry = tk.Entry(
                section,
                textvariable=cooldown_sound,
                bg=colors["input"],
                fg=colors["text"],
                relief="solid",
                bd=1,
            )
            cooldown_entry.grid(
                row=offset, column=8, sticky="ew", padx=5, pady=3, ipady=5
            )
            cooldown_choose = self._button(
                section,
                "选择",
                lambda r=len(self.special_end_only_rows): self.choose_special_sound(
                    r, "cooldown"
                ),
            )
            cooldown_choose.grid(row=offset, column=9, padx=5, pady=3)
            cooldown_test = self._button(
                section,
                "试听",
                lambda r=len(self.special_end_only_rows): self.test_special_sound(
                    r, "cooldown"
                ),
            )
            cooldown_test.grid(row=offset, column=10, padx=(5, 12), pady=3)

            row = SpecialEndOnlyRow(
                item=item,
                enabled=enabled,
                ended_enabled=ended_enabled,
                ended_sound=ended_sound,
                cooldown_enabled=cooldown_enabled,
                cooldown_seconds=cooldown_seconds,
                cooldown_sound=cooldown_sound,
                cooldown_widget=cooldown_widget,
                ended_toggle=ended_toggle,
                ended_sound_entry=ended_entry,
                ended_choose=ended_choose,
                ended_test=ended_test,
                cooldown_toggle=cooldown_toggle,
                cooldown_sound_entry=cooldown_entry,
                cooldown_choose=cooldown_choose,
                cooldown_test=cooldown_test,
            )
            self.special_end_only_rows.append(row)
            enabled.trace_add(
                "write",
                lambda *_args, special_row=row: self._sync_special_end_only_state(
                    special_row
                ),
            )
            ended_enabled.trace_add(
                "write",
                lambda *_args, special_row=row: self._sync_special_end_only_state(
                    special_row
                ),
            )
            cooldown_enabled.trace_add(
                "write",
                lambda *_args, special_row=row: self._sync_special_end_only_state(
                    special_row
                ),
            )
            self._sync_special_end_only_state(row)

    def _build_food_timer(self, parent: tk.Frame, row_index: int) -> None:
        colors = self._colors()
        item = find_or_create_food_effect(self.data)
        timer_enabled = BooleanVar(value=bool(item.get("timer_enabled", False)))
        duration_seconds = IntVar(value=max(0, int(item.get("duration_seconds", 0))))
        remaining_enabled = BooleanVar(value=bool(item.get("alerts") or []))
        remaining_seconds = IntVar(value=max(0, food_remaining_seconds(item)))
        remaining_sound = StringVar(value=food_remaining_sound(item))
        ended_sound = StringVar(value=item.get("ended_sound", DEFAULT_ENDED_SOUND))

        section = tk.Frame(parent, bg=colors["row_alt"], bd=1, relief="solid")
        section.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(8, 10))
        for col, weight in [(0, 0), (1, 0), (2, 0), (3, 0), (4, 1), (5, 0), (6, 0), (7, 1), (8, 0), (9, 0)]:
            section.columnconfigure(col, weight=weight)

        tk.Label(
            section,
            text="庆典料理倒计时",
            bg=colors["row_alt"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 6), columnspan=10)

        tk.Checkbutton(
            section,
            variable=timer_enabled,
            text="启用倒计时",
            bg=colors["row_alt"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row_alt"],
            bd=0,
            highlightthickness=0,
        ).grid(row=1, column=0, sticky="w", padx=12, pady=6)
        tk.Label(
            section,
            text="持续秒数",
            bg=colors["row_alt"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
        ).grid(row=1, column=1, sticky="e", padx=5, pady=6)
        duration_widget = tk.Spinbox(
            section,
            from_=0,
            to=99999,
            textvariable=duration_seconds,
            width=8,
            bg=colors["input"],
            fg=colors["text"],
            buttonbackground=colors["button"],
            relief="solid",
            bd=1,
            justify="center",
        )
        duration_widget.grid(row=1, column=2, sticky="ew", padx=5, pady=6, ipady=4)

        tk.Checkbutton(
            section,
            variable=remaining_enabled,
            text="剩余提醒",
            bg=colors["row_alt"],
            fg=colors["text"],
            selectcolor=colors["accent"],
            activebackground=colors["row_alt"],
            bd=0,
            highlightthickness=0,
        ).grid(row=1, column=3, sticky="w", padx=5, pady=6)
        remaining_widget = tk.Spinbox(
            section,
            from_=0,
            to=99999,
            textvariable=remaining_seconds,
            width=8,
            bg=colors["input"],
            fg=colors["text"],
            buttonbackground=colors["button"],
            relief="solid",
            bd=1,
            justify="center",
        )
        remaining_widget.grid(row=1, column=4, sticky="ew", padx=5, pady=6, ipady=4)

        tk.Entry(
            section,
            textvariable=remaining_sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        ).grid(row=2, column=0, sticky="ew", padx=(12, 5), pady=(4, 10), columnspan=4, ipady=5)
        self._button(section, "提醒音源", lambda: self.choose_food_sound("remaining")).grid(
            row=2, column=4, sticky="ew", padx=5, pady=(4, 10)
        )
        self._button(section, "试听", lambda: self.test_food_sound("remaining")).grid(
            row=2, column=5, sticky="ew", padx=5, pady=(4, 10)
        )
        tk.Entry(
            section,
            textvariable=ended_sound,
            bg=colors["input"],
            fg=colors["text"],
            relief="solid",
            bd=1,
        ).grid(row=2, column=6, sticky="ew", padx=5, pady=(4, 10), columnspan=2, ipady=5)
        self._button(section, "结束音源", lambda: self.choose_food_sound("ended")).grid(
            row=2, column=8, sticky="ew", padx=5, pady=(4, 10)
        )
        self._button(section, "试听", lambda: self.test_food_sound("ended")).grid(
            row=2, column=9, sticky="ew", padx=(5, 12), pady=(4, 10)
        )

        self.food_timer = FoodTimerRow(
            item=item,
            timer_enabled=timer_enabled,
            duration_seconds=duration_seconds,
            remaining_enabled=remaining_enabled,
            remaining_seconds=remaining_seconds,
            remaining_sound=remaining_sound,
            ended_sound=ended_sound,
            duration_widget=duration_widget,
            remaining_widget=remaining_widget,
        )
        timer_enabled.trace_add("write", lambda *_args: self._sync_food_timer_state())
        remaining_enabled.trace_add("write", lambda *_args: self._sync_food_timer_state())
        self._sync_food_timer_state()

    def _sync_volume_label(self) -> None:
        self.volume_label.configure(text=f"{self.volume.get()}%")

    def _sync_visual_hud_state(self) -> None:
        if self.visual_hud is None:
            return
        row = self.visual_hud
        master_enabled = bool(row.enabled.get())
        for ccid, toggle in row.condition_toggles.items():
            toggle.configure(state="normal" if master_enabled else "disabled")
            detail_state = (
                "normal"
                if master_enabled and row.condition_enabled[ccid].get()
                else "disabled"
            )
            for widget in (
                row.show_before_widgets[ccid],
                row.ring_toggles[ccid],
                row.icon_entries[ccid],
                row.icon_choose_buttons[ccid],
                row.icon_reset_buttons[ccid],
            ):
                widget.configure(state=detail_state)

    def _sync_other_skill_hud_state(self) -> None:
        if self.other_skill_hud is None:
            return
        row = self.other_skill_hud
        master_enabled = bool(row.enabled.get())
        for key, toggle in row.condition_toggles.items():
            toggle.configure(state="normal" if master_enabled else "disabled")
            detail_state = (
                "normal"
                if master_enabled and row.condition_enabled[key].get()
                else "disabled"
            )
            for widget in (
                row.icon_entries[key],
                row.icon_choose_buttons[key],
                row.icon_reset_buttons[key],
            ):
                widget.configure(state=detail_state)

    def _sync_short_cooldown_hud_state(self) -> None:
        if self.short_cooldown_hud is None:
            return
        row = self.short_cooldown_hud
        for key, toggle in row.condition_toggles.items():
            toggle.configure(state="normal")
            detail_state = (
                "normal" if row.condition_enabled[key].get() else "disabled"
            )
            for widget in (
                row.cooldown_widgets[key],
                row.icon_entries[key],
                row.icon_choose_buttons[key],
                row.icon_reset_buttons[key],
            ):
                widget.configure(state=detail_state)

    def _sync_seconds_state(self, row: BuffRow) -> None:
        if item_remaining_locked(row.item):
            if row.remaining_enabled.get():
                row.remaining_enabled.set(False)
            row.remaining_toggle.configure(state="disabled")
            row.seconds_widget.configure(state="disabled")
            row.remaining_sound_entry.configure(state="disabled")
            row.remaining_choose.configure(state="disabled")
            row.remaining_test.configure(state="disabled")
            return

        row.remaining_toggle.configure(state="normal")
        row.remaining_sound_entry.configure(state="normal")
        row.remaining_choose.configure(state="normal")
        row.remaining_test.configure(state="normal")
        state = "normal" if row.remaining_enabled.get() else "disabled"
        row.seconds_widget.configure(state=state)

    def _sync_food_timer_state(self) -> None:
        if self.food_timer is None:
            return
        timer_state = "normal" if self.food_timer.timer_enabled.get() else "disabled"
        remaining_state = (
            "normal"
            if self.food_timer.timer_enabled.get() and self.food_timer.remaining_enabled.get()
            else "disabled"
        )
        self.food_timer.duration_widget.configure(state=timer_state)
        self.food_timer.remaining_widget.configure(state=remaining_state)

    def _sync_magic_shield_state(self) -> None:
        if self.magic_shield_delay is None:
            return
        row = self.magic_shield_delay
        enabled = row.enabled.get()
        ended_state = "normal" if enabled and row.ended_enabled.get() else "disabled"
        missing_state = (
            "normal" if enabled and row.missing_enabled.get() else "disabled"
        )
        row.ended_toggle.configure(state="normal" if enabled else "disabled")
        row.ended_sound_entry.configure(state=ended_state)
        row.ended_choose.configure(state=ended_state)
        row.ended_test.configure(state=ended_state)
        row.delay_widget.configure(state=ended_state)
        row.missing_toggle.configure(state="normal" if enabled else "disabled")
        row.missing_sound_entry.configure(state=missing_state)
        row.missing_choose.configure(state=missing_state)
        row.missing_test.configure(state=missing_state)
        row.missing_delay_widget.configure(state=missing_state)

    def _sync_azure_wound_state(self) -> None:
        if self.azure_wound is None:
            return
        row = self.azure_wound
        enabled_state = "normal" if row.enabled.get() else "disabled"
        row.danger_widget.configure(state=enabled_state)
        row.danger_sound_entry.configure(state=enabled_state)
        row.danger_choose.configure(state=enabled_state)
        row.danger_test.configure(state=enabled_state)
        row.clear_toggle.configure(state=enabled_state)
        clear_state = (
            "normal" if row.enabled.get() and row.clear_enabled.get() else "disabled"
        )
        row.clear_sound_entry.configure(state=clear_state)
        row.clear_choose.configure(state=clear_state)
        row.clear_test.configure(state=clear_state)

    def _sync_safehouse_state(self) -> None:
        if self.safehouse is None:
            return
        state = "normal" if self.safehouse.enabled.get() else "disabled"
        self.safehouse.lead_widget.configure(state=state)
        self.safehouse.warning_sound_entry.configure(state=state)
        self.safehouse.warning_choose.configure(state=state)
        self.safehouse.warning_test.configure(state=state)

    def _sync_boss_hp_state(self, row: BossHpAlertRow) -> None:
        state = "normal" if row.enabled.get() else "disabled"
        row.thresholds_entry.configure(state=state)
        row.sound_entry.configure(state=state)
        row.choose.configure(state=state)
        row.test.configure(state=state)

    def _sync_boss_red_orb_state(self) -> None:
        if self.boss_red_orb is None:
            return
        self.boss_red_orb.sound_entry.configure(state="normal")
        self.boss_red_orb.choose.configure(state="normal")
        self.boss_red_orb.test.configure(state="normal")
        self.boss_red_orb.voice_pack.configure(state="normal")

    def _sync_boss_laser_state(self) -> None:
        if self.boss_laser is None:
            return
        self.boss_laser.sound_entry.configure(state="normal")
        self.boss_laser.choose.configure(state="normal")
        self.boss_laser.test.configure(state="normal")
        self.boss_laser.voice_pack.configure(state="normal")

    def _key_enemy_debuff_threshold_values(self) -> dict[str, object]:
        if self.key_enemy_debuff is None:
            return {}
        row = self.key_enemy_debuff
        return {
            "physical_break_min": row.physical_break_min.get(),
            "magic_break_min": row.magic_break_min.get(),
            "damage_bonus_min": row.damage_bonus_min.get(),
            "rabbit_stacks_min": row.rabbit_stacks_min.get(),
        }

    def _on_key_enemy_debuff_activation_changed(
        self,
        variable: BooleanVar,
    ) -> None:
        if variable.get():
            try:
                parse_key_enemy_debuff_threshold_values(
                    self._key_enemy_debuff_threshold_values(),
                    require_complete=True,
                )
            except ValueError as exc:
                messagebox.showerror("无法启用破防上齐提醒", str(exc))
                variable.set(False)
                return
        self._sync_key_enemy_debuff_state()

    def _sync_key_enemy_debuff_state(self) -> None:
        if self.key_enemy_debuff is None:
            return
        row = self.key_enemy_debuff
        complete_state = "normal" if row.complete_enabled.get() else "disabled"
        expiry_state = "normal" if row.expiry_enabled.get() else "disabled"
        expiry_seconds_state = (
            "normal"
            if row.expiry_enabled.get() or row.visual_expiry_enabled.get()
            else "disabled"
        )
        row.complete_sound_entry.configure(state=complete_state)
        row.complete_choose.configure(state=complete_state)
        row.complete_test.configure(state=complete_state)
        row.expiry_seconds_widget.configure(state=expiry_seconds_state)
        row.expiry_sound_entry.configure(state=expiry_state)
        row.expiry_choose.configure(state=expiry_state)
        row.expiry_test.configure(state=expiry_state)
        for widget in (
            row.physical_widget,
            row.magic_widget,
            row.damage_bonus_widget,
            row.rabbit_stacks_widget,
        ):
            widget.configure(state="normal")

    def _sync_special_end_only_state(self, row: SpecialEndOnlyRow) -> None:
        enabled = row.enabled.get()
        ended_state = "normal" if enabled and row.ended_enabled.get() else "disabled"
        cooldown_state = (
            "normal" if enabled and row.cooldown_enabled.get() else "disabled"
        )
        row.ended_toggle.configure(state="normal" if enabled else "disabled")
        row.ended_sound_entry.configure(state=ended_state)
        row.ended_choose.configure(state=ended_state)
        row.ended_test.configure(state=ended_state)
        row.cooldown_toggle.configure(state="normal" if enabled else "disabled")
        row.cooldown_widget.configure(state=cooldown_state)
        row.cooldown_sound_entry.configure(state=cooldown_state)
        row.cooldown_choose.configure(state=cooldown_state)
        row.cooldown_test.configure(state=cooldown_state)

    def _colors(self) -> dict[str, str]:
        return dict(SETTINGS_COLORS)

    def _set_window_icon(self) -> None:
        image_candidates = [
            self.config_dir / "assets" / "icon" / "buffwatcher_icon.png",
            app_root() / "assets" / "icon" / "buffwatcher_icon.png",
        ]
        for image_path in image_candidates:
            if not image_path.is_file():
                continue
            try:
                self.window_icon_image = tk.PhotoImage(file=str(image_path))
                self.root.iconphoto(True, self.window_icon_image)
                break
            except tk.TclError:
                continue
        candidates = [
            self.config_dir / "assets" / "icon" / "buffwatcher.ico",
            app_root() / "assets" / "icon" / "buffwatcher.ico",
        ]
        for icon_path in candidates:
            if not icon_path.is_file():
                continue
            try:
                self.root.iconbitmap(str(icon_path))
                return
            except tk.TclError:
                continue

    def _row_frame(self, parent: tk.Frame) -> tk.Frame:
        colors = self._colors()
        return tk.Frame(parent, bg=colors["row"], bd=1, relief="solid")

    def _button(
        self,
        parent: tk.Misc,
        text: str,
        command: object,
        *,
        primary: bool = False,
    ) -> tk.Button:
        colors = self._colors()
        bg = colors["accent"] if primary else "#eee5d8"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            activebackground=colors["accent_dark"],
            fg=colors["text"],
            relief="solid",
            bd=1,
            padx=18,
            pady=5,
            font=("Microsoft YaHei UI", 10, "bold"),
        )

    def choose_sound(self, row_index: int, kind: str) -> None:
        row = self.rows[row_index]
        label = "结束提醒" if kind == "ended" else "剩余提醒"
        selected = filedialog.askopenfilename(
            title=f"选择 {row.item['name']} 的{label}音源",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return

        identifier = row.item.get("ccid", row.item.get("stat_id", "item"))
        value = self._import_sound(Path(selected), identifier, kind)
        if kind == "ended":
            row.ended_sound.set(value)
        else:
            row.remaining_sound.set(value)

    def choose_magic_shield_sound(self) -> None:
        if self.magic_shield_delay is None:
            return
        selected = filedialog.askopenfilename(
            title=f"选择 {MAGIC_SHIELD_NAME} 的结束提醒音源",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return

        value = self._import_sound(Path(selected), 59, "ended")
        self.magic_shield_delay.ended_sound.set(value)

    def choose_magic_shield_missing_sound(self) -> None:
        if self.magic_shield_delay is None:
            return
        selected = filedialog.askopenfilename(
            title=f"选择 {MAGIC_SHIELD_MISSING_ALERT_NAME} 的音源",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return

        value = self._import_sound(Path(selected), 59, "missing")
        self.magic_shield_delay.missing_sound.set(value)

    def choose_food_sound(self, kind: str) -> None:
        if self.food_timer is None:
            return
        label = "结束提醒" if kind == "ended" else "剩余提醒"
        selected = filedialog.askopenfilename(
            title=f"选择 {FOOD_EFFECT_NAME} 的{label}音源",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return

        value = self._import_sound(Path(selected), "food", kind)
        if kind == "ended":
            self.food_timer.ended_sound.set(value)
        else:
            self.food_timer.remaining_sound.set(value)

    def choose_safehouse_sound(self) -> None:
        if self.safehouse is None:
            return
        selected = filedialog.askopenfilename(
            title=f"选择 {SAFEHOUSE_NAME} 的预警音源",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return

        value = self._import_sound(Path(selected), "safehouse", "warning")
        self.safehouse.warning_sound.set(value)

    def choose_boss_hp_sound(self, row_index: int) -> None:
        row = self.boss_hp_rows[row_index]
        selected = filedialog.askopenfilename(
            title=f"选择 {row.item.get('short_name', row.item.get('name', 'Boss'))} 的血量提醒音源",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return

        value = self._import_sound(
            Path(selected), row.item.get("entity_id", "boss_hp"), "boss_hp"
        )
        row.sound.set(value)

    def choose_boss_red_orb_sound(self) -> None:
        if self.boss_red_orb is None:
            return
        selected = filedialog.askopenfilename(
            title=f"选择 {BOSS_RED_ORB_NAME} 的预警音源",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return

        value = self._import_sound(Path(selected), "boss_red_orb", "warning")
        self.boss_red_orb.sound.set(value)

    def choose_boss_laser_sound(self) -> None:
        if self.boss_laser is None:
            return
        selected = filedialog.askopenfilename(
            title=f"选择 {BOSS_LASER_ALERT_NAME} 的预警音源",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return

        value = self._import_sound(Path(selected), "boss_laser", "warning")
        self.boss_laser.sound.set(value)

    @staticmethod
    def _voice_pack_file(folder: Path, *names: str) -> Path | None:
        extensions = (".wav", ".mp3", ".m4a", ".wma", ".aac")
        for name in names:
            path = folder / name
            if path.is_file():
                return path
            stem = Path(name).stem
            for extension in extensions:
                candidate = folder / f"{stem}{extension}"
                if candidate.is_file():
                    return candidate
        return None

    def _import_voice_pack_file(
        self,
        folder: Path,
        identifier: object,
        kind: str,
        *names: str,
    ) -> str | None:
        path = self._voice_pack_file(folder, *names)
        if path is None:
            return None
        return self._import_sound(path, identifier, kind)

    def _import_voice_pack_countdown(
        self,
        folder: Path,
        identifier: object,
        numbers: list[int],
        existing: dict | None,
    ) -> dict[str, str]:
        result = {str(key): str(value) for key, value in (existing or {}).items()}
        for number in numbers:
            names = (
                f"count_{number:02d}.wav",
                f"count_{number}.wav",
                f"{number}.wav",
                f"{number:02d}.wav",
            )
            value = self._import_voice_pack_file(
                folder, identifier, f"count_{number}", *names
            )
            if value:
                result[str(number)] = value
        return result

    def choose_boss_red_orb_voice_pack(self) -> None:
        if self.boss_red_orb is None:
            return
        selected = filedialog.askdirectory(title="\u9009\u62e9\u7ea2\u7403\u64ad\u62a5\u8bed\u97f3\u5305\u76ee\u5f55")
        if not selected:
            return
        folder = Path(selected)
        prefix = self._import_voice_pack_file(
            folder,
            "boss_red_orb",
            "warning",
            "danger_red_orb.wav",
            "warning.wav",
            "prefix.wav",
            "red_orb.wav",
        )
        if prefix:
            self.boss_red_orb.sound.set(prefix)
        safe = self._import_voice_pack_file(
            folder,
            "boss_red_orb",
            "safe",
            "safe_complete.wav",
            "safe.wav",
            "complete.wav",
            "success.wav",
        )
        if safe:
            self.boss_red_orb.item["safe_sound"] = safe
        self.boss_red_orb.item["countdown_sounds"] = self._import_voice_pack_countdown(
            folder,
            "boss_red_orb",
            [5, 4, 3, 2, 1, 0],
            self.boss_red_orb.item.get("countdown_sounds"),
        )
        messagebox.showinfo(
            "\u8bed\u97f3\u5305",
            "\u7ea2\u7403\u64ad\u62a5\u8bed\u97f3\u5305\u5df2\u5bfc\u5165\u3002",
        )

    def choose_boss_laser_voice_pack(self) -> None:
        if self.boss_laser is None:
            return
        selected = filedialog.askdirectory(title="\u9009\u62e9\u6fc0\u5149\u9884\u8b66\u8bed\u97f3\u5305\u76ee\u5f55")
        if not selected:
            return
        folder = Path(selected)
        prefix = self._import_voice_pack_file(
            folder,
            "boss_laser",
            "warning",
            "laser_warning_prefix.wav",
            "warning.wav",
            "prefix.wav",
            "laser.wav",
        )
        if prefix:
            self.boss_laser.sound.set(prefix)
        self.boss_laser.item["countdown_sounds"] = self._import_voice_pack_countdown(
            folder,
            "boss_laser",
            [4, 3, 2, 1, 0],
            self.boss_laser.item.get("countdown_sounds"),
        )
        messagebox.showinfo(
            "\u8bed\u97f3\u5305",
            "\u6fc0\u5149\u9884\u8b66\u8bed\u97f3\u5305\u5df2\u5bfc\u5165\u3002",
        )

    def choose_key_enemy_debuff_sound(self, kind: str) -> None:
        if self.key_enemy_debuff is None:
            return
        label = "DEBUFF上齐提醒" if kind == "complete" else "破防DEBUFF续期提醒"
        selected = filedialog.askopenfilename(
            title=f"选择 {KEY_ENEMY_DEBUFF_SECTION_NAME} 的{label}音源",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return

        value = self._import_sound(Path(selected), "key_enemy_debuff", kind)
        if kind == "complete":
            self.key_enemy_debuff.complete_sound.set(value)
        else:
            self.key_enemy_debuff.expiry_sound.set(value)

    def choose_azure_wound_sound(self, kind: str) -> None:
        if self.azure_wound is None:
            return
        label = "消除提示" if kind == "clear" else "危险提醒"
        selected = filedialog.askopenfilename(
            title=f"选择 {AZURE_WOUND_NAME} 的{label}音源",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return

        value = self._import_sound(Path(selected), AZURE_WOUND_CCID, kind)
        if kind == "clear":
            self.azure_wound.clear_sound.set(value)
        else:
            self.azure_wound.danger_sound.set(value)

    def choose_special_sound(self, row_index: int, kind: str) -> None:
        row = self.special_end_only_rows[row_index]
        label = "冷却提醒" if kind == "cooldown" else "结束提醒"
        selected = filedialog.askopenfilename(
            title=f"选择 {row.item['name']} 的{label}音源",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.m4a *.wma *.aac"),
                ("所有文件", "*.*"),
            ],
        )
        if not selected:
            return

        identifier = row.item.get("ccid", "special")
        value = self._import_sound(Path(selected), identifier, kind)
        if kind == "cooldown":
            row.cooldown_sound.set(value)
        else:
            row.ended_sound.set(value)

    def choose_visual_hud_icon(self, ccid: int) -> None:
        if self.visual_hud is None or ccid not in VISUAL_HUD_CONDITION_DEFAULTS:
            return
        label = VISUAL_HUD_CONDITION_DEFAULTS[ccid]["name"]
        selected = filedialog.askopenfilename(
            title=f"选择 {label} 的 HUD 图标",
            filetypes=[
                ("支持的图片", "*.png *.gif"),
                ("PNG 图片", "*.png"),
                ("GIF 图片", "*.gif"),
            ],
        )
        if not selected:
            return
        value = self._import_visual_hud_icon(Path(selected), ccid)
        self.visual_hud.condition_icons[ccid].set(value)

    def reset_visual_hud_icon(self, ccid: int) -> None:
        if self.visual_hud is None or ccid not in VISUAL_HUD_DEFAULT_ICONS:
            return
        self.visual_hud.condition_icons[ccid].set(VISUAL_HUD_DEFAULT_ICONS[ccid])

    def _import_visual_hud_icon(self, source: Path, ccid: int) -> str:
        custom_dir = self.config_dir / "assets" / "custom" / "visual_hud"
        custom_dir.mkdir(parents=True, exist_ok=True)
        suffix = source.suffix.lower()
        target = custom_dir / f"{ccid}{suffix}"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return relpath(target, self.config_dir)

    def choose_other_skill_hud_icon(self, key: str) -> None:
        if (
            self.other_skill_hud is None
            or key not in OTHER_SKILL_HUD_CONDITION_DEFAULTS
        ):
            return
        label = OTHER_SKILL_HUD_CONDITION_DEFAULTS[key]["name"]
        selected = filedialog.askopenfilename(
            title=f"选择 {label} 的 HUD 图标",
            filetypes=[
                ("支持的图片", "*.png *.gif"),
                ("PNG 图片", "*.png"),
                ("GIF 图片", "*.gif"),
            ],
        )
        if not selected:
            return
        value = self._import_other_skill_hud_icon(Path(selected), key)
        self.other_skill_hud.condition_icons[key].set(value)

    def reset_other_skill_hud_icon(self, key: str) -> None:
        if (
            self.other_skill_hud is None
            or key not in OTHER_SKILL_HUD_CONDITION_DEFAULTS
        ):
            return
        self.other_skill_hud.condition_icons[key].set(
            OTHER_SKILL_HUD_CONDITION_DEFAULTS[key]["icon"]
        )

    def _import_other_skill_hud_icon(self, source: Path, key: str) -> str:
        custom_dir = self.config_dir / "assets" / "custom" / "other_skill_hud"
        custom_dir.mkdir(parents=True, exist_ok=True)
        suffix = source.suffix.lower()
        target = custom_dir / f"{key}{suffix}"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return relpath(target, self.config_dir)

    def choose_short_cooldown_hud_icon(self, key: str) -> None:
        if (
            self.short_cooldown_hud is None
            or key not in SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS
        ):
            return
        name = SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS[key]["name"]
        selected = filedialog.askopenfilename(
            title=f"选择{name}的 HUD 图标",
            filetypes=[
                ("支持的图片", "*.png *.gif"),
                ("PNG 图片", "*.png"),
                ("GIF 图片", "*.gif"),
            ],
        )
        if not selected:
            return
        value = self._import_short_cooldown_hud_icon(Path(selected), key)
        self.short_cooldown_hud.condition_icons[key].set(value)

    def reset_short_cooldown_hud_icon(self, key: str) -> None:
        if (
            self.short_cooldown_hud is None
            or key not in SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS
        ):
            return
        self.short_cooldown_hud.condition_icons[key].set(
            SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS[key]["icon"]
        )

    def _import_short_cooldown_hud_icon(self, source: Path, key: str) -> str:
        custom_dir = self.config_dir / "assets" / "custom" / "short_cooldown_hud"
        custom_dir.mkdir(parents=True, exist_ok=True)
        suffix = source.suffix.lower()
        target = custom_dir / f"{key}{suffix}"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return relpath(target, self.config_dir)

    def _import_sound(self, source: Path, identifier: object, kind: str) -> str:
        custom_dir = self.config_dir / "assets" / "custom"
        custom_dir.mkdir(parents=True, exist_ok=True)
        target = custom_dir / source.name
        if target.exists() and source.resolve() != target.resolve():
            target = custom_dir / f"{source.stem}_{identifier}_{kind}{source.suffix}"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return relpath(target, self.config_dir)

    def test_sound(self, row_index: int, kind: str) -> None:
        row = self.rows[row_index]
        sound_value = row.ended_sound.get() if kind == "ended" else row.remaining_sound.get()
        sound_path = Path(sound_value)
        if not sound_path.is_absolute():
            sound_path = self.config_dir / sound_path
        play_sound(sound_path, async_play=True, volume=self.volume.get())

    def test_magic_shield_sound(self) -> None:
        if self.magic_shield_delay is None:
            return
        sound_value = self.magic_shield_delay.ended_sound.get()
        sound_path = Path(sound_value)
        if not sound_path.is_absolute():
            sound_path = self.config_dir / sound_path
        play_sound(sound_path, async_play=True, volume=self.volume.get())

    def test_magic_shield_missing_sound(self) -> None:
        if self.magic_shield_delay is None:
            return
        sound_value = self.magic_shield_delay.missing_sound.get()
        sound_path = Path(sound_value)
        if not sound_path.is_absolute():
            sound_path = self.config_dir / sound_path
        play_sound(sound_path, async_play=True, volume=self.volume.get())

    def test_food_sound(self, kind: str) -> None:
        if self.food_timer is None:
            return
        sound_value = (
            self.food_timer.ended_sound.get()
            if kind == "ended"
            else self.food_timer.remaining_sound.get()
        )
        sound_path = Path(sound_value)
        if not sound_path.is_absolute():
            sound_path = self.config_dir / sound_path
        play_sound(sound_path, async_play=True, volume=self.volume.get())

    def test_safehouse_sound(self) -> None:
        if self.safehouse is None:
            return
        sound_value = self.safehouse.warning_sound.get()
        sound_path = Path(sound_value)
        if not sound_path.is_absolute():
            sound_path = self.config_dir / sound_path
        play_sound(sound_path, async_play=True, volume=self.volume.get())

    def test_boss_hp_sound(self, row_index: int) -> None:
        row = self.boss_hp_rows[row_index]
        sound_value = row.sound.get()
        sound_path = Path(sound_value)
        if not sound_path.is_absolute():
            sound_path = self.config_dir / sound_path
        play_sound(sound_path, async_play=True, volume=self.volume.get())

    def test_boss_red_orb_sound(self) -> None:
        if self.boss_red_orb is None:
            return

        def resolve(value: str) -> Path:
            sound_path = Path(value)
            if not sound_path.is_absolute():
                sound_path = self.config_dir / sound_path
            return sound_path

        countdown_sounds = {
            "5": BOSS_RED_ORB_COUNTDOWN_5_SOUND,
            "4": BOSS_RED_ORB_COUNTDOWN_4_SOUND,
            "3": BOSS_RED_ORB_COUNTDOWN_3_SOUND,
            "2": BOSS_RED_ORB_COUNTDOWN_2_SOUND,
            "1": BOSS_RED_ORB_COUNTDOWN_1_SOUND,
            "0": BOSS_RED_ORB_COUNTDOWN_0_SOUND,
            **(self.boss_red_orb.item.get("countdown_sounds") or {}),
        }
        sound = make_timed_sound_sequence(
            (0.0, resolve(self.boss_red_orb.sound.get() or BOSS_RED_ORB_SOUND)),
            (1.0, resolve(countdown_sounds["5"])),
            (2.0, resolve(countdown_sounds["4"])),
            (3.0, resolve(countdown_sounds["3"])),
            (4.0, resolve(countdown_sounds["2"])),
            (5.0, resolve(countdown_sounds["1"])),
            (6.0, resolve(countdown_sounds["0"])),
        )
        play_sound(sound, async_play=True, volume=self.volume.get())

    def test_boss_laser_sound(self) -> None:
        if self.boss_laser is None:
            return

        def resolve(value: str) -> Path:
            sound_path = Path(value)
            if not sound_path.is_absolute():
                sound_path = self.config_dir / sound_path
            return sound_path

        countdown_sounds = {
            "4": BOSS_LASER_COUNTDOWN_4_SOUND,
            "3": BOSS_LASER_COUNTDOWN_3_SOUND,
            "2": BOSS_LASER_COUNTDOWN_2_SOUND,
            "1": BOSS_LASER_COUNTDOWN_1_SOUND,
            "0": BOSS_LASER_COUNTDOWN_0_SOUND,
            **(self.boss_laser.item.get("countdown_sounds") or {}),
        }
        sound = make_timed_sound_sequence(
            (0.0, resolve(self.boss_laser.sound.get() or BOSS_LASER_ALERT_SOUND)),
            (1.0, resolve(countdown_sounds["4"])),
            (2.0, resolve(countdown_sounds["3"])),
            (3.0, resolve(countdown_sounds["2"])),
            (4.0, resolve(countdown_sounds["1"])),
            (5.0, resolve(countdown_sounds["0"])),
        )
        play_sound(sound, async_play=True, volume=self.volume.get())

    def test_key_enemy_debuff_sound(self, kind: str) -> None:
        if self.key_enemy_debuff is None:
            return
        sound_value = (
            self.key_enemy_debuff.complete_sound.get()
            if kind == "complete"
            else self.key_enemy_debuff.expiry_sound.get()
        )
        sound_path = Path(sound_value)
        if not sound_path.is_absolute():
            sound_path = self.config_dir / sound_path
        play_sound(sound_path, async_play=True, volume=self.volume.get())

    def test_azure_wound_sound(self, kind: str) -> None:
        if self.azure_wound is None:
            return
        sound_value = (
            self.azure_wound.clear_sound.get()
            if kind == "clear"
            else self.azure_wound.danger_sound.get()
        )
        sound_path = Path(sound_value)
        if not sound_path.is_absolute():
            sound_path = self.config_dir / sound_path
        play_sound(sound_path, async_play=True, volume=self.volume.get())

    def test_special_sound(self, row_index: int, kind: str) -> None:
        row = self.special_end_only_rows[row_index]
        sound_value = (
            row.cooldown_sound.get() if kind == "cooldown" else row.ended_sound.get()
        )
        sound_path = Path(sound_value)
        if not sound_path.is_absolute():
            sound_path = self.config_dir / sound_path
        play_sound(sound_path, async_play=True, volume=self.volume.get())

    def restore_defaults(self) -> None:
        if not messagebox.askyesno("恢复默认规则", "要把当前项目的提醒规则恢复到测试默认值吗？"):
            return
        if self.visual_hud is not None:
            self.visual_hud.enabled.set(True)
            self.visual_hud.tuan_silence_enabled.set(False)
            for ccid, defaults in VISUAL_HUD_CONDITION_DEFAULTS.items():
                self.visual_hud.condition_enabled[ccid].set(defaults["enabled"])
                self.visual_hud.condition_show_before_seconds[ccid].set(
                    defaults["show_before_seconds"]
                )
                self.visual_hud.condition_ring_sound_enabled[ccid].set(
                    defaults["ring_sound_enabled"]
                )
            for ccid, icon in VISUAL_HUD_DEFAULT_ICONS.items():
                self.visual_hud.condition_icons[ccid].set(icon)
            self._sync_visual_hud_state()
        if self.other_skill_hud is not None:
            self.other_skill_hud.enabled.set(False)
            for key, defaults in OTHER_SKILL_HUD_CONDITION_DEFAULTS.items():
                self.other_skill_hud.condition_enabled[key].set(
                    defaults["enabled"]
                )
                self.other_skill_hud.condition_icons[key].set(defaults["icon"])
            self._sync_other_skill_hud_state()
        if self.short_cooldown_hud is not None:
            for key, defaults in SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS.items():
                self.short_cooldown_hud.condition_enabled[key].set(
                    defaults["enabled"]
                )
                self.short_cooldown_hud.cooldown_seconds[key].set(
                    f"{float(defaults['cooldown_seconds']):g}"
                )
                self.short_cooldown_hud.condition_icons[key].set(defaults["icon"])
            self._sync_short_cooldown_hud_state()
        if self.astrology_card_tracker is not None:
            defaults = default_astrology_card_tracker_config()
            for skill_id, variable in (
                self.astrology_card_tracker.enabled_skills.items()
            ):
                variable.set(
                    bool(defaults["tracked_skills"].get(str(skill_id), False))
                )
            self.astrology_card_tracker.counter_threshold.set(
                str(ASTROLOGY_DEFAULT_COUNTER_THRESHOLD)
            )
            for variable, card in zip(
                self.astrology_card_tracker.deck,
                defaults["deck"],
            ):
                variable.set(card or ASTROLOGY_UNSET_LABEL)
            for skill_id, variable in self.astrology_card_tracker.skill_suits.items():
                suit = defaults["skill_suits"].get(str(skill_id), "")
                variable.set(suit or ASTROLOGY_UNSET_LABEL)
            for skill_id, variable in (
                self.astrology_card_tracker.base_cooldown_seconds.items()
            ):
                seconds = defaults["base_cooldown_seconds"][str(skill_id)]
                variable.set(f"{float(seconds):g}")
        for row in self.rows:
            rule = DEFAULT_RULES.get(row.item["name"])
            if rule is None:
                continue
            row.enabled.set(bool(rule.get("enabled", True)))
            row.remaining_enabled.set(rule["remaining_enabled"])
            row.seconds.set(rule["seconds"])
        if self.food_timer is not None:
            self.food_timer.timer_enabled.set(False)
            self.food_timer.duration_seconds.set(0)
            self.food_timer.remaining_enabled.set(False)
            self.food_timer.remaining_seconds.set(FOOD_DEFAULT_WARNING_SECONDS)
            self.food_timer.remaining_sound.set(DEFAULT_WARN_SOUND)
            self.food_timer.ended_sound.set(DEFAULT_ENDED_SOUND)
            self._sync_food_timer_state()
        if self.magic_shield_delay is not None:
            self.magic_shield_delay.enabled.set(True)
            self.magic_shield_delay.ended_enabled.set(True)
            self.magic_shield_delay.ended_sound.set(MAGIC_SHIELD_DEFAULT_ENDED_SOUND)
            self.magic_shield_delay.ended_grace_seconds.set(
                MAGIC_SHIELD_DEFAULT_ENDED_GRACE_SECONDS
            )
            self.magic_shield_delay.missing_enabled.set(False)
            self.magic_shield_delay.missing_sound.set(MAGIC_SHIELD_DEFAULT_MISSING_SOUND)
            self.magic_shield_delay.missing_delay_seconds.set(
                MAGIC_SHIELD_DEFAULT_MISSING_DELAY_SECONDS
            )
            self._sync_magic_shield_state()
        if self.azure_wound is not None:
            self.azure_wound.enabled.set(True)
            self.azure_wound.danger_stacks.set(AZURE_WOUND_DEFAULT_DANGER_STACKS)
            self.azure_wound.danger_sound.set(AZURE_WOUND_DEFAULT_DANGER_SOUND)
            self.azure_wound.clear_enabled.set(True)
            self.azure_wound.clear_sound.set(AZURE_WOUND_DEFAULT_CLEAR_SOUND)
            self._sync_azure_wound_state()
        if self.safehouse is not None:
            self.safehouse.enabled.set(True)
            self.safehouse.lead_seconds.set(SAFEHOUSE_DEFAULT_LEAD_SECONDS)
            self.safehouse.warning_sound.set(SAFEHOUSE_DEFAULT_SOUND)
            self._sync_safehouse_state()
        if self.bronntanas_hp_hud_enabled is not None:
            self.bronntanas_hp_hud_enabled.set(True)
        if self.miracle_orb_hp_hud_enabled is not None:
            self.miracle_orb_hp_hud_enabled.set(True)
        if self.rotating_laser_countdown_hud_enabled is not None:
            self.rotating_laser_countdown_hud_enabled.set(True)
        boss_defaults = {item["short_name"]: item for item in BOSS_HP_DEFAULTS}
        for row in self.boss_hp_rows:
            defaults = boss_defaults.get(row.item.get("short_name"))
            row.enabled.set(True)
            row.thresholds.set(
                format_thresholds([] if defaults is None else defaults["thresholds"])
            )
            row.sound.set(BOSS_HP_DEFAULT_SOUND)
            self._sync_boss_hp_state(row)
        if self.key_enemy_debuff is not None:
            self.key_enemy_debuff.complete_enabled.set(False)
            self.key_enemy_debuff.expiry_enabled.set(True)
            self.key_enemy_debuff.visual_hud_enabled.set(False)
            self.key_enemy_debuff.visual_expiry_enabled.set(True)
            self.key_enemy_debuff.expiry_seconds.set(
                KEY_ENEMY_DEBUFF_DEFAULT_EXPIRY_SECONDS
            )
            self.key_enemy_debuff.physical_break_min.set("")
            self.key_enemy_debuff.magic_break_min.set("")
            self.key_enemy_debuff.damage_bonus_min.set("")
            self.key_enemy_debuff.rabbit_stacks_min.set("")
            self.key_enemy_debuff.complete_sound.set(KEY_ENEMY_DEBUFF_COMPLETE_SOUND)
            self.key_enemy_debuff.expiry_sound.set(KEY_ENEMY_DEBUFF_EXPIRY_SOUND)
            self._sync_key_enemy_debuff_state()
        if self.gunner_eye_row is not None:
            self.gunner_eye_row.enabled.set(False)
            self.gunner_eye_row.remaining_enabled.set(True)
            self.gunner_eye_row.seconds.set(KEY_ENEMY_GUNNER_EYE_DEFAULT_SECONDS)
            self.gunner_eye_row.remaining_sound.set(KEY_ENEMY_GUNNER_EYE_REMAINING_SOUND)
            self.gunner_eye_row.ended_sound.set(KEY_ENEMY_GUNNER_EYE_ENDED_SOUND)
            self._sync_seconds_state(self.gunner_eye_row)
        if self.music_strong_enabled is not None:
            self.music_strong_enabled.set(MUSIC_STRONG_REMINDER_ENABLED)
        if self.music_tuan_silence_enabled is not None:
            self.music_tuan_silence_enabled.set(MUSIC_TUAN_SILENCE_DEFAULT)
        if self.boss_red_orb is not None:
            self.boss_red_orb.enabled.set(True)
            self.boss_red_orb.sound.set(BOSS_RED_ORB_SOUND)
            self.boss_red_orb.item["safe_sound"] = BOSS_RED_ORB_SAFE_SOUND
            self.boss_red_orb.item["countdown_sounds"] = boss_red_orb_defaults()[
                "countdown_sounds"
            ]
            self._sync_boss_red_orb_state()
        if self.boss_laser is not None:
            self.boss_laser.enabled.set(False)
            self.boss_laser.sound.set(BOSS_LASER_ALERT_SOUND)
            self.boss_laser.item["countdown_sounds"] = boss_laser_alert_defaults()[
                "countdown_sounds"
            ]
            self._sync_boss_laser_state()
        for row in self.special_end_only_rows:
            rules = SPECIAL_END_ONLY_DEFAULTS[row.item["name"]]
            row.enabled.set(True)
            row.ended_enabled.set(bool(rules.get("ended_enabled", True)))
            row.ended_sound.set(rules["ended_sound"])
            row.cooldown_enabled.set(rules["cooldown_enabled"])
            row.cooldown_seconds.set(rules["cooldown_seconds"])
            row.cooldown_sound.set(rules["cooldown_sound"])
            self._sync_special_end_only_state(row)

    def apply_to_data(self) -> None:
        self.data["audio_volume"] = normalize_volume(self.volume.get())
        self.apply_visual_hud_to_data()
        self.apply_other_skill_hud_to_data()
        self.apply_short_cooldown_hud_to_data()
        self.apply_astrology_card_tracker_to_data()
        music_strong = find_or_create_music_strong_reminder(self.data)
        if self.music_strong_enabled is not None:
            music_strong["enabled"] = bool(self.music_strong_enabled.get())
        self.data["music_strong_reminder"] = music_strong
        if self.music_tuan_silence_enabled is not None:
            self.data["music_tuan_silence_enabled"] = bool(
                self.music_tuan_silence_enabled.get()
            )
        for row in self.rows:
            item = row.item
            name = item["name"]
            item["audio_volume"] = self.data["audio_volume"]
            remaining_sound = row.remaining_sound.get().strip()
            ended_sound = row.ended_sound.get().strip()
            if item_is_progress(item):
                item["enabled"] = bool(row.remaining_enabled.get())
                if row.remaining_enabled.get():
                    remaining_progress = max(0, min(100, int(row.seconds.get())))
                    item["alerts"] = [
                        {
                            "remaining_progress": remaining_progress,
                            "sound": remaining_sound or DEFAULT_WARN_SOUND,
                            "message": alert_message(name),
                        }
                    ]
                else:
                    item["alerts"] = []
                item["warn_sound"] = remaining_sound or DEFAULT_WARN_SOUND
                item["ended_alert"] = False
                continue

            remaining_requested = (
                False
                if item_remaining_locked(item)
                else bool(row.remaining_enabled.get())
            )
            ended_requested = bool(row.enabled.get())
            item["enabled"] = bool(ended_requested or remaining_requested)
            item["ended_alert"] = ended_requested
            item["ended_sound"] = ended_sound or DEFAULT_ENDED_SOUND
            item["ended_message"] = "{name} 结束"
            if name in ASTROLOGY_BUFF_NAMES:
                item["ended_sound"] = ended_sound or ASTROLOGY_SOUND
                item["ended_message"] = ASTROLOGY_MESSAGE
                item["ended_on_remove_only"] = True
                item["ended_grace_seconds"] = 0
                item["sbt_ended_lead_seconds"] = 0
                item["use_dynamic_sbt_adjust"] = False
            if name == "状态支援":
                item["prefer_sbt_when_duration_present"] = False
            if name in HAMSTER_BUFF_NAMES:
                item["duration_seconds"] = HAMSTER_BUFF_DURATION_SECONDS
                item["ended_on_remove_only"] = True
                item["ended_grace_seconds"] = 0
                item["sbt_ended_lead_seconds"] = 0
                item["use_dynamic_sbt_adjust"] = False
            item["warn_sound"] = remaining_sound or DEFAULT_WARN_SOUND
            if name == MAGIC_SHIELD_NAME and self.magic_shield_delay is not None:
                try:
                    delay_value = self.magic_shield_delay.ended_grace_seconds.get()
                except tk.TclError:
                    delay_value = MAGIC_SHIELD_DEFAULT_ENDED_GRACE_SECONDS
                item["ended_grace_seconds"] = clamp_float(
                    delay_value,
                    0.0,
                    MAGIC_SHIELD_MAX_ENDED_GRACE_SECONDS,
                )

            if item_remaining_locked(item):
                item["alerts"] = []
                item["warn_seconds"] = 0
                item["critical_seconds"] = 0
            elif remaining_requested:
                seconds = max(0, int(row.seconds.get()))
                item["alerts"] = [
                    {
                        "remaining_seconds": seconds,
                        "sound": remaining_sound or DEFAULT_WARN_SOUND,
                        "message": alert_message(name),
                    }
                ]
                item["warn_seconds"] = seconds
                item["critical_seconds"] = seconds
            else:
                item["alerts"] = []
        self.apply_magic_shield_to_data()
        self.apply_azure_wound_to_data()
        self.apply_safehouse_to_data()
        self.apply_boss_hp_alerts_to_data()
        self.apply_bronntanas_hp_hud_to_data()
        self.apply_miracle_orb_hp_hud_to_data()
        self.apply_rotating_laser_countdown_hud_to_data()
        self.apply_key_enemy_debuff_to_data()
        self.data.pop("boss_skill_burst_alerts", None)
        self.apply_boss_red_orb_to_data()
        self.apply_boss_laser_to_data()
        self.apply_special_end_only_to_data()
        self.apply_food_timer_to_data()

    def apply_visual_hud_to_data(self) -> None:
        if self.visual_hud is None:
            return
        row = self.visual_hud
        item = find_or_create_visual_hud(self.data)
        item["enabled"] = bool(row.enabled.get())
        item["ring_sound_enabled"] = False
        item["muted"] = False
        item["condition_controls_version"] = 1
        item["tuan_silence_enabled"] = bool(row.tuan_silence_enabled.get())

        conditions = item["conditions"]
        for ccid, icon_variable in row.condition_icons.items():
            condition = conditions[str(ccid)]
            condition["enabled"] = bool(row.condition_enabled[ccid].get())
            condition["ring_sound_enabled"] = bool(
                row.condition_ring_sound_enabled[ccid].get()
            )
            try:
                show_before_seconds = row.condition_show_before_seconds[ccid].get()
            except tk.TclError:
                show_before_seconds = VISUAL_HUD_DEFAULT_SHOW_BEFORE_SECONDS
            condition["show_before_seconds"] = clamp_float(
                show_before_seconds,
                VISUAL_HUD_MIN_SHOW_BEFORE_SECONDS,
                VISUAL_HUD_MAX_SHOW_BEFORE_SECONDS,
            )
            condition["icon"] = icon_variable.get().strip()
        item["default_icons_version"] = VISUAL_HUD_DEFAULT_ICONS_VERSION
        self.data[VISUAL_HUD_CONFIG_KEY] = item

    def apply_bronntanas_hp_hud_to_data(self) -> None:
        if self.bronntanas_hp_hud_enabled is None:
            return
        item = find_or_create_bronntanas_hp_hud(self.data)
        item["enabled"] = bool(self.bronntanas_hp_hud_enabled.get())
        self.data[BRONNTANAS_HP_HUD_CONFIG_KEY] = item

    def apply_miracle_orb_hp_hud_to_data(self) -> None:
        if self.miracle_orb_hp_hud_enabled is None:
            return
        item = find_or_create_miracle_orb_hp_hud(self.data)
        item["enabled"] = bool(self.miracle_orb_hp_hud_enabled.get())
        self.data[MIRACLE_ORB_HP_HUD_CONFIG_KEY] = item

    def apply_rotating_laser_countdown_hud_to_data(self) -> None:
        if self.rotating_laser_countdown_hud_enabled is None:
            return
        item = find_or_create_rotating_laser_countdown_hud(self.data)
        item["enabled"] = bool(self.rotating_laser_countdown_hud_enabled.get())
        self.data[ROTATING_LASER_COUNTDOWN_HUD_CONFIG_KEY] = item

    def apply_other_skill_hud_to_data(self) -> None:
        if self.other_skill_hud is None:
            return
        row = self.other_skill_hud
        item = find_or_create_other_skill_hud(self.data)
        item["enabled"] = bool(row.enabled.get())
        item["left_offset_px"] = 8
        item["center_y_ratio"] = 0.28
        item["gap_px"] = 6
        conditions = item["conditions"]
        for key, icon_variable in row.condition_icons.items():
            condition = conditions[key]
            condition["enabled"] = bool(row.condition_enabled[key].get())
            condition["name"] = OTHER_SKILL_HUD_CONDITION_DEFAULTS[key]["name"]
            condition["icon"] = icon_variable.get().strip()
        item["default_icons_version"] = OTHER_SKILL_HUD_DEFAULT_ICONS_VERSION
        self.data[OTHER_SKILL_HUD_CONFIG_KEY] = item

    def apply_short_cooldown_hud_to_data(self) -> None:
        if self.short_cooldown_hud is None:
            return
        row = self.short_cooldown_hud
        item = find_or_create_short_cooldown_hud(self.data)
        item["enabled"] = any(
            variable.get() for variable in row.condition_enabled.values()
        )
        item["center_y_ratio"] = 0.715
        item["gap_px"] = 6
        for key, defaults in SHORT_COOLDOWN_HUD_CONDITION_DEFAULTS.items():
            condition = item["conditions"][key]
            condition["enabled"] = bool(row.condition_enabled[key].get())
            condition["name"] = defaults["name"]
            condition["icon"] = row.condition_icons[key].get().strip()
            cooldown_seconds = clamp_float(
                row.cooldown_seconds[key].get(),
                0.1,
                9999.0,
            )
            tracker = find_or_create_short_cooldown_tracker(self.data, key)
            tracker["cooldown_delay_seconds"] = (
                int(cooldown_seconds)
                if cooldown_seconds.is_integer()
                else cooldown_seconds
            )
        item["default_icons_version"] = SHORT_COOLDOWN_HUD_DEFAULT_ICONS_VERSION
        self.data[SHORT_COOLDOWN_HUD_CONFIG_KEY] = item

    def apply_astrology_card_tracker_to_data(self) -> None:
        if self.astrology_card_tracker is None:
            return
        row = self.astrology_card_tracker
        item = ensure_astrology_card_tracker_config(self.data)
        try:
            threshold = int(row.counter_threshold.get())
        except (TypeError, ValueError):
            threshold = ASTROLOGY_DEFAULT_COUNTER_THRESHOLD
        item["tracked_skills"] = {
            str(skill_id): bool(variable.get())
            for skill_id, variable in row.enabled_skills.items()
        }
        item["counter_threshold"] = (
            threshold
            if threshold in ASTROLOGY_COUNTER_CHOICES
            else ASTROLOGY_DEFAULT_COUNTER_THRESHOLD
        )
        deck: list[str] = []
        deck_ended = False
        for variable in row.deck:
            value = variable.get()
            if deck_ended or value == ASTROLOGY_UNSET_LABEL:
                deck_ended = True
                deck.append("")
            else:
                deck.append(value)
        item["deck"] = deck
        item["skill_suits"] = {
            str(skill_id): (
                "" if variable.get() == ASTROLOGY_UNSET_LABEL else variable.get()
            )
            for skill_id, variable in row.skill_suits.items()
        }
        base_cooldown_seconds: dict[str, float | int] = {}
        for skill_id, variable in row.base_cooldown_seconds.items():
            default = ASTROLOGY_CORE_COOLDOWN_DEFAULTS[skill_id]
            try:
                seconds = float(variable.get())
            except (TypeError, ValueError, tk.TclError):
                seconds = default
            seconds = max(
                ASTROLOGY_MIN_COOLDOWN_SECONDS,
                min(ASTROLOGY_MAX_COOLDOWN_SECONDS, seconds),
            )
            base_cooldown_seconds[str(skill_id)] = (
                int(seconds) if seconds.is_integer() else seconds
            )
        item["base_cooldown_seconds"] = base_cooldown_seconds
        self.data[ASTROLOGY_CARD_TRACKER_CONFIG_KEY] = item

    def apply_magic_shield_to_data(self) -> None:
        if self.magic_shield_delay is None:
            return
        row = self.magic_shield_delay
        item = row.item
        item["name"] = MAGIC_SHIELD_NAME
        item["ccid"] = 59
        item["enabled"] = bool(row.enabled.get())
        item["audio_volume"] = self.data["audio_volume"]
        item["alerts"] = []
        item["warn_seconds"] = 0
        item["critical_seconds"] = 0
        item["ended_alert"] = bool(row.ended_enabled.get())
        item["ended_sound"] = (
            row.ended_sound.get().strip() or MAGIC_SHIELD_DEFAULT_ENDED_SOUND
        )
        item["ended_message"] = MAGIC_SHIELD_DEFAULT_ENDED_MESSAGE
        item["warn_sound"] = item.get("warn_sound", DEFAULT_WARN_SOUND)
        try:
            delay_value = row.ended_grace_seconds.get()
        except tk.TclError:
            delay_value = MAGIC_SHIELD_DEFAULT_ENDED_GRACE_SECONDS
        item["ended_grace_seconds"] = clamp_float(
            delay_value,
            0.0,
            MAGIC_SHIELD_MAX_ENDED_GRACE_SECONDS,
        )
        try:
            missing_delay_value = row.missing_delay_seconds.get()
        except tk.TclError:
            missing_delay_value = MAGIC_SHIELD_DEFAULT_MISSING_DELAY_SECONDS
        item["missing_shield_alert"] = {
            "enabled": bool(row.missing_enabled.get()),
            "delay_seconds": clamp_float(
                missing_delay_value,
                0.0,
                MAGIC_SHIELD_MAX_MISSING_DELAY_SECONDS,
            ),
            "repeat_seconds": MAGIC_SHIELD_DEFAULT_MISSING_REPEAT_SECONDS,
            "sound": (
                row.missing_sound.get().strip()
                or MAGIC_SHIELD_DEFAULT_MISSING_SOUND
            ),
            "message": MAGIC_SHIELD_DEFAULT_MISSING_MESSAGE,
        }

    def apply_azure_wound_to_data(self) -> None:
        if self.azure_wound is None:
            return
        row = self.azure_wound
        item = row.item
        item["name"] = AZURE_WOUND_NAME
        item["ccid"] = AZURE_WOUND_CCID
        item["enabled"] = bool(row.enabled.get())
        item["audio_volume"] = self.data["audio_volume"]
        item["stack_field"] = AZURE_WOUND_STACK_FIELD
        item["max_stacks"] = AZURE_WOUND_MAX_STACKS
        item["alerts"] = []
        item["warn_seconds"] = 0
        item["critical_seconds"] = 0
        item["warn_sound"] = row.danger_sound.get().strip() or AZURE_WOUND_DEFAULT_DANGER_SOUND
        try:
            danger_stacks = int(row.danger_stacks.get())
        except (TypeError, ValueError, tk.TclError):
            danger_stacks = AZURE_WOUND_DEFAULT_DANGER_STACKS
        item["stack_alert"] = {
            "enabled": True,
            "stacks": max(1, min(AZURE_WOUND_MAX_STACKS, danger_stacks)),
            "sound": item["warn_sound"],
            "message": "{name} 达到危险层数",
        }
        item["clear_after_stack_alert"] = bool(row.clear_enabled.get())
        item["clear_sound"] = (
            row.clear_sound.get().strip() or AZURE_WOUND_DEFAULT_CLEAR_SOUND
        )
        item["clear_message"] = "{name} 已清除"
        item["clear_grace_seconds"] = 1.5
        item["clear_after_stack_min_active_seconds"] = (
            AZURE_WOUND_CLEAR_MIN_ACTIVE_SECONDS
        )
        item["ended_alert"] = False

    def apply_safehouse_to_data(self) -> None:
        if self.safehouse is None:
            return
        row = self.safehouse
        item = row.item
        item["name"] = SAFEHOUSE_NAME
        item["enabled"] = bool(row.enabled.get())
        item["audio_volume"] = self.data["audio_volume"]
        defaults = safehouse_defaults()
        item["trigger"] = defaults["trigger"]
        item.pop("start_trigger", None)
        item["start_stat_matches"] = defaults["start_stat_matches"]
        item["stop_stat_matches"] = defaults["stop_stat_matches"]
        item["start_offset_seconds"] = SAFEHOUSE_FIRST_ALERTED_OCCURRENCE_SECONDS
        item["timer_sync_stat_matches"] = defaults["timer_sync_stat_matches"]
        item["timer_sync_event_id"] = SAFEHOUSE_SYNC_EVENT_ID
        item["timer_sync_initial_min_delay_seconds"] = (
            SAFEHOUSE_SYNC_INITIAL_MIN_SECONDS
        )
        item["timer_sync_initial_max_delay_seconds"] = (
            SAFEHOUSE_SYNC_INITIAL_MAX_SECONDS
        )
        item["timer_sync_expected_tolerance_seconds"] = (
            SAFEHOUSE_SYNC_EXPECTED_TOLERANCE_SECONDS
        )
        item["timer_sync_min_interval_seconds"] = SAFEHOUSE_SYNC_MIN_INTERVAL_SECONDS
        item["timer_sync_max_interval_seconds"] = SAFEHOUSE_SYNC_MAX_INTERVAL_SECONDS
        item["trigger_dedupe_seconds"] = SAFEHOUSE_TRIGGER_DEDUPE_SECONDS
        item["ignore_trigger_while_active"] = False
        item["trigger_rearm_tolerance_seconds"] = 0
        item["repeat_timer"] = True
        item["self_filter"] = False
        item["drop_rules"] = []
        item["min_drop_count"] = 1
        item["allow_unseen_drop"] = False
        item["timer_enabled"] = True
        item["duration_seconds"] = SAFEHOUSE_INTERVAL_SECONDS
        item["warn_sound"] = row.warning_sound.get().strip() or SAFEHOUSE_DEFAULT_SOUND
        item["ended_alert"] = False
        item["ended_sound"] = item.get("ended_sound", DEFAULT_ENDED_SOUND)
        item["ended_message"] = "{name} 结束"
        try:
            lead_seconds = int(row.lead_seconds.get())
        except (TypeError, ValueError, tk.TclError):
            lead_seconds = SAFEHOUSE_DEFAULT_LEAD_SECONDS
        item["alerts"] = [
            {
                "remaining_seconds": max(
                    SAFEHOUSE_MIN_LEAD_SECONDS,
                    min(SAFEHOUSE_MAX_LEAD_SECONDS, lead_seconds),
                ),
                "sound": item["warn_sound"],
                "message": "安全屋",
            }
        ]

    def apply_boss_hp_alerts_to_data(self) -> None:
        items = []
        for row in self.boss_hp_rows:
            item = row.item
            thresholds = parse_thresholds_text(row.thresholds.get())
            sound = row.sound.get().strip() or BOSS_HP_DEFAULT_SOUND
            updated = {
                "name": item.get("name", ""),
                "short_name": item.get("short_name", ""),
                "entity_id": str(item.get("entity_id", "")),
                "max_hp_values": list(item.get("max_hp_values", [])),
                "enabled": bool(row.enabled.get()),
                "current_hp_stat_id": BOSS_HP_CURRENT_STAT_ID,
                "max_hp_stat_id": BOSS_HP_MAX_STAT_ID,
                "warn_sound": sound,
                "alerts": [
                    {
                        "threshold_percent": threshold,
                        "sound": sound,
                        "message": BOSS_HP_DEFAULT_MESSAGE,
                    }
                    for threshold in thresholds
                ],
                "audio_volume": self.data["audio_volume"],
            }
            for key in (
                "safehouse_countdown_enabled",
                "safehouse_countdown_effect_name",
                "safehouse_countdown_sound_dir",
                "safehouse_countdown_message_template",
                "safehouse_countdown_min_seconds",
                "safehouse_countdown_max_seconds",
            ):
                if key in item:
                    updated[key] = item[key]
            item.clear()
            item.update(updated)
            items.append(item)
        existing_by_short_name = {
            str(item.get("short_name", "")): item
            for item in self.data.get("boss_hp_alerts", [])
            if item.get("short_name")
        }
        for defaults in BOSS_HP_DEFAULTS:
            if not defaults.get("hidden"):
                continue
            item = existing_by_short_name.get(defaults["short_name"])
            if item is None:
                item = boss_hp_alert_item(defaults)
            item["name"] = defaults["name"]
            item["short_name"] = defaults["short_name"]
            item["entity_id"] = defaults["entity_id"]
            item["max_hp_values"] = list(defaults.get("max_hp_values", []))
            item["enabled"] = True
            item["current_hp_stat_id"] = BOSS_HP_CURRENT_STAT_ID
            item["max_hp_stat_id"] = BOSS_HP_MAX_STAT_ID
            item["warn_sound"] = item.get("warn_sound", BOSS_HP_DEFAULT_SOUND)
            item["alerts"] = []
            item["audio_volume"] = self.data["audio_volume"]
            item["hidden"] = True
            item["track_only"] = bool(defaults.get("track_only", False))
            items.append(item)
        self.data["boss_hp_alerts"] = items

    def apply_key_enemy_debuff_to_data(self) -> None:
        if self.key_enemy_debuff is None:
            return
        row = self.key_enemy_debuff
        item = row.item
        complete_enabled = bool(row.complete_enabled.get())
        visual_hud_enabled = bool(row.visual_hud_enabled.get())
        threshold_values = parse_key_enemy_debuff_threshold_values(
            self._key_enemy_debuff_threshold_values(),
            require_complete=complete_enabled or visual_hud_enabled,
        )
        item["name"] = KEY_ENEMY_DEBUFF_SECTION_NAME
        item["complete_enabled"] = complete_enabled
        item["expiry_enabled"] = bool(row.expiry_enabled.get())
        item["visual_hud_enabled"] = visual_hud_enabled
        item["visual_expiry_enabled"] = bool(row.visual_expiry_enabled.get())
        item["audio_volume"] = self.data["audio_volume"]
        item["max_hp_values"] = list(KEY_ENEMY_DEBUFF_BOSS_MAX_HP_VALUES)
        item["current_hp_stat_id"] = BOSS_HP_CURRENT_STAT_ID
        item["max_hp_stat_id"] = BOSS_HP_MAX_STAT_ID
        item["complete_sound"] = (
            row.complete_sound.get().strip() or KEY_ENEMY_DEBUFF_COMPLETE_SOUND
        )
        item["complete_message"] = KEY_ENEMY_DEBUFF_COMPLETE_MESSAGE
        item["expiry_sound"] = (
            row.expiry_sound.get().strip() or KEY_ENEMY_DEBUFF_EXPIRY_SOUND
        )
        item["expiry_message"] = KEY_ENEMY_DEBUFF_EXPIRY_MESSAGE

        try:
            expiry_seconds = int(row.expiry_seconds.get())
        except (TypeError, ValueError, tk.TclError):
            expiry_seconds = KEY_ENEMY_DEBUFF_DEFAULT_EXPIRY_SECONDS
        item["expiry_seconds"] = max(0, min(600, expiry_seconds))

        for key, _label, _minimum, _maximum in KEY_ENEMY_DEBUFF_THRESHOLD_FIELDS:
            item[key] = threshold_values[key]
        gunner_eye = key_enemy_gunner_eye_defaults()
        if self.gunner_eye_row is not None:
            gunner_row = self.gunner_eye_row
            try:
                gunner_eye_seconds = int(gunner_row.seconds.get())
            except (TypeError, ValueError, tk.TclError):
                gunner_eye_seconds = KEY_ENEMY_GUNNER_EYE_DEFAULT_SECONDS
            gunner_ended_enabled = bool(gunner_row.enabled.get())
            gunner_remaining_enabled = bool(gunner_row.remaining_enabled.get())
            gunner_eye["enabled"] = bool(
                gunner_ended_enabled or gunner_remaining_enabled
            )
            gunner_eye["remaining_enabled"] = gunner_remaining_enabled
            gunner_eye["ended_enabled"] = gunner_ended_enabled
            gunner_eye["remaining_seconds"] = max(0, min(600, gunner_eye_seconds))
            gunner_eye["remaining_sound"] = (
                gunner_row.remaining_sound.get().strip()
                or KEY_ENEMY_GUNNER_EYE_REMAINING_SOUND
            )
            gunner_eye["ended_sound"] = (
                gunner_row.ended_sound.get().strip()
                or KEY_ENEMY_GUNNER_EYE_ENDED_SOUND
            )
        else:
            gunner_eye["remaining_seconds"] = KEY_ENEMY_GUNNER_EYE_DEFAULT_SECONDS
        gunner_eye["remaining_message"] = KEY_ENEMY_GUNNER_EYE_REMAINING_MESSAGE
        gunner_eye.setdefault("ended_enabled", False)
        gunner_eye["ended_message"] = KEY_ENEMY_GUNNER_EYE_ENDED_MESSAGE
        item["watched_debuffs"] = [gunner_eye]
        self.data["key_enemy_debuff_alert"] = item

    def apply_boss_red_orb_to_data(self) -> None:
        if self.boss_red_orb is None:
            return
        row = self.boss_red_orb
        item = row.item
        defaults = boss_red_orb_defaults()
        countdown_sounds = dict(item.get("countdown_sounds") or {})
        safe_sound = item.get("safe_sound", defaults["safe_sound"])
        item.update(defaults)
        item["enabled"] = bool(row.enabled.get())
        item["sound"] = row.sound.get().strip() or BOSS_RED_ORB_SOUND
        item["safe_sound"] = safe_sound or defaults["safe_sound"]
        item["countdown_sounds"] = countdown_sounds or defaults["countdown_sounds"]
        item["audio_volume"] = self.data["audio_volume"]

        items = [
            existing
            for existing in self.data.get("boss_red_orb_alerts", [])
            if existing is item or existing.get("name") != BOSS_RED_ORB_NAME
        ]
        if item not in items:
            items.append(item)
        self.data["boss_red_orb_alerts"] = items

    def apply_boss_laser_to_data(self) -> None:
        if self.boss_laser is None:
            return
        row = self.boss_laser
        item = row.item
        defaults = boss_laser_alert_defaults()
        countdown_sounds = dict(item.get("countdown_sounds") or {})
        item.update(defaults)
        item["enabled"] = bool(row.enabled.get())
        item["sound"] = row.sound.get().strip() or BOSS_LASER_ALERT_SOUND
        item["countdown_sounds"] = countdown_sounds or defaults["countdown_sounds"]
        item["audio_volume"] = self.data["audio_volume"]

        items = [
            existing
            for existing in self.data.get("boss_laser_alerts", [])
            if existing is item or existing.get("name") != BOSS_LASER_ALERT_NAME
        ]
        if item not in items:
            items.append(item)
        self.data["boss_laser_alerts"] = items

    def apply_special_end_only_to_data(self) -> None:
        for row in self.special_end_only_rows:
            item = row.item
            name = item["name"]
            rules = SPECIAL_END_ONLY_DEFAULTS[name]
            item["enabled"] = bool(row.enabled.get())
            item["audio_volume"] = self.data["audio_volume"]
            item["alerts"] = []
            item["warn_seconds"] = 0
            item["critical_seconds"] = 0
            item["ended_alert"] = bool(row.ended_enabled.get())
            item["ended_sound"] = row.ended_sound.get().strip() or rules["ended_sound"]
            item["ended_message"] = rules["ended_message"]
            item["cooldown_alert"] = bool(row.cooldown_enabled.get())
            try:
                cooldown_seconds = int(row.cooldown_seconds.get())
            except (TypeError, ValueError, tk.TclError):
                cooldown_seconds = int(rules["cooldown_seconds"])
            if rules.get("cooldown_fixed"):
                item["cooldown_delay_seconds"] = int(rules["cooldown_seconds"])
            elif "cooldown_choices" in rules:
                if cooldown_seconds not in rules["cooldown_choices"]:
                    cooldown_seconds = int(rules["cooldown_seconds"])
                item["cooldown_delay_seconds"] = cooldown_seconds
            else:
                item["cooldown_delay_seconds"] = max(
                    int(rules["cooldown_min"]),
                    min(int(rules["cooldown_max"]), cooldown_seconds),
                )
            if rules.get("cooldown_from_apply"):
                item["cooldown_from_apply"] = True
            else:
                item.pop("cooldown_from_apply", None)
            if rules.get("cooldown_from_skill_use"):
                item["cooldown_from_skill_use"] = True
            else:
                item.pop("cooldown_from_skill_use", None)
            item["cooldown_sound"] = (
                row.cooldown_sound.get().strip() or rules["cooldown_sound"]
            )
            item["cooldown_message"] = rules["cooldown_message"]
            if rules.get("ended_on_remove_only"):
                item["ended_on_remove_only"] = True
            else:
                item.pop("ended_on_remove_only", None)
            if "ended_grace_seconds" in rules:
                item["ended_grace_seconds"] = rules["ended_grace_seconds"]
            if "sbt_ended_lead_seconds" in rules:
                item["sbt_ended_lead_seconds"] = rules["sbt_ended_lead_seconds"]
            if "use_dynamic_sbt_adjust" in rules:
                item["use_dynamic_sbt_adjust"] = rules["use_dynamic_sbt_adjust"]
            if name == SELF_BUFF_CIRCLE_NAME:
                item["skill_id"] = 10103
                item["linked_ccids"] = [10138, 10137]

    def apply_food_timer_to_data(self) -> None:
        if self.food_timer is None:
            return
        row = self.food_timer
        item = row.item
        item["enabled"] = True
        item["audio_volume"] = self.data["audio_volume"]
        if not item.get("drop_rules") or not all(
            "max_drop" in rule for rule in item.get("drop_rules", [])
        ):
            item["drop_rules"] = FOOD_DROP_RULES
        item["min_drop_count"] = 6
        item["allow_unseen_drop"] = True
        item["timer_enabled"] = bool(row.timer_enabled.get())
        item["duration_seconds"] = max(0, int(row.duration_seconds.get()))
        item["warn_sound"] = row.remaining_sound.get().strip() or DEFAULT_WARN_SOUND
        item["ended_alert"] = True
        item["ended_sound"] = row.ended_sound.get().strip() or DEFAULT_ENDED_SOUND
        item["ended_message"] = "{name} 结束"

        if (
            item["timer_enabled"]
            and item["duration_seconds"] > 0
            and row.remaining_enabled.get()
        ):
            item["alerts"] = [
                {
                    "remaining_seconds": max(0, int(row.remaining_seconds.get())),
                    "sound": item["warn_sound"],
                    "message": "{name}",
                }
            ]
        else:
            item["alerts"] = []

    def save(self) -> None:
        try:
            self.apply_to_data()
            save_config(self.config_path, self.data)
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return
        messagebox.showinfo("已保存", "设置已保存。下次启动提醒器时生效。")

    def save_and_close(self) -> None:
        try:
            self.apply_to_data()
            save_config(self.config_path, self.data)
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return
        self.root.destroy()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Edit 洛奇播报小助手 settings.")
    parser.add_argument("--config", default=str(app_root() / "buffwatcher.config.local.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = Path(args.config)
    root = Tk()
    SettingsApp(root, config_path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

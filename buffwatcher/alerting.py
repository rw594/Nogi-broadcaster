from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import argparse
import audioop
import ctypes
import json
import math
import os
import statistics
import sys
import tempfile
import threading
import time
import uuid
import wave
from typing import Any, Iterable

from .config_migration import migrate_config_file
from .events import (
    DEFAULT_TZ_OFFSET_HOURS,
    event_remaining_seconds,
    iter_raw_events,
    latest_raw_file,
    sbt_to_unix_ms,
)


DEFAULT_WARN_SOUND = "assets/audio/warn.wav"
DEFAULT_CRITICAL_SOUND = "assets/audio/critical.wav"
DEFAULT_ENDED_SOUND = "assets/audio/ended.wav"
ALERT_REARM_MARGIN_SECONDS = 10
DEFAULT_ENDED_GRACE_SECONDS = 1.5
ENTITY_REMOVED_EVENT_ID = 2
DEFAULT_DEATH_CLEAR_SUPPRESSION_WINDOW_MS = 500
DEFAULT_DEATH_CLEAR_SUPPRESSION_MIN_BUFFS = 5
DEFAULT_DEATH_SIGNAL_EVENT_IDS = (15,)
DEFAULT_DEATH_SIGNAL_SUPPRESSION_WINDOW_MS = 1500
DEFAULT_SBT_ENDED_LEAD_SECONDS = 1.0
EVENT_DURATION_KEYS = ("MCD", "DUR", "SDUR", "DURA", "DURATION", "MCED", "MCWPWD")
SBT_ADJUST_DURATION_KEYS = EVENT_DURATION_KEYS
MAX_DYNAMIC_SBT_ADJUST_SAMPLES = 20
DYNAMIC_SBT_NEW_END_MARGIN_SECONDS = 5.0
DYNAMIC_SBT_MIN_OBSERVED_ADJUST_SECONDS = -5.0
DYNAMIC_SBT_MAX_OBSERVED_ADJUST_SECONDS = 35.0
DYNAMIC_SBT_MAX_BASELINE_DEVIATION_SECONDS = 8.0
DYNAMIC_SBT_REMOVE_MIN_PREDICTED_DELTA_SECONDS = -3.0
DYNAMIC_SBT_REMOVE_MAX_PREDICTED_DELTA_SECONDS = 30.0
BATTLE_TIMER_OP = "0xaca7"
BATTLE_TIMER_MESSAGE_KEY = "remaintime"
BATTLE_TIMER_NAME = "战斗时限"
MAGIC_SHIELD_NAME = "魔法盾"
MAGIC_SHIELD_CCID = 59
DEFAULT_MAGIC_SHIELD_MISSING_DELAY_SECONDS = 5.0
DEFAULT_MAGIC_SHIELD_MISSING_REPEAT_SECONDS = 5.0
DEFAULT_MAGIC_SHIELD_MISSING_SOUND = "assets/audio/xiaoyi/magic_shield_missing.wav"
DEFAULT_MAGIC_SHIELD_MISSING_MESSAGE = "魔法盾忘开啦"
DEFAULT_MAGIC_SHIELD_ENDED_MESSAGE = "\u9b54\u6cd5\u76fe\u5173\u95ed"
MUSIC_BUFF_CCIDS = frozenset({192, 193, 680})
TUAN_SONG_CCID = 1124
MUSIC_APPLY_REMOVE_NOISE_WINDOW_MS = 1000
MUSIC_REAPPLY_SUPPRESSION_GRACE_SECONDS = 1.0
MUSIC_TUAN_EXTENSION_MIN_REMAINING_SECONDS = 700
MUSIC_TUAN_EXTENSION_RECENT_WINDOW_MS = 15_000
DEFAULT_MUSIC_STRONG_REMINDER_ENABLED = False
DEFAULT_MUSIC_STRONG_REMINDER_REPEAT_SECONDS = 5.0
DEFAULT_MUSIC_STRONG_REMINDER_PREFIX_SOUND = "assets/audio/xiaoyi/music_strong_beep.wav"
PLAYER_HP_STAT_ID = 28
BOSS_HP_CURRENT_STAT_ID = 28
BOSS_HP_MAX_STAT_ID = 30
BOSS_HP_INFERRED_BATTLE_STALE_MS = 15_000
BOSS_HP_PHASE_HANDOFF_GRACE_MS = 10_000
BOSS_HP_UPWARD_JUMP_TOLERANCE_PERCENT = 2.0
BOSS_HP_RESET_PERCENT = 99.0
DEFAULT_BOSS_HP_ALERT_SOUND = "assets/audio/xiaoyi/boss_mechanic_warning.wav"
DEFAULT_BOSS_HP_ALERT_MESSAGE = "注意机制"
DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_SOUND_DIR = (
    "assets/audio/xiaoyi/safehouse_countdown"
)
DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_MESSAGE = "{message}，安全屋{seconds}秒"
DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_MIN_SECONDS = 0
DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_MAX_SECONDS = 70
DEFAULT_BOSS_DOUBLE_LASER_SOUND = DEFAULT_WARN_SOUND
DEFAULT_BOSS_DOUBLE_LASER_MESSAGE = "Boss技能提醒"
DEFAULT_BOSS_DOUBLE_LASER_SKILL_ID = 0
DEFAULT_BOSS_DOUBLE_LASER_BURST_WINDOW_MS = 150
DEFAULT_BOSS_DOUBLE_LASER_REPEAT_WINDOW_MS = 1500
DEFAULT_BOSS_DOUBLE_LASER_DEDUPE_SECONDS = 8.0
LEGACY_BOSS_RED_ORB_SOUND = "assets/audio/xiaoyi/bu3_red_orb_warning.wav"
DEFAULT_BOSS_RED_ORB_SOUND = "assets/audio/xiaoyi/red_orb_countdown/danger_red_orb.wav"
DEFAULT_BOSS_RED_ORB_MESSAGE = "危险红球，5，4，3，2，1，0"
DEFAULT_BOSS_RED_ORB_SAFE_SOUND = (
    "assets/audio/xiaoyi/red_orb_countdown/safe_complete.wav"
)
DEFAULT_BOSS_RED_ORB_SAFE_MESSAGE = "红球已安全处理"
DEFAULT_BOSS_RED_ORB_COUNTDOWN_PREFIX_SOUND = (
    "assets/audio/xiaoyi/red_orb_countdown/danger_red_orb.wav"
)
DEFAULT_BOSS_RED_ORB_COUNTDOWN_5_SOUND = (
    "assets/audio/xiaoyi/red_orb_countdown/count_05.wav"
)
DEFAULT_BOSS_RED_ORB_COUNTDOWN_4_SOUND = (
    "assets/audio/xiaoyi/red_orb_countdown/count_04.wav"
)
DEFAULT_BOSS_RED_ORB_COUNTDOWN_3_SOUND = (
    "assets/audio/xiaoyi/red_orb_countdown/count_03.wav"
)
DEFAULT_BOSS_RED_ORB_COUNTDOWN_2_SOUND = (
    "assets/audio/xiaoyi/red_orb_countdown/count_02.wav"
)
DEFAULT_BOSS_RED_ORB_COUNTDOWN_1_SOUND = (
    "assets/audio/xiaoyi/red_orb_countdown/count_01.wav"
)
DEFAULT_BOSS_RED_ORB_COUNTDOWN_0_SOUND = (
    "assets/audio/xiaoyi/red_orb_countdown/count_00.wav"
)
DEFAULT_BOSS_RED_ORB_COUNTDOWN_SOUNDS = {
    5: DEFAULT_BOSS_RED_ORB_COUNTDOWN_5_SOUND,
    4: DEFAULT_BOSS_RED_ORB_COUNTDOWN_4_SOUND,
    3: DEFAULT_BOSS_RED_ORB_COUNTDOWN_3_SOUND,
    2: DEFAULT_BOSS_RED_ORB_COUNTDOWN_2_SOUND,
    1: DEFAULT_BOSS_RED_ORB_COUNTDOWN_1_SOUND,
    0: DEFAULT_BOSS_RED_ORB_COUNTDOWN_0_SOUND,
}
DEFAULT_BOSS_RED_ORB_BOSS_MAX_HP_VALUES = (1_967_880_100,)
DEFAULT_BOSS_RED_ORB_RACE_IDS = (7604, 7605, 7606, 7607)
DEFAULT_BOSS_RED_ORB_COUNTDOWN_OP = "0x6d62"
DEFAULT_BOSS_RED_ORB_COUNTDOWN_MARKER = "280"
DEFAULT_BOSS_RED_ORB_DAMAGE_SKILL_ID = 52407
DEFAULT_BOSS_RED_ORB_DAMAGE_ACTIVITY_MAX = 10_000
DEFAULT_BOSS_RED_ORB_START_STEP = "4"
DEFAULT_BOSS_RED_ORB_CONFIRM_STEP = "5"
DEFAULT_BOSS_RED_ORB_PAIR_WINDOW_MS = 250
DEFAULT_BOSS_RED_ORB_HIGH_HP_EXPLOSION_DELAY_SECONDS = 15.0
DEFAULT_BOSS_RED_ORB_LOW_HP_EXPLOSION_DELAY_SECONDS = 20.0
DEFAULT_BOSS_RED_ORB_EXPLOSION_DELAY_SECONDS = (
    DEFAULT_BOSS_RED_ORB_HIGH_HP_EXPLOSION_DELAY_SECONDS
)
DEFAULT_BOSS_RED_ORB_LEAD_SECONDS = 3.0
DEFAULT_BOSS_RED_ORB_CONTACT_CHECK_SECONDS = 12.0
DEFAULT_BOSS_RED_ORB_SAFE_MIN_CONTACT_TICKS = 8
DEFAULT_BOSS_RED_ORB_SAFE_LAST_CONTACT_BEFORE_SECONDS = 12.0
DEFAULT_BOSS_RED_ORB_CONTACT_GROUP_MS = 120
DEFAULT_BOSS_RED_ORB_HP_SPLIT_PERCENT = 60.0
DEFAULT_BOSS_RED_ORB_HIGH_HP_REQUIRED_CONTACT_TICKS = 8
DEFAULT_BOSS_RED_ORB_HIGH_HP_EARLY_CHECK_SECONDS = 5.0
DEFAULT_BOSS_RED_ORB_HIGH_HP_EARLY_MAX_CONTACT_TICKS = 2
DEFAULT_BOSS_RED_ORB_HIGH_HP_FINAL_CHECK_SECONDS = 8.0
DEFAULT_BOSS_RED_ORB_LOW_HP_REQUIRED_CONTACT_TICKS = 10
DEFAULT_BOSS_RED_ORB_LOW_HP_EARLY_CHECK_SECONDS = 10.0
DEFAULT_BOSS_RED_ORB_LOW_HP_EARLY_MAX_CONTACT_TICKS = 5
DEFAULT_BOSS_RED_ORB_LOW_HP_FINAL_CHECK_SECONDS = 11.0
DEFAULT_BOSS_RED_ORB_LATE_CONFIRM_OP = "0x6d66"
DEFAULT_BOSS_RED_ORB_LATE_CONFIRM_START_SECONDS = 12.0
DEFAULT_BOSS_RED_ORB_LATE_CONFIRM_END_SECONDS = 14.75
DEFAULT_BOSS_RED_ORB_STALE_SECONDS = 25.0
DEFAULT_BOSS_LASER_WARNING_NAME = "布3/布4激光预警"
DEFAULT_BOSS_LASER_WARNING_SOUND = "assets/audio/xiaoyi/laser_warning_prefix.wav"
DEFAULT_BOSS_LASER_WARNING_MESSAGE = "激光 四 三 二 一 零"
DEFAULT_BOSS_LASER_BOSS_MAX_HP_VALUES = (1_967_880_100, 3_449_779_200)
DEFAULT_BOSS_LASER_STARDUST_RACE_IDS = (
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
)
DEFAULT_BOSS_LASER_CAST_OP = "0xafe7"
DEFAULT_BOSS_LASER_SKILL_ID = 52401
DEFAULT_BOSS_LASER_CAST_SECONDS = 5.0
DEFAULT_BOSS_LASER_CLUSTER_WINDOW_MS = 250
DEFAULT_BOSS_LASER_STALE_SECONDS = 8.0
DEFAULT_BOSS_LASER_COUNTDOWN_SOUNDS = {
    4: DEFAULT_BOSS_RED_ORB_COUNTDOWN_4_SOUND,
    3: DEFAULT_BOSS_RED_ORB_COUNTDOWN_3_SOUND,
    2: DEFAULT_BOSS_RED_ORB_COUNTDOWN_2_SOUND,
    1: DEFAULT_BOSS_RED_ORB_COUNTDOWN_1_SOUND,
    0: DEFAULT_BOSS_RED_ORB_COUNTDOWN_0_SOUND,
}
DEFAULT_KEY_ENEMY_DEBUFF_COMPLETE_SOUND = "assets/audio/xiaoyi/debuffs_ready.wav"
DEFAULT_KEY_ENEMY_DEBUFF_EXPIRY_SOUND = "assets/audio/xiaoyi/debuffs_renew.wav"
DEFAULT_KEY_ENEMY_DEBUFF_COMPLETE_MESSAGE = "BUFF齐啦"
DEFAULT_KEY_ENEMY_DEBUFF_EXPIRY_MESSAGE = "破防该续啦"
DEFAULT_KEY_ENEMY_DEBUFF_EXPIRY_SECONDS = 30
DEFAULT_KEY_ENEMY_DEBUFF_PHYSICAL_BREAK_MIN = 30
DEFAULT_KEY_ENEMY_DEBUFF_MAGIC_BREAK_MIN = 41
DEFAULT_KEY_ENEMY_DEBUFF_DAMAGE_BONUS_MIN = 61
DEFAULT_KEY_ENEMY_DEBUFF_RABBIT_STACKS_MIN = 4
KEY_ENEMY_DEBUFF_UNTIMED_CCIDS = {598}
KAILAHE_PHASE_1_MAX_HP = 80_032_160
KAILAHE_PHASE_2_MAX_HP = 104_041_810
DEFAULT_KEY_ENEMY_GUNNER_EYE_NAME = "枪手之眼"
DEFAULT_KEY_ENEMY_GUNNER_EYE_CCID = 1122
DEFAULT_KEY_ENEMY_GUNNER_EYE_SECONDS = 5
DEFAULT_KEY_ENEMY_GUNNER_EYE_REMAINING_SOUND = (
    "assets/audio/xiaoyi/gunner_eye_remaining.wav"
)
DEFAULT_KEY_ENEMY_GUNNER_EYE_ENDED_SOUND = (
    "assets/audio/xiaoyi/gunner_eye_ended.wav"
)
DEFAULT_KEY_ENEMY_GUNNER_EYE_REMAINING_MESSAGE = "枪手之眼"
DEFAULT_KEY_ENEMY_GUNNER_EYE_ENDED_MESSAGE = "枪手之眼 结束"
KEY_ENEMY_DEBUFF_COMPLETE_REFRESH_GRACE_MS = 1000
KEY_ENEMY_DEBUFF_REJECTED_REMOVE_GRACE_MS = 30000
DEFAULT_KEY_ENEMY_DEBUFF_BOSS_MAX_HP_VALUES = (
    698_517_000,
    850_368_600,
    1_143_352_700,
    1_967_880_100,
    3_449_779_200,
    KAILAHE_PHASE_1_MAX_HP,
    KAILAHE_PHASE_2_MAX_HP,
)
KEY_ENEMY_DEBUFF_REQUIREMENTS = (
    "physical_break",
    "magic_break",
    "damage_bonus",
    "bernak_physical",
    "bernak_magic",
    "cat",
    "dragon_thunder",
    "rabbit",
    "kart_bubble",
)
KEY_ENEMY_DEBUFF_CCID_TO_REQUIREMENT = {
    1164: "physical_break",
    1165: "magic_break",
    1166: "damage_bonus",
    1094: "bernak_physical",
    1093: "bernak_magic",
    912: "cat",
    913: "cat",
    392: "dragon_thunder",
    1138: "rabbit",
    598: "kart_bubble",
}
DEFAULT_KEY_ENEMY_WATCHED_DEBUFFS = (
    {
        "name": DEFAULT_KEY_ENEMY_GUNNER_EYE_NAME,
        "ccids": (DEFAULT_KEY_ENEMY_GUNNER_EYE_CCID,),
        "enabled": False,
        "remaining_enabled": True,
        "remaining_seconds": DEFAULT_KEY_ENEMY_GUNNER_EYE_SECONDS,
        "remaining_sound": DEFAULT_KEY_ENEMY_GUNNER_EYE_REMAINING_SOUND,
        "remaining_message": DEFAULT_KEY_ENEMY_GUNNER_EYE_REMAINING_MESSAGE,
        "ended_enabled": True,
        "ended_sound": DEFAULT_KEY_ENEMY_GUNNER_EYE_ENDED_SOUND,
        "ended_message": DEFAULT_KEY_ENEMY_GUNNER_EYE_ENDED_MESSAGE,
    },
)
SOUND_SEQUENCE_PREFIX = "sequence:"
SOUND_SEQUENCE_SEPARATOR = "|"
SOUND_TIMED_SEQUENCE_PREFIX = "timed_sequence:"
_SOUND_CANCEL_LOCK = threading.Lock()
_SOUND_CANCEL_GENERATIONS: dict[str, int] = {}
_ASYNC_AUDIO_LOCK = threading.Lock()


@dataclass(frozen=True)
class AlertRule:
    remaining_seconds: int
    sound: str
    message: str


@dataclass(frozen=True)
class ProgressAlertRule:
    remaining_progress: float
    sound: str
    message: str


@dataclass(frozen=True)
class StackAlertRule:
    stacks: int
    sound: str
    message: str


@dataclass(frozen=True)
class EventMessageMatch:
    index: int
    type: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class EventFieldMatch:
    field: str
    value: str | None = None


@dataclass(frozen=True)
class StatValueMatch:
    stat_id: int
    value: float | None = None
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True)
class EventTrigger:
    event_id: int
    op: str | None = None
    message_matches: tuple[EventMessageMatch, ...] = ()
    field_matches: tuple[EventFieldMatch, ...] = ()


@dataclass(frozen=True)
class StatDropRule:
    stat_id: int
    min_drop: float
    max_drop: float | None = None


@dataclass(frozen=True)
class MissingMagicShieldSpec:
    ccid: int = MAGIC_SHIELD_CCID
    delay_seconds: float = DEFAULT_MAGIC_SHIELD_MISSING_DELAY_SECONDS
    repeat_seconds: float = DEFAULT_MAGIC_SHIELD_MISSING_REPEAT_SECONDS
    sound: str = DEFAULT_MAGIC_SHIELD_MISSING_SOUND
    message: str = DEFAULT_MAGIC_SHIELD_MISSING_MESSAGE
    audio_volume: int = 100


@dataclass(frozen=True)
class BossHpAlertRule:
    threshold_percent: float
    sound: str
    message: str


@dataclass(frozen=True)
class BossHpAlertSpec:
    name: str
    entity_id: str = ""
    short_name: str = ""
    max_hp_values: tuple[float, ...] = ()
    current_hp_stat_id: int = BOSS_HP_CURRENT_STAT_ID
    max_hp_stat_id: int = BOSS_HP_MAX_STAT_ID
    alerts: list[BossHpAlertRule] = field(default_factory=list)
    audio_volume: int = 100
    safehouse_countdown_enabled: bool = False
    safehouse_countdown_effect_name: str = ""
    safehouse_countdown_sound_dir: str = (
        DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_SOUND_DIR
    )
    safehouse_countdown_message_template: str = (
        DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_MESSAGE
    )
    safehouse_countdown_min_seconds: int = (
        DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_MIN_SECONDS
    )
    safehouse_countdown_max_seconds: int = (
        DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_MAX_SECONDS
    )


@dataclass(frozen=True)
class BossSkillBurstAlertSpec:
    name: str
    entity_id: str = ""
    max_hp_values: tuple[float, ...] = ()
    skill_id: int = DEFAULT_BOSS_DOUBLE_LASER_SKILL_ID
    burst_window_ms: int = DEFAULT_BOSS_DOUBLE_LASER_BURST_WINDOW_MS
    repeat_window_ms: int = DEFAULT_BOSS_DOUBLE_LASER_REPEAT_WINDOW_MS
    dedupe_seconds: float = DEFAULT_BOSS_DOUBLE_LASER_DEDUPE_SECONDS
    sound: str = DEFAULT_BOSS_DOUBLE_LASER_SOUND
    message: str = DEFAULT_BOSS_DOUBLE_LASER_MESSAGE
    audio_volume: int = 100


@dataclass(frozen=True)
class BossRedOrbAlertSpec:
    name: str
    entity_id: str = ""
    max_hp_values: tuple[float, ...] = DEFAULT_BOSS_RED_ORB_BOSS_MAX_HP_VALUES
    current_hp_stat_id: int = BOSS_HP_CURRENT_STAT_ID
    max_hp_stat_id: int = BOSS_HP_MAX_STAT_ID
    orb_race_ids: tuple[int, ...] = DEFAULT_BOSS_RED_ORB_RACE_IDS
    countdown_op: str = DEFAULT_BOSS_RED_ORB_COUNTDOWN_OP
    countdown_marker: str = DEFAULT_BOSS_RED_ORB_COUNTDOWN_MARKER
    start_step: str = DEFAULT_BOSS_RED_ORB_START_STEP
    confirm_step: str = DEFAULT_BOSS_RED_ORB_CONFIRM_STEP
    pair_window_ms: int = DEFAULT_BOSS_RED_ORB_PAIR_WINDOW_MS
    explosion_delay_seconds: float = DEFAULT_BOSS_RED_ORB_EXPLOSION_DELAY_SECONDS
    high_hp_explosion_delay_seconds: float = (
        DEFAULT_BOSS_RED_ORB_HIGH_HP_EXPLOSION_DELAY_SECONDS
    )
    low_hp_explosion_delay_seconds: float = (
        DEFAULT_BOSS_RED_ORB_LOW_HP_EXPLOSION_DELAY_SECONDS
    )
    lead_seconds: float = DEFAULT_BOSS_RED_ORB_LEAD_SECONDS
    contact_check_seconds: float = DEFAULT_BOSS_RED_ORB_CONTACT_CHECK_SECONDS
    safe_min_contact_ticks: int = DEFAULT_BOSS_RED_ORB_SAFE_MIN_CONTACT_TICKS
    safe_last_contact_before_seconds: float = (
        DEFAULT_BOSS_RED_ORB_SAFE_LAST_CONTACT_BEFORE_SECONDS
    )
    contact_group_ms: int = DEFAULT_BOSS_RED_ORB_CONTACT_GROUP_MS
    hp_split_percent: float = DEFAULT_BOSS_RED_ORB_HP_SPLIT_PERCENT
    high_hp_required_contact_ticks: int = (
        DEFAULT_BOSS_RED_ORB_HIGH_HP_REQUIRED_CONTACT_TICKS
    )
    high_hp_early_check_seconds: float = (
        DEFAULT_BOSS_RED_ORB_HIGH_HP_EARLY_CHECK_SECONDS
    )
    high_hp_early_max_contact_ticks: int = (
        DEFAULT_BOSS_RED_ORB_HIGH_HP_EARLY_MAX_CONTACT_TICKS
    )
    high_hp_final_check_seconds: float = (
        DEFAULT_BOSS_RED_ORB_HIGH_HP_FINAL_CHECK_SECONDS
    )
    low_hp_required_contact_ticks: int = (
        DEFAULT_BOSS_RED_ORB_LOW_HP_REQUIRED_CONTACT_TICKS
    )
    low_hp_early_check_seconds: float = (
        DEFAULT_BOSS_RED_ORB_LOW_HP_EARLY_CHECK_SECONDS
    )
    low_hp_early_max_contact_ticks: int = (
        DEFAULT_BOSS_RED_ORB_LOW_HP_EARLY_MAX_CONTACT_TICKS
    )
    low_hp_final_check_seconds: float = (
        DEFAULT_BOSS_RED_ORB_LOW_HP_FINAL_CHECK_SECONDS
    )
    late_confirm_op: str = DEFAULT_BOSS_RED_ORB_LATE_CONFIRM_OP
    late_confirm_start_seconds: float = DEFAULT_BOSS_RED_ORB_LATE_CONFIRM_START_SECONDS
    late_confirm_end_seconds: float = DEFAULT_BOSS_RED_ORB_LATE_CONFIRM_END_SECONDS
    stale_seconds: float = DEFAULT_BOSS_RED_ORB_STALE_SECONDS
    sound: str = DEFAULT_BOSS_RED_ORB_SOUND
    message: str = DEFAULT_BOSS_RED_ORB_MESSAGE
    safe_sound: str = DEFAULT_BOSS_RED_ORB_SAFE_SOUND
    countdown_sounds: dict[int, str] = field(default_factory=dict)
    audio_volume: int = 100


@dataclass(frozen=True)
class BossLaserAlertSpec:
    name: str
    entity_id: str = ""
    max_hp_values: tuple[float, ...] = DEFAULT_BOSS_LASER_BOSS_MAX_HP_VALUES
    current_hp_stat_id: int = BOSS_HP_CURRENT_STAT_ID
    max_hp_stat_id: int = BOSS_HP_MAX_STAT_ID
    stardust_race_ids: tuple[int, ...] = DEFAULT_BOSS_LASER_STARDUST_RACE_IDS
    cast_op: str = DEFAULT_BOSS_LASER_CAST_OP
    skill_id: int = DEFAULT_BOSS_LASER_SKILL_ID
    cast_seconds: float = DEFAULT_BOSS_LASER_CAST_SECONDS
    cluster_window_ms: int = DEFAULT_BOSS_LASER_CLUSTER_WINDOW_MS
    stale_seconds: float = DEFAULT_BOSS_LASER_STALE_SECONDS
    sound: str = DEFAULT_BOSS_LASER_WARNING_SOUND
    message: str = DEFAULT_BOSS_LASER_WARNING_MESSAGE
    countdown_sounds: dict[int, str] = field(default_factory=dict)
    audio_volume: int = 100


@dataclass(frozen=True)
class WatchedKeyEnemyDebuffSpec:
    name: str
    ccids: tuple[int, ...]
    enabled: bool = True
    remaining_enabled: bool = True
    remaining_seconds: int = DEFAULT_KEY_ENEMY_GUNNER_EYE_SECONDS
    remaining_sound: str = DEFAULT_KEY_ENEMY_GUNNER_EYE_REMAINING_SOUND
    remaining_message: str = DEFAULT_KEY_ENEMY_GUNNER_EYE_REMAINING_MESSAGE
    ended_enabled: bool = True
    ended_sound: str = DEFAULT_KEY_ENEMY_GUNNER_EYE_ENDED_SOUND
    ended_message: str = DEFAULT_KEY_ENEMY_GUNNER_EYE_ENDED_MESSAGE


@dataclass(frozen=True)
class KeyEnemyDebuffAlertSpec:
    complete_enabled: bool = False
    expiry_enabled: bool = True
    max_hp_values: tuple[float, ...] = DEFAULT_KEY_ENEMY_DEBUFF_BOSS_MAX_HP_VALUES
    current_hp_stat_id: int = BOSS_HP_CURRENT_STAT_ID
    max_hp_stat_id: int = BOSS_HP_MAX_STAT_ID
    complete_sound: str = DEFAULT_KEY_ENEMY_DEBUFF_COMPLETE_SOUND
    complete_message: str = DEFAULT_KEY_ENEMY_DEBUFF_COMPLETE_MESSAGE
    expiry_sound: str = DEFAULT_KEY_ENEMY_DEBUFF_EXPIRY_SOUND
    expiry_message: str = DEFAULT_KEY_ENEMY_DEBUFF_EXPIRY_MESSAGE
    expiry_seconds: int = DEFAULT_KEY_ENEMY_DEBUFF_EXPIRY_SECONDS
    physical_break_min: float = DEFAULT_KEY_ENEMY_DEBUFF_PHYSICAL_BREAK_MIN
    magic_break_min: float = DEFAULT_KEY_ENEMY_DEBUFF_MAGIC_BREAK_MIN
    damage_bonus_min: float = DEFAULT_KEY_ENEMY_DEBUFF_DAMAGE_BONUS_MIN
    rabbit_stacks_min: int = DEFAULT_KEY_ENEMY_DEBUFF_RABBIT_STACKS_MIN
    watched_debuffs: tuple[WatchedKeyEnemyDebuffSpec, ...] = ()
    audio_volume: int = 100


@dataclass
class BuffSpec:
    name: str
    ccid: int
    skill_id: int | None = None
    self_filter: bool = True
    required_extra: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float | None = None
    sbt_adjust_seconds: float = 0
    use_dynamic_sbt_adjust: bool = True
    sbt_ended_lead_seconds: float = DEFAULT_SBT_ENDED_LEAD_SECONDS
    linked_ccids: set[int] = field(default_factory=set)
    stack_field: str | None = None
    max_stacks: int | None = None
    stack_alert: StackAlertRule | None = None
    alerts: list[AlertRule] = field(default_factory=list)
    audio_volume: int = 100
    ended_alert: bool = True
    ended_sound: str = DEFAULT_ENDED_SOUND
    ended_message: str = "{name} 结束"
    ended_on_remove_only: bool = False
    ended_grace_seconds: float = DEFAULT_ENDED_GRACE_SECONDS
    early_remove_reapply_grace_seconds: float = 0
    cooldown_alert: bool = False
    cooldown_delay_seconds: float = 0
    cooldown_sound: str = DEFAULT_ENDED_SOUND
    cooldown_message: str = "{name} 就绪"
    clear_after_stack_alert: bool = False
    clear_sound: str = DEFAULT_ENDED_SOUND
    clear_message: str = "{name} 已清除"
    clear_grace_seconds: float = DEFAULT_ENDED_GRACE_SECONDS
    clear_after_stack_min_active_seconds: float = 0
    suppress_remaining_if_active_ccids: set[int] = field(default_factory=set)
    suppress_ended_if_active_ccids: set[int] = field(default_factory=set)
    prefer_sbt_when_duration_present: bool = False


@dataclass
class ProgressSpec:
    name: str
    stat_id: int
    max_value: float = 100
    alerts: list[ProgressAlertRule] = field(default_factory=list)
    audio_volume: int = 100


@dataclass
class StatDropEffectSpec:
    name: str
    trigger: EventTrigger
    start_trigger: EventTrigger | None = None
    start_stat_matches: tuple[StatValueMatch, ...] = ()
    stop_stat_matches: tuple[StatValueMatch, ...] = ()
    start_offset_seconds: float = 0
    timer_sync_stat_matches: tuple[StatValueMatch, ...] = ()
    timer_sync_event_id: int | None = None
    timer_sync_initial_min_delay_seconds: float = 0
    timer_sync_initial_max_delay_seconds: float = 0
    timer_sync_expected_tolerance_seconds: float = 0
    timer_sync_min_interval_seconds: float = 0
    timer_sync_max_interval_seconds: float = 0
    drop_rules: list[StatDropRule] = field(default_factory=list)
    min_drop_count: int = 1
    allow_unseen_drop: bool = False
    trigger_dedupe_seconds: float = 0
    ignore_trigger_while_active: bool = False
    trigger_rearm_tolerance_seconds: float = 0
    repeat_timer: bool = False
    self_filter: bool = True
    timer_enabled: bool = False
    duration_seconds: int = 0
    alerts: list[AlertRule] = field(default_factory=list)
    audio_volume: int = 100
    ended_alert: bool = True
    ended_sound: str = DEFAULT_ENDED_SOUND
    ended_message: str = "{name} 结束"


@dataclass
class BuffState:
    spec: BuffSpec
    end_ms: int | None = None
    stacks: int | None = None
    active: bool = False
    active_ccid: int | None = None
    fired_thresholds: set[int] = field(default_factory=set)
    ended_fired: bool = False
    ended_pending_at_ms: int | None = None
    cooldown_pending_at_ms: int | None = None
    cooldown_fired: bool = False
    stack_alert_fired: bool = False
    clear_alert_fired: bool = False
    clear_pending_at_ms: int | None = None
    clear_pending_cleared_at_ms: int | None = None
    last_apply_at_ms: int | None = None
    last_event_at_ms: int | None = None
    last_timing_source: str | None = None
    last_computed_end_ms: int | None = None
    last_raw_sbt_end_ms: int | None = None
    last_sbt_adjust_seconds: float | None = None
    last_sbt_adjust_source: str | None = None
    last_raw_sbt_remaining_seconds: float | None = None
    last_adjusted_remaining_seconds: float | None = None
    pending_dynamic_sbt_learn_at_ms: int | None = None
    pending_dynamic_sbt_remove_at_ms: int | None = None
    pending_dynamic_sbt_raw_end_ms: int | None = None
    music_strong_reminder_next_at_ms: int | None = None
    music_strong_reminder_rule_seconds: int | None = None
    music_strong_reminder_sound: str | None = None
    music_toan_extended: bool = False
    music_toan_extended_at_ms: int | None = None
    music_toan_extension_source: str | None = None


@dataclass
class ProgressState:
    spec: ProgressSpec
    value: float | None = None
    fired_thresholds: set[float] = field(default_factory=set)


@dataclass
class StatDropEffectState:
    spec: StatDropEffectSpec
    active: bool = False
    ended_fired: bool = False
    end_ms: int | None = None
    fired_thresholds: set[int] = field(default_factory=set)
    last_values: dict[int, float] = field(default_factory=dict)
    last_trigger_at_ms: int | None = None
    last_start_at_ms: int | None = None
    tracked_entity_id: str | None = None
    timer_sync_last_at_ms: int | None = None
    timer_sync_seen_entity_ids: set[str] = field(default_factory=set)
    timer_sync_entity_values: dict[str, dict[int, float]] = field(
        default_factory=dict
    )


@dataclass
class BossHpAlertState:
    spec: BossHpAlertSpec
    tracked_entity_id: str | None = None
    active: bool = False
    previous_percent: float | None = None
    fired_thresholds: set[float] = field(default_factory=set)
    last_seen_at_ms: int | None = None
    last_current_hp: float | None = None
    last_max_hp: float | None = None
    last_raw_percent: float | None = None
    phase_handoff_until_ms: int | None = None


@dataclass
class BossSkillBurstAlertState:
    spec: BossSkillBurstAlertSpec
    tracked_entity_id: str | None = None
    active: bool = False
    current_burst_started_at_ms: int | None = None
    current_burst_last_at_ms: int | None = None
    previous_burst_started_at_ms: int | None = None
    last_fired_at_ms: int | None = None


@dataclass
class BossRedOrbPendingState:
    boss_entity_id: str
    start_at_ms: int
    confirm_at_ms: int | None
    warn_at_ms: int
    explosion_at_ms: int
    final_warn_at_ms: int | None = None
    early_warn_max_contact_ticks: int | None = None
    required_contact_ticks: int = DEFAULT_BOSS_RED_ORB_SAFE_MIN_CONTACT_TICKS
    hp_percent: float | None = None
    profile_name: str = ""
    confirmed: bool = False
    fired: bool = False
    canceled: bool = False
    sound_canceled: bool = False
    last_activity_at_ms: int | None = None
    contact_at_mses: list[int] = field(default_factory=list)
    orb_entity_ids: set[str] = field(default_factory=set)
    removed_orb_entity_ids: set[str] = field(default_factory=set)


@dataclass
class BossRedOrbAlertState:
    spec: BossRedOrbAlertSpec
    tracked_entity_id: str | None = None
    active: bool = False
    last_seen_at_ms: int | None = None
    last_current_hp: float | None = None
    last_max_hp: float | None = None
    pending_start_at_ms: int | None = None
    pending_alerts: list[BossRedOrbPendingState] = field(default_factory=list)
    orb_entity_to_pending: dict[str, int] = field(default_factory=dict)


@dataclass
class BossLaserPendingState:
    boss_entity_id: str
    start_at_ms: int
    impact_at_ms: int
    stardust_entity_ids: set[str] = field(default_factory=set)
    stardust_race_ids_by_entity_id: dict[str, int] = field(default_factory=dict)
    removed_stardust_entity_ids: set[str] = field(default_factory=set)
    canceled: bool = False
    sound_canceled: bool = False


@dataclass
class BossLaserAlertState:
    spec: BossLaserAlertSpec
    tracked_entity_id: str | None = None
    active: bool = False
    last_seen_at_ms: int | None = None
    last_current_hp: float | None = None
    last_max_hp: float | None = None
    stardust_entity_ids: set[str] = field(default_factory=set)
    stardust_race_ids_by_entity_id: dict[str, int] = field(default_factory=dict)
    stardust_removed_entity_ids: set[str] = field(default_factory=set)
    pending_alerts: list[BossLaserPendingState] = field(default_factory=list)


@dataclass
class KeyEnemyDebuffRequirementState:
    active: bool = False
    end_ms: int | None = None
    warned_end_ms: int | None = None
    ended_fired_end_ms: int | None = None
    last_apply_at_ms: int | None = None
    active_instance_end_ms_by_ccid: dict[int, list[int | None]] = field(
        default_factory=dict
    )
    rejected_instance_end_ms_by_ccid: dict[int, list[int]] = field(
        default_factory=dict
    )


@dataclass
class KeyEnemyDebuffEntityState:
    spec: KeyEnemyDebuffAlertSpec
    tracked_entity_id: str
    active: bool = False
    requirements: dict[str, KeyEnemyDebuffRequirementState] = field(
        default_factory=lambda: {
            key: KeyEnemyDebuffRequirementState()
            for key in KEY_ENEMY_DEBUFF_REQUIREMENTS
        }
    )
    expiry_requirements: dict[str, KeyEnemyDebuffRequirementState] = field(
        default_factory=lambda: {
            key: KeyEnemyDebuffRequirementState()
            for key in KEY_ENEMY_DEBUFF_REQUIREMENTS
        }
    )
    watched_debuffs: dict[str, KeyEnemyDebuffRequirementState] = field(
        default_factory=dict
    )
    complete_active: bool = False
    complete_lost_at_ms: int | None = None
    last_complete_alert_at_ms: int | None = None
    last_seen_at_ms: int | None = None
    last_current_hp: float | None = None
    last_max_hp: float | None = None


@dataclass
class FiredAlert:
    at_ms: int
    kind: str
    name: str
    ccid: int | None
    remaining_seconds: int | None
    message: str
    sound: str
    volume: int = 100
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadedSpecs:
    buffs: list[BuffSpec]
    progresses: list[ProgressSpec]
    stat_drop_effects: list[StatDropEffectSpec] = field(default_factory=list)
    boss_hp_alerts: list[BossHpAlertSpec] = field(default_factory=list)
    boss_skill_burst_alerts: list[BossSkillBurstAlertSpec] = field(
        default_factory=list
    )
    boss_red_orb_alerts: list[BossRedOrbAlertSpec] = field(default_factory=list)
    boss_laser_alerts: list[BossLaserAlertSpec] = field(default_factory=list)
    key_enemy_debuff_alert: KeyEnemyDebuffAlertSpec | None = None
    magic_shield_missing: MissingMagicShieldSpec | None = None
    death_clear_suppression_window_ms: int = DEFAULT_DEATH_CLEAR_SUPPRESSION_WINDOW_MS
    death_clear_suppression_min_buffs: int = DEFAULT_DEATH_CLEAR_SUPPRESSION_MIN_BUFFS
    death_signal_event_ids: set[int] = field(
        default_factory=lambda: set(DEFAULT_DEATH_SIGNAL_EVENT_IDS)
    )
    death_signal_suppression_window_ms: int = (
        DEFAULT_DEATH_SIGNAL_SUPPRESSION_WINDOW_MS
    )
    music_strong_reminder_enabled: bool = DEFAULT_MUSIC_STRONG_REMINDER_ENABLED
    music_strong_reminder_repeat_seconds: float = (
        DEFAULT_MUSIC_STRONG_REMINDER_REPEAT_SECONDS
    )
    music_strong_reminder_prefix_sound: str = DEFAULT_MUSIC_STRONG_REMINDER_PREFIX_SOUND


def load_all_specs(config_path: str | Path) -> LoadedSpecs:
    config_file = Path(config_path)
    config_dir = config_file.resolve().parent
    data = migrate_config_file(config_file)
    buff_specs: list[BuffSpec] = []
    progress_specs: list[ProgressSpec] = []
    stat_drop_effect_specs: list[StatDropEffectSpec] = []
    boss_hp_alert_specs: list[BossHpAlertSpec] = []
    boss_skill_burst_alert_specs: list[BossSkillBurstAlertSpec] = []
    boss_red_orb_alert_specs: list[BossRedOrbAlertSpec] = []
    boss_laser_alert_specs: list[BossLaserAlertSpec] = []
    key_enemy_debuff_alert_spec: KeyEnemyDebuffAlertSpec | None = None
    magic_shield_missing_spec: MissingMagicShieldSpec | None = None
    default_sbt_adjust_seconds = float(
        data.get("sbt_adjust_seconds", data.get("end_time_adjust_seconds", 0))
    )
    default_sbt_ended_lead_seconds = max(
        0.0,
        float(
            data.get(
                "sbt_ended_lead_seconds",
                data.get(
                    "end_time_ended_lead_seconds",
                    DEFAULT_SBT_ENDED_LEAD_SECONDS,
                ),
            )
        ),
    )
    default_audio_volume = normalize_volume(data.get("audio_volume", 100))
    default_ended_grace_seconds = max(
        0.0, float(data.get("ended_grace_seconds", DEFAULT_ENDED_GRACE_SECONDS))
    )
    death_clear_suppression_window_ms = max(
        0,
        int(
            data.get(
                "death_clear_suppression_window_ms",
                DEFAULT_DEATH_CLEAR_SUPPRESSION_WINDOW_MS,
            )
        ),
    )
    death_clear_suppression_min_buffs = max(
        0,
        int(
            data.get(
                "death_clear_suppression_min_buffs",
                DEFAULT_DEATH_CLEAR_SUPPRESSION_MIN_BUFFS,
            )
        ),
    )
    raw_death_signal_event_ids = data.get(
        "death_signal_event_ids", list(DEFAULT_DEATH_SIGNAL_EVENT_IDS)
    )
    if isinstance(raw_death_signal_event_ids, (int, str)):
        raw_death_signal_event_ids = [raw_death_signal_event_ids]
    death_signal_event_ids = {
        int(value) for value in raw_death_signal_event_ids if str(value).strip()
    }
    death_signal_suppression_window_ms = max(
        0,
        int(
            data.get(
                "death_signal_suppression_window_ms",
                DEFAULT_DEATH_SIGNAL_SUPPRESSION_WINDOW_MS,
            )
        ),
    )

    def sound_path(value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str(config_dir / path)

    def countdown_sound_paths(
        value: Any,
        defaults: dict[int, str],
    ) -> dict[int, str]:
        if not isinstance(value, dict):
            value = {}
        result: dict[int, str] = {}
        for number, default_sound in defaults.items():
            raw_sound = value.get(str(number), value.get(number, default_sound))
            result[number] = sound_path(str(raw_sound or default_sound))
        return result

    def parse_max_hp_values(raw_values: Any) -> list[float]:
        if isinstance(raw_values, (int, float, str)):
            raw_values = [raw_values]
        max_hp_values: list[float] = []
        for raw_max_hp in raw_values or []:
            try:
                max_hp = float(raw_max_hp)
            except (TypeError, ValueError):
                continue
            if max_hp > 0:
                max_hp_values.append(max_hp)
        return max_hp_values

    music_strong_data = data.get("music_strong_reminder") or {}
    if not isinstance(music_strong_data, dict):
        music_strong_data = {}
    music_strong_reminder_enabled = bool(
        music_strong_data.get(
            "enabled",
            DEFAULT_MUSIC_STRONG_REMINDER_ENABLED,
        )
    )
    music_strong_reminder_repeat_seconds = max(
        0.5,
        float(
            music_strong_data.get(
                "repeat_seconds",
                DEFAULT_MUSIC_STRONG_REMINDER_REPEAT_SECONDS,
            )
        ),
    )
    music_strong_reminder_prefix_sound = sound_path(
        str(
            music_strong_data.get(
                "prefix_sound",
                DEFAULT_MUSIC_STRONG_REMINDER_PREFIX_SOUND,
            )
        )
    )

    for item in data.get("buffs", []):
        try:
            item_ccid = int(item.get("ccid"))
        except (TypeError, ValueError):
            item_ccid = None
        if (
            item.get("enabled")
            and (item.get("name") == MAGIC_SHIELD_NAME or item_ccid == MAGIC_SHIELD_CCID)
        ):
            missing_data = item.get("missing_shield_alert") or {}
            if missing_data.get("enabled"):
                magic_shield_missing_spec = MissingMagicShieldSpec(
                    ccid=item_ccid or MAGIC_SHIELD_CCID,
                    delay_seconds=max(
                        0.0,
                        float(
                            missing_data.get(
                                "delay_seconds",
                                DEFAULT_MAGIC_SHIELD_MISSING_DELAY_SECONDS,
                            )
                        ),
                    ),
                    repeat_seconds=max(
                        0.1,
                        float(
                            missing_data.get(
                                "repeat_seconds",
                                DEFAULT_MAGIC_SHIELD_MISSING_REPEAT_SECONDS,
                            )
                        ),
                    ),
                    sound=sound_path(
                        missing_data.get(
                            "sound", DEFAULT_MAGIC_SHIELD_MISSING_SOUND
                        )
                    ),
                    message=missing_data.get(
                        "message", DEFAULT_MAGIC_SHIELD_MISSING_MESSAGE
                    ),
                    audio_volume=normalize_volume(
                        item.get("audio_volume", default_audio_volume)
                    ),
                )
        if (
            item.get("name") == MAGIC_SHIELD_NAME
            and item.get("ended_message") in (None, "{name} \u5df2\u7ed3\u675f")
        ):
            item["ended_message"] = DEFAULT_MAGIC_SHIELD_ENDED_MESSAGE
        if not item.get("enabled"):
            continue

        warn_sound = sound_path(item.get("warn_sound", DEFAULT_WARN_SOUND))
        critical_sound = sound_path(item.get("critical_sound", DEFAULT_CRITICAL_SOUND))
        ended_sound = sound_path(item.get("ended_sound", DEFAULT_ENDED_SOUND))
        cooldown_sound = sound_path(
            item.get("cooldown_sound", item.get("ended_sound", DEFAULT_ENDED_SOUND))
        )
        stack_alert_data = item.get("stack_alert") or {}
        stack_alert = None
        if stack_alert_data and stack_alert_data.get("enabled", True):
            stack_alert = StackAlertRule(
                stacks=max(1, int(stack_alert_data.get("stacks", 1))),
                sound=(
                    sound_path(stack_alert_data["sound"])
                    if stack_alert_data.get("sound")
                    else warn_sound
                ),
                message=stack_alert_data.get("message", "{name} 达到危险层数"),
            )
        clear_sound = sound_path(
            item.get("clear_sound", item.get("ended_sound", DEFAULT_ENDED_SOUND))
        )

        if "alerts" in item:
            alerts = [
                AlertRule(
                    remaining_seconds=int(alert["remaining_seconds"]),
                    sound=sound_path(alert["sound"]) if alert.get("sound") else warn_sound,
                    message=alert.get("message", "{name}"),
                )
                for alert in item["alerts"]
            ]
        else:
            alerts = [
                AlertRule(
                    remaining_seconds=int(item.get("warn_seconds", 60)),
                    sound=warn_sound,
                    message="{name}",
                ),
                AlertRule(
                    remaining_seconds=int(item.get("critical_seconds", 15)),
                    sound=critical_sound,
                    message="{name}",
                ),
            ]

        alerts.sort(key=lambda alert: alert.remaining_seconds, reverse=True)

        buff_specs.append(
            BuffSpec(
                name=item.get("name", f"cc_{item['ccid']}"),
                ccid=int(item["ccid"]),
                skill_id=int(item["skill_id"]) if item.get("skill_id") else None,
                self_filter=bool(item.get("self_filter", True)),
                required_extra=dict(item.get("required_extra") or {}),
                duration_seconds=(
                    float(item["duration_seconds"])
                    if item.get("duration_seconds") is not None
                    else (
                        float(item["fixed_duration_seconds"])
                        if item.get("fixed_duration_seconds") is not None
                        else None
                    )
                ),
                sbt_adjust_seconds=float(
                    item.get(
                        "sbt_adjust_seconds",
                        item.get("end_time_adjust_seconds", default_sbt_adjust_seconds),
                    )
                ),
                use_dynamic_sbt_adjust=bool(
                    item.get(
                        "use_dynamic_sbt_adjust",
                        data.get("use_dynamic_sbt_adjust", True),
                    )
                ),
                sbt_ended_lead_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "sbt_ended_lead_seconds",
                            item.get(
                                "end_time_ended_lead_seconds",
                                default_sbt_ended_lead_seconds,
                            ),
                        )
                    ),
                ),
                linked_ccids={int(ccid) for ccid in item.get("linked_ccids", [])},
                stack_field=item.get("stack_field"),
                max_stacks=item.get("max_stacks"),
                stack_alert=stack_alert,
                alerts=alerts,
                audio_volume=normalize_volume(
                    item.get("audio_volume", default_audio_volume)
                ),
                ended_alert=bool(item.get("ended_alert", True)),
                ended_sound=ended_sound,
                ended_message=item.get("ended_message", "{name} 结束"),
                ended_on_remove_only=bool(item.get("ended_on_remove_only", False)),
                ended_grace_seconds=max(
                    0.0,
                    float(item.get("ended_grace_seconds", default_ended_grace_seconds)),
                ),
                early_remove_reapply_grace_seconds=max(
                    0.0,
                    float(item.get("early_remove_reapply_grace_seconds", 0)),
                ),
                cooldown_alert=bool(item.get("cooldown_alert", False)),
                cooldown_delay_seconds=max(
                    0.0, float(item.get("cooldown_delay_seconds", 0))
                ),
                cooldown_sound=cooldown_sound,
                cooldown_message=item.get("cooldown_message", "{name} 就绪"),
                clear_after_stack_alert=bool(
                    item.get("clear_after_stack_alert", False)
                ),
                clear_sound=clear_sound,
                clear_message=item.get("clear_message", "{name} 已清除"),
                clear_grace_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "clear_grace_seconds",
                            item.get(
                                "ended_grace_seconds", default_ended_grace_seconds
                            ),
                        )
                    ),
                ),
                clear_after_stack_min_active_seconds=max(
                    0.0, float(item.get("clear_after_stack_min_active_seconds", 0))
                ),
                suppress_remaining_if_active_ccids={
                    int(ccid)
                    for ccid in item.get("suppress_remaining_if_active_ccids", [])
                },
                suppress_ended_if_active_ccids={
                    int(ccid)
                    for ccid in item.get("suppress_ended_if_active_ccids", [])
                },
                prefer_sbt_when_duration_present=bool(
                    item.get("prefer_sbt_when_duration_present", False)
                ),
            )
        )

    for item in data.get("progresses", []):
        if not item.get("enabled"):
            continue

        warn_sound = sound_path(item.get("warn_sound", DEFAULT_WARN_SOUND))
        alerts = [
            ProgressAlertRule(
                remaining_progress=float(alert.get("remaining_progress", 5)),
                sound=sound_path(alert["sound"]) if alert.get("sound") else warn_sound,
                message=alert.get("message", "{name} 已达到 {progress_percent:g}%"),
            )
            for alert in item.get("alerts", [])
        ]
        alerts.sort(key=lambda alert: alert.remaining_progress, reverse=True)
        progress_specs.append(
            ProgressSpec(
                name=item.get("name", f"stat_{item['stat_id']}"),
                stat_id=int(item["stat_id"]),
                max_value=float(item.get("max_value", 100)),
                alerts=alerts,
                audio_volume=normalize_volume(
                    item.get("audio_volume", default_audio_volume)
                ),
            )
        )

    def parse_event_trigger(trigger_data: dict[str, Any]) -> EventTrigger:
        message_matches = []
        for match in trigger_data.get("message_matches", []):
            try:
                index = int(match.get("index", 0))
            except (TypeError, ValueError):
                continue
            message_matches.append(
                EventMessageMatch(
                    index=index,
                    type=None if match.get("type") is None else str(match.get("type")),
                    value=None
                    if "value" not in match
                    else str(match.get("value")),
                )
            )
        field_matches = []
        for match in trigger_data.get("field_matches", []):
            field_name = str(match.get("field", "")).strip()
            if not field_name:
                continue
            field_matches.append(
                EventFieldMatch(
                    field=field_name,
                    value=None
                    if "value" not in match
                    else str(match.get("value")),
                )
            )
        return EventTrigger(
            event_id=int(trigger_data.get("event_id", 0)),
            op=trigger_data.get("op"),
            message_matches=tuple(message_matches),
            field_matches=tuple(field_matches),
        )

    def parse_stat_value_matches(items: list[dict[str, Any]]) -> tuple[StatValueMatch, ...]:
        matches: list[StatValueMatch] = []
        for match in items:
            try:
                stat_id = int(match["stat_id"])
            except (KeyError, TypeError, ValueError):
                continue
            value = None if match.get("value") is None else float(match["value"])
            min_value = (
                None if match.get("min_value") is None else float(match["min_value"])
            )
            max_value = (
                None if match.get("max_value") is None else float(match["max_value"])
            )
            matches.append(
                StatValueMatch(
                    stat_id=stat_id,
                    value=value,
                    min_value=min_value,
                    max_value=max_value,
                )
            )
        return tuple(matches)

    for item in data.get("stat_drop_effects", []):
        if not item.get("enabled"):
            continue

        trigger_data = item.get("trigger") or {}
        start_trigger_data = item.get("start_trigger") or None

        drop_rules = [
            StatDropRule(
                stat_id=int(rule["stat_id"]),
                min_drop=float(rule.get("min_drop", 1)),
                max_drop=(
                    None
                    if rule.get("max_drop") is None
                    else float(rule.get("max_drop"))
                ),
            )
            for rule in item.get("drop_rules", [])
        ]
        raw_timer_sync_event_id = item.get("timer_sync_event_id")
        try:
            timer_sync_event_id = (
                None
                if raw_timer_sync_event_id is None
                else int(raw_timer_sync_event_id)
            )
        except (TypeError, ValueError):
            timer_sync_event_id = None
        warn_sound = sound_path(item.get("warn_sound", DEFAULT_WARN_SOUND))
        alerts = [
            AlertRule(
                remaining_seconds=int(alert.get("remaining_seconds", 60)),
                sound=sound_path(alert["sound"]) if alert.get("sound") else warn_sound,
                message=alert.get("message", "{name}"),
            )
            for alert in item.get("alerts", [])
        ]
        alerts.sort(key=lambda alert: alert.remaining_seconds, reverse=True)

        stat_drop_effect_specs.append(
            StatDropEffectSpec(
                name=item.get("name", f"event_{trigger_data.get('event_id', 0)}"),
                trigger=parse_event_trigger(trigger_data),
                start_trigger=(
                    parse_event_trigger(start_trigger_data)
                    if isinstance(start_trigger_data, dict)
                    else None
                ),
                start_stat_matches=parse_stat_value_matches(
                    item.get("start_stat_matches", [])
                ),
                stop_stat_matches=parse_stat_value_matches(
                    item.get("stop_stat_matches", [])
                ),
                start_offset_seconds=max(
                    0.0, float(item.get("start_offset_seconds", 0))
                ),
                timer_sync_stat_matches=parse_stat_value_matches(
                    item.get("timer_sync_stat_matches", [])
                ),
                timer_sync_event_id=timer_sync_event_id,
                timer_sync_initial_min_delay_seconds=max(
                    0.0,
                    float(item.get("timer_sync_initial_min_delay_seconds", 0)),
                ),
                timer_sync_initial_max_delay_seconds=max(
                    0.0,
                    float(item.get("timer_sync_initial_max_delay_seconds", 0)),
                ),
                timer_sync_expected_tolerance_seconds=max(
                    0.0,
                    float(item.get("timer_sync_expected_tolerance_seconds", 0)),
                ),
                timer_sync_min_interval_seconds=max(
                    0.0, float(item.get("timer_sync_min_interval_seconds", 0))
                ),
                timer_sync_max_interval_seconds=max(
                    0.0, float(item.get("timer_sync_max_interval_seconds", 0))
                ),
                drop_rules=drop_rules,
                min_drop_count=max(1, int(item.get("min_drop_count", 1))),
                allow_unseen_drop=bool(item.get("allow_unseen_drop", False)),
                trigger_dedupe_seconds=max(
                    0.0, float(item.get("trigger_dedupe_seconds", 0))
                ),
                ignore_trigger_while_active=bool(
                    item.get("ignore_trigger_while_active", False)
                ),
                trigger_rearm_tolerance_seconds=max(
                    0.0, float(item.get("trigger_rearm_tolerance_seconds", 0))
                ),
                repeat_timer=bool(item.get("repeat_timer", False)),
                self_filter=bool(item.get("self_filter", True)),
                timer_enabled=bool(item.get("timer_enabled", False)),
                duration_seconds=max(0, int(item.get("duration_seconds", 0))),
                alerts=alerts,
                audio_volume=normalize_volume(
                    item.get("audio_volume", default_audio_volume)
                ),
                ended_alert=bool(item.get("ended_alert", True)),
                ended_sound=sound_path(item.get("ended_sound", DEFAULT_ENDED_SOUND)),
                ended_message=item.get("ended_message", "{name} 结束"),
            )
        )

    for item in data.get("boss_hp_alerts", []):
        if not item.get("enabled", True):
            continue

        warn_sound = sound_path(item.get("warn_sound", DEFAULT_BOSS_HP_ALERT_SOUND))
        raw_max_hp_values = item.get(
            "max_hp_values",
            item.get("max_hp", item.get("max_hp_value", [])),
        )
        if isinstance(raw_max_hp_values, (int, float, str)):
            raw_max_hp_values = [raw_max_hp_values]
        max_hp_values: list[float] = []
        for raw_max_hp in raw_max_hp_values or []:
            try:
                max_hp = float(raw_max_hp)
            except (TypeError, ValueError):
                continue
            if max_hp > 0:
                max_hp_values.append(max_hp)
        alerts = [
            BossHpAlertRule(
                threshold_percent=max(
                    0.0, min(100.0, float(alert.get("threshold_percent", 0)))
                ),
                sound=sound_path(alert["sound"]) if alert.get("sound") else warn_sound,
                message=alert.get("message", DEFAULT_BOSS_HP_ALERT_MESSAGE),
            )
            for alert in item.get("alerts", [])
            if alert.get("threshold_percent") is not None
        ]
        alerts.sort(key=lambda alert: alert.threshold_percent, reverse=True)
        if not alerts and not bool(item.get("track_only", False)):
            continue

        entity_id = str(item.get("entity_id", item.get("id", ""))).strip()
        if not entity_id and not max_hp_values:
            continue

        boss_hp_alert_specs.append(
            BossHpAlertSpec(
                name=item.get("name", entity_id),
                entity_id=entity_id,
                short_name=item.get("short_name", ""),
                max_hp_values=tuple(max_hp_values),
                current_hp_stat_id=int(
                    item.get("current_hp_stat_id", BOSS_HP_CURRENT_STAT_ID)
                ),
                max_hp_stat_id=int(item.get("max_hp_stat_id", BOSS_HP_MAX_STAT_ID)),
                alerts=alerts,
                audio_volume=normalize_volume(
                    item.get("audio_volume", default_audio_volume)
                ),
                safehouse_countdown_enabled=bool(
                    item.get("safehouse_countdown_enabled", False)
                ),
                safehouse_countdown_effect_name=str(
                    item.get("safehouse_countdown_effect_name", "")
                ).strip(),
                safehouse_countdown_sound_dir=sound_path(
                    item.get(
                        "safehouse_countdown_sound_dir",
                        DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_SOUND_DIR,
                    )
                ),
                safehouse_countdown_message_template=str(
                    item.get(
                        "safehouse_countdown_message_template",
                        DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_MESSAGE,
                    )
                ),
                safehouse_countdown_min_seconds=max(
                    0,
                    int(
                        item.get(
                            "safehouse_countdown_min_seconds",
                            DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_MIN_SECONDS,
                        )
                    ),
                ),
                safehouse_countdown_max_seconds=max(
                    0,
                    int(
                        item.get(
                            "safehouse_countdown_max_seconds",
                            DEFAULT_BOSS_HP_SAFEHOUSE_COUNTDOWN_MAX_SECONDS,
                        )
                    ),
                ),
            )
        )

    tracked_boss_hp_keys = {
        int(round(max_hp))
        for spec in boss_hp_alert_specs
        for max_hp in spec.max_hp_values
    }
    for name, short_name, max_hp in (
        ("凯莱赫-1阶段", "雪女1阶段", KAILAHE_PHASE_1_MAX_HP),
        ("凯莱赫-2阶段", "雪女2阶段", KAILAHE_PHASE_2_MAX_HP),
    ):
        max_hp_key = int(round(max_hp))
        if max_hp_key in tracked_boss_hp_keys:
            continue
        tracked_boss_hp_keys.add(max_hp_key)
        boss_hp_alert_specs.append(
            BossHpAlertSpec(
                name=name,
                short_name=short_name,
                max_hp_values=(float(max_hp),),
                current_hp_stat_id=BOSS_HP_CURRENT_STAT_ID,
                max_hp_stat_id=BOSS_HP_MAX_STAT_ID,
                alerts=[],
                audio_volume=default_audio_volume,
            )
        )

    # Retained for legacy config compatibility, but disabled because the old
    # skill-burst heuristic was not reliable enough to ship.
    for item in ():
        if not item.get("enabled", True):
            continue

        raw_max_hp_values = item.get(
            "max_hp_values",
            item.get("max_hp", item.get("max_hp_value", [])),
        )
        if isinstance(raw_max_hp_values, (int, float, str)):
            raw_max_hp_values = [raw_max_hp_values]
        max_hp_values = []
        for raw_max_hp in raw_max_hp_values or []:
            try:
                max_hp = float(raw_max_hp)
            except (TypeError, ValueError):
                continue
            if max_hp > 0:
                max_hp_values.append(max_hp)

        entity_id = str(item.get("entity_id", item.get("id", ""))).strip()
        if not entity_id and not max_hp_values:
            continue

        boss_skill_burst_alert_specs.append(
            BossSkillBurstAlertSpec(
                name=str(item.get("name", entity_id or "Boss技能提醒")),
                entity_id=entity_id,
                max_hp_values=tuple(max_hp_values),
                skill_id=int(
                    item.get(
                        "skill_id",
                        item.get(
                            "trigger_skill_id",
                            DEFAULT_BOSS_DOUBLE_LASER_SKILL_ID,
                        ),
                    )
                ),
                burst_window_ms=max(
                    0,
                    int(
                        item.get(
                            "burst_window_ms",
                            DEFAULT_BOSS_DOUBLE_LASER_BURST_WINDOW_MS,
                        )
                    ),
                ),
                repeat_window_ms=max(
                    1,
                    int(
                        item.get(
                            "repeat_window_ms",
                            DEFAULT_BOSS_DOUBLE_LASER_REPEAT_WINDOW_MS,
                        )
                    ),
                ),
                dedupe_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "dedupe_seconds",
                            DEFAULT_BOSS_DOUBLE_LASER_DEDUPE_SECONDS,
                        )
                    ),
                ),
                sound=sound_path(
                    item.get("sound", DEFAULT_BOSS_DOUBLE_LASER_SOUND)
                ),
                message=str(
                    item.get("message", DEFAULT_BOSS_DOUBLE_LASER_MESSAGE)
                ),
                audio_volume=normalize_volume(
                    item.get("audio_volume", default_audio_volume)
                ),
            )
        )

    for item in data.get("boss_red_orb_alerts", []):
        if not item.get("enabled", True):
            continue

        raw_max_hp_values = item.get(
            "max_hp_values",
            item.get("max_hp", item.get("max_hp_value", [])),
        )
        if isinstance(raw_max_hp_values, (int, float, str)):
            raw_max_hp_values = [raw_max_hp_values]
        max_hp_values = parse_max_hp_values(raw_max_hp_values)
        if not max_hp_values:
            max_hp_values = list(DEFAULT_BOSS_RED_ORB_BOSS_MAX_HP_VALUES)

        raw_orb_race_ids = item.get(
            "orb_race_ids",
            item.get("race_ids", list(DEFAULT_BOSS_RED_ORB_RACE_IDS)),
        )
        if isinstance(raw_orb_race_ids, (int, str)):
            raw_orb_race_ids = [raw_orb_race_ids]
        orb_race_ids: list[int] = []
        for raw_race_id in raw_orb_race_ids or []:
            try:
                race_id = int(raw_race_id)
            except (TypeError, ValueError):
                continue
            if race_id > 0:
                orb_race_ids.append(race_id)
        if not orb_race_ids:
            orb_race_ids = list(DEFAULT_BOSS_RED_ORB_RACE_IDS)

        entity_id = str(item.get("entity_id", item.get("id", ""))).strip()
        if not entity_id and not max_hp_values:
            continue

        red_orb_sound = str(item.get("sound", DEFAULT_BOSS_RED_ORB_SOUND))
        if red_orb_sound == LEGACY_BOSS_RED_ORB_SOUND:
            red_orb_sound = DEFAULT_BOSS_RED_ORB_SOUND
        red_orb_message = str(item.get("message", DEFAULT_BOSS_RED_ORB_MESSAGE))
        if red_orb_message == "球要炸了":
            red_orb_message = DEFAULT_BOSS_RED_ORB_MESSAGE
        red_orb_safe_sound = str(
            item.get("safe_sound", DEFAULT_BOSS_RED_ORB_SAFE_SOUND)
        )
        red_orb_countdown_sounds = countdown_sound_paths(
            item.get("countdown_sounds"),
            DEFAULT_BOSS_RED_ORB_COUNTDOWN_SOUNDS,
        )

        boss_red_orb_alert_specs.append(
            BossRedOrbAlertSpec(
                name=str(item.get("name", entity_id or "布3红球爆炸")),
                entity_id=entity_id,
                max_hp_values=tuple(max_hp_values),
                current_hp_stat_id=int(
                    item.get("current_hp_stat_id", BOSS_HP_CURRENT_STAT_ID)
                ),
                max_hp_stat_id=int(item.get("max_hp_stat_id", BOSS_HP_MAX_STAT_ID)),
                orb_race_ids=tuple(orb_race_ids),
                countdown_op=str(
                    item.get("countdown_op", DEFAULT_BOSS_RED_ORB_COUNTDOWN_OP)
                ),
                countdown_marker=str(
                    item.get(
                        "countdown_marker",
                        DEFAULT_BOSS_RED_ORB_COUNTDOWN_MARKER,
                    )
                ),
                start_step=str(
                    item.get("start_step", DEFAULT_BOSS_RED_ORB_START_STEP)
                ),
                confirm_step=str(
                    item.get("confirm_step", DEFAULT_BOSS_RED_ORB_CONFIRM_STEP)
                ),
                pair_window_ms=max(
                    1,
                    int(
                        item.get(
                            "pair_window_ms",
                            DEFAULT_BOSS_RED_ORB_PAIR_WINDOW_MS,
                        )
                    ),
                ),
                explosion_delay_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "explosion_delay_seconds",
                            DEFAULT_BOSS_RED_ORB_EXPLOSION_DELAY_SECONDS,
                        )
                    ),
                ),
                high_hp_explosion_delay_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "high_hp_explosion_delay_seconds",
                            item.get(
                                "explosion_delay_seconds",
                                DEFAULT_BOSS_RED_ORB_HIGH_HP_EXPLOSION_DELAY_SECONDS,
                            ),
                        )
                    ),
                ),
                low_hp_explosion_delay_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "low_hp_explosion_delay_seconds",
                            DEFAULT_BOSS_RED_ORB_LOW_HP_EXPLOSION_DELAY_SECONDS,
                        )
                    ),
                ),
                lead_seconds=max(
                    0.0,
                    float(item.get("lead_seconds", DEFAULT_BOSS_RED_ORB_LEAD_SECONDS)),
                ),
                contact_check_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "contact_check_seconds",
                            DEFAULT_BOSS_RED_ORB_CONTACT_CHECK_SECONDS,
                        )
                    ),
                ),
                safe_min_contact_ticks=max(
                    0,
                    int(
                        item.get(
                            "safe_min_contact_ticks",
                            DEFAULT_BOSS_RED_ORB_SAFE_MIN_CONTACT_TICKS,
                        )
                    ),
                ),
                safe_last_contact_before_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "safe_last_contact_before_seconds",
                            DEFAULT_BOSS_RED_ORB_SAFE_LAST_CONTACT_BEFORE_SECONDS,
                        )
                    ),
                ),
                contact_group_ms=max(
                    0,
                    int(
                        item.get(
                            "contact_group_ms",
                            DEFAULT_BOSS_RED_ORB_CONTACT_GROUP_MS,
                        )
                    ),
                ),
                hp_split_percent=max(
                    0.0,
                    min(
                        100.0,
                        float(
                            item.get(
                                "hp_split_percent",
                                DEFAULT_BOSS_RED_ORB_HP_SPLIT_PERCENT,
                            )
                        ),
                    ),
                ),
                high_hp_required_contact_ticks=max(
                    1,
                    int(
                        item.get(
                            "high_hp_required_contact_ticks",
                            DEFAULT_BOSS_RED_ORB_HIGH_HP_REQUIRED_CONTACT_TICKS,
                        )
                    ),
                ),
                high_hp_early_check_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "high_hp_early_check_seconds",
                            DEFAULT_BOSS_RED_ORB_HIGH_HP_EARLY_CHECK_SECONDS,
                        )
                    ),
                ),
                high_hp_early_max_contact_ticks=max(
                    0,
                    int(
                        item.get(
                            "high_hp_early_max_contact_ticks",
                            DEFAULT_BOSS_RED_ORB_HIGH_HP_EARLY_MAX_CONTACT_TICKS,
                        )
                    ),
                ),
                high_hp_final_check_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "high_hp_final_check_seconds",
                            DEFAULT_BOSS_RED_ORB_HIGH_HP_FINAL_CHECK_SECONDS,
                        )
                    ),
                ),
                low_hp_required_contact_ticks=max(
                    1,
                    int(
                        item.get(
                            "low_hp_required_contact_ticks",
                            DEFAULT_BOSS_RED_ORB_LOW_HP_REQUIRED_CONTACT_TICKS,
                        )
                    ),
                ),
                low_hp_early_check_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "low_hp_early_check_seconds",
                            DEFAULT_BOSS_RED_ORB_LOW_HP_EARLY_CHECK_SECONDS,
                        )
                    ),
                ),
                low_hp_early_max_contact_ticks=max(
                    0,
                    int(
                        item.get(
                            "low_hp_early_max_contact_ticks",
                            DEFAULT_BOSS_RED_ORB_LOW_HP_EARLY_MAX_CONTACT_TICKS,
                        )
                    ),
                ),
                low_hp_final_check_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "low_hp_final_check_seconds",
                            DEFAULT_BOSS_RED_ORB_LOW_HP_FINAL_CHECK_SECONDS,
                        )
                    ),
                ),
                late_confirm_op=str(
                    item.get("late_confirm_op", DEFAULT_BOSS_RED_ORB_LATE_CONFIRM_OP)
                ),
                late_confirm_start_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "late_confirm_start_seconds",
                            DEFAULT_BOSS_RED_ORB_LATE_CONFIRM_START_SECONDS,
                        )
                    ),
                ),
                late_confirm_end_seconds=max(
                    0.0,
                    float(
                        item.get(
                            "late_confirm_end_seconds",
                            DEFAULT_BOSS_RED_ORB_LATE_CONFIRM_END_SECONDS,
                        )
                    ),
                ),
                stale_seconds=max(
                    1.0,
                    float(item.get("stale_seconds", DEFAULT_BOSS_RED_ORB_STALE_SECONDS)),
                ),
                sound=sound_path(red_orb_sound),
                message=red_orb_message,
                safe_sound=sound_path(red_orb_safe_sound),
                countdown_sounds=red_orb_countdown_sounds,
                audio_volume=normalize_volume(
                    item.get("audio_volume", default_audio_volume)
                ),
            )
        )

    for item in data.get("boss_laser_alerts", []):
        if not item.get("enabled", True):
            continue

        raw_max_hp_values = item.get(
            "max_hp_values",
            item.get("max_hp", item.get("max_hp_value", [])),
        )
        if isinstance(raw_max_hp_values, (int, float, str)):
            raw_max_hp_values = [raw_max_hp_values]
        max_hp_values = parse_max_hp_values(raw_max_hp_values)
        if not max_hp_values:
            max_hp_values = list(DEFAULT_BOSS_LASER_BOSS_MAX_HP_VALUES)

        raw_stardust_race_ids = item.get(
            "stardust_race_ids",
            item.get("race_ids", list(DEFAULT_BOSS_LASER_STARDUST_RACE_IDS)),
        )
        if isinstance(raw_stardust_race_ids, (int, str)):
            raw_stardust_race_ids = [raw_stardust_race_ids]
        stardust_race_ids: list[int] = []
        for raw_race_id in raw_stardust_race_ids or []:
            try:
                race_id = int(raw_race_id)
            except (TypeError, ValueError):
                continue
            if race_id > 0:
                stardust_race_ids.append(race_id)
        if not stardust_race_ids:
            stardust_race_ids = list(DEFAULT_BOSS_LASER_STARDUST_RACE_IDS)

        entity_id = str(item.get("entity_id", item.get("id", ""))).strip()
        if not entity_id and not max_hp_values:
            continue

        boss_laser_alert_specs.append(
            BossLaserAlertSpec(
                name=str(item.get("name", entity_id or DEFAULT_BOSS_LASER_WARNING_NAME)),
                entity_id=entity_id,
                max_hp_values=tuple(max_hp_values),
                current_hp_stat_id=int(
                    item.get("current_hp_stat_id", BOSS_HP_CURRENT_STAT_ID)
                ),
                max_hp_stat_id=int(item.get("max_hp_stat_id", BOSS_HP_MAX_STAT_ID)),
                stardust_race_ids=tuple(stardust_race_ids),
                cast_op=str(item.get("cast_op", DEFAULT_BOSS_LASER_CAST_OP)),
                skill_id=int(item.get("skill_id", DEFAULT_BOSS_LASER_SKILL_ID)),
                cast_seconds=max(
                    0.0,
                    float(item.get("cast_seconds", DEFAULT_BOSS_LASER_CAST_SECONDS)),
                ),
                cluster_window_ms=max(
                    0,
                    int(
                        item.get(
                            "cluster_window_ms",
                            DEFAULT_BOSS_LASER_CLUSTER_WINDOW_MS,
                        )
                    ),
                ),
                stale_seconds=max(
                    1.0,
                    float(item.get("stale_seconds", DEFAULT_BOSS_LASER_STALE_SECONDS)),
                ),
                sound=sound_path(item.get("sound", DEFAULT_BOSS_LASER_WARNING_SOUND)),
                message=str(item.get("message", DEFAULT_BOSS_LASER_WARNING_MESSAGE)),
                countdown_sounds=countdown_sound_paths(
                    item.get("countdown_sounds"),
                    DEFAULT_BOSS_LASER_COUNTDOWN_SOUNDS,
                ),
                audio_volume=normalize_volume(
                    item.get("audio_volume", default_audio_volume)
                ),
            )
        )

    key_enemy_data = data.get("key_enemy_debuff_alert")
    if isinstance(key_enemy_data, dict):
        complete_enabled = bool(
            key_enemy_data.get(
                "complete_enabled",
                key_enemy_data.get("enabled", False),
            )
        )
        expiry_enabled = bool(key_enemy_data.get("expiry_enabled", True))
        raw_max_hp_values = key_enemy_data.get(
            "max_hp_values",
            DEFAULT_KEY_ENEMY_DEBUFF_BOSS_MAX_HP_VALUES,
        )
        max_hp_values = parse_max_hp_values(raw_max_hp_values)
        if not max_hp_values:
            max_hp_values = list(DEFAULT_KEY_ENEMY_DEBUFF_BOSS_MAX_HP_VALUES)
        max_hp_value_keys = {int(round(value)) for value in max_hp_values}
        for default_max_hp in DEFAULT_KEY_ENEMY_DEBUFF_BOSS_MAX_HP_VALUES:
            default_key = int(round(default_max_hp))
            if default_key not in max_hp_value_keys:
                max_hp_values.append(float(default_max_hp))
                max_hp_value_keys.add(default_key)

        watched_debuffs: list[WatchedKeyEnemyDebuffSpec] = []
        raw_watched_debuffs = key_enemy_data.get(
            "watched_debuffs",
            list(DEFAULT_KEY_ENEMY_WATCHED_DEBUFFS),
        )
        if isinstance(raw_watched_debuffs, dict):
            raw_watched_debuffs = [raw_watched_debuffs]
        for watched_data in raw_watched_debuffs or []:
            if not isinstance(watched_data, dict):
                continue
            raw_ccids = watched_data.get("ccids", watched_data.get("ccid", []))
            if isinstance(raw_ccids, (int, str)):
                raw_ccids = [raw_ccids]
            ccids: list[int] = []
            for raw_ccid in raw_ccids or []:
                try:
                    ccid = int(raw_ccid)
                except (TypeError, ValueError):
                    continue
                if ccid > 0:
                    ccids.append(ccid)
            if not ccids:
                continue
            enabled = bool(watched_data.get("enabled", True))
            remaining_enabled = bool(watched_data.get("remaining_enabled", True))
            ended_enabled = bool(watched_data.get("ended_enabled", True))
            if not enabled or not (remaining_enabled or ended_enabled):
                continue
            name = str(
                watched_data.get("name", DEFAULT_KEY_ENEMY_GUNNER_EYE_NAME)
            ).strip()
            if not name:
                name = DEFAULT_KEY_ENEMY_GUNNER_EYE_NAME
            watched_debuffs.append(
                WatchedKeyEnemyDebuffSpec(
                    name=name,
                    ccids=tuple(sorted(set(ccids))),
                    enabled=enabled,
                    remaining_enabled=remaining_enabled,
                    remaining_seconds=max(
                        0,
                        int(
                            watched_data.get(
                                "remaining_seconds",
                                DEFAULT_KEY_ENEMY_GUNNER_EYE_SECONDS,
                            )
                        ),
                    ),
                    remaining_sound=sound_path(
                        watched_data.get(
                            "remaining_sound",
                            DEFAULT_KEY_ENEMY_GUNNER_EYE_REMAINING_SOUND,
                        )
                    ),
                    remaining_message=str(
                        watched_data.get(
                            "remaining_message",
                            DEFAULT_KEY_ENEMY_GUNNER_EYE_REMAINING_MESSAGE,
                        )
                    ),
                    ended_enabled=ended_enabled,
                    ended_sound=sound_path(
                        watched_data.get(
                            "ended_sound",
                            DEFAULT_KEY_ENEMY_GUNNER_EYE_ENDED_SOUND,
                        )
                    ),
                    ended_message=str(
                        watched_data.get(
                            "ended_message",
                            DEFAULT_KEY_ENEMY_GUNNER_EYE_ENDED_MESSAGE,
                        )
                    ),
                )
            )

        if complete_enabled or expiry_enabled or watched_debuffs:
            key_enemy_debuff_alert_spec = KeyEnemyDebuffAlertSpec(
                complete_enabled=complete_enabled,
                expiry_enabled=expiry_enabled,
                max_hp_values=tuple(max_hp_values),
                current_hp_stat_id=int(
                    key_enemy_data.get("current_hp_stat_id", BOSS_HP_CURRENT_STAT_ID)
                ),
                max_hp_stat_id=int(
                    key_enemy_data.get("max_hp_stat_id", BOSS_HP_MAX_STAT_ID)
                ),
                complete_sound=sound_path(
                    key_enemy_data.get(
                        "complete_sound",
                        DEFAULT_KEY_ENEMY_DEBUFF_COMPLETE_SOUND,
                    )
                ),
                complete_message=str(
                    key_enemy_data.get(
                        "complete_message",
                        DEFAULT_KEY_ENEMY_DEBUFF_COMPLETE_MESSAGE,
                    )
                ),
                expiry_sound=sound_path(
                    key_enemy_data.get(
                        "expiry_sound",
                        DEFAULT_KEY_ENEMY_DEBUFF_EXPIRY_SOUND,
                    )
                ),
                expiry_message=str(
                    key_enemy_data.get(
                        "expiry_message",
                        DEFAULT_KEY_ENEMY_DEBUFF_EXPIRY_MESSAGE,
                    )
                ),
                expiry_seconds=max(
                    0,
                    int(
                        key_enemy_data.get(
                            "expiry_seconds",
                            DEFAULT_KEY_ENEMY_DEBUFF_EXPIRY_SECONDS,
                        )
                    ),
                ),
                physical_break_min=float(
                    key_enemy_data.get(
                        "physical_break_min",
                        DEFAULT_KEY_ENEMY_DEBUFF_PHYSICAL_BREAK_MIN,
                    )
                ),
                magic_break_min=float(
                    key_enemy_data.get(
                        "magic_break_min",
                        DEFAULT_KEY_ENEMY_DEBUFF_MAGIC_BREAK_MIN,
                    )
                ),
                damage_bonus_min=float(
                    key_enemy_data.get(
                        "damage_bonus_min",
                        DEFAULT_KEY_ENEMY_DEBUFF_DAMAGE_BONUS_MIN,
                    )
                ),
                rabbit_stacks_min=max(
                    1,
                    int(
                        key_enemy_data.get(
                            "rabbit_stacks_min",
                            DEFAULT_KEY_ENEMY_DEBUFF_RABBIT_STACKS_MIN,
                        )
                    ),
                ),
                watched_debuffs=tuple(watched_debuffs),
                audio_volume=normalize_volume(
                    key_enemy_data.get("audio_volume", default_audio_volume)
                ),
            )

    return LoadedSpecs(
        buffs=buff_specs,
        progresses=progress_specs,
        stat_drop_effects=stat_drop_effect_specs,
        boss_hp_alerts=boss_hp_alert_specs,
        boss_skill_burst_alerts=boss_skill_burst_alert_specs,
        boss_red_orb_alerts=boss_red_orb_alert_specs,
        boss_laser_alerts=boss_laser_alert_specs,
        key_enemy_debuff_alert=key_enemy_debuff_alert_spec,
        magic_shield_missing=magic_shield_missing_spec,
        death_clear_suppression_window_ms=death_clear_suppression_window_ms,
        death_clear_suppression_min_buffs=death_clear_suppression_min_buffs,
        death_signal_event_ids=death_signal_event_ids,
        death_signal_suppression_window_ms=death_signal_suppression_window_ms,
        music_strong_reminder_enabled=music_strong_reminder_enabled,
        music_strong_reminder_repeat_seconds=music_strong_reminder_repeat_seconds,
        music_strong_reminder_prefix_sound=music_strong_reminder_prefix_sound,
    )


def load_specs(config_path: str | Path) -> list[BuffSpec]:
    return load_all_specs(config_path).buffs


class AlertEngine:
    def __init__(
        self,
        specs: Iterable[BuffSpec],
        *,
        progress_specs: Iterable[ProgressSpec] = (),
        stat_drop_effect_specs: Iterable[StatDropEffectSpec] = (),
        boss_hp_alert_specs: Iterable[BossHpAlertSpec] = (),
        boss_skill_burst_alert_specs: Iterable[BossSkillBurstAlertSpec] = (),
        boss_red_orb_alert_specs: Iterable[BossRedOrbAlertSpec] = (),
        boss_laser_alert_specs: Iterable[BossLaserAlertSpec] = (),
        key_enemy_debuff_alert: KeyEnemyDebuffAlertSpec | None = None,
        magic_shield_missing: MissingMagicShieldSpec | None = None,
        tz_offset_hours: int = DEFAULT_TZ_OFFSET_HOURS,
        death_clear_suppression_window_ms: int = DEFAULT_DEATH_CLEAR_SUPPRESSION_WINDOW_MS,
        death_clear_suppression_min_buffs: int = DEFAULT_DEATH_CLEAR_SUPPRESSION_MIN_BUFFS,
        death_signal_event_ids: Iterable[int] = DEFAULT_DEATH_SIGNAL_EVENT_IDS,
        death_signal_suppression_window_ms: int = DEFAULT_DEATH_SIGNAL_SUPPRESSION_WINDOW_MS,
        music_strong_reminder_enabled: bool = DEFAULT_MUSIC_STRONG_REMINDER_ENABLED,
        music_strong_reminder_repeat_seconds: float = (
            DEFAULT_MUSIC_STRONG_REMINDER_REPEAT_SECONDS
        ),
        music_strong_reminder_prefix_sound: str = DEFAULT_MUSIC_STRONG_REMINDER_PREFIX_SOUND,
    ) -> None:
        self.tz_offset_hours = tz_offset_hours
        self.death_clear_suppression_window_ms = max(
            0, int(death_clear_suppression_window_ms)
        )
        self.death_clear_suppression_min_buffs = max(
            0, int(death_clear_suppression_min_buffs)
        )
        self.death_signal_event_ids = {int(event_id) for event_id in death_signal_event_ids}
        self.death_signal_suppression_window_ms = max(
            0, int(death_signal_suppression_window_ms)
        )
        self.music_strong_reminder_enabled = bool(music_strong_reminder_enabled)
        self.music_strong_reminder_repeat_seconds = max(
            0.5, float(music_strong_reminder_repeat_seconds)
        )
        self.music_strong_reminder_prefix_sound = str(
            music_strong_reminder_prefix_sound
            or DEFAULT_MUSIC_STRONG_REMINDER_PREFIX_SOUND
        )
        self.recent_music_remove_with_tuan_at_ms: dict[int, int] = {}
        self.dynamic_sbt_adjust_seconds: float | None = None
        self._dynamic_sbt_adjust_samples: list[float] = []
        self._dynamic_sbt_adjust_sample_keys: list[tuple[int, int]] = []
        self._dynamic_sbt_adjust_sample_key_set: set[tuple[int, int]] = set()
        self.death_clear_suppressed_until_ms = -1
        self.states: dict[int, BuffState] = {}
        self.progress_states: dict[int, ProgressState] = {}
        self.stat_drop_effect_states: list[StatDropEffectState] = []
        self.boss_hp_alert_states: dict[str, BossHpAlertState] = {}
        self.boss_hp_alert_states_by_max_hp: dict[int, BossHpAlertState] = {}
        self.boss_skill_burst_alert_states: dict[str, BossSkillBurstAlertState] = {}
        self.boss_skill_burst_alert_states_by_max_hp: dict[
            int, BossSkillBurstAlertState
        ] = {}
        self.boss_red_orb_alert_states: dict[str, BossRedOrbAlertState] = {}
        self.boss_red_orb_alert_states_by_max_hp: dict[int, BossRedOrbAlertState] = {}
        self.boss_laser_alert_states: dict[str, BossLaserAlertState] = {}
        self.boss_laser_alert_states_by_max_hp: dict[int, BossLaserAlertState] = {}
        self.boss_laser_stardust_to_state: dict[str, BossLaserAlertState] = {}
        self.boss_laser_pending_stardust_by_owner: dict[str, set[str]] = {}
        self.boss_laser_pending_stardust_race_by_entity_id: dict[str, int] = {}
        self.key_enemy_debuff_alert = key_enemy_debuff_alert
        self.key_enemy_debuff_entity_states: dict[str, KeyEnemyDebuffEntityState] = {}
        self.key_enemy_watched_debuffs_by_ccid: dict[
            int, WatchedKeyEnemyDebuffSpec
        ] = {}
        self.key_enemy_debuff_max_hp_keys: set[int] = (
            {
                self._boss_hp_fingerprint_key(max_hp)
                for max_hp in key_enemy_debuff_alert.max_hp_values
            }
            if key_enemy_debuff_alert is not None
            else set()
        )
        if key_enemy_debuff_alert is not None:
            for watched_spec in key_enemy_debuff_alert.watched_debuffs:
                if not watched_spec.enabled:
                    continue
                for ccid in watched_spec.ccids:
                    self.key_enemy_watched_debuffs_by_ccid[ccid] = watched_spec
        self.magic_shield_missing = magic_shield_missing
        self.battle_timer_active = False
        self.battle_timer_started_at_ms: int | None = None
        self.magic_shield_missing_next_due_ms: int | None = None
        self.magic_shield_state_observed = False
        self.self_entity_id: str | None = None
        self.self_player_dead = False
        self.last_self_hp: float | None = None
        self.ccid_to_primary: dict[int, int] = {}
        self.skill_id_to_primary: dict[int, int] = {}

        for spec in specs:
            self.states[spec.ccid] = BuffState(spec=spec)
            self.ccid_to_primary[spec.ccid] = spec.ccid
            if spec.skill_id is not None:
                self.skill_id_to_primary[spec.skill_id] = spec.ccid
            for linked_ccid in spec.linked_ccids:
                self.ccid_to_primary[linked_ccid] = spec.ccid

        for spec in progress_specs:
            self.progress_states[spec.stat_id] = ProgressState(spec=spec)

        for spec in stat_drop_effect_specs:
            self.stat_drop_effect_states.append(StatDropEffectState(spec=spec))

        for spec in boss_hp_alert_specs:
            state = BossHpAlertState(spec=spec)
            if spec.entity_id:
                self.boss_hp_alert_states[spec.entity_id] = state
            for max_hp in spec.max_hp_values:
                self.boss_hp_alert_states_by_max_hp[
                    self._boss_hp_fingerprint_key(max_hp)
                ] = state

        for spec in boss_skill_burst_alert_specs:
            state = BossSkillBurstAlertState(spec=spec)
            if spec.entity_id:
                state.tracked_entity_id = spec.entity_id
                state.active = True
                self.boss_skill_burst_alert_states[spec.entity_id] = state
            for max_hp in spec.max_hp_values:
                self.boss_skill_burst_alert_states_by_max_hp[
                    self._boss_hp_fingerprint_key(max_hp)
                ] = state

        for spec in boss_red_orb_alert_specs:
            state = BossRedOrbAlertState(spec=spec)
            if spec.entity_id:
                state.tracked_entity_id = spec.entity_id
                state.active = True
                self.boss_red_orb_alert_states[spec.entity_id] = state
            for max_hp in spec.max_hp_values:
                self.boss_red_orb_alert_states_by_max_hp[
                    self._boss_hp_fingerprint_key(max_hp)
                ] = state

        for spec in boss_laser_alert_specs:
            state = BossLaserAlertState(spec=spec)
            if spec.entity_id:
                state.tracked_entity_id = spec.entity_id
                state.active = True
                self.boss_laser_alert_states[spec.entity_id] = state
            for max_hp in spec.max_hp_values:
                self.boss_laser_alert_states_by_max_hp[
                    self._boss_hp_fingerprint_key(max_hp)
                ] = state

        if (
            self.magic_shield_missing is not None
            and self.magic_shield_missing.ccid not in self.states
        ):
            spec = BuffSpec(
                name=MAGIC_SHIELD_NAME,
                ccid=self.magic_shield_missing.ccid,
                alerts=[],
                ended_alert=False,
            )
            self.states[spec.ccid] = BuffState(spec=spec)
            self.ccid_to_primary[spec.ccid] = spec.ccid

    def set_self_entity_id(self, self_id: str | None) -> None:
        normalized = None if self_id is None else str(self_id)
        if self.self_entity_id == normalized:
            return
        self._reset_self_filtered_buff_states()
        self.self_entity_id = normalized
        self.self_player_dead = False
        self.last_self_hp = None
        self._clear_magic_shield_missing_schedule()

    def _reset_self_filtered_buff_states(self) -> None:
        for primary, state in list(self.states.items()):
            if not state.spec.self_filter:
                continue
            self.states[primary] = BuffState(spec=state.spec)

    def process_event(self, event: dict[str, Any]) -> list[FiredAlert]:
        alerts: list[FiredAlert] = []
        if self.is_death_signal_event(event):
            self._apply_death_signal(event, int(event.get("At", 0)))
            return alerts

        if self.is_battle_timer_event(event):
            self._process_battle_timer_event(event)
            return alerts

        if event.get("EventId") == 17:
            self._process_self_stats(event)
            alerts.extend(self._process_stats(event))
            alerts.extend(self._process_boss_hp_stats(event))
            self._process_boss_skill_burst_stats(event)
            self._process_boss_red_orb_stats(event)
            self._process_boss_laser_stats(event)
            self._process_key_enemy_debuff_stats(event)
            alerts.extend(self._process_stat_drop_effect_stats(event))
            return alerts

        self._process_boss_hp_entity_lifecycle(event)
        self._process_boss_skill_burst_entity_lifecycle(event)
        self._process_boss_red_orb_entity_lifecycle(event)
        self._process_boss_laser_entity_lifecycle(event)
        self._process_key_enemy_debuff_entity_lifecycle(event)
        self._process_stat_drop_effect_entity_lifecycle(event)
        alerts.extend(self._process_stat_drop_effect_trigger(event))
        alerts.extend(self._process_boss_skill_burst_event(event))
        alerts.extend(self._process_boss_red_orb_event(event))
        alerts.extend(self._process_boss_laser_event(event))
        alerts.extend(self._process_key_enemy_debuff_event(event))

        ccid = event.get("CCId")
        if ccid is None:
            return alerts

        primary = self.ccid_to_primary.get(int(ccid))
        if primary is None:
            return alerts

        state = self.states[primary]
        event_id = event.get("EventId")
        at_ms = int(event.get("At", 0))

        if not self._event_allowed_for_buff_spec(state.spec, event):
            return alerts

        if event_id == 4:
            alerts.extend(self._apply_or_refresh(state, event, at_ms))
            return alerts
        if event_id == 5:
            alerts.extend(self._remove(state, int(ccid), at_ms))
            return alerts
        return alerts

    def effective_sbt_adjust_seconds(self, spec: BuffSpec) -> float:
        if spec.use_dynamic_sbt_adjust and self.dynamic_sbt_adjust_seconds is not None:
            return self.dynamic_sbt_adjust_seconds
        return spec.sbt_adjust_seconds

    def is_progress_event(self, event: dict[str, Any]) -> bool:
        if event.get("EventId") != 17 or not self.progress_states:
            return False
        for item in event.get("Stats") or []:
            stat_id = item.get("StatId")
            if stat_id is not None and int(stat_id) in self.progress_states:
                return True
        return False

    def is_stat_drop_effect_event(self, event: dict[str, Any]) -> bool:
        if not self.stat_drop_effect_states:
            return False
        if self._is_tracked_stat_drop_effect_entity_event(event):
            return True
        if event.get("EventId") == 17:
            return True
        return any(
            self._event_matches_trigger(event, state.spec.trigger)
            or (
                state.spec.start_trigger is not None
                and self._event_matches_trigger(event, state.spec.start_trigger)
            )
            for state in self.stat_drop_effect_states
        )

    def is_boss_hp_event(self, event: dict[str, Any]) -> bool:
        if not self.boss_hp_alert_states and not self.boss_hp_alert_states_by_max_hp:
            return False
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if event.get("EventId") == ENTITY_REMOVED_EVENT_ID:
            return bool(event_entity_id and event_entity_id in self.boss_hp_alert_states)
        if event.get("EventId") != 17:
            return False
        if event_entity_id and event_entity_id in self.boss_hp_alert_states:
            return True
        current_values = _event_stat_values(event)
        max_hp = current_values.get(BOSS_HP_MAX_STAT_ID)
        return self._boss_hp_state_for_max_hp(max_hp) is not None

    def is_key_enemy_debuff_event(self, event: dict[str, Any]) -> bool:
        spec = self.key_enemy_debuff_alert
        if spec is None:
            return False

        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        event_id = event.get("EventId")
        if event_id == ENTITY_REMOVED_EVENT_ID:
            return bool(
                event_entity_id
                and event_entity_id in self.key_enemy_debuff_entity_states
            )
        if event_id == 17:
            if event_entity_id and event_entity_id in self.key_enemy_debuff_entity_states:
                return True
            current_values = _event_stat_values(event)
            max_hp = current_values.get(spec.max_hp_stat_id)
            return self._boss_hp_fingerprint_key(max_hp) in self.key_enemy_debuff_max_hp_keys
        if event_id not in (4, 5):
            return False
        try:
            ccid = int(event.get("CCId"))
        except (TypeError, ValueError):
            return False
        if (
            ccid not in KEY_ENEMY_DEBUFF_CCID_TO_REQUIREMENT
            and ccid not in self.key_enemy_watched_debuffs_by_ccid
        ):
            return False
        return bool(
            event_entity_id
            and event_entity_id in self.key_enemy_debuff_entity_states
        )

    def is_boss_red_orb_event(self, event: dict[str, Any]) -> bool:
        if (
            not self.boss_red_orb_alert_states
            and not self.boss_red_orb_alert_states_by_max_hp
        ):
            return False

        event_id = event.get("EventId")
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        specs = [state.spec for state in self._unique_boss_red_orb_states()]

        if event_id == 17:
            if event_entity_id and event_entity_id in self.boss_red_orb_alert_states:
                return True
            current_values = _event_stat_values(event)
            max_hp = current_values.get(BOSS_HP_MAX_STAT_ID)
            return self._boss_red_orb_state_for_max_hp(max_hp) is not None

        if event_id == 0:
            op = str(event.get("Op", "")).lower()
            messages = event.get("Msg") or []
            marker = None
            if messages and isinstance(messages[0], dict):
                marker = str(messages[0].get("V"))
            return any(
                op == spec.countdown_op.lower()
                and marker == spec.countdown_marker
                for spec in specs
            )

        if event_id == 1:
            try:
                race_id = int(event.get("RaceId"))
            except (TypeError, ValueError):
                return False
            return any(race_id in spec.orb_race_ids for spec in specs)

        if event_id == 3:
            try:
                skill_id = int(event.get("SkillId"))
            except (TypeError, ValueError):
                return False
            return skill_id == DEFAULT_BOSS_RED_ORB_DAMAGE_SKILL_ID

        if event_id in (ENTITY_REMOVED_EVENT_ID, 15):
            if event_entity_id and event_entity_id in self.boss_red_orb_alert_states:
                return True
            return any(
                event_entity_id and event_entity_id in state.orb_entity_to_pending
                for state in self._unique_boss_red_orb_states()
            )

        return False

    def is_boss_laser_event(self, event: dict[str, Any]) -> bool:
        if (
            not self.boss_laser_alert_states
            and not self.boss_laser_alert_states_by_max_hp
        ):
            return False

        event_id = event.get("EventId")
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if event_entity_id and event_entity_id in self.boss_laser_alert_states:
            return True
        if event_entity_id and event_entity_id in self.boss_laser_stardust_to_state:
            return True

        if event_id == 17:
            current_values = _event_stat_values(event)
            max_hp = current_values.get(BOSS_HP_MAX_STAT_ID)
            return self._boss_laser_state_for_max_hp(max_hp) is not None

        if event_id == 1:
            owner_id = "" if event.get("OwnerId") is None else str(event.get("OwnerId"))
            state = self.boss_laser_alert_states.get(owner_id)
            try:
                race_id = int(event.get("RaceId"))
            except (TypeError, ValueError):
                return False
            if state is not None and state.tracked_entity_id == owner_id:
                return race_id in set(state.spec.stardust_race_ids)
            return any(
                race_id in state.spec.stardust_race_ids
                for state in self._unique_boss_laser_states()
            )

        return False

    def is_unfiltered_stat_drop_effect_event(self, event: dict[str, Any]) -> bool:
        if not self.stat_drop_effect_states:
            return False

        if self._is_tracked_stat_drop_effect_entity_event(event):
            return True

        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if event.get("EventId") == 17:
            current_values = _event_stat_values(event)
            for state in self.stat_drop_effect_states:
                if state.spec.self_filter:
                    continue
                if (
                    state.tracked_entity_id is not None
                    and event_entity_id == state.tracked_entity_id
                ):
                    return True
                if self._stats_match(current_values, state.spec.start_stat_matches):
                    return True
            return False

        return any(
            not state.spec.self_filter
            and (
                self._event_matches_trigger(event, state.spec.trigger)
                or (
                    state.spec.start_trigger is not None
                    and self._event_matches_trigger(event, state.spec.start_trigger)
                )
            )
            for state in self.stat_drop_effect_states
        )

    def is_death_signal_event(self, event: dict[str, Any]) -> bool:
        event_id = event.get("EventId")
        if event_id is None:
            return False
        return int(event_id) in self.death_signal_event_ids

    def is_battle_timer_event(self, event: dict[str, Any]) -> bool:
        return self._battle_timer_event_kind(event) is not None

    def advance_time(self, at_ms: int) -> list[FiredAlert]:
        alerts: list[FiredAlert] = []
        for state in self.states.values():
            if (
                state.pending_dynamic_sbt_learn_at_ms is not None
                and at_ms >= state.pending_dynamic_sbt_learn_at_ms
            ):
                self._fire_pending_dynamic_sbt_adjust(state, at_ms)

            if (
                not state.active
                and state.ended_pending_at_ms is not None
                and at_ms >= state.ended_pending_at_ms
            ):
                alerts.extend(self._fire_ended_alert(state))

            if (
                not state.active
                and state.clear_pending_at_ms is not None
                and at_ms >= state.clear_pending_at_ms
            ):
                alerts.extend(self._fire_stack_clear_alert(state))

            if (
                not state.active
                and state.cooldown_pending_at_ms is not None
                and at_ms >= state.cooldown_pending_at_ms
            ):
                alerts.extend(self._fire_cooldown_alert(state))

            alerts.extend(self._advance_music_strong_reminder(state, at_ms))

            if not state.active or state.end_ms is None:
                continue
            if state.spec.ended_on_remove_only and at_ms >= state.end_ms:
                state.active = False
                state.active_ccid = None
                state.end_ms = None
                state.fired_thresholds.clear()
                continue
            remaining_exact = (state.end_ms - at_ms) / 1000
            remaining = max(0, math.ceil(remaining_exact))
            for rule in state.spec.alerts:
                if rule.remaining_seconds in state.fired_thresholds:
                    continue
                if remaining_exact <= rule.remaining_seconds:
                    state.fired_thresholds.add(rule.remaining_seconds)
                    if self._should_suppress_remaining_alert(state, at_ms, remaining):
                        continue
                    sound = rule.sound
                    if self._music_strong_reminder_should_apply(state, at_ms):
                        sound = self._music_strong_reminder_sound(rule.sound)
                        self._schedule_music_strong_reminder(state, rule, at_ms)
                    alerts.append(
                        FiredAlert(
                            at_ms=at_ms,
                            kind="threshold",
                            name=state.spec.name,
                            ccid=state.spec.ccid,
                            remaining_seconds=max(0, remaining),
                            message=format_message(
                                rule.message,
                                state.spec,
                                remaining=max(0, remaining),
                                stacks=state.stacks,
                            ),
                            sound=sound,
                            volume=state.spec.audio_volume,
                        )
                    )
            if (
                state.spec.ended_alert
                and not state.spec.ended_on_remove_only
                and not state.ended_fired
                and at_ms >= state.end_ms - int(state.spec.sbt_ended_lead_seconds * 1000)
            ):
                alerts.extend(self._fire_ended_alert(state, at_ms=at_ms))
            if at_ms >= state.end_ms:
                ended_at_ms = state.end_ms
                state.active = False
                state.active_ccid = None
                state.end_ms = None
                state.fired_thresholds.clear()
                alerts.extend(
                    self._stack_clear_alert(state, at_ms, cleared_at_ms=ended_at_ms)
                )
                alerts.extend(self._ended_alert(state, at_ms, ended_at_ms=ended_at_ms))
                alerts.extend(
                    self._cooldown_alert(state, at_ms, ended_at_ms=ended_at_ms)
                )
        for state in self.stat_drop_effect_states:
            alerts.extend(self._advance_stat_drop_effect_time(state, at_ms))
        alerts.extend(self._advance_boss_red_orb_time(at_ms))
        alerts.extend(self._advance_key_enemy_debuff_time(at_ms))
        alerts.extend(self._advance_magic_shield_missing(at_ms))
        return alerts

    def drain_scheduled_alerts(self) -> list[FiredAlert]:
        pending_times: set[int] = set()
        for state in self.states.values():
            if state.pending_dynamic_sbt_learn_at_ms is not None:
                pending_times.add(state.pending_dynamic_sbt_learn_at_ms)
            if state.clear_pending_at_ms is not None:
                pending_times.add(state.clear_pending_at_ms)
            if state.cooldown_pending_at_ms is not None:
                pending_times.add(state.cooldown_pending_at_ms)
            if state.ended_pending_at_ms is not None:
                pending_times.add(state.ended_pending_at_ms)
            if state.music_strong_reminder_next_at_ms is not None:
                pending_times.add(state.music_strong_reminder_next_at_ms)
            if not state.active or state.end_ms is None:
                continue
            for rule in state.spec.alerts:
                if rule.remaining_seconds not in state.fired_thresholds:
                    pending_times.add(state.end_ms - rule.remaining_seconds * 1000)
            if state.spec.ended_on_remove_only:
                pending_times.add(state.end_ms)
                continue
            if state.spec.ended_alert and not state.ended_fired:
                lead_ms = int(state.spec.sbt_ended_lead_seconds * 1000)
                pending_times.add(state.end_ms - lead_ms)
            if state.spec.cooldown_alert and not state.cooldown_fired:
                cooldown_ms = int(state.spec.cooldown_delay_seconds * 1000)
                pending_times.add(state.end_ms + cooldown_ms)
            if (
                state.spec.clear_after_stack_alert
                and state.stack_alert_fired
                and not state.clear_alert_fired
            ):
                grace_ms = int(state.spec.clear_grace_seconds * 1000)
                pending_times.add(state.end_ms + grace_ms)
        for state in self.stat_drop_effect_states:
            if not state.active or state.end_ms is None:
                continue
            for rule in state.spec.alerts:
                if rule.remaining_seconds not in state.fired_thresholds:
                    pending_times.add(state.end_ms - rule.remaining_seconds * 1000)
        seen_red_orb_states: set[int] = set()
        for state in list(self.boss_red_orb_alert_states.values()) + list(
            self.boss_red_orb_alert_states_by_max_hp.values()
        ):
            state_id = id(state)
            if state_id in seen_red_orb_states:
                continue
            seen_red_orb_states.add(state_id)
            for pending in state.pending_alerts:
                if (
                    pending.confirmed
                    and not pending.canceled
                    and not pending.fired
                ):
                    pending_times.add(pending.warn_at_ms)
                    if pending.final_warn_at_ms is not None:
                        pending_times.add(pending.final_warn_at_ms)
        if (
            self.key_enemy_debuff_alert is not None
            and self.key_enemy_debuff_alert.expiry_enabled
        ):
            expiry_ms = int(self.key_enemy_debuff_alert.expiry_seconds * 1000)
            for entity_state in self.key_enemy_debuff_entity_states.values():
                for requirement_state in entity_state.requirements.values():
                    if (
                        requirement_state.active
                        and requirement_state.end_ms is not None
                        and requirement_state.warned_end_ms != requirement_state.end_ms
                    ):
                        pending_times.add(requirement_state.end_ms - expiry_ms)
        if self.magic_shield_missing_next_due_ms is not None:
            pending_times.add(self.magic_shield_missing_next_due_ms)
        alerts: list[FiredAlert] = []
        for at_ms in sorted(pending_times):
            alerts.extend(self.advance_time(at_ms))
        return alerts

    def _apply_or_refresh(
        self, state: BuffState, event: dict[str, Any], at_ms: int
    ) -> list[FiredAlert]:
        alerts: list[FiredAlert] = []
        extra = event.get("ExtraData") or {}
        try:
            event_ccid = int(event.get("CCId"))
        except (TypeError, ValueError):
            event_ccid = state.spec.ccid
        previous_end = state.end_ms
        previous_raw_sbt_end_ms = state.last_raw_sbt_end_ms
        previous_active_ccid = state.active_ccid
        was_active = state.active
        next_end_ms: int | None = None
        clear_pending_cancelled = False
        if state.pending_dynamic_sbt_learn_at_ms is not None:
            if at_ms >= state.pending_dynamic_sbt_learn_at_ms:
                self._fire_pending_dynamic_sbt_adjust(state, at_ms)
            else:
                self._clear_pending_dynamic_sbt_adjust(state)

        if state.spec.duration_seconds is not None and "SBT" in extra:
            raw_end_ms = sbt_to_unix_ms(extra["SBT"], self.tz_offset_hours)
            sbt_adjust_seconds = self.effective_sbt_adjust_seconds(state.spec)
            adjusted_end_ms = raw_end_ms + int(sbt_adjust_seconds * 1000)
            adjusted_remaining_seconds = (adjusted_end_ms - at_ms) / 1000
            if state.spec.prefer_sbt_when_duration_present:
                state.last_timing_source = "sbt_duration_preferred"
                state.last_computed_end_ms = adjusted_end_ms
                state.last_raw_sbt_end_ms = raw_end_ms
                state.last_sbt_adjust_seconds = sbt_adjust_seconds
                state.last_sbt_adjust_source = (
                    "dynamic"
                    if state.spec.use_dynamic_sbt_adjust
                    and self.dynamic_sbt_adjust_seconds is not None
                    else "config"
                )
                state.last_raw_sbt_remaining_seconds = (raw_end_ms - at_ms) / 1000
                state.last_adjusted_remaining_seconds = adjusted_remaining_seconds
                if adjusted_remaining_seconds <= 0:
                    state.last_event_at_ms = at_ms
                    if state.active:
                        alerts.extend(self.advance_time(at_ms))
                    return alerts
                next_end_ms = adjusted_end_ms
            else:
                next_end_ms = at_ms + int(state.spec.duration_seconds * 1000)
                state.last_timing_source = "duration_seconds"
                state.last_computed_end_ms = next_end_ms
                state.last_raw_sbt_end_ms = None
                state.last_sbt_adjust_seconds = None
                state.last_sbt_adjust_source = None
                state.last_raw_sbt_remaining_seconds = None
                state.last_adjusted_remaining_seconds = state.spec.duration_seconds
        elif state.spec.duration_seconds is not None and (
            state.spec.stack_field is not None
            and state.spec.stack_field in extra
        ):
            next_end_ms = at_ms + int(state.spec.duration_seconds * 1000)
            state.last_timing_source = "duration_seconds"
            state.last_computed_end_ms = next_end_ms
            state.last_raw_sbt_end_ms = None
            state.last_sbt_adjust_seconds = None
            state.last_sbt_adjust_source = None
            state.last_raw_sbt_remaining_seconds = None
            state.last_adjusted_remaining_seconds = state.spec.duration_seconds
        elif (duration_ms := _explicit_duration_ms(extra)) is not None:
            raw_sbt_end_ms = (
                sbt_to_unix_ms(extra["SBT"], self.tz_offset_hours)
                if "SBT" in extra
                else None
            )
            stale_sbt_duration_snapshot = (
                raw_sbt_end_ms is not None
                and previous_raw_sbt_end_ms is not None
                and raw_sbt_end_ms
                < previous_raw_sbt_end_ms
                + int(DYNAMIC_SBT_NEW_END_MARGIN_SECONDS * 1000)
            )
            if state.spec.prefer_sbt_when_duration_present and raw_sbt_end_ms is not None:
                sbt_adjust_seconds = self.effective_sbt_adjust_seconds(state.spec)
                next_end_ms = raw_sbt_end_ms + int(sbt_adjust_seconds * 1000)
                state.last_timing_source = "sbt_event_duration_preferred"
                state.last_sbt_adjust_seconds = sbt_adjust_seconds
                state.last_sbt_adjust_source = (
                    "dynamic"
                    if state.spec.use_dynamic_sbt_adjust
                    and self.dynamic_sbt_adjust_seconds is not None
                    else "config"
                )
                if next_end_ms <= at_ms:
                    state.last_computed_end_ms = next_end_ms
                    state.last_raw_sbt_end_ms = raw_sbt_end_ms
                    state.last_raw_sbt_remaining_seconds = (
                        (raw_sbt_end_ms - at_ms) / 1000
                    )
                    state.last_adjusted_remaining_seconds = (
                        (next_end_ms - at_ms) / 1000
                    )
                    state.last_event_at_ms = at_ms
                    if state.active:
                        alerts.extend(self.advance_time(at_ms))
                    return alerts
            elif stale_sbt_duration_snapshot:
                state.last_timing_source = "event_duration_stale_sbt_snapshot"
                state.last_computed_end_ms = previous_end
                state.last_raw_sbt_end_ms = previous_raw_sbt_end_ms
                state.last_sbt_adjust_seconds = None
                state.last_sbt_adjust_source = None
                state.last_raw_sbt_remaining_seconds = (
                    (raw_sbt_end_ms - at_ms) / 1000
                    if raw_sbt_end_ms is not None
                    else None
                )
                state.last_adjusted_remaining_seconds = (
                    (previous_end - at_ms) / 1000
                    if previous_end is not None
                    else None
                )
                state.last_event_at_ms = at_ms
                if not was_active:
                    return alerts
                next_end_ms = previous_end
            else:
                next_end_ms = at_ms + duration_ms
                state.last_timing_source = "event_duration"
                state.last_sbt_adjust_seconds = None
                state.last_sbt_adjust_source = None
            if not stale_sbt_duration_snapshot:
                state.last_computed_end_ms = next_end_ms
                state.last_raw_sbt_end_ms = raw_sbt_end_ms
                state.last_raw_sbt_remaining_seconds = (
                    (raw_sbt_end_ms - at_ms) / 1000
                    if raw_sbt_end_ms is not None
                    else None
                )
                state.last_adjusted_remaining_seconds = (
                    (next_end_ms - at_ms) / 1000
                    if state.spec.prefer_sbt_when_duration_present
                    and raw_sbt_end_ms is not None
                    else duration_ms / 1000
                )
        elif "SBT" in extra:
            raw_end_ms = sbt_to_unix_ms(extra["SBT"], self.tz_offset_hours)
            self._learn_dynamic_sbt_adjust(
                state,
                event,
                at_ms,
                raw_end_ms,
                previous_raw_sbt_end_ms=previous_raw_sbt_end_ms,
                was_active=was_active,
            )
            sbt_adjust_seconds = self.effective_sbt_adjust_seconds(state.spec)
            next_end_ms = raw_end_ms + int(sbt_adjust_seconds * 1000)
            state.last_timing_source = "sbt"
            state.last_computed_end_ms = next_end_ms
            state.last_raw_sbt_end_ms = raw_end_ms
            state.last_sbt_adjust_seconds = sbt_adjust_seconds
            state.last_sbt_adjust_source = (
                "dynamic"
                if state.spec.use_dynamic_sbt_adjust
                and self.dynamic_sbt_adjust_seconds is not None
                else "config"
            )
            state.last_raw_sbt_remaining_seconds = (raw_end_ms - at_ms) / 1000
            state.last_adjusted_remaining_seconds = (next_end_ms - at_ms) / 1000
            if next_end_ms <= at_ms:
                state.last_event_at_ms = at_ms
                if state.spec.ccid in MUSIC_BUFF_CCIDS:
                    if state.active:
                        alerts.extend(self.advance_time(at_ms))
                    return alerts
                if state.spec.ended_on_remove_only:
                    state.fired_thresholds.clear()
                    state.ended_fired = False
                    state.ended_pending_at_ms = None
                    state.cooldown_fired = False
                    state.cooldown_pending_at_ms = None
                    if not clear_pending_cancelled:
                        state.stack_alert_fired = False
                        state.clear_alert_fired = False
                        state.clear_pending_at_ms = None
                        state.clear_pending_cleared_at_ms = None
                    state.active = True
                    state.active_ccid = event_ccid
                    state.end_ms = None
                    state.last_apply_at_ms = at_ms
                    self._sync_magic_shield_missing_after_buff_change(state, at_ms)
                    alerts.extend(self._apply_stack_alert(state, at_ms))
                    return alerts
                if state.active:
                    alerts.extend(self.advance_time(at_ms))
                return alerts

        if state.clear_pending_at_ms is not None:
            if at_ms >= state.clear_pending_at_ms:
                alerts.extend(self._fire_stack_clear_alert(state))
            else:
                state.clear_pending_at_ms = None
                state.clear_pending_cleared_at_ms = None
                clear_pending_cancelled = True

        if state.cooldown_pending_at_ms is not None:
            if at_ms >= state.cooldown_pending_at_ms:
                alerts.extend(self._fire_cooldown_alert(state))
            else:
                state.cooldown_pending_at_ms = None

        if state.ended_pending_at_ms is not None:
            if at_ms >= state.ended_pending_at_ms:
                alerts.extend(self._fire_ended_alert(state))
            else:
                state.ended_pending_at_ms = None

        if not was_active:
            state.fired_thresholds.clear()
            state.ended_fired = False
            state.ended_pending_at_ms = None
            state.cooldown_fired = False
            state.cooldown_pending_at_ms = None
            if not clear_pending_cancelled:
                state.stack_alert_fired = False
                state.clear_alert_fired = False
                state.clear_pending_at_ms = None
                state.clear_pending_cleared_at_ms = None

        if next_end_ms is not None:
            if previous_end is not None and was_active:
                remaining = math.floor((next_end_ms - at_ms) / 1000)
                state.fired_thresholds = {
                    threshold
                    for threshold in state.fired_thresholds
                    if remaining <= threshold + ALERT_REARM_MARGIN_SECONDS
                }
                if next_end_ms > previous_end + ALERT_REARM_MARGIN_SECONDS * 1000:
                    state.ended_fired = False
                    state.ended_pending_at_ms = None
                    state.cooldown_fired = False
                    state.cooldown_pending_at_ms = None

            state.end_ms = next_end_ms

        if state.spec.stack_field and state.spec.stack_field in extra:
            state.stacks = int(extra[state.spec.stack_field])

        state.active = True
        if (
            event_ccid != state.spec.ccid
            and was_active
            and previous_active_ccid == state.spec.ccid
        ):
            state.active_ccid = previous_active_ccid
        else:
            state.active_ccid = event_ccid
        state.last_apply_at_ms = at_ms
        state.ended_pending_at_ms = None
        state.last_event_at_ms = at_ms
        if (
            self.self_player_dead
            and state.spec.ccid == MAGIC_SHIELD_CCID
            and self._event_targets_self(event)
        ):
            self.self_player_dead = False
        if state.spec.ccid == TUAN_SONG_CCID:
            self._clear_music_strong_reminders_for_tuan()
            for music_state in self.states.values():
                if music_state.active and music_state.spec.ccid in MUSIC_BUFF_CCIDS:
                    self._update_music_toan_extension_on_apply(music_state, at_ms)
        else:
            self._update_music_toan_extension_on_apply(state, at_ms)
        self._sync_magic_shield_missing_after_buff_change(state, at_ms)
        alerts.extend(self._flush_pending_music_cover_ended_alerts(state, at_ms))
        alerts.extend(self._apply_stack_alert(state, at_ms))
        alerts.extend(self.advance_time(at_ms))
        return alerts

    def _flush_pending_music_cover_ended_alerts(
        self, applied_state: BuffState, at_ms: int
    ) -> list[FiredAlert]:
        if applied_state.spec.ccid not in MUSIC_BUFF_CCIDS:
            return []

        alerts: list[FiredAlert] = []
        for state in self.states.values():
            if state is applied_state:
                continue
            if state.spec.ccid not in MUSIC_BUFF_CCIDS:
                continue
            if state.active or state.ended_pending_at_ms is None:
                continue

            self._clear_pending_dynamic_sbt_adjust(state)
            alert_at_ms = (
                state.last_event_at_ms
                if state.last_event_at_ms is not None
                else at_ms
            )
            alerts.extend(self._fire_ended_alert(state, at_ms=alert_at_ms))
        return alerts

    def _learn_dynamic_sbt_adjust(
        self,
        state: BuffState,
        event: dict[str, Any],
        at_ms: int,
        raw_end_ms: int,
        *,
        previous_raw_sbt_end_ms: int | None,
        was_active: bool,
    ) -> None:
        if not state.spec.use_dynamic_sbt_adjust:
            return

        extra = event.get("ExtraData") or {}
        if "SBT" not in extra:
            return

        duration_ms = _explicit_duration_ms(extra)
        if duration_ms is None:
            return

        if was_active and previous_raw_sbt_end_ms is not None:
            min_new_end_ms = previous_raw_sbt_end_ms + int(
                DYNAMIC_SBT_NEW_END_MARGIN_SECONDS * 1000
            )
            if raw_end_ms < min_new_end_ms:
                return

        raw_remaining_seconds = (raw_end_ms - at_ms) / 1000
        observed_adjust_seconds = (duration_ms / 1000) - raw_remaining_seconds
        self._record_dynamic_sbt_adjust_sample(
            state,
            raw_end_ms=raw_end_ms,
            observed_adjust_seconds=observed_adjust_seconds,
            require_baseline=True,
            at_ms=at_ms,
        )

    def _ended_grace_seconds_for_remove(
        self, state: BuffState, ended_at_ms: int | None
    ) -> float:
        grace_seconds = state.spec.ended_grace_seconds
        if ended_at_ms is not None and state.spec.ccid in MUSIC_BUFF_CCIDS:
            grace_seconds = max(
                grace_seconds, MUSIC_REAPPLY_SUPPRESSION_GRACE_SECONDS
            )
        if (
            state.spec.early_remove_reapply_grace_seconds > grace_seconds
            and ended_at_ms is not None
            and state.last_computed_end_ms is not None
            and state.last_computed_end_ms - ended_at_ms > int(grace_seconds * 1000)
        ):
            grace_seconds = state.spec.early_remove_reapply_grace_seconds
        return grace_seconds

    def _clear_pending_dynamic_sbt_adjust(self, state: BuffState) -> None:
        state.pending_dynamic_sbt_learn_at_ms = None
        state.pending_dynamic_sbt_remove_at_ms = None
        state.pending_dynamic_sbt_raw_end_ms = None

    def _schedule_pending_dynamic_sbt_adjust_from_remove(
        self, state: BuffState, at_ms: int
    ) -> None:
        if state.last_raw_sbt_end_ms is None:
            return
        grace_ms = int(self._ended_grace_seconds_for_remove(state, at_ms) * 1000)
        if grace_ms <= 0:
            return
        state.pending_dynamic_sbt_learn_at_ms = at_ms + grace_ms
        state.pending_dynamic_sbt_remove_at_ms = at_ms
        state.pending_dynamic_sbt_raw_end_ms = state.last_raw_sbt_end_ms

    def _has_active_other_music_buff(self, ccid: int) -> bool:
        if ccid not in MUSIC_BUFF_CCIDS:
            return False
        for state in self.states.values():
            if state.spec.ccid == ccid or state.spec.ccid not in MUSIC_BUFF_CCIDS:
                continue
            if state.active:
                return True
        return False

    def _is_tuan_song_active(self, at_ms: int | None = None) -> bool:
        return self._is_ccid_active(TUAN_SONG_CCID, at_ms)

    def _clear_music_strong_reminder(self, state: BuffState) -> None:
        state.music_strong_reminder_next_at_ms = None
        state.music_strong_reminder_rule_seconds = None
        state.music_strong_reminder_sound = None

    def _clear_music_strong_reminders_for_tuan(self) -> None:
        for state in self.states.values():
            if state.spec.ccid in MUSIC_BUFF_CCIDS:
                self._clear_music_strong_reminder(state)

    def _music_strong_reminder_should_apply(
        self, state: BuffState, at_ms: int | None = None
    ) -> bool:
        return (
            self.music_strong_reminder_enabled
            and state.spec.ccid in MUSIC_BUFF_CCIDS
            and not state.music_toan_extended
            and not self._is_tuan_song_active(at_ms)
        )

    def _music_strong_reminder_sound(self, base_sound: str) -> str:
        return make_timed_sound_sequence(
            (0.0, self.music_strong_reminder_prefix_sound),
            (0.35, base_sound),
        )

    def _schedule_music_strong_reminder(
        self, state: BuffState, rule: AlertRule, at_ms: int
    ) -> None:
        if not self._music_strong_reminder_should_apply(state, at_ms):
            self._clear_music_strong_reminder(state)
            return
        state.music_strong_reminder_next_at_ms = at_ms + int(
            self.music_strong_reminder_repeat_seconds * 1000
        )
        state.music_strong_reminder_rule_seconds = rule.remaining_seconds
        state.music_strong_reminder_sound = rule.sound

    def _advance_music_strong_reminder(
        self, state: BuffState, at_ms: int
    ) -> list[FiredAlert]:
        if state.music_strong_reminder_next_at_ms is None:
            return []
        if (
            not state.active
            or state.end_ms is None
            or state.spec.ccid not in MUSIC_BUFF_CCIDS
        ):
            self._clear_music_strong_reminder(state)
            return []
        if self._is_tuan_song_active(at_ms) or state.music_toan_extended:
            self._clear_music_strong_reminder(state)
            return []
        if at_ms < state.music_strong_reminder_next_at_ms:
            return []
        if at_ms >= state.end_ms:
            self._clear_music_strong_reminder(state)
            return []

        remaining = max(0, math.ceil((state.end_ms - at_ms) / 1000))
        state.music_strong_reminder_next_at_ms = at_ms + int(
            self.music_strong_reminder_repeat_seconds * 1000
        )
        base_sound = state.music_strong_reminder_sound
        if not base_sound:
            base_sound = (
                state.spec.alerts[0].sound
                if state.spec.alerts
                else DEFAULT_WARN_SOUND
            )
        return [
            FiredAlert(
                at_ms=at_ms,
                kind="music_strong_threshold",
                name=state.spec.name,
                ccid=state.spec.ccid,
                remaining_seconds=remaining,
                message=format_message(
                    "{name}",
                    state.spec,
                    remaining=remaining,
                    stacks=state.stacks,
                ),
                sound=self._music_strong_reminder_sound(base_sound),
                volume=state.spec.audio_volume,
                detail={
                    "repeat_seconds": self.music_strong_reminder_repeat_seconds,
                    "threshold_seconds": state.music_strong_reminder_rule_seconds,
                },
            )
        ]

    def _mark_music_toan_extension(
        self, state: BuffState, at_ms: int, source: str
    ) -> None:
        state.music_toan_extended = True
        state.music_toan_extended_at_ms = at_ms
        state.music_toan_extension_source = source
        self._clear_music_strong_reminder(state)

    def _update_music_toan_extension_on_apply(
        self, state: BuffState, at_ms: int
    ) -> None:
        if state.spec.ccid not in MUSIC_BUFF_CCIDS or state.end_ms is None:
            return
        remaining_seconds = (state.end_ms - at_ms) / 1000
        recent_remove_at_ms = self.recent_music_remove_with_tuan_at_ms.get(
            state.spec.ccid
        )
        recent_remove_with_tuan = (
            recent_remove_at_ms is not None
            and 0 <= at_ms - recent_remove_at_ms <= MUSIC_TUAN_EXTENSION_RECENT_WINDOW_MS
        )
        if (
            remaining_seconds >= MUSIC_TUAN_EXTENSION_MIN_REMAINING_SECONDS
            and self._is_tuan_song_active(at_ms)
        ):
            self._mark_music_toan_extension(state, at_ms, "tuan_active_long_duration")
            return
        if (
            remaining_seconds >= MUSIC_TUAN_EXTENSION_MIN_REMAINING_SECONDS
            and recent_remove_with_tuan
        ):
            self._mark_music_toan_extension(state, at_ms, "reapply_after_tuan_remove")
            return
        if remaining_seconds < MUSIC_TUAN_EXTENSION_MIN_REMAINING_SECONDS:
            state.music_toan_extended = False
            state.music_toan_extended_at_ms = None
            state.music_toan_extension_source = None

    def _is_ccid_active(self, ccid: int, at_ms: int | None = None) -> bool:
        primary = self.ccid_to_primary.get(ccid, ccid)
        state = self.states.get(primary)
        if state is None or not state.active:
            return False
        if at_ms is not None and state.end_ms is not None and at_ms >= state.end_ms:
            return False
        return True

    def _fire_pending_dynamic_sbt_adjust(
        self, state: BuffState, at_ms: int
    ) -> None:
        if state.pending_dynamic_sbt_learn_at_ms is None:
            return
        if at_ms < state.pending_dynamic_sbt_learn_at_ms:
            return
        remove_at_ms = state.pending_dynamic_sbt_remove_at_ms
        raw_end_ms = state.pending_dynamic_sbt_raw_end_ms
        self._clear_pending_dynamic_sbt_adjust(state)
        if remove_at_ms is None or raw_end_ms is None:
            return
        if self._should_suppress_ended_alert(state.spec, at_ms=at_ms):
            return
        observed_adjust_seconds = (remove_at_ms - raw_end_ms) / 1000
        self._record_dynamic_sbt_adjust_sample(
            state,
            raw_end_ms=raw_end_ms,
            observed_adjust_seconds=observed_adjust_seconds,
            require_baseline=False,
            at_ms=at_ms,
        )

    def _learn_dynamic_sbt_adjust_from_remove(
        self,
        state: BuffState,
        event_ccid: int,
        at_ms: int,
    ) -> None:
        if not state.spec.use_dynamic_sbt_adjust:
            return
        if event_ccid != state.spec.ccid:
            return
        if self._has_active_other_music_buff(state.spec.ccid):
            return
        if state.last_timing_source != "sbt":
            return
        if state.last_raw_sbt_end_ms is None or state.last_computed_end_ms is None:
            return

        predicted_delta_seconds = (at_ms - state.last_computed_end_ms) / 1000
        if predicted_delta_seconds < DYNAMIC_SBT_REMOVE_MIN_PREDICTED_DELTA_SECONDS:
            self._schedule_pending_dynamic_sbt_adjust_from_remove(state, at_ms)
            return
        if predicted_delta_seconds > DYNAMIC_SBT_REMOVE_MAX_PREDICTED_DELTA_SECONDS:
            return

        observed_adjust_seconds = (at_ms - state.last_raw_sbt_end_ms) / 1000
        self._record_dynamic_sbt_adjust_sample(
            state,
            raw_end_ms=state.last_raw_sbt_end_ms,
            observed_adjust_seconds=observed_adjust_seconds,
            require_baseline=False,
            at_ms=at_ms,
        )

    def _record_dynamic_sbt_adjust_sample(
        self,
        state: BuffState,
        *,
        raw_end_ms: int,
        observed_adjust_seconds: float,
        require_baseline: bool,
        at_ms: int,
    ) -> None:
        sample_key = (state.spec.ccid, raw_end_ms)
        if sample_key in self._dynamic_sbt_adjust_sample_key_set:
            return

        if not (
            DYNAMIC_SBT_MIN_OBSERVED_ADJUST_SECONDS
            <= observed_adjust_seconds
            <= DYNAMIC_SBT_MAX_OBSERVED_ADJUST_SECONDS
        ):
            return

        baseline = (
            self.dynamic_sbt_adjust_seconds
            if self.dynamic_sbt_adjust_seconds is not None
            else state.spec.sbt_adjust_seconds
        )
        if require_baseline and (
            abs(observed_adjust_seconds - baseline)
            > DYNAMIC_SBT_MAX_BASELINE_DEVIATION_SECONDS
        ):
            return

        self._dynamic_sbt_adjust_samples.append(observed_adjust_seconds)
        self._dynamic_sbt_adjust_sample_keys.append(sample_key)
        self._dynamic_sbt_adjust_sample_key_set.add(sample_key)
        if len(self._dynamic_sbt_adjust_samples) > MAX_DYNAMIC_SBT_ADJUST_SAMPLES:
            self._dynamic_sbt_adjust_samples = self._dynamic_sbt_adjust_samples[
                -MAX_DYNAMIC_SBT_ADJUST_SAMPLES:
            ]
            self._dynamic_sbt_adjust_sample_keys = self._dynamic_sbt_adjust_sample_keys[
                -MAX_DYNAMIC_SBT_ADJUST_SAMPLES:
            ]
            self._dynamic_sbt_adjust_sample_key_set = set(
                self._dynamic_sbt_adjust_sample_keys
            )
        previous_dynamic_sbt_adjust_seconds = self.dynamic_sbt_adjust_seconds
        self.dynamic_sbt_adjust_seconds = float(
            statistics.median(self._dynamic_sbt_adjust_samples)
        )
        if (
            previous_dynamic_sbt_adjust_seconds is None
            or abs(
                self.dynamic_sbt_adjust_seconds
                - previous_dynamic_sbt_adjust_seconds
            )
            >= 0.05
        ):
            self._resync_active_sbt_states(at_ms)

    def _resync_active_sbt_states(self, at_ms: int) -> None:
        if self.dynamic_sbt_adjust_seconds is None:
            return
        for state in self.states.values():
            if not state.active:
                continue
            if state.last_timing_source != "sbt":
                continue
            if state.last_raw_sbt_end_ms is None:
                continue
            previous_end_ms = state.end_ms
            next_end_ms = state.last_raw_sbt_end_ms + int(
                self.effective_sbt_adjust_seconds(state.spec) * 1000
            )
            if previous_end_ms is not None and abs(next_end_ms - previous_end_ms) < 250:
                continue
            state.end_ms = next_end_ms
            state.last_computed_end_ms = next_end_ms
            state.last_sbt_adjust_seconds = self.effective_sbt_adjust_seconds(state.spec)
            state.last_sbt_adjust_source = "dynamic"
            if state.last_apply_at_ms is not None:
                state.last_adjusted_remaining_seconds = (
                    next_end_ms - state.last_apply_at_ms
                ) / 1000
            remaining_seconds = math.floor((next_end_ms - at_ms) / 1000)
            state.fired_thresholds = {
                threshold
                for threshold in state.fired_thresholds
                if remaining_seconds <= threshold + ALERT_REARM_MARGIN_SECONDS
            }
            if (
                previous_end_ms is not None
                and next_end_ms
                > previous_end_ms + ALERT_REARM_MARGIN_SECONDS * 1000
            ):
                state.ended_fired = False
                state.ended_pending_at_ms = None
                state.cooldown_fired = False
                state.cooldown_pending_at_ms = None

    def _remove(self, state: BuffState, event_ccid: int, at_ms: int) -> list[FiredAlert]:
        state.last_event_at_ms = at_ms
        if (
            event_ccid != state.spec.ccid
            and state.active
            and state.active_ccid is not None
            and state.active_ccid != event_ccid
        ):
            return []
        if not state.active and event_ccid != state.spec.ccid:
            return []
        if (
            state.active
            and event_ccid == state.spec.ccid
            and state.spec.ccid in MUSIC_BUFF_CCIDS
            and state.last_apply_at_ms is not None
            and 0 <= at_ms - state.last_apply_at_ms <= MUSIC_APPLY_REMOVE_NOISE_WINDOW_MS
        ):
            return []
        if event_ccid == state.spec.ccid and state.spec.ccid in MUSIC_BUFF_CCIDS:
            if self._is_tuan_song_active(at_ms):
                self.recent_music_remove_with_tuan_at_ms[state.spec.ccid] = at_ms
            self._clear_music_strong_reminder(state)
            state.music_toan_extended = False
            state.music_toan_extended_at_ms = None
            state.music_toan_extension_source = None
        if not state.active and event_ccid == state.spec.ccid:
            state.fired_thresholds.clear()
            if self._in_death_clear_suppression(at_ms):
                self._suppress_ended_state(state)
                return []
            self._learn_dynamic_sbt_adjust_from_remove(state, event_ccid, at_ms)
            self._sync_magic_shield_missing_after_buff_change(state, at_ms)
            alerts = self._stack_clear_alert(state, at_ms, cleared_at_ms=at_ms)
            alerts.extend(self._ended_alert(state, at_ms, ended_at_ms=at_ms))
            alerts.extend(self._cooldown_alert(state, at_ms, ended_at_ms=at_ms))
            self._suppress_death_clear_if_needed(at_ms)
            return alerts
        if self._in_death_clear_suppression(at_ms):
            state.active = False
            state.active_ccid = None
            state.end_ms = None
            state.fired_thresholds.clear()
            self._suppress_ended_state(state)
            return []
        self._learn_dynamic_sbt_adjust_from_remove(state, event_ccid, at_ms)
        state.active = False
        state.active_ccid = None
        state.end_ms = None
        state.fired_thresholds.clear()
        self._sync_magic_shield_missing_after_buff_change(state, at_ms)
        alerts = self._stack_clear_alert(state, at_ms, cleared_at_ms=at_ms)
        alerts.extend(self._ended_alert(state, at_ms, ended_at_ms=at_ms))
        alerts.extend(self._cooldown_alert(state, at_ms, ended_at_ms=at_ms))
        self._suppress_death_clear_if_needed(at_ms)
        return alerts

    def _process_stats(self, event: dict[str, Any]) -> list[FiredAlert]:
        alerts: list[FiredAlert] = []
        at_ms = int(event.get("At", 0))
        for item in event.get("Stats") or []:
            stat_id = item.get("StatId")
            if stat_id is None:
                continue
            state = self.progress_states.get(int(stat_id))
            if state is None:
                continue
            value = item.get("Value")
            if not isinstance(value, (int, float)):
                continue
            alerts.extend(self._apply_progress(state, float(value), at_ms))
        return alerts

    def _apply_progress(
        self, state: ProgressState, value: float, at_ms: int
    ) -> list[FiredAlert]:
        spec = state.spec
        if state.value is not None and value < state.value - 5:
            state.fired_thresholds.clear()
        state.value = value

        alerts: list[FiredAlert] = []
        for rule in spec.alerts:
            threshold = max(0.0, spec.max_value - rule.remaining_progress)
            if rule.remaining_progress in state.fired_thresholds:
                continue
            if value >= threshold:
                state.fired_thresholds.add(rule.remaining_progress)
                remaining = max(0.0, spec.max_value - value)
                alerts.append(
                    FiredAlert(
                        at_ms=at_ms,
                        kind="progress",
                        name=spec.name,
                        ccid=None,
                        remaining_seconds=None,
                        message=format_progress_message(
                            rule.message,
                            spec,
                            progress=value,
                            remaining=remaining,
                        ),
                        sound=rule.sound,
                        volume=spec.audio_volume,
                    )
                )
        return alerts

    def _apply_stack_alert(self, state: BuffState, at_ms: int) -> list[FiredAlert]:
        rule = state.spec.stack_alert
        if rule is None or state.stack_alert_fired:
            return []
        if state.stacks is None or state.stacks < rule.stacks:
            return []

        state.stack_alert_fired = True
        state.clear_alert_fired = False
        state.clear_pending_at_ms = None
        state.clear_pending_cleared_at_ms = None
        return [
            FiredAlert(
                at_ms=at_ms,
                kind="stack",
                name=state.spec.name,
                ccid=state.spec.ccid,
                remaining_seconds=None,
                message=format_message(
                    rule.message,
                    state.spec,
                    remaining=None,
                    stacks=state.stacks,
                ),
                sound=rule.sound,
                volume=state.spec.audio_volume,
            )
        ]

    def _stack_clear_alert(
        self, state: BuffState, at_ms: int, *, cleared_at_ms: int | None = None
    ) -> list[FiredAlert]:
        if (
            not state.stack_alert_fired
            or state.clear_alert_fired
        ):
            return []

        if state.clear_pending_at_ms is not None:
            if at_ms >= state.clear_pending_at_ms:
                return self._fire_stack_clear_alert(state)
            return []

        grace_ms = int(state.spec.clear_grace_seconds * 1000)
        state.clear_pending_cleared_at_ms = cleared_at_ms or at_ms
        if grace_ms > 0:
            state.clear_pending_at_ms = (cleared_at_ms or at_ms) + grace_ms
            if at_ms < state.clear_pending_at_ms:
                return []
        return self._fire_stack_clear_alert(state, at_ms=at_ms)

    def _fire_stack_clear_alert(
        self, state: BuffState, *, at_ms: int | None = None
    ) -> list[FiredAlert]:
        alert_at_ms = at_ms if at_ms is not None else state.clear_pending_at_ms
        alert_at_ms = alert_at_ms if alert_at_ms is not None else state.last_event_at_ms
        alert_at_ms = alert_at_ms if alert_at_ms is not None else 0
        cleared_at_ms = state.clear_pending_cleared_at_ms or alert_at_ms
        state.clear_pending_at_ms = None
        state.clear_pending_cleared_at_ms = None
        if (
            not state.stack_alert_fired
            or state.clear_alert_fired
        ):
            return []
        if not state.spec.clear_after_stack_alert:
            state.clear_alert_fired = True
            return []
        if self._in_death_clear_suppression(alert_at_ms):
            self._suppress_ended_state(state)
            return []

        min_active_ms = int(state.spec.clear_after_stack_min_active_seconds * 1000)
        if (
            min_active_ms > 0
            and state.last_apply_at_ms is not None
            and cleared_at_ms - state.last_apply_at_ms < min_active_ms
        ):
            return []

        state.clear_alert_fired = True
        return [
            FiredAlert(
                at_ms=alert_at_ms,
                kind="cleared",
                name=state.spec.name,
                ccid=state.spec.ccid,
                remaining_seconds=None,
                message=format_message(
                    state.spec.clear_message,
                    state.spec,
                    remaining=None,
                    stacks=state.stacks,
                ),
                sound=state.spec.clear_sound,
                volume=state.spec.audio_volume,
            )
        ]

    def _ended_alert(
        self, state: BuffState, at_ms: int, *, ended_at_ms: int | None = None
    ) -> list[FiredAlert]:
        if not state.spec.ended_alert or state.ended_fired:
            return []

        if state.ended_pending_at_ms is not None:
            if at_ms >= state.ended_pending_at_ms:
                return self._fire_ended_alert(state)
            return []

        grace_seconds = self._ended_grace_seconds_for_remove(state, ended_at_ms)
        grace_ms = int(grace_seconds * 1000)
        if grace_ms > 0:
            state.ended_pending_at_ms = (ended_at_ms or at_ms) + grace_ms
            if at_ms < state.ended_pending_at_ms:
                return []
        return self._fire_ended_alert(state, at_ms=at_ms)

    def _fire_ended_alert(
        self, state: BuffState, *, at_ms: int | None = None
    ) -> list[FiredAlert]:
        alert_at_ms = at_ms if at_ms is not None else state.ended_pending_at_ms
        alert_at_ms = alert_at_ms if alert_at_ms is not None else state.last_event_at_ms
        alert_at_ms = alert_at_ms if alert_at_ms is not None else 0
        state.ended_pending_at_ms = None
        if not state.spec.ended_alert or state.ended_fired:
            return []
        if self._in_death_clear_suppression(alert_at_ms):
            self._suppress_ended_state(state)
            return []
        if self._should_suppress_ended_alert(state.spec, at_ms=alert_at_ms):
            state.ended_fired = True
            return []

        state.ended_fired = True
        return [
            FiredAlert(
                at_ms=alert_at_ms,
                kind="ended",
                name=state.spec.name,
                ccid=state.spec.ccid,
                remaining_seconds=None,
                message=format_message(
                    state.spec.ended_message,
                    state.spec,
                    remaining=None,
                    stacks=state.stacks,
                ),
                sound=state.spec.ended_sound,
                volume=state.spec.audio_volume,
            )
        ]

    def _cooldown_alert(
        self, state: BuffState, at_ms: int, *, ended_at_ms: int | None = None
    ) -> list[FiredAlert]:
        if not state.spec.cooldown_alert or state.cooldown_fired:
            return []

        if state.cooldown_pending_at_ms is not None:
            if at_ms >= state.cooldown_pending_at_ms:
                return self._fire_cooldown_alert(state)
            return []

        cooldown_ms = int(state.spec.cooldown_delay_seconds * 1000)
        state.cooldown_pending_at_ms = (ended_at_ms or at_ms) + cooldown_ms
        if at_ms < state.cooldown_pending_at_ms:
            return []
        return self._fire_cooldown_alert(state, at_ms=at_ms)

    def _fire_cooldown_alert(
        self, state: BuffState, *, at_ms: int | None = None
    ) -> list[FiredAlert]:
        alert_at_ms = at_ms if at_ms is not None else state.cooldown_pending_at_ms
        alert_at_ms = alert_at_ms if alert_at_ms is not None else state.last_event_at_ms
        alert_at_ms = alert_at_ms if alert_at_ms is not None else 0
        state.cooldown_pending_at_ms = None
        if not state.spec.cooldown_alert or state.cooldown_fired:
            return []
        if self._in_death_clear_suppression(alert_at_ms):
            self._suppress_ended_state(state)
            return []

        state.cooldown_fired = True
        return [
            FiredAlert(
                at_ms=alert_at_ms,
                kind="cooldown",
                name=state.spec.name,
                ccid=state.spec.ccid,
                remaining_seconds=None,
                message=format_message(
                    state.spec.cooldown_message,
                    state.spec,
                    remaining=None,
                    stacks=state.stacks,
                ),
                sound=state.spec.cooldown_sound,
                volume=state.spec.audio_volume,
            )
        ]

    def _should_suppress_remaining_alert(
        self, state: BuffState, at_ms: int, remaining_seconds: int
    ) -> bool:
        if not state.spec.suppress_remaining_if_active_ccids:
            return False
        for ccid in state.spec.suppress_remaining_if_active_ccids:
            primary = self.ccid_to_primary.get(ccid, ccid)
            other_state = self.states.get(primary)
            if other_state is None or not other_state.active:
                continue
            if other_state.end_ms is None:
                return True
            if at_ms >= other_state.end_ms:
                continue
            other_remaining = math.floor((other_state.end_ms - at_ms) / 1000)
            if other_remaining >= remaining_seconds:
                return True
        return False

    def _should_suppress_ended_alert(
        self, spec: BuffSpec, *, at_ms: int | None = None
    ) -> bool:
        if spec.ccid in MUSIC_BUFF_CCIDS and self._is_ccid_active(
            TUAN_SONG_CCID, at_ms
        ):
            return True
        if not spec.suppress_ended_if_active_ccids:
            return False
        for ccid in spec.suppress_ended_if_active_ccids:
            if self._is_ccid_active(ccid, at_ms):
                return True
        return False

    def _battle_timer_event_kind(self, event: dict[str, Any]) -> str | None:
        if int(event.get("EventId", -1)) != 0:
            return None
        if str(event.get("Op", "")).lower() != BATTLE_TIMER_OP:
            return None

        messages = event.get("Msg") or []
        if len(messages) < 2:
            return None
        first = messages[0] if isinstance(messages[0], dict) else {}
        second = messages[1] if isinstance(messages[1], dict) else {}
        if str(second.get("V")) != BATTLE_TIMER_MESSAGE_KEY:
            return None

        marker = str(first.get("V"))
        if marker == "1":
            has_battle_timer_name = any(
                isinstance(message, dict)
                and str(message.get("V")) == BATTLE_TIMER_NAME
                for message in messages
            )
            return "start" if has_battle_timer_name else None
        if marker == "0":
            return "stop"
        return None

    def _process_battle_timer_event(self, event: dict[str, Any]) -> None:
        kind = self._battle_timer_event_kind(event)
        if kind is None:
            return
        at_ms = int(event.get("At", 0))
        if kind == "start":
            self.battle_timer_active = True
            self.battle_timer_started_at_ms = at_ms
            self._reset_all_boss_hp_states()
            self._reset_all_boss_skill_burst_states()
            self._reset_all_boss_red_orb_states()
            self._reset_all_boss_laser_states()
            self._reset_all_key_enemy_debuff_states()
            self._resync_magic_shield_missing_schedule(at_ms)
            return

        self.battle_timer_active = False
        self.battle_timer_started_at_ms = None
        self._reset_all_boss_hp_states()
        self._reset_all_boss_skill_burst_states()
        self._reset_all_boss_red_orb_states()
        self._reset_all_boss_laser_states()
        self._reset_all_key_enemy_debuff_states()
        self._clear_magic_shield_missing_schedule()

    def _sync_magic_shield_missing_after_buff_change(
        self, state: BuffState, at_ms: int
    ) -> None:
        if (
            self.magic_shield_missing is None
            or state.spec.ccid != self.magic_shield_missing.ccid
        ):
            return
        self.magic_shield_state_observed = True
        self._resync_magic_shield_missing_schedule(at_ms)

    def _magic_shield_is_active(self) -> bool:
        if self.magic_shield_missing is None:
            return False
        primary = self.ccid_to_primary.get(
            self.magic_shield_missing.ccid,
            self.magic_shield_missing.ccid,
        )
        state = self.states.get(primary)
        return bool(state is not None and state.active)

    def _event_targets_self(self, event: dict[str, Any]) -> bool:
        if self.self_entity_id is None:
            return False
        for key in ("Id", "TargetId"):
            value = event.get(key)
            if value is not None and str(value) == self.self_entity_id:
                return True
        return False

    def _event_allowed_for_buff_spec(
        self, spec: BuffSpec, event: dict[str, Any]
    ) -> bool:
        if (
            spec.self_filter
            and self.self_entity_id is not None
            and not self._event_targets_self(event)
        ):
            return False
        if event.get("EventId") == 4 and spec.required_extra:
            return _extra_matches_required(
                event.get("ExtraData") or {}, spec.required_extra
            )
        return True

    def _process_self_stats(self, event: dict[str, Any]) -> None:
        if not self._event_targets_self(event):
            return
        current_values = _event_stat_values(event)
        hp = current_values.get(PLAYER_HP_STAT_ID)
        if hp is None:
            return
        self.last_self_hp = hp
        if self.self_player_dead and hp > 0:
            self.self_player_dead = False
            self._resync_magic_shield_missing_schedule(int(event.get("At", 0)))

    def _clear_magic_shield_missing_schedule(self) -> None:
        self.magic_shield_missing_next_due_ms = None

    def _is_boss_battle_active(self, at_ms: int) -> bool:
        if self.battle_timer_active:
            return True
        seen: set[int] = set()
        for state in list(self.boss_hp_alert_states.values()) + list(
            self.boss_hp_alert_states_by_max_hp.values()
        ):
            state_id = id(state)
            if state_id in seen:
                continue
            seen.add(state_id)
            if not state.active or state.last_seen_at_ms is None:
                continue
            if at_ms - state.last_seen_at_ms <= BOSS_HP_INFERRED_BATTLE_STALE_MS:
                return True
        return False

    def _resync_magic_shield_missing_schedule(self, at_ms: int) -> None:
        if self.magic_shield_missing is None:
            return
        if (
            not self.magic_shield_state_observed
            or not self._is_boss_battle_active(at_ms)
            or self.self_player_dead
            or self._magic_shield_is_active()
        ):
            self._clear_magic_shield_missing_schedule()
            return
        if self.magic_shield_missing_next_due_ms is None:
            delay_ms = int(self.magic_shield_missing.delay_seconds * 1000)
            self.magic_shield_missing_next_due_ms = at_ms + delay_ms

    def _advance_magic_shield_missing(self, at_ms: int) -> list[FiredAlert]:
        spec = self.magic_shield_missing
        if spec is None:
            return []
        if (
            not self.magic_shield_state_observed
            or not self._is_boss_battle_active(at_ms)
            or self.self_player_dead
            or self._magic_shield_is_active()
        ):
            self._clear_magic_shield_missing_schedule()
            return []
        if self.magic_shield_missing_next_due_ms is None:
            self._resync_magic_shield_missing_schedule(at_ms)
            return []
        if at_ms < self.magic_shield_missing_next_due_ms:
            return []

        repeat_ms = int(spec.repeat_seconds * 1000)
        self.magic_shield_missing_next_due_ms = at_ms + max(100, repeat_ms)
        return [
            FiredAlert(
                at_ms=at_ms,
                kind="missing_magic_shield",
                name="魔法盾漏开提醒",
                ccid=spec.ccid,
                remaining_seconds=None,
                message=spec.message,
                sound=spec.sound,
                volume=spec.audio_volume,
            )
        ]

    def _in_death_clear_suppression(self, at_ms: int) -> bool:
        return at_ms <= self.death_clear_suppressed_until_ms

    def _suppress_ended_state(self, state: BuffState) -> None:
        state.ended_pending_at_ms = None
        state.ended_fired = True
        state.cooldown_pending_at_ms = None
        state.cooldown_fired = True
        state.clear_pending_at_ms = None
        state.clear_pending_cleared_at_ms = None
        self._clear_pending_dynamic_sbt_adjust(state)
        if state.spec.clear_after_stack_alert:
            state.clear_alert_fired = True

    def _apply_death_signal(self, event: dict[str, Any], at_ms: int) -> None:
        if self._event_targets_self(event):
            self.self_player_dead = True
            self._clear_magic_shield_missing_schedule()

        lookback_ms = max(
            self.death_clear_suppression_window_ms,
            self.death_signal_suppression_window_ms,
        )
        if lookback_ms <= 0:
            return

        self.death_clear_suppressed_until_ms = max(
            self.death_clear_suppressed_until_ms,
            at_ms + self.death_signal_suppression_window_ms,
        )
        self._suppress_recent_ended_states(at_ms, lookback_ms)

    def _suppress_recent_ended_states(self, at_ms: int, lookback_ms: int) -> None:
        window_start = at_ms - lookback_ms
        for state in self.states.values():
            if (
                not state.active
                and (
                    state.ended_pending_at_ms is not None
                    or state.clear_pending_at_ms is not None
                    or state.cooldown_pending_at_ms is not None
                )
                and state.last_event_at_ms is not None
                and window_start <= state.last_event_at_ms <= at_ms
            ):
                self._suppress_ended_state(state)

    def _suppress_death_clear_if_needed(self, at_ms: int) -> None:
        if (
            self.death_clear_suppression_window_ms <= 0
            or self.death_clear_suppression_min_buffs <= 1
        ):
            return

        window_start = at_ms - self.death_clear_suppression_window_ms
        pending_states = [
            state
            for state in self.states.values()
            if (
                not state.active
                and (
                    state.ended_pending_at_ms is not None
                    or state.clear_pending_at_ms is not None
                    or state.cooldown_pending_at_ms is not None
                )
                and state.last_event_at_ms is not None
                and window_start <= state.last_event_at_ms <= at_ms
            )
        ]
        distinct_ccids = {state.spec.ccid for state in pending_states}
        if len(distinct_ccids) < self.death_clear_suppression_min_buffs:
            return

        latest_remove_at = max(
            state.last_event_at_ms or at_ms for state in pending_states
        )
        self.death_clear_suppressed_until_ms = max(
            self.death_clear_suppressed_until_ms,
            latest_remove_at + self.death_clear_suppression_window_ms,
        )
        for state in pending_states:
            self._suppress_ended_state(state)

    def _process_stat_drop_effect_trigger(
        self, event: dict[str, Any]
    ) -> list[FiredAlert]:
        alerts: list[FiredAlert] = []
        at_ms = int(event.get("At", 0))
        for state in self.stat_drop_effect_states:
            if state.spec.start_trigger is not None and self._event_matches_trigger(
                event, state.spec.start_trigger
            ):
                dedupe_ms = int(state.spec.trigger_dedupe_seconds * 1000)
                if (
                    dedupe_ms > 0
                    and state.last_start_at_ms is not None
                    and at_ms - state.last_start_at_ms < dedupe_ms
                ):
                    continue
                state.active = True
                state.ended_fired = False
                state.last_start_at_ms = at_ms
                state.fired_thresholds.clear()
                self._reset_stat_drop_effect_timer_sync(state)
                if state.spec.timer_enabled and state.spec.duration_seconds > 0:
                    state.end_ms = at_ms + int(
                        state.spec.start_offset_seconds * 1000
                    )
                    alerts.extend(self._advance_stat_drop_effect_time(state, at_ms))
                else:
                    state.end_ms = None
                continue

            if self._event_matches_trigger(event, state.spec.trigger):
                if (
                    state.spec.start_trigger is not None
                    and state.last_start_at_ms is None
                ):
                    continue
                if (
                    state.spec.ignore_trigger_while_active
                    and state.end_ms is not None
                ):
                    rearm_ms = int(state.spec.trigger_rearm_tolerance_seconds * 1000)
                    if at_ms < state.end_ms - rearm_ms:
                        continue
                    if rearm_ms > 0 and at_ms > state.end_ms + rearm_ms:
                        continue
                dedupe_ms = int(state.spec.trigger_dedupe_seconds * 1000)
                if (
                    dedupe_ms > 0
                    and state.last_trigger_at_ms is not None
                    and at_ms - state.last_trigger_at_ms < dedupe_ms
                ):
                    continue
                state.active = True
                state.ended_fired = False
                state.last_trigger_at_ms = at_ms
                state.fired_thresholds.clear()
                self._reset_stat_drop_effect_timer_sync(state)
                if state.spec.timer_enabled and state.spec.duration_seconds > 0:
                    state.end_ms = at_ms + state.spec.duration_seconds * 1000
                    alerts.extend(self._advance_stat_drop_effect_time(state, at_ms))
                else:
                    state.end_ms = None
        return alerts

    def _process_boss_hp_entity_lifecycle(self, event: dict[str, Any]) -> None:
        if event.get("EventId") != ENTITY_REMOVED_EVENT_ID:
            return
        at_ms = int(event.get("At", 0))
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        state = self.boss_hp_alert_states.get(event_entity_id)
        if state is None:
            return
        if state.tracked_entity_id != event_entity_id:
            self.boss_hp_alert_states.pop(event_entity_id, None)
            return
        if self.battle_timer_active or self._should_keep_boss_hp_phase_handoff(state):
            state.tracked_entity_id = None
            state.phase_handoff_until_ms = at_ms + BOSS_HP_PHASE_HANDOFF_GRACE_MS
            self.boss_hp_alert_states.pop(event_entity_id, None)
            return
        self._reset_boss_hp_state(state)
        self._resync_magic_shield_missing_schedule(at_ms)

    def _process_boss_hp_stats(self, event: dict[str, Any]) -> list[FiredAlert]:
        if not self.boss_hp_alert_states and not self.boss_hp_alert_states_by_max_hp:
            return []

        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        current_values = _event_stat_values(event)
        max_hp = current_values.get(BOSS_HP_MAX_STAT_ID)
        state = self.boss_hp_alert_states.get(event_entity_id)
        if state is None:
            state = self._boss_hp_state_for_max_hp(max_hp)
        if state is None:
            return []

        current_hp = current_values.get(state.spec.current_hp_stat_id)
        max_hp = current_values.get(state.spec.max_hp_stat_id)
        if current_hp is None or max_hp is None or max_hp <= 0:
            return []

        at_ms = int(event.get("At", 0))
        if (
            state.phase_handoff_until_ms is not None
            and at_ms > state.phase_handoff_until_ms
        ):
            self._reset_boss_hp_state(state)
        current_hp = max(0.0, current_hp)
        raw_percent = max(0.0, min(100.0, current_hp / max_hp * 100.0))
        percent = self._boss_hp_logical_percent(state, raw_percent)
        if event_entity_id and state.tracked_entity_id != event_entity_id:
            self._bind_boss_hp_state_to_entity(state, event_entity_id, percent, at_ms)
            state.last_current_hp = current_hp
            state.last_max_hp = max_hp
            state.last_raw_percent = raw_percent
            self._resync_magic_shield_missing_schedule(at_ms)
            return []

        if current_hp <= 0:
            self._reset_boss_hp_state(state)
            self._resync_magic_shield_missing_schedule(at_ms)
            return []

        if not state.active:
            state.active = True
            state.previous_percent = percent
            state.fired_thresholds = {
                rule.threshold_percent
                for rule in state.spec.alerts
                if percent <= rule.threshold_percent
            }
            state.last_seen_at_ms = at_ms
            state.last_current_hp = current_hp
            state.last_max_hp = max_hp
            state.last_raw_percent = raw_percent
            self._resync_magic_shield_missing_schedule(at_ms)
            return []

        previous_percent = state.previous_percent
        alerts: list[FiredAlert] = []
        if previous_percent is not None:
            for rule in state.spec.alerts:
                threshold = rule.threshold_percent
                if threshold in state.fired_thresholds:
                    continue
                if previous_percent > threshold >= percent:
                    state.fired_thresholds.add(threshold)
                    message, sound = self._boss_hp_alert_payload(
                        state.spec, rule, at_ms
                    )
                    alerts.append(
                        FiredAlert(
                            at_ms=at_ms,
                            kind="boss_hp",
                            name=state.spec.short_name or state.spec.name,
                            ccid=None,
                            remaining_seconds=None,
                            message=message,
                            sound=sound,
                            volume=state.spec.audio_volume,
                        )
                    )

        state.previous_percent = percent
        state.last_seen_at_ms = at_ms
        state.last_current_hp = current_hp
        state.last_max_hp = max_hp
        state.last_raw_percent = raw_percent
        self._resync_magic_shield_missing_schedule(at_ms)
        return alerts

    def _boss_hp_alert_payload(
        self,
        spec: BossHpAlertSpec,
        rule: BossHpAlertRule,
        at_ms: int,
    ) -> tuple[str, str]:
        message = rule.message
        sound = rule.sound
        seconds = self._boss_hp_safehouse_countdown_seconds(spec, at_ms)
        if seconds is None:
            return message, sound

        try:
            message = spec.safehouse_countdown_message_template.format(
                message=message,
                seconds=seconds,
            )
        except (KeyError, ValueError):
            message = f"{message}，安全屋{seconds}秒"

        countdown_sound = self._boss_hp_safehouse_countdown_sound(spec, seconds)
        if countdown_sound:
            sound = make_sound_sequence(sound, countdown_sound)
        return message, sound

    def _boss_hp_safehouse_countdown_seconds(
        self,
        spec: BossHpAlertSpec,
        at_ms: int,
    ) -> int | None:
        if (
            not spec.safehouse_countdown_enabled
            or not spec.safehouse_countdown_effect_name
        ):
            return None

        for state in self.stat_drop_effect_states:
            if state.spec.name != spec.safehouse_countdown_effect_name:
                continue
            if (
                not state.active
                or state.end_ms is None
                or not state.spec.repeat_timer
                or state.spec.duration_seconds <= 0
            ):
                return None

            end_ms = state.end_ms
            interval_ms = state.spec.duration_seconds * 1000
            while end_ms <= at_ms:
                end_ms += interval_ms
            seconds = max(0, math.ceil((end_ms - at_ms) / 1000))
            if seconds < spec.safehouse_countdown_min_seconds:
                return None
            if seconds > spec.safehouse_countdown_max_seconds:
                return None
            return seconds
        return None

    @staticmethod
    def _boss_hp_safehouse_countdown_sound(
        spec: BossHpAlertSpec,
        seconds: int,
    ) -> str | None:
        sound_path = (
            Path(spec.safehouse_countdown_sound_dir)
            / f"safehouse_{seconds:02d}.wav"
        )
        if sound_path.is_file():
            return str(sound_path)
        return None

    def _process_boss_skill_burst_entity_lifecycle(self, event: dict[str, Any]) -> None:
        if event.get("EventId") != ENTITY_REMOVED_EVENT_ID:
            return
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        state = self.boss_skill_burst_alert_states.get(event_entity_id)
        if state is None or state.tracked_entity_id != event_entity_id:
            return
        self._reset_boss_skill_burst_state(state)

    def _process_boss_skill_burst_stats(self, event: dict[str, Any]) -> None:
        if (
            not self.boss_skill_burst_alert_states
            and not self.boss_skill_burst_alert_states_by_max_hp
        ):
            return

        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        current_values = _event_stat_values(event)
        max_hp = current_values.get(BOSS_HP_MAX_STAT_ID)
        state = self.boss_skill_burst_alert_states.get(event_entity_id)
        if state is None:
            state = self._boss_skill_burst_state_for_max_hp(max_hp)
        if state is None:
            return

        current_hp = current_values.get(BOSS_HP_CURRENT_STAT_ID)
        if current_hp is not None and current_hp <= 0:
            self._reset_boss_skill_burst_state(state)
            return

        at_ms = int(event.get("At", 0))
        if event_entity_id and state.tracked_entity_id != event_entity_id:
            self._bind_boss_skill_burst_state_to_entity(state, event_entity_id)
        state.active = True
        if state.current_burst_last_at_ms is not None:
            stale_ms = max(
                state.spec.repeat_window_ms * 2,
                int(state.spec.dedupe_seconds * 1000),
            )
            if at_ms - state.current_burst_last_at_ms > stale_ms:
                state.current_burst_started_at_ms = None
                state.current_burst_last_at_ms = None
                state.previous_burst_started_at_ms = None

    def _process_boss_skill_burst_event(
        self, event: dict[str, Any]
    ) -> list[FiredAlert]:
        if event.get("EventId") != 3:
            return []
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return []
        state = self.boss_skill_burst_alert_states.get(event_entity_id)
        if state is None or state.tracked_entity_id != event_entity_id:
            return []
        if not state.active:
            return []
        if int(event.get("SkillId", -1)) != state.spec.skill_id:
            return []

        at_ms = int(event.get("At", 0))
        if state.current_burst_last_at_ms is not None and at_ms < state.current_burst_last_at_ms:
            state.current_burst_started_at_ms = None
            state.current_burst_last_at_ms = None
            state.previous_burst_started_at_ms = None

        burst_window_ms = max(0, int(state.spec.burst_window_ms))
        repeat_window_ms = max(1, int(state.spec.repeat_window_ms))
        if (
            state.current_burst_last_at_ms is not None
            and at_ms - state.current_burst_last_at_ms <= burst_window_ms
        ):
            state.current_burst_last_at_ms = at_ms
            return []

        previous_burst_started_at_ms = state.current_burst_started_at_ms
        state.previous_burst_started_at_ms = previous_burst_started_at_ms
        state.current_burst_started_at_ms = at_ms
        state.current_burst_last_at_ms = at_ms
        if previous_burst_started_at_ms is None:
            return []
        if at_ms - previous_burst_started_at_ms > repeat_window_ms:
            return []

        dedupe_ms = int(max(0.0, state.spec.dedupe_seconds) * 1000)
        if (
            state.last_fired_at_ms is not None
            and at_ms - state.last_fired_at_ms < dedupe_ms
        ):
            return []
        state.last_fired_at_ms = at_ms
        return [
            FiredAlert(
                at_ms=at_ms,
                kind="boss_skill_burst",
                name=state.spec.name,
                ccid=None,
                remaining_seconds=None,
                message=state.spec.message,
                sound=state.spec.sound,
                volume=state.spec.audio_volume,
            )
        ]

    def _boss_skill_burst_state_for_max_hp(
        self, max_hp: float | int | None
    ) -> BossSkillBurstAlertState | None:
        if max_hp is None:
            return None
        return self.boss_skill_burst_alert_states_by_max_hp.get(
            self._boss_hp_fingerprint_key(max_hp)
        )

    def _bind_boss_skill_burst_state_to_entity(
        self,
        state: BossSkillBurstAlertState,
        entity_id: str,
    ) -> None:
        if state.tracked_entity_id and state.tracked_entity_id != entity_id:
            self.boss_skill_burst_alert_states.pop(state.tracked_entity_id, None)
        state.tracked_entity_id = entity_id
        state.active = True
        state.current_burst_started_at_ms = None
        state.current_burst_last_at_ms = None
        state.previous_burst_started_at_ms = None
        state.last_fired_at_ms = None
        self.boss_skill_burst_alert_states[entity_id] = state

    def _reset_all_boss_skill_burst_states(self) -> None:
        seen: set[int] = set()
        for state in list(self.boss_skill_burst_alert_states.values()) + list(
            self.boss_skill_burst_alert_states_by_max_hp.values()
        ):
            state_id = id(state)
            if state_id in seen:
                continue
            seen.add(state_id)
            self._reset_boss_skill_burst_state(state)

    def _reset_boss_skill_burst_state(
        self, state: BossSkillBurstAlertState
    ) -> None:
        if state.tracked_entity_id:
            self.boss_skill_burst_alert_states.pop(state.tracked_entity_id, None)
        state.tracked_entity_id = None
        state.active = False
        state.current_burst_started_at_ms = None
        state.current_burst_last_at_ms = None
        state.previous_burst_started_at_ms = None
        state.last_fired_at_ms = None

    def _process_boss_red_orb_stats(self, event: dict[str, Any]) -> None:
        if (
            not self.boss_red_orb_alert_states
            and not self.boss_red_orb_alert_states_by_max_hp
        ):
            return

        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        current_values = _event_stat_values(event)
        max_hp = current_values.get(BOSS_HP_MAX_STAT_ID)
        state = self.boss_red_orb_alert_states.get(event_entity_id)
        if state is None:
            state = self._boss_red_orb_state_for_max_hp(max_hp)
        if state is None:
            return

        current_hp = current_values.get(BOSS_HP_CURRENT_STAT_ID)
        if current_hp is not None and current_hp <= 0:
            self._reset_boss_red_orb_state(state)
            return

        at_ms = int(event.get("At", 0))
        if event_entity_id and state.tracked_entity_id != event_entity_id:
            self._bind_boss_red_orb_state_to_entity(state, event_entity_id)
        state.active = True
        state.last_seen_at_ms = at_ms
        if current_hp is not None:
            state.last_current_hp = float(current_hp)
        if max_hp is not None:
            state.last_max_hp = float(max_hp)

    def _process_boss_red_orb_entity_lifecycle(self, event: dict[str, Any]) -> None:
        event_id = event.get("EventId")
        if event_id not in (ENTITY_REMOVED_EVENT_ID, 15):
            return
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return

        state = self.boss_red_orb_alert_states.get(event_entity_id)
        if state is not None and state.tracked_entity_id == event_entity_id:
            self._reset_boss_red_orb_state(state)
            return

        for state in self._unique_boss_red_orb_states():
            pending_start_at_ms = state.orb_entity_to_pending.get(event_entity_id)
            if pending_start_at_ms is None:
                at_ms = int(event.get("At", 0))
                for pending in state.pending_alerts:
                    if (
                        pending.canceled
                        or at_ms < pending.start_at_ms
                        or at_ms > pending.explosion_at_ms + 1000
                    ):
                        continue
                    pending.removed_orb_entity_ids.add(event_entity_id)
                    if self._boss_red_orb_should_cancel_for_removed_orbs(pending):
                        self._cancel_boss_red_orb_countdown(pending)
                        pending.canceled = True
                continue
            pending = self._boss_red_orb_pending_by_start(
                state, pending_start_at_ms
            )
            if pending is None:
                state.orb_entity_to_pending.pop(event_entity_id, None)
                continue
            pending.removed_orb_entity_ids.add(event_entity_id)
            if self._boss_red_orb_should_cancel_for_removed_orbs(pending):
                self._cancel_boss_red_orb_countdown(pending)
                pending.canceled = True
            return

    def _process_boss_red_orb_event(
        self, event: dict[str, Any]
    ) -> list[FiredAlert]:
        if (
            not self.boss_red_orb_alert_states
            and not self.boss_red_orb_alert_states_by_max_hp
        ):
            return []

        event_id = event.get("EventId")
        if event_id == 1:
            return self._process_boss_red_orb_spawn(event)
        if event_id == 3:
            return self._process_boss_red_orb_damage_event(event)
        if event_id != 0:
            return []

        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return []

        state = self.boss_red_orb_alert_states.get(event_entity_id)
        if state is not None and state.tracked_entity_id == event_entity_id:
            self._process_boss_red_orb_countdown_event(state, event)
            return []

        for state in self._unique_boss_red_orb_states():
            pending_start_at_ms = state.orb_entity_to_pending.get(event_entity_id)
            if pending_start_at_ms is None:
                continue
            return self._process_boss_red_orb_orb_event(
                state, pending_start_at_ms, event
            )
        return []

    def _process_boss_red_orb_countdown_event(
        self, state: BossRedOrbAlertState, event: dict[str, Any]
    ) -> None:
        spec = state.spec
        if str(event.get("Op", "")).lower() != spec.countdown_op.lower():
            return
        messages = event.get("Msg") or []
        if len(messages) < 2:
            return
        first = messages[0] if isinstance(messages[0], dict) else {}
        second = messages[1] if isinstance(messages[1], dict) else {}
        marker = str(first.get("V"))
        step = str(second.get("V"))
        if marker != spec.countdown_marker:
            return

        at_ms = int(event.get("At", 0))
        if step == spec.start_step:
            state.pending_start_at_ms = at_ms
            return
        if step != spec.confirm_step or state.pending_start_at_ms is None:
            return
        if at_ms - state.pending_start_at_ms > spec.pair_window_ms:
            state.pending_start_at_ms = None
            return

        start_at_ms = state.pending_start_at_ms
        state.pending_start_at_ms = None
        if self._boss_red_orb_pending_by_start(state, start_at_ms) is not None:
            return

        hp_percent = self._boss_red_orb_hp_percent(state)
        (
            profile_name,
            explosion_delay_seconds,
            required_contact_ticks,
            early_check_seconds,
            early_max_contact_ticks,
            final_check_seconds,
        ) = self._boss_red_orb_profile_for_hp(spec, hp_percent)
        explosion_delay_ms = int(explosion_delay_seconds * 1000)
        explosion_at_ms = start_at_ms + explosion_delay_ms
        early_warn_at_ms = start_at_ms + int(early_check_seconds * 1000)
        final_warn_at_ms = start_at_ms + int(final_check_seconds * 1000)
        lead_warn_at_ms = explosion_at_ms - int(spec.lead_seconds * 1000)
        final_warn_at_ms = min(max(final_warn_at_ms, early_warn_at_ms), lead_warn_at_ms)
        warn_at_ms = min(early_warn_at_ms, final_warn_at_ms)
        pending = BossRedOrbPendingState(
            boss_entity_id=state.tracked_entity_id or "",
            start_at_ms=start_at_ms,
            confirm_at_ms=at_ms,
            warn_at_ms=max(start_at_ms, warn_at_ms),
            explosion_at_ms=explosion_at_ms,
            final_warn_at_ms=max(start_at_ms, final_warn_at_ms),
            early_warn_max_contact_ticks=early_max_contact_ticks,
            required_contact_ticks=required_contact_ticks,
            hp_percent=hp_percent,
            profile_name=profile_name,
            confirmed=True,
        )
        state.pending_alerts.append(pending)
        self._prune_boss_red_orb_pending(state, at_ms)

    @staticmethod
    def _boss_red_orb_hp_percent(state: BossRedOrbAlertState) -> float | None:
        if (
            state.last_current_hp is None
            or state.last_max_hp is None
            or state.last_max_hp <= 0
        ):
            return None
        return max(0.0, min(100.0, state.last_current_hp / state.last_max_hp * 100))

    @staticmethod
    def _boss_red_orb_profile_for_hp(
        spec: BossRedOrbAlertSpec, hp_percent: float | None
    ) -> tuple[str, float, int, float, int, float]:
        if hp_percent is not None and hp_percent > spec.hp_split_percent:
            return (
                "high_hp",
                spec.high_hp_explosion_delay_seconds,
                spec.high_hp_required_contact_ticks,
                spec.high_hp_early_check_seconds,
                spec.high_hp_early_max_contact_ticks,
                spec.high_hp_final_check_seconds,
            )
        return (
            "low_hp",
            spec.low_hp_explosion_delay_seconds,
            spec.low_hp_required_contact_ticks,
            spec.low_hp_early_check_seconds,
            spec.low_hp_early_max_contact_ticks,
            spec.low_hp_final_check_seconds,
        )

    def _process_boss_red_orb_spawn(
        self, event: dict[str, Any]
    ) -> list[FiredAlert]:
        owner_id = "" if event.get("OwnerId") is None else str(event.get("OwnerId"))
        if not owner_id:
            return []
        state = self.boss_red_orb_alert_states.get(owner_id)
        if state is None or state.tracked_entity_id != owner_id:
            return []
        try:
            race_id = int(event.get("RaceId"))
        except (TypeError, ValueError):
            return []
        if race_id not in set(state.spec.orb_race_ids):
            return []

        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return []
        at_ms = int(event.get("At", 0))
        pending = self._boss_red_orb_pending_for_orb_spawn(state, at_ms)
        if pending is None:
            return []
        pending.orb_entity_ids.add(event_entity_id)
        state.orb_entity_to_pending[event_entity_id] = pending.start_at_ms
        pending.confirmed = True
        if at_ms >= pending.warn_at_ms:
            return self._fire_boss_red_orb_alert_if_live(state, pending, at_ms)
        return []

    def _process_boss_red_orb_damage_event(
        self, event: dict[str, Any]
    ) -> list[FiredAlert]:
        try:
            skill_id = int(event.get("SkillId"))
        except (TypeError, ValueError):
            return []
        if skill_id != DEFAULT_BOSS_RED_ORB_DAMAGE_SKILL_ID:
            return []

        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return []
        state = self.boss_red_orb_alert_states.get(event_entity_id)
        if state is None or state.tracked_entity_id != event_entity_id:
            return []

        try:
            damage = float(event.get("Damage") or 0)
        except (TypeError, ValueError):
            damage = 0.0
        try:
            mana_damage = float(event.get("ManaDamage") or 0)
        except (TypeError, ValueError):
            mana_damage = 0.0
        if (
            damage >= DEFAULT_BOSS_RED_ORB_DAMAGE_ACTIVITY_MAX
            or mana_damage >= DEFAULT_BOSS_RED_ORB_DAMAGE_ACTIVITY_MAX
        ):
            return []

        at_ms = int(event.get("At", 0))
        alerts: list[FiredAlert] = []
        for pending in list(state.pending_alerts):
            if pending.canceled:
                continue
            if at_ms < pending.start_at_ms:
                continue
            # Ignore the actual explosion moment; this fallback is only for
            # small contact ticks that prove the orb is still being handled.
            if at_ms >= pending.explosion_at_ms - 500:
                continue
            pending.confirmed = True
            pending.last_activity_at_ms = at_ms
            pending.contact_at_mses.append(at_ms)
            if pending.fired:
                if self._boss_red_orb_is_safe_by_contact_rule(state, pending):
                    alerts.extend(
                        self._complete_boss_red_orb_after_alert(
                            state, pending, at_ms
                        )
                    )
                continue
            if at_ms >= pending.warn_at_ms:
                alerts.extend(
                    self._fire_boss_red_orb_alert_if_live(state, pending, at_ms)
                )
        return alerts

    def _process_boss_red_orb_orb_event(
        self,
        state: BossRedOrbAlertState,
        pending_start_at_ms: int,
        event: dict[str, Any],
    ) -> list[FiredAlert]:
        pending = self._boss_red_orb_pending_by_start(state, pending_start_at_ms)
        if pending is None or pending.canceled or pending.fired:
            return []
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if event_entity_id in pending.removed_orb_entity_ids:
            return []
        if str(event.get("Op", "")).lower() != state.spec.late_confirm_op.lower():
            return []

        at_ms = int(event.get("At", 0))
        start_ms = pending.start_at_ms + int(
            state.spec.late_confirm_start_seconds * 1000
        )
        end_ms = pending.start_at_ms + int(state.spec.late_confirm_end_seconds * 1000)
        if at_ms < start_ms or at_ms > end_ms:
            return []

        pending.confirmed = True
        if self._boss_red_orb_should_cancel_for_removed_orbs(pending):
            pending.canceled = True
            return []
        if at_ms >= pending.warn_at_ms:
            return self._fire_boss_red_orb_alert_if_live(state, pending, at_ms)
        return []

    def _advance_boss_red_orb_time(self, at_ms: int) -> list[FiredAlert]:
        alerts: list[FiredAlert] = []
        for state in self._unique_boss_red_orb_states():
            self._prune_boss_red_orb_pending(state, at_ms)
            for pending in list(state.pending_alerts):
                if pending.canceled or pending.fired:
                    continue
                if self._boss_red_orb_should_cancel_for_removed_orbs(pending):
                    pending.canceled = True
                    continue
                if at_ms >= pending.warn_at_ms:
                    alerts.extend(
                        self._fire_boss_red_orb_alert_if_live(state, pending, at_ms)
                    )
        return alerts

    def _fire_boss_red_orb_alert_if_live(
        self,
        state: BossRedOrbAlertState,
        pending: BossRedOrbPendingState,
        at_ms: int,
    ) -> list[FiredAlert]:
        if self._boss_red_orb_should_cancel_for_removed_orbs(pending):
            pending.canceled = True
            return []
        if self._boss_red_orb_is_safe_by_contact_rule(state, pending):
            self._cancel_boss_red_orb_countdown(pending)
            pending.canceled = True
            return []
        if at_ms < pending.warn_at_ms and not self._boss_red_orb_has_active_evidence(
            state, pending, at_ms
        ):
            return []
        contact_ticks = self._boss_red_orb_contact_tick_count(state, pending)
        final_warn_at_ms = pending.final_warn_at_ms or pending.warn_at_ms
        if at_ms < final_warn_at_ms:
            early_max = pending.early_warn_max_contact_ticks
            if early_max is not None and contact_ticks > early_max:
                pending.warn_at_ms = final_warn_at_ms
                return []
        return self._fire_boss_red_orb_alert(state, pending, at_ms)

    def _fire_boss_red_orb_alert(
        self,
        state: BossRedOrbAlertState,
        pending: BossRedOrbPendingState,
        at_ms: int,
    ) -> list[FiredAlert]:
        if pending.canceled or pending.fired:
            return []
        pending.fired = True
        sound = self._boss_red_orb_countdown_sound(state, pending, at_ms) or state.spec.sound
        contact_ticks = self._boss_red_orb_contact_tick_count(state, pending)
        return [
            FiredAlert(
                at_ms=at_ms,
                kind="boss_red_orb",
                name=state.spec.name,
                ccid=None,
                remaining_seconds=max(
                    0, math.ceil((pending.explosion_at_ms - at_ms) / 1000)
                ),
                message=state.spec.message,
                sound=sound,
                volume=state.spec.audio_volume,
                detail={
                    "start_at_ms": pending.start_at_ms,
                    "explosion_at_ms": pending.explosion_at_ms,
                    "hp_percent": (
                        round(pending.hp_percent, 3)
                        if pending.hp_percent is not None
                        else None
                    ),
                    "profile": pending.profile_name,
                    "contact_ticks": contact_ticks,
                    "required_contact_ticks": pending.required_contact_ticks,
                    "raw_contact_packets": len(pending.contact_at_mses),
                    "last_contact_after_start_seconds": (
                        round(
                            (pending.contact_at_mses[-1] - pending.start_at_ms)
                            / 1000,
                            3,
                        )
                        if pending.contact_at_mses
                        else None
                    ),
                },
            )
        ]

    def _complete_boss_red_orb_after_alert(
        self,
        state: BossRedOrbAlertState,
        pending: BossRedOrbPendingState,
        at_ms: int,
    ) -> list[FiredAlert]:
        if pending.canceled or not pending.fired:
            return []
        self._cancel_boss_red_orb_countdown(pending)
        pending.canceled = True
        contact_ticks = self._boss_red_orb_contact_tick_count(state, pending)
        return [
            FiredAlert(
                at_ms=at_ms,
                kind="boss_red_orb_safe",
                name=state.spec.name,
                ccid=None,
                remaining_seconds=max(
                    0, math.ceil((pending.explosion_at_ms - at_ms) / 1000)
                ),
                message=DEFAULT_BOSS_RED_ORB_SAFE_MESSAGE,
                sound=state.spec.safe_sound,
                volume=state.spec.audio_volume,
                detail={
                    "start_at_ms": pending.start_at_ms,
                    "explosion_at_ms": pending.explosion_at_ms,
                    "hp_percent": (
                        round(pending.hp_percent, 3)
                        if pending.hp_percent is not None
                        else None
                    ),
                    "profile": pending.profile_name,
                    "contact_ticks": contact_ticks,
                    "required_contact_ticks": pending.required_contact_ticks,
                    "raw_contact_packets": len(pending.contact_at_mses),
                },
            )
        ]

    def _boss_red_orb_countdown_sound(
        self,
        state: BossRedOrbAlertState,
        pending: BossRedOrbPendingState,
        at_ms: int,
    ) -> str:
        def offset(seconds_before_explosion: float) -> float:
            return max(0.0, (pending.explosion_at_ms - at_ms) / 1000 - seconds_before_explosion)

        count_sounds = {
            **DEFAULT_BOSS_RED_ORB_COUNTDOWN_SOUNDS,
            **state.spec.countdown_sounds,
        }
        return make_timed_sound_sequence(
            (0.0, state.spec.sound),
            (offset(5.0), count_sounds[5]),
            (offset(4.0), count_sounds[4]),
            (offset(3.0), count_sounds[3]),
            (offset(2.0), count_sounds[2]),
            (offset(1.0), count_sounds[1]),
            (offset(0.0), count_sounds[0]),
            cancel_key=AlertEngine._boss_red_orb_countdown_cancel_key(pending),
        )

    @staticmethod
    def _boss_red_orb_is_safe_by_contact_rule(
        state: BossRedOrbAlertState,
        pending: BossRedOrbPendingState,
    ) -> bool:
        return (
            AlertEngine._boss_red_orb_contact_tick_count(state, pending)
            >= pending.required_contact_ticks
        )

    @staticmethod
    def _boss_red_orb_contact_tick_count(
        state: BossRedOrbAlertState,
        pending: BossRedOrbPendingState,
    ) -> int:
        contacts = sorted(
            at_ms
            for at_ms in pending.contact_at_mses
            if pending.start_at_ms <= at_ms <= pending.explosion_at_ms
        )
        if not contacts:
            return 0
        gap_ms = max(0, int(state.spec.contact_group_ms))
        if gap_ms <= 0:
            return len(contacts)
        count = 1
        previous = contacts[0]
        for at_ms in contacts[1:]:
            if at_ms - previous > gap_ms:
                count += 1
            previous = at_ms
        return count

    @staticmethod
    def _boss_red_orb_countdown_cancel_key(
        pending: BossRedOrbPendingState,
    ) -> str:
        return f"boss_red_orb:{pending.boss_entity_id}:{pending.start_at_ms}"

    @staticmethod
    def _cancel_boss_red_orb_countdown(pending: BossRedOrbPendingState) -> None:
        if not pending.fired or pending.sound_canceled:
            return
        pending.sound_canceled = True
        cancel_sound_sequence(AlertEngine._boss_red_orb_countdown_cancel_key(pending))

    def _boss_red_orb_pending_for_orb_spawn(
        self, state: BossRedOrbAlertState, at_ms: int
    ) -> BossRedOrbPendingState | None:
        candidates = [
            pending
            for pending in state.pending_alerts
            if not pending.canceled
            and pending.start_at_ms <= at_ms <= pending.explosion_at_ms + 1000
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda pending: pending.start_at_ms)

    @staticmethod
    def _boss_red_orb_pending_by_start(
        state: BossRedOrbAlertState, start_at_ms: int
    ) -> BossRedOrbPendingState | None:
        for pending in state.pending_alerts:
            if pending.start_at_ms == start_at_ms:
                return pending
        return None

    @staticmethod
    def _boss_red_orb_should_cancel_for_removed_orbs(
        pending: BossRedOrbPendingState,
    ) -> bool:
        # Red-orb entity remove packets are visual/lifecycle hints and can arrive
        # before the actual explosion. They are kept for diagnostics only.
        return False

    @staticmethod
    def _boss_red_orb_has_live_orbs(pending: BossRedOrbPendingState) -> bool:
        return bool(pending.orb_entity_ids - pending.removed_orb_entity_ids)

    def _boss_red_orb_has_active_evidence(
        self,
        state: BossRedOrbAlertState,
        pending: BossRedOrbPendingState,
        at_ms: int,
    ) -> bool:
        if self._boss_red_orb_has_live_orbs(pending):
            return True
        if pending.last_activity_at_ms is None:
            return False
        activity_window_ms = max(1000, int(state.spec.lead_seconds * 1000))
        return (
            pending.warn_at_ms - activity_window_ms
            <= pending.last_activity_at_ms
            <= min(at_ms, pending.explosion_at_ms)
        )

    def _prune_boss_red_orb_pending(
        self, state: BossRedOrbAlertState, at_ms: int
    ) -> None:
        stale_ms = int(state.spec.stale_seconds * 1000)
        keep: list[BossRedOrbPendingState] = []
        active_starts: set[int] = set()
        for pending in state.pending_alerts:
            if at_ms - pending.start_at_ms <= stale_ms:
                keep.append(pending)
                active_starts.add(pending.start_at_ms)
        state.pending_alerts = keep
        for entity_id, start_at_ms in list(state.orb_entity_to_pending.items()):
            if start_at_ms not in active_starts:
                state.orb_entity_to_pending.pop(entity_id, None)

    def _boss_red_orb_state_for_max_hp(
        self, max_hp: float | int | None
    ) -> BossRedOrbAlertState | None:
        if max_hp is None:
            return None
        return self.boss_red_orb_alert_states_by_max_hp.get(
            self._boss_hp_fingerprint_key(max_hp)
        )

    def _bind_boss_red_orb_state_to_entity(
        self,
        state: BossRedOrbAlertState,
        entity_id: str,
    ) -> None:
        if state.tracked_entity_id and state.tracked_entity_id != entity_id:
            self.boss_red_orb_alert_states.pop(state.tracked_entity_id, None)
        for pending in state.pending_alerts:
            self._cancel_boss_red_orb_countdown(pending)
        state.tracked_entity_id = entity_id
        state.active = True
        state.pending_start_at_ms = None
        state.pending_alerts.clear()
        state.orb_entity_to_pending.clear()
        self.boss_red_orb_alert_states[entity_id] = state

    def _reset_all_boss_red_orb_states(self) -> None:
        for state in self._unique_boss_red_orb_states():
            self._reset_boss_red_orb_state(state)

    def _reset_boss_red_orb_state(self, state: BossRedOrbAlertState) -> None:
        if state.tracked_entity_id:
            self.boss_red_orb_alert_states.pop(state.tracked_entity_id, None)
        for pending in state.pending_alerts:
            self._cancel_boss_red_orb_countdown(pending)
        state.tracked_entity_id = None
        state.active = False
        state.last_seen_at_ms = None
        state.last_current_hp = None
        state.last_max_hp = None
        state.pending_start_at_ms = None
        state.pending_alerts.clear()
        state.orb_entity_to_pending.clear()

    def _unique_boss_red_orb_states(self) -> list[BossRedOrbAlertState]:
        seen: set[int] = set()
        states: list[BossRedOrbAlertState] = []
        for state in list(self.boss_red_orb_alert_states.values()) + list(
            self.boss_red_orb_alert_states_by_max_hp.values()
        ):
            state_id = id(state)
            if state_id in seen:
                continue
            seen.add(state_id)
            states.append(state)
        return states

    def _process_boss_laser_stats(self, event: dict[str, Any]) -> None:
        if (
            not self.boss_laser_alert_states
            and not self.boss_laser_alert_states_by_max_hp
        ):
            return

        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return

        current_values = _event_stat_values(event)
        state = self.boss_laser_alert_states.get(event_entity_id)
        if state is None:
            max_hp = current_values.get(BOSS_HP_MAX_STAT_ID)
            state = self._boss_laser_state_for_max_hp(max_hp)
        if state is not None:
            current_hp = current_values.get(state.spec.current_hp_stat_id)
            if current_hp is not None and current_hp <= 0:
                self._reset_boss_laser_state(state)
                return
            at_ms = int(event.get("At", 0))
            if event_entity_id and state.tracked_entity_id != event_entity_id:
                self._bind_boss_laser_state_to_entity(state, event_entity_id)
            state.active = True
            state.last_seen_at_ms = at_ms
            if current_hp is not None:
                state.last_current_hp = float(current_hp)
            max_hp = current_values.get(state.spec.max_hp_stat_id)
            if max_hp is not None:
                state.last_max_hp = float(max_hp)
            return

        state = self.boss_laser_stardust_to_state.get(event_entity_id)
        if state is None:
            return
        current_hp = current_values.get(BOSS_HP_CURRENT_STAT_ID)
        if current_hp is not None and current_hp <= 0:
            self._mark_boss_laser_stardust_removed(
                state, event_entity_id, int(event.get("At", 0))
            )

    def _process_boss_laser_entity_lifecycle(self, event: dict[str, Any]) -> None:
        if (
            not self.boss_laser_alert_states
            and not self.boss_laser_alert_states_by_max_hp
        ):
            return

        event_id = event.get("EventId")
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return

        if event_id == 1:
            owner_id = "" if event.get("OwnerId") is None else str(event.get("OwnerId"))
            try:
                race_id = int(event.get("RaceId"))
            except (TypeError, ValueError):
                return
            state = self.boss_laser_alert_states.get(owner_id)
            if state is None or state.tracked_entity_id != owner_id:
                if any(
                    race_id in candidate.spec.stardust_race_ids
                    for candidate in self._unique_boss_laser_states()
                ):
                    self.boss_laser_pending_stardust_by_owner.setdefault(
                        owner_id, set()
                    ).add(event_entity_id)
                    self.boss_laser_pending_stardust_race_by_entity_id[
                        event_entity_id
                    ] = race_id
                return
            if race_id not in set(state.spec.stardust_race_ids):
                return
            state.stardust_entity_ids.add(event_entity_id)
            state.stardust_race_ids_by_entity_id[event_entity_id] = race_id
            state.stardust_removed_entity_ids.discard(event_entity_id)
            self.boss_laser_stardust_to_state[event_entity_id] = state
            return

        if event_id not in (ENTITY_REMOVED_EVENT_ID, 15):
            return
        state = self.boss_laser_alert_states.get(event_entity_id)
        if state is not None and state.tracked_entity_id == event_entity_id:
            self._reset_boss_laser_state(state)
            return
        state = self.boss_laser_stardust_to_state.get(event_entity_id)
        if state is None:
            self.boss_laser_pending_stardust_race_by_entity_id.pop(
                event_entity_id, None
            )
            return
        self._mark_boss_laser_stardust_removed(
            state, event_entity_id, int(event.get("At", 0))
        )

    def _process_boss_laser_event(self, event: dict[str, Any]) -> list[FiredAlert]:
        if event.get("EventId") != 0:
            return []
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return []
        state = self.boss_laser_stardust_to_state.get(event_entity_id)
        if state is None or not state.active or not state.tracked_entity_id:
            return []

        spec = state.spec
        if str(event.get("Op", "")).lower() != spec.cast_op.lower():
            return []
        messages = event.get("Msg") or []
        if not messages or not isinstance(messages[0], dict):
            return []
        message_skill_id = str(messages[0].get("V"))
        message_mode = ""
        if len(messages) > 1 and isinstance(messages[1], dict):
            message_mode = str(messages[1].get("V"))
        if message_skill_id == "0" and message_mode == "1":
            self._mark_boss_laser_stardust_removed(
                state, event_entity_id, int(event.get("At", 0))
            )
            return []
        if message_skill_id != str(spec.skill_id):
            return []

        at_ms = int(event.get("At", 0))
        self._prune_boss_laser_pending(state, at_ms)
        pending = self._boss_laser_recent_pending(state, at_ms)
        race_id = state.stardust_race_ids_by_entity_id.get(event_entity_id)
        if pending is not None:
            pending.stardust_entity_ids.add(event_entity_id)
            if race_id is not None:
                pending.stardust_race_ids_by_entity_id[event_entity_id] = race_id
            return []

        impact_at_ms = at_ms + int(max(0.0, spec.cast_seconds) * 1000)
        pending = BossLaserPendingState(
            boss_entity_id=state.tracked_entity_id,
            start_at_ms=at_ms,
            impact_at_ms=impact_at_ms,
            stardust_entity_ids={event_entity_id},
        )
        if race_id is not None:
            pending.stardust_race_ids_by_entity_id[event_entity_id] = race_id
        state.pending_alerts.append(pending)
        return [
            FiredAlert(
                at_ms=at_ms,
                kind="boss_laser",
                name=spec.name,
                ccid=None,
                remaining_seconds=max(0, math.ceil((impact_at_ms - at_ms) / 1000)),
                message=spec.message,
                sound=self._boss_laser_countdown_sound(state, pending),
                volume=spec.audio_volume,
                detail={
                    "boss_entity_id": state.tracked_entity_id,
                    "stardust_entity_id": event_entity_id,
                    "start_at_ms": at_ms,
                    "impact_at_ms": impact_at_ms,
                    "cast_seconds": spec.cast_seconds,
                },
            )
        ]

    def _boss_laser_recent_pending(
        self,
        state: BossLaserAlertState,
        at_ms: int,
    ) -> BossLaserPendingState | None:
        cluster_window_ms = max(0, int(state.spec.cluster_window_ms))
        candidates = [
            pending
            for pending in state.pending_alerts
            if not pending.canceled
            and pending.start_at_ms <= at_ms
            and at_ms - pending.start_at_ms <= cluster_window_ms
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda pending: pending.start_at_ms)

    def _mark_boss_laser_stardust_removed(
        self,
        state: BossLaserAlertState,
        entity_id: str,
        at_ms: int,
    ) -> None:
        state.stardust_removed_entity_ids.add(entity_id)
        for pending in list(state.pending_alerts):
            if pending.canceled:
                continue
            if at_ms < pending.start_at_ms or at_ms > pending.impact_at_ms + 1000:
                continue
            if entity_id not in pending.stardust_entity_ids:
                continue
            pending.removed_stardust_entity_ids.add(entity_id)
            if self._boss_laser_should_cancel_for_removed_stardust(pending):
                self._cancel_boss_laser_countdown(pending)
                pending.canceled = True

    @staticmethod
    def _boss_laser_key_stardust_entity_id(
        pending: BossLaserPendingState,
    ) -> str | None:
        if not pending.stardust_entity_ids:
            return None
        if pending.stardust_entity_ids - set(
            pending.stardust_race_ids_by_entity_id
        ):
            return None
        return min(
            pending.stardust_entity_ids,
            key=lambda entity_id: (
                pending.stardust_race_ids_by_entity_id[entity_id],
                entity_id,
            ),
        )

    @classmethod
    def _boss_laser_should_cancel_for_removed_stardust(
        cls,
        pending: BossLaserPendingState,
    ) -> bool:
        key_stardust_id = cls._boss_laser_key_stardust_entity_id(pending)
        if key_stardust_id is not None:
            return key_stardust_id in pending.removed_stardust_entity_ids
        return bool(pending.stardust_entity_ids) and pending.stardust_entity_ids <= (
            pending.removed_stardust_entity_ids
        )

    @staticmethod
    def _boss_laser_countdown_cancel_key(pending: BossLaserPendingState) -> str:
        return f"boss_laser:{pending.boss_entity_id}:{pending.start_at_ms}"

    @staticmethod
    def _cancel_boss_laser_countdown(pending: BossLaserPendingState) -> None:
        if pending.sound_canceled:
            return
        pending.sound_canceled = True
        cancel_sound_sequence(AlertEngine._boss_laser_countdown_cancel_key(pending))

    @staticmethod
    def _boss_laser_countdown_sound(
        state: BossLaserAlertState,
        pending: BossLaserPendingState,
    ) -> str:
        def offset(seconds_before_impact: float) -> float:
            return max(0.0, state.spec.cast_seconds - seconds_before_impact)

        count_sounds = {
            **DEFAULT_BOSS_LASER_COUNTDOWN_SOUNDS,
            **state.spec.countdown_sounds,
        }
        return make_timed_sound_sequence(
            (0.0, state.spec.sound),
            (offset(4.0), count_sounds[4]),
            (offset(3.0), count_sounds[3]),
            (offset(2.0), count_sounds[2]),
            (offset(1.0), count_sounds[1]),
            (offset(0.0), count_sounds[0]),
            cancel_key=AlertEngine._boss_laser_countdown_cancel_key(pending),
        )

    def _prune_boss_laser_pending(
        self,
        state: BossLaserAlertState,
        at_ms: int,
    ) -> None:
        stale_ms = int(max(1.0, state.spec.stale_seconds) * 1000)
        state.pending_alerts = [
            pending
            for pending in state.pending_alerts
            if at_ms - pending.start_at_ms <= stale_ms
        ]

    def _boss_laser_state_for_max_hp(
        self, max_hp: float | int | None
    ) -> BossLaserAlertState | None:
        if max_hp is None:
            return None
        return self.boss_laser_alert_states_by_max_hp.get(
            self._boss_hp_fingerprint_key(max_hp)
        )

    def _bind_boss_laser_state_to_entity(
        self,
        state: BossLaserAlertState,
        entity_id: str,
    ) -> None:
        if state.tracked_entity_id and state.tracked_entity_id != entity_id:
            self.boss_laser_alert_states.pop(state.tracked_entity_id, None)
        for pending in state.pending_alerts:
            self._cancel_boss_laser_countdown(pending)
        for stardust_id in state.stardust_entity_ids:
            self.boss_laser_stardust_to_state.pop(stardust_id, None)
            self.boss_laser_pending_stardust_race_by_entity_id.pop(stardust_id, None)
        state.tracked_entity_id = entity_id
        state.active = True
        state.stardust_entity_ids.clear()
        state.stardust_race_ids_by_entity_id.clear()
        state.stardust_removed_entity_ids.clear()
        state.pending_alerts.clear()
        self.boss_laser_alert_states[entity_id] = state
        for stardust_id in self.boss_laser_pending_stardust_by_owner.pop(
            entity_id, set()
        ):
            state.stardust_entity_ids.add(stardust_id)
            race_id = self.boss_laser_pending_stardust_race_by_entity_id.pop(
                stardust_id, None
            )
            if race_id is not None:
                state.stardust_race_ids_by_entity_id[stardust_id] = race_id
            state.stardust_removed_entity_ids.discard(stardust_id)
            self.boss_laser_stardust_to_state[stardust_id] = state

    def _reset_all_boss_laser_states(self) -> None:
        for state in self._unique_boss_laser_states():
            self._reset_boss_laser_state(state)
        self.boss_laser_pending_stardust_by_owner.clear()
        self.boss_laser_pending_stardust_race_by_entity_id.clear()

    def _reset_boss_laser_state(self, state: BossLaserAlertState) -> None:
        if state.tracked_entity_id:
            self.boss_laser_alert_states.pop(state.tracked_entity_id, None)
            self.boss_laser_pending_stardust_by_owner.pop(state.tracked_entity_id, None)
        for pending in state.pending_alerts:
            self._cancel_boss_laser_countdown(pending)
        for stardust_id in state.stardust_entity_ids:
            self.boss_laser_stardust_to_state.pop(stardust_id, None)
            self.boss_laser_pending_stardust_race_by_entity_id.pop(stardust_id, None)
        state.tracked_entity_id = None
        state.active = False
        state.last_seen_at_ms = None
        state.last_current_hp = None
        state.last_max_hp = None
        state.stardust_entity_ids.clear()
        state.stardust_race_ids_by_entity_id.clear()
        state.stardust_removed_entity_ids.clear()
        state.pending_alerts.clear()

    def _unique_boss_laser_states(self) -> list[BossLaserAlertState]:
        seen: set[int] = set()
        states: list[BossLaserAlertState] = []
        for state in list(self.boss_laser_alert_states.values()) + list(
            self.boss_laser_alert_states_by_max_hp.values()
        ):
            state_id = id(state)
            if state_id in seen:
                continue
            seen.add(state_id)
            states.append(state)
        return states

    def _process_key_enemy_debuff_stats(self, event: dict[str, Any]) -> None:
        spec = self.key_enemy_debuff_alert
        if spec is None:
            return

        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return

        current_values = _event_stat_values(event)
        max_hp = current_values.get(spec.max_hp_stat_id)
        if self._boss_hp_fingerprint_key(max_hp) not in self.key_enemy_debuff_max_hp_keys:
            state = self.key_enemy_debuff_entity_states.get(event_entity_id)
            if state is None:
                return
            max_hp = state.last_max_hp

        current_hp = current_values.get(spec.current_hp_stat_id)
        if current_hp is not None and current_hp <= 0:
            self._reset_key_enemy_debuff_entity(event_entity_id)
            return

        state = self.key_enemy_debuff_entity_states.get(event_entity_id)
        if state is None:
            self._reset_other_key_enemy_debuff_entities(event_entity_id)
            state = KeyEnemyDebuffEntityState(
                spec=spec,
                tracked_entity_id=event_entity_id,
            )
            self.key_enemy_debuff_entity_states[event_entity_id] = state
        state.active = True
        state.last_seen_at_ms = int(event.get("At", 0))
        if current_hp is not None:
            state.last_current_hp = float(current_hp)
        if max_hp is not None:
            state.last_max_hp = float(max_hp)

    def _process_key_enemy_debuff_entity_lifecycle(self, event: dict[str, Any]) -> None:
        if event.get("EventId") != ENTITY_REMOVED_EVENT_ID:
            return
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if event_entity_id:
            self._reset_key_enemy_debuff_entity(event_entity_id)

    def _process_key_enemy_debuff_event(
        self, event: dict[str, Any]
    ) -> list[FiredAlert]:
        spec = self.key_enemy_debuff_alert
        if spec is None or event.get("EventId") not in (4, 5):
            return []

        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return []
        entity_state = self.key_enemy_debuff_entity_states.get(event_entity_id)
        if entity_state is None or not entity_state.active:
            return []

        try:
            ccid = int(event.get("CCId"))
        except (TypeError, ValueError):
            return []
        requirement_key = KEY_ENEMY_DEBUFF_CCID_TO_REQUIREMENT.get(ccid)
        watched_spec = self.key_enemy_watched_debuffs_by_ccid.get(ccid)
        if requirement_key is None and watched_spec is None:
            return []

        at_ms = int(event.get("At", 0))
        alerts: list[FiredAlert] = []
        alerts.extend(self._advance_key_enemy_watched_debuff_time(entity_state, at_ms))
        self._expire_key_enemy_debuff_entity(entity_state, at_ms)
        self._settle_key_enemy_debuff_complete_latch(entity_state, at_ms)

        if watched_spec is not None:
            alerts.extend(
                self._process_key_enemy_watched_debuff_event(
                    entity_state,
                    watched_spec,
                    ccid,
                    event,
                    at_ms,
                )
            )
            if requirement_key is None:
                alerts.extend(self._advance_key_enemy_debuff_time(at_ms))
                return alerts

        requirement_state = entity_state.requirements[requirement_key]
        expiry_requirement_state = entity_state.expiry_requirements[requirement_key]
        if event.get("EventId") == 5:
            previous_expiry_end_ms = expiry_requirement_state.end_ms
            self._remove_key_enemy_debuff_requirement_instance(
                expiry_requirement_state, ccid
            )
            self._refresh_key_enemy_debuff_requirement_state(
                expiry_requirement_state
            )
            if previous_expiry_end_ms != expiry_requirement_state.end_ms:
                expiry_requirement_state.warned_end_ms = None
                expiry_requirement_state.ended_fired_end_ms = None

            if self._key_enemy_debuff_remove_matches_rejected_instance(
                requirement_state, ccid, at_ms
            ):
                return alerts
            previous_active = requirement_state.active
            previous_end_ms = requirement_state.end_ms
            self._remove_key_enemy_debuff_requirement_instance(
                requirement_state, ccid
            )
            self._refresh_key_enemy_debuff_requirement_state(requirement_state)
            if previous_end_ms != requirement_state.end_ms:
                requirement_state.warned_end_ms = None
                requirement_state.ended_fired_end_ms = None
            if previous_active and not requirement_state.active:
                self._mark_key_enemy_debuff_incomplete(entity_state, at_ms)
            return alerts

        previous_expiry_end_ms = expiry_requirement_state.end_ms
        end_ms = self._key_enemy_debuff_event_end_ms(event, at_ms)
        self._add_key_enemy_debuff_requirement_instance(
            expiry_requirement_state, ccid, end_ms
        )
        self._refresh_key_enemy_debuff_requirement_state(expiry_requirement_state)
        if previous_expiry_end_ms != expiry_requirement_state.end_ms:
            expiry_requirement_state.warned_end_ms = None
            expiry_requirement_state.ended_fired_end_ms = None
        if (
            end_ms is not None
            and expiry_requirement_state.end_ms == end_ms
            and end_ms - at_ms <= int(spec.expiry_seconds * 1000)
        ):
            # Short debuffs such as kart bubble can be valid, but applying them
            # should not immediately sound like an overdue renewal at pull.
            expiry_requirement_state.warned_end_ms = end_ms

        if not self._key_enemy_debuff_apply_is_successful(spec, requirement_key, event):
            rejected_end_ms = self._key_enemy_debuff_event_end_ms(event, at_ms)
            if rejected_end_ms is not None:
                rejected_instances = (
                    requirement_state.rejected_instance_end_ms_by_ccid.setdefault(
                        ccid, []
                    )
                )
                if rejected_end_ms not in rejected_instances:
                    rejected_instances.append(rejected_end_ms)
            self._prune_key_enemy_debuff_rejected_instances(
                requirement_state, at_ms
            )
            alerts.extend(self._advance_key_enemy_debuff_time(at_ms))
            return alerts

        previous_end_ms = requirement_state.end_ms
        self._add_key_enemy_debuff_requirement_instance(
            requirement_state, ccid, end_ms
        )
        self._refresh_key_enemy_debuff_requirement_state(requirement_state)
        requirement_state.last_apply_at_ms = at_ms
        if previous_end_ms != requirement_state.end_ms:
            requirement_state.warned_end_ms = None
            requirement_state.ended_fired_end_ms = None

        if self._key_enemy_debuff_all_complete(entity_state):
            entity_state.complete_lost_at_ms = None
            if not entity_state.complete_active:
                entity_state.complete_active = True
                if (
                    spec.complete_enabled
                    and not self._key_enemy_debuff_recent_complete_alert(
                        entity_state, at_ms
                    )
                ):
                    entity_state.last_complete_alert_at_ms = at_ms
                    alerts.append(
                        FiredAlert(
                            at_ms=at_ms,
                            kind="key_enemy_debuff_complete",
                            name="关键敌人DEBUFF",
                            ccid=None,
                            remaining_seconds=None,
                            message=spec.complete_message,
                            sound=spec.complete_sound,
                            volume=spec.audio_volume,
                        )
                    )
        else:
            self._settle_key_enemy_debuff_complete_latch(entity_state, at_ms)
        alerts.extend(self._advance_key_enemy_debuff_time(at_ms))
        return alerts

    def _advance_key_enemy_debuff_time(self, at_ms: int) -> list[FiredAlert]:
        spec = self.key_enemy_debuff_alert
        if spec is None:
            return []

        alerts: list[FiredAlert] = []
        threshold_ms = int(spec.expiry_seconds * 1000)
        for entity_state in list(self.key_enemy_debuff_entity_states.values()):
            alerts.extend(
                self._advance_key_enemy_watched_debuff_time(entity_state, at_ms)
            )
            self._expire_key_enemy_debuff_entity(entity_state, at_ms)
            self._settle_key_enemy_debuff_complete_latch(entity_state, at_ms)
            if not spec.expiry_enabled:
                continue

            due_details: list[dict[str, Any]] = []
            for (
                requirement_key,
                requirement_state,
            ) in entity_state.expiry_requirements.items():
                if not requirement_state.active or requirement_state.end_ms is None:
                    continue
                if requirement_state.warned_end_ms == requirement_state.end_ms:
                    continue
                remaining_ms = requirement_state.end_ms - at_ms
                if remaining_ms <= threshold_ms:
                    requirement_state.warned_end_ms = requirement_state.end_ms
                    due_details.append(
                        {
                            "requirement": requirement_key,
                            "source_ccids": sorted(
                                requirement_state.active_instance_end_ms_by_ccid
                            ),
                            "end_ms": requirement_state.end_ms,
                            "remaining_ms": max(0, remaining_ms),
                        }
                    )

            if due_details:
                remaining_seconds = max(
                    0,
                    math.ceil(
                        min(item["remaining_ms"] for item in due_details) / 1000
                    ),
                )
                alerts.append(
                    FiredAlert(
                        at_ms=at_ms,
                        kind="key_enemy_debuff_expiry",
                        name="关键敌人DEBUFF",
                        ccid=None,
                        remaining_seconds=remaining_seconds,
                        message=spec.expiry_message,
                        sound=spec.expiry_sound,
                        volume=spec.audio_volume,
                        detail={"due_requirements": due_details},
                    )
                )
        return alerts

    def _process_key_enemy_watched_debuff_event(
        self,
        entity_state: KeyEnemyDebuffEntityState,
        watched_spec: WatchedKeyEnemyDebuffSpec,
        ccid: int,
        event: dict[str, Any],
        at_ms: int,
    ) -> list[FiredAlert]:
        requirement_state = self._key_enemy_watched_debuff_state(
            entity_state,
            watched_spec,
        )
        if event.get("EventId") == 5:
            previous_active = requirement_state.active
            previous_end_ms = requirement_state.end_ms
            self._remove_key_enemy_debuff_requirement_instance(
                requirement_state,
                ccid,
            )
            self._refresh_key_enemy_debuff_requirement_state(requirement_state)
            if previous_end_ms != requirement_state.end_ms:
                requirement_state.warned_end_ms = None
                requirement_state.ended_fired_end_ms = None
            if previous_active and not requirement_state.active:
                return self._fire_key_enemy_watched_debuff_ended(
                    watched_spec,
                    requirement_state,
                    at_ms,
                    previous_end_ms,
                )
            return []

        previous_end_ms = requirement_state.end_ms
        end_ms = self._key_enemy_debuff_event_end_ms(event, at_ms)
        self._add_key_enemy_debuff_requirement_instance(
            requirement_state,
            ccid,
            end_ms,
        )
        self._refresh_key_enemy_debuff_requirement_state(requirement_state)
        requirement_state.last_apply_at_ms = at_ms
        if previous_end_ms != requirement_state.end_ms:
            requirement_state.warned_end_ms = None
            requirement_state.ended_fired_end_ms = None
        return []

    def _advance_key_enemy_watched_debuff_time(
        self,
        entity_state: KeyEnemyDebuffEntityState,
        at_ms: int,
    ) -> list[FiredAlert]:
        spec = self.key_enemy_debuff_alert
        if spec is None:
            return []

        alerts: list[FiredAlert] = []
        for watched_spec in spec.watched_debuffs:
            if not watched_spec.enabled:
                continue
            requirement_state = entity_state.watched_debuffs.get(watched_spec.name)
            if (
                requirement_state is None
                or not requirement_state.active
                or requirement_state.end_ms is None
            ):
                continue

            remaining_ms = requirement_state.end_ms - at_ms
            if (
                watched_spec.remaining_enabled
                and requirement_state.warned_end_ms != requirement_state.end_ms
                and remaining_ms <= int(watched_spec.remaining_seconds * 1000)
            ):
                requirement_state.warned_end_ms = requirement_state.end_ms
                alerts.append(
                    FiredAlert(
                        at_ms=at_ms,
                        kind="key_enemy_watched_debuff_remaining",
                        name=watched_spec.name,
                        ccid=None,
                        remaining_seconds=max(0, math.ceil(remaining_ms / 1000)),
                        message=watched_spec.remaining_message,
                        sound=watched_spec.remaining_sound,
                        volume=spec.audio_volume,
                        detail={
                            "watched_debuff": watched_spec.name,
                            "end_ms": requirement_state.end_ms,
                        },
                    )
                )

            if remaining_ms <= 0:
                alerts.extend(
                    self._fire_key_enemy_watched_debuff_ended(
                        watched_spec,
                        requirement_state,
                        at_ms,
                        requirement_state.end_ms,
                    )
                )
        return alerts

    def _fire_key_enemy_watched_debuff_ended(
        self,
        watched_spec: WatchedKeyEnemyDebuffSpec,
        requirement_state: KeyEnemyDebuffRequirementState,
        at_ms: int,
        end_ms: int | None,
    ) -> list[FiredAlert]:
        spec = self.key_enemy_debuff_alert
        if (
            spec is None
            or not watched_spec.ended_enabled
            or end_ms is None
            or requirement_state.ended_fired_end_ms == end_ms
        ):
            return []
        requirement_state.ended_fired_end_ms = end_ms
        return [
            FiredAlert(
                at_ms=at_ms,
                kind="key_enemy_watched_debuff_ended",
                name=watched_spec.name,
                ccid=None,
                remaining_seconds=None,
                message=watched_spec.ended_message,
                sound=watched_spec.ended_sound,
                volume=spec.audio_volume,
                detail={
                    "watched_debuff": watched_spec.name,
                    "end_ms": end_ms,
                },
            )
        ]

    @staticmethod
    def _key_enemy_watched_debuff_state(
        entity_state: KeyEnemyDebuffEntityState,
        watched_spec: WatchedKeyEnemyDebuffSpec,
    ) -> KeyEnemyDebuffRequirementState:
        return entity_state.watched_debuffs.setdefault(
            watched_spec.name,
            KeyEnemyDebuffRequirementState(),
        )

    def _expire_key_enemy_debuff_entity(
        self,
        entity_state: KeyEnemyDebuffEntityState,
        at_ms: int,
    ) -> None:
        for requirement_state in entity_state.requirements.values():
            self._prune_key_enemy_debuff_rejected_instances(
                requirement_state, at_ms
            )
            lost_at_ms = self._expire_key_enemy_debuff_requirement_instances(
                requirement_state, at_ms
            )
            if lost_at_ms is not None:
                self._mark_key_enemy_debuff_incomplete(entity_state, lost_at_ms)
        for requirement_state in entity_state.expiry_requirements.values():
            self._expire_key_enemy_debuff_requirement_instances(
                requirement_state, at_ms
            )
        for requirement_state in entity_state.watched_debuffs.values():
            self._expire_key_enemy_debuff_requirement_instances(
                requirement_state, at_ms
            )

    @staticmethod
    def _add_key_enemy_debuff_requirement_instance(
        requirement_state: KeyEnemyDebuffRequirementState,
        ccid: int,
        end_ms: int | None,
    ) -> None:
        instances = requirement_state.active_instance_end_ms_by_ccid.setdefault(
            ccid, []
        )
        if end_ms in instances:
            return
        instances.append(end_ms)

    @staticmethod
    def _remove_key_enemy_debuff_requirement_instance(
        requirement_state: KeyEnemyDebuffRequirementState,
        ccid: int,
    ) -> None:
        instances = requirement_state.active_instance_end_ms_by_ccid.get(ccid)
        if not instances:
            return
        finite_indices = [
            (index, end_ms)
            for index, end_ms in enumerate(instances)
            if end_ms is not None
        ]
        if finite_indices:
            remove_index = min(finite_indices, key=lambda item: item[1])[0]
        else:
            remove_index = 0
        instances.pop(remove_index)
        if not instances:
            requirement_state.active_instance_end_ms_by_ccid.pop(ccid, None)

    @staticmethod
    def _refresh_key_enemy_debuff_requirement_state(
        requirement_state: KeyEnemyDebuffRequirementState,
    ) -> None:
        instances = [
            end_ms
            for end_mses in requirement_state.active_instance_end_ms_by_ccid.values()
            for end_ms in end_mses
        ]
        requirement_state.active = bool(instances)
        if not instances:
            requirement_state.end_ms = None
            return
        finite_end_mses = [end_ms for end_ms in instances if end_ms is not None]
        requirement_state.end_ms = max(finite_end_mses) if finite_end_mses else None

    def _expire_key_enemy_debuff_requirement_instances(
        self,
        requirement_state: KeyEnemyDebuffRequirementState,
        at_ms: int,
    ) -> int | None:
        lost_at_ms: int | None = None
        for ccid, instances in list(
            requirement_state.active_instance_end_ms_by_ccid.items()
        ):
            kept: list[int | None] = []
            for end_ms in instances:
                if end_ms is not None and at_ms >= end_ms:
                    if lost_at_ms is None or end_ms > lost_at_ms:
                        lost_at_ms = end_ms
                    continue
                kept.append(end_ms)
            if kept:
                requirement_state.active_instance_end_ms_by_ccid[ccid] = kept
            else:
                requirement_state.active_instance_end_ms_by_ccid.pop(ccid, None)
        previous_active = requirement_state.active
        previous_end_ms = requirement_state.end_ms
        self._refresh_key_enemy_debuff_requirement_state(requirement_state)
        if previous_end_ms != requirement_state.end_ms:
            requirement_state.warned_end_ms = None
            requirement_state.ended_fired_end_ms = None
        if previous_active and requirement_state.active:
            return None
        return lost_at_ms

    @staticmethod
    def _prune_key_enemy_debuff_rejected_instances(
        requirement_state: KeyEnemyDebuffRequirementState,
        at_ms: int,
    ) -> None:
        cutoff_ms = at_ms - KEY_ENEMY_DEBUFF_REJECTED_REMOVE_GRACE_MS
        for ccid, end_mses in list(
            requirement_state.rejected_instance_end_ms_by_ccid.items()
        ):
            kept = [end_ms for end_ms in end_mses if end_ms >= cutoff_ms]
            if kept:
                requirement_state.rejected_instance_end_ms_by_ccid[ccid] = kept
            else:
                requirement_state.rejected_instance_end_ms_by_ccid.pop(ccid, None)

    def _key_enemy_debuff_remove_matches_rejected_instance(
        self,
        requirement_state: KeyEnemyDebuffRequirementState,
        ccid: int,
        at_ms: int,
    ) -> bool:
        self._prune_key_enemy_debuff_rejected_instances(requirement_state, at_ms)
        rejected_end_mses = requirement_state.rejected_instance_end_ms_by_ccid.get(
            ccid, []
        )
        candidates = [
            end_ms
            for end_ms in rejected_end_mses
            if 0 <= at_ms - end_ms <= KEY_ENEMY_DEBUFF_REJECTED_REMOVE_GRACE_MS
        ]
        if not candidates:
            return False
        matched_end_ms = max(candidates)
        rejected_end_mses.remove(matched_end_ms)
        if not rejected_end_mses:
            requirement_state.rejected_instance_end_ms_by_ccid.pop(ccid, None)
        return True

    def _mark_key_enemy_debuff_incomplete(
        self,
        entity_state: KeyEnemyDebuffEntityState,
        at_ms: int,
    ) -> None:
        if entity_state.complete_active:
            if (
                entity_state.complete_lost_at_ms is None
                or at_ms < entity_state.complete_lost_at_ms
            ):
                entity_state.complete_lost_at_ms = at_ms
        else:
            entity_state.complete_lost_at_ms = None

    def _settle_key_enemy_debuff_complete_latch(
        self,
        entity_state: KeyEnemyDebuffEntityState,
        at_ms: int,
    ) -> None:
        if self._key_enemy_debuff_all_complete(entity_state):
            entity_state.complete_lost_at_ms = None
            return
        if (
            entity_state.complete_active
            and entity_state.complete_lost_at_ms is not None
            and at_ms - entity_state.complete_lost_at_ms
            >= KEY_ENEMY_DEBUFF_COMPLETE_REFRESH_GRACE_MS
        ):
            entity_state.complete_active = False
            entity_state.complete_lost_at_ms = None

    @staticmethod
    def _key_enemy_debuff_recent_complete_alert(
        entity_state: KeyEnemyDebuffEntityState,
        at_ms: int,
    ) -> bool:
        return (
            entity_state.last_complete_alert_at_ms is not None
            and at_ms - entity_state.last_complete_alert_at_ms
            < KEY_ENEMY_DEBUFF_COMPLETE_REFRESH_GRACE_MS
        )

    @staticmethod
    def _key_enemy_debuff_all_complete(
        entity_state: KeyEnemyDebuffEntityState,
    ) -> bool:
        return all(
            entity_state.requirements[key].active
            for key in KEY_ENEMY_DEBUFF_REQUIREMENTS
        )

    def _key_enemy_debuff_apply_is_successful(
        self,
        spec: KeyEnemyDebuffAlertSpec,
        requirement_key: str,
        event: dict[str, Any],
    ) -> bool:
        extra = event.get("ExtraData") or {}
        if requirement_key == "physical_break":
            return (
                _max_numeric_extra(extra, ("MCDDPV", "MCDDTPV"))
                >= spec.physical_break_min
            )
        if requirement_key == "magic_break":
            return (
                _max_numeric_extra(extra, ("MCDMDPV", "MCDMDTPV"))
                >= spec.magic_break_min
            )
        if requirement_key == "damage_bonus":
            return (
                _max_numeric_extra(
                    extra,
                    ("DAMAGE_BONUS", "MCDDMBPV", "MCDDMBTPV"),
                )
                >= spec.damage_bonus_min
            )
        if requirement_key == "rabbit":
            return _numeric_extra(extra, "MCCSSC") >= spec.rabbit_stacks_min
        return True

    def _key_enemy_debuff_event_end_ms(
        self,
        event: dict[str, Any],
        at_ms: int,
    ) -> int | None:
        try:
            ccid = int(event.get("CCId"))
        except (TypeError, ValueError):
            ccid = 0
        if ccid in KEY_ENEMY_DEBUFF_UNTIMED_CCIDS:
            return None
        extra = event.get("ExtraData") or {}
        if (duration_ms := _explicit_duration_ms(extra)) is not None:
            return at_ms + duration_ms
        if "SBT" not in extra:
            return None
        raw_end_ms = sbt_to_unix_ms(extra["SBT"], self.tz_offset_hours)
        end_ms = raw_end_ms
        if self.dynamic_sbt_adjust_seconds is not None:
            end_ms += int(self.dynamic_sbt_adjust_seconds * 1000)
        if end_ms > at_ms:
            return end_ms
        return None

    def _reset_all_key_enemy_debuff_states(self) -> None:
        self.key_enemy_debuff_entity_states.clear()

    def _reset_key_enemy_debuff_entity(self, entity_id: str) -> None:
        self.key_enemy_debuff_entity_states.pop(entity_id, None)

    def _reset_other_key_enemy_debuff_entities(self, entity_id: str) -> None:
        for other_entity_id in list(self.key_enemy_debuff_entity_states):
            if other_entity_id != entity_id:
                self._reset_key_enemy_debuff_entity(other_entity_id)

    def _boss_hp_logical_percent(
        self, state: BossHpAlertState, raw_percent: float
    ) -> float:
        previous_percent = state.previous_percent
        if not state.active or previous_percent is None:
            return raw_percent
        if raw_percent <= previous_percent + BOSS_HP_UPWARD_JUMP_TOLERANCE_PERCENT:
            return raw_percent
        # Multi-phase bosses can swap backend entities while the UI keeps one bar.
        # Ignore the new entity's transient full-HP stat and keep the visible bar monotonic.
        return previous_percent

    def _should_keep_boss_hp_phase_handoff(self, state: BossHpAlertState) -> bool:
        if (
            state.last_current_hp is None
            or state.last_current_hp <= 0
            or state.last_max_hp is None
        ):
            return False
        phase_keys = [
            self._boss_hp_fingerprint_key(max_hp)
            for max_hp in state.spec.max_hp_values
        ]
        if len(phase_keys) < 2:
            return False
        current_key = self._boss_hp_fingerprint_key(state.last_max_hp)
        return current_key in set(phase_keys[:-1])

    @staticmethod
    def _boss_hp_fingerprint_key(value: float | int | None) -> int:
        if value is None:
            return 0
        return int(round(float(value)))

    def _boss_hp_state_for_max_hp(
        self, max_hp: float | int | None
    ) -> BossHpAlertState | None:
        if max_hp is None:
            return None
        return self.boss_hp_alert_states_by_max_hp.get(
            self._boss_hp_fingerprint_key(max_hp)
        )

    def _bind_boss_hp_state_to_entity(
        self,
        state: BossHpAlertState,
        entity_id: str,
        percent: float,
        at_ms: int,
    ) -> None:
        state.tracked_entity_id = entity_id
        self.boss_hp_alert_states[entity_id] = state
        state.active = True
        state.previous_percent = percent
        state.phase_handoff_until_ms = None
        state.fired_thresholds.update(
            rule.threshold_percent
            for rule in state.spec.alerts
            if percent <= rule.threshold_percent
        )
        state.last_seen_at_ms = at_ms

    def _reset_all_boss_hp_states(self) -> None:
        seen: set[int] = set()
        for state in list(self.boss_hp_alert_states.values()) + list(
            self.boss_hp_alert_states_by_max_hp.values()
        ):
            state_id = id(state)
            if state_id in seen:
                continue
            seen.add(state_id)
            self._reset_boss_hp_state(state)

    @staticmethod
    def _reset_boss_hp_state(state: BossHpAlertState) -> None:
        state.tracked_entity_id = None
        state.active = False
        state.previous_percent = None
        state.fired_thresholds.clear()
        state.last_seen_at_ms = None
        state.last_current_hp = None
        state.last_max_hp = None
        state.last_raw_percent = None
        state.phase_handoff_until_ms = None

    def _is_tracked_stat_drop_effect_entity_event(self, event: dict[str, Any]) -> bool:
        if event.get("EventId") != ENTITY_REMOVED_EVENT_ID:
            return False
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return False
        return any(
            not state.spec.self_filter
            and state.active
            and state.tracked_entity_id == event_entity_id
            for state in self.stat_drop_effect_states
        )

    def _process_stat_drop_effect_entity_lifecycle(
        self, event: dict[str, Any]
    ) -> None:
        if event.get("EventId") != ENTITY_REMOVED_EVENT_ID:
            return
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))
        if not event_entity_id:
            return
        for state in self.stat_drop_effect_states:
            if not state.active or state.tracked_entity_id != event_entity_id:
                continue
            self._stop_stat_drop_effect_state(state, reset_start=True)

    def _process_stat_drop_effect_stats(
        self, event: dict[str, Any]
    ) -> list[FiredAlert]:
        stats = event.get("Stats") or []
        if not stats or not self.stat_drop_effect_states:
            return []

        at_ms = int(event.get("At", 0))
        current_values = _event_stat_values(event)
        event_entity_id = "" if event.get("Id") is None else str(event.get("Id"))

        alerts: list[FiredAlert] = []
        for state in self.stat_drop_effect_states:
            self._sync_stat_drop_effect_timer_from_entity(
                state,
                event=event,
                current_values=current_values,
                event_entity_id=event_entity_id,
                at_ms=at_ms,
            )

            if (
                state.tracked_entity_id is not None
                and event_entity_id != state.tracked_entity_id
            ):
                continue

            if (
                state.spec.start_stat_matches
                and not state.active
                and self._stats_match(current_values, state.spec.start_stat_matches)
            ):
                dedupe_ms = int(state.spec.trigger_dedupe_seconds * 1000)
                if (
                    dedupe_ms <= 0
                    or state.last_start_at_ms is None
                    or at_ms - state.last_start_at_ms >= dedupe_ms
                ):
                    state.active = True
                    state.ended_fired = False
                    state.last_start_at_ms = at_ms
                    state.last_trigger_at_ms = at_ms
                    state.tracked_entity_id = event_entity_id or None
                    state.last_values.clear()
                    state.fired_thresholds.clear()
                    self._reset_stat_drop_effect_timer_sync(state)
                    if state.spec.timer_enabled and state.spec.duration_seconds > 0:
                        state.end_ms = at_ms + int(
                            state.spec.start_offset_seconds * 1000
                        )
                        alerts.extend(self._advance_stat_drop_effect_time(state, at_ms))
                    else:
                        state.end_ms = None

            if (
                state.active
                and state.spec.stop_stat_matches
                and self._stats_match(current_values, state.spec.stop_stat_matches)
            ):
                self._stop_stat_drop_effect_state(state)
                continue

            matched = 0
            can_detect = state.active or state.spec.allow_unseen_drop
            if can_detect and not state.ended_fired:
                for rule in state.spec.drop_rules:
                    previous = state.last_values.get(rule.stat_id)
                    current = current_values.get(rule.stat_id)
                    if previous is None or current is None:
                        continue
                    drop = previous - current
                    if drop < rule.min_drop:
                        continue
                    if rule.max_drop is not None and drop > rule.max_drop:
                        continue
                    matched += 1
                if matched >= state.spec.min_drop_count:
                    self._stop_stat_drop_effect_state(state, clear_values=False)
                    if state.spec.ended_alert:
                        alerts.append(
                            FiredAlert(
                                at_ms=at_ms,
                                kind="ended",
                                name=state.spec.name,
                                ccid=None,
                                remaining_seconds=None,
                                message=format_stat_drop_effect_message(
                                    state.spec.ended_message,
                                    state.spec,
                                    remaining=None,
                                ),
                                sound=state.spec.ended_sound,
                                volume=state.spec.audio_volume,
                            )
                        )
            for stat_id, value in current_values.items():
                state.last_values[stat_id] = value
        return alerts

    def _sync_stat_drop_effect_timer_from_entity(
        self,
        state: StatDropEffectState,
        *,
        event: dict[str, Any],
        current_values: dict[int, float],
        event_entity_id: str,
        at_ms: int,
    ) -> None:
        spec = state.spec
        if (
            not state.active
            or not spec.timer_enabled
            or spec.duration_seconds <= 0
            or not spec.timer_sync_stat_matches
            or not event_entity_id
        ):
            return
        if (
            spec.timer_sync_event_id is not None
            and int(event.get("EventId", -1)) != spec.timer_sync_event_id
        ):
            return
        if event_entity_id == state.tracked_entity_id:
            return

        entity_values = state.timer_sync_entity_values.setdefault(event_entity_id, {})
        entity_values.update(current_values)
        if not self._stats_match(entity_values, spec.timer_sync_stat_matches):
            return
        if event_entity_id in state.timer_sync_seen_entity_ids:
            return

        state.timer_sync_seen_entity_ids.add(event_entity_id)
        if not self._should_accept_stat_drop_effect_timer_sync(state, at_ms):
            return

        previous_sync_at_ms = state.timer_sync_last_at_ms
        state.timer_sync_last_at_ms = at_ms
        interval_ms = int(spec.duration_seconds * 1000)
        if previous_sync_at_ms is not None and at_ms > previous_sync_at_ms:
            interval_ms = at_ms - previous_sync_at_ms
        state.end_ms = at_ms + interval_ms
        state.fired_thresholds.clear()

    def _should_accept_stat_drop_effect_timer_sync(
        self, state: StatDropEffectState, at_ms: int
    ) -> bool:
        spec = state.spec
        if state.timer_sync_last_at_ms is not None:
            interval_seconds = (at_ms - state.timer_sync_last_at_ms) / 1000
            return (
                spec.timer_sync_min_interval_seconds
                <= interval_seconds
                <= spec.timer_sync_max_interval_seconds
            )

        if state.last_start_at_ms is not None:
            since_start_seconds = (at_ms - state.last_start_at_ms) / 1000
            if (
                spec.timer_sync_initial_max_delay_seconds > 0
                and spec.timer_sync_initial_min_delay_seconds
                <= since_start_seconds
                <= spec.timer_sync_initial_max_delay_seconds
            ):
                return True

        if state.end_ms is not None and spec.timer_sync_expected_tolerance_seconds > 0:
            delta_seconds = abs((at_ms - state.end_ms) / 1000)
            if delta_seconds <= spec.timer_sync_expected_tolerance_seconds:
                return True

        return False

    @staticmethod
    def _stop_stat_drop_effect_state(
        state: StatDropEffectState,
        *,
        clear_values: bool = True,
        reset_start: bool = False,
    ) -> None:
        state.active = False
        state.ended_fired = True
        state.end_ms = None
        state.fired_thresholds.clear()
        state.tracked_entity_id = None
        AlertEngine._reset_stat_drop_effect_timer_sync(state)
        if clear_values:
            state.last_values.clear()
        if reset_start:
            state.last_start_at_ms = None

    @staticmethod
    def _reset_stat_drop_effect_timer_sync(state: StatDropEffectState) -> None:
        state.timer_sync_last_at_ms = None
        state.timer_sync_seen_entity_ids.clear()
        state.timer_sync_entity_values.clear()

    def _event_matches_trigger(
        self, event: dict[str, Any], trigger: EventTrigger
    ) -> bool:
        if int(event.get("EventId", -1)) != trigger.event_id:
            return False
        if trigger.op and str(event.get("Op", "")).lower() != trigger.op.lower():
            return False

        messages = event.get("Msg") or []
        for match in trigger.message_matches:
            if match.index < 0 or match.index >= len(messages):
                return False
            message = messages[match.index]
            if match.type is not None and str(message.get("T")) != match.type:
                return False
            if match.value is not None and str(message.get("V")) != match.value:
                return False
        for match in trigger.field_matches:
            value = _event_field_value(event, match.field)
            if match.value == "$self":
                if value is None or str(value) in ("", "0"):
                    return False
                continue
            if value is None:
                return False
            if match.value is not None and str(value) != match.value:
                return False
        return True

    @staticmethod
    def _stats_match(
        current_values: dict[int, float], matches: tuple[StatValueMatch, ...]
    ) -> bool:
        if not matches:
            return False
        for match in matches:
            current = current_values.get(match.stat_id)
            if current is None:
                return False
            if match.value is not None and abs(current - match.value) > 0.001:
                return False
            if match.min_value is not None and current < match.min_value:
                return False
            if match.max_value is not None and current > match.max_value:
                return False
        return True

    def _advance_stat_drop_effect_time(
        self, state: StatDropEffectState, at_ms: int
    ) -> list[FiredAlert]:
        if (
            not state.active
            or state.end_ms is None
            or not state.spec.timer_enabled
            or state.spec.duration_seconds <= 0
        ):
            return []

        alerts: list[FiredAlert] = []
        remaining_exact = (state.end_ms - at_ms) / 1000
        remaining = max(0, math.ceil(remaining_exact))
        for rule in state.spec.alerts:
            if rule.remaining_seconds in state.fired_thresholds:
                continue
            if remaining_exact <= rule.remaining_seconds:
                state.fired_thresholds.add(rule.remaining_seconds)
                alerts.append(
                    FiredAlert(
                        at_ms=at_ms,
                        kind="threshold",
                        name=state.spec.name,
                        ccid=None,
                        remaining_seconds=max(0, remaining),
                        message=format_stat_drop_effect_message(
                            rule.message,
                            state.spec,
                            remaining=max(0, remaining),
                        ),
                        sound=rule.sound,
                        volume=state.spec.audio_volume,
                    )
                )

        if at_ms >= state.end_ms and state.spec.repeat_timer:
            interval_ms = state.spec.duration_seconds * 1000
            if interval_ms <= 0:
                state.active = False
                state.end_ms = None
                state.fired_thresholds.clear()
                return alerts
            while state.end_ms is not None and at_ms >= state.end_ms:
                state.end_ms += interval_ms
                state.fired_thresholds.clear()
            return alerts

        if at_ms >= state.end_ms:
            if (
                state.spec.ignore_trigger_while_active
                and state.spec.trigger_rearm_tolerance_seconds > 0
            ):
                return alerts
            # The manual timer is only used for pre-expiry reminders. The actual
            # end alert for stat-drop effects must come from the observed stat drop,
            # otherwise a user-entered duration could create a false "ended" alert.
            state.active = False
            state.end_ms = None
            state.fired_thresholds.clear()
        return alerts


def _numeric_extra(extra: dict[str, Any], key: str) -> float:
    value = extra.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return float("-inf")
    return float("-inf")


def _max_numeric_extra(extra: dict[str, Any], keys: Iterable[str]) -> float:
    values = [_numeric_extra(extra, key) for key in keys]
    return max(values) if values else float("-inf")


def _extra_matches_required(
    extra: dict[str, Any], required: dict[str, Any]
) -> bool:
    for key, expected in required.items():
        if key not in extra:
            return False
        if not _extra_value_matches(extra.get(key), expected):
            return False
    return True


def _extra_value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_extra_value_matches(actual, value) for value in expected)
    try:
        return abs(float(actual) - float(expected)) < 0.000001
    except (TypeError, ValueError):
        return str(actual) == str(expected)


def _explicit_duration_ms(extra: dict[str, Any]) -> int | None:
    for key in EVENT_DURATION_KEYS:
        if key not in extra:
            continue
        try:
            duration_ms = int(float(extra[key]))
        except (TypeError, ValueError):
            continue
        if duration_ms > 0:
            return duration_ms
    return None


def _event_field_value(event: dict[str, Any], field_name: str) -> Any:
    value: Any = event
    for part in field_name.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _event_stat_values(event: dict[str, Any]) -> dict[int, float]:
    values: dict[int, float] = {}
    for item in event.get("Stats") or []:
        stat_id = item.get("StatId")
        value = item.get("Value")
        if stat_id is None or not isinstance(value, (int, float)):
            continue
        values[int(stat_id)] = float(value)
    return values


def format_message(
    template: str, spec: BuffSpec, *, remaining: int | None, stacks: int | None
) -> str:
    max_stacks = spec.max_stacks if spec.max_stacks is not None else ""
    return template.format(
        name=spec.name,
        ccid=spec.ccid,
        remaining_seconds="" if remaining is None else remaining,
        stacks="" if stacks is None else stacks,
        max_stacks=max_stacks,
    )


def format_stat_drop_effect_message(
    template: str, spec: StatDropEffectSpec, *, remaining: int | None
) -> str:
    return template.format(
        name=spec.name,
        remaining_seconds="" if remaining is None else remaining,
        duration_seconds=spec.duration_seconds,
    )


def format_progress_message(
    template: str, spec: ProgressSpec, *, progress: float, remaining: float
) -> str:
    return template.format(
        name=spec.name,
        stat_id=spec.stat_id,
        progress=progress,
        progress_percent=progress,
        remaining_progress=remaining,
    )


def normalize_volume(value: Any) -> int:
    try:
        volume = int(value)
    except (TypeError, ValueError):
        return 100
    return max(0, min(100, volume))


def make_sound_sequence(*paths: str | Path) -> str:
    parts = [str(path) for path in paths if str(path)]
    return SOUND_SEQUENCE_PREFIX + SOUND_SEQUENCE_SEPARATOR.join(parts)


def make_timed_sound_sequence(
    *clips: tuple[float, str | Path],
    cancel_key: str | None = None,
) -> str:
    payload = [
        {"offset_seconds": max(0.0, float(offset_seconds)), "path": str(path)}
        for offset_seconds, path in clips
        if str(path)
    ]
    value: Any
    if cancel_key:
        value = {"cancel_key": cancel_key, "clips": payload}
    else:
        value = payload
    return SOUND_TIMED_SEQUENCE_PREFIX + json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def cancel_sound_sequence(cancel_key: str) -> None:
    if not cancel_key:
        return
    with _SOUND_CANCEL_LOCK:
        _SOUND_CANCEL_GENERATIONS[cancel_key] = (
            _SOUND_CANCEL_GENERATIONS.get(cancel_key, 0) + 1
        )


def _sound_cancel_generation(cancel_key: str | None) -> int:
    if not cancel_key:
        return 0
    with _SOUND_CANCEL_LOCK:
        return _SOUND_CANCEL_GENERATIONS.get(cancel_key, 0)


def _sound_sequence_canceled(cancel_key: str | None, generation: int) -> bool:
    return bool(cancel_key) and _sound_cancel_generation(cancel_key) != generation


def _sleep_until_sound_offset(
    started_at: float,
    offset_seconds: float,
    *,
    cancel_key: str | None,
    cancel_generation: int,
) -> bool:
    while True:
        if _sound_sequence_canceled(cancel_key, cancel_generation):
            return False
        wait_seconds = offset_seconds - (time.monotonic() - started_at)
        if wait_seconds <= 0:
            return True
        time.sleep(min(wait_seconds, 0.05))


def resolve_sound_path(path: str | Path) -> Path:
    sound_path = Path(path)
    if sound_path.is_absolute():
        return sound_path
    candidates = [Path.cwd() / sound_path]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / sound_path)
    candidates.append(Path(__file__).resolve().parent.parent / sound_path)
    return next((candidate for candidate in candidates if candidate.is_file()), candidates[0])


def _play_timed_sequence_clip(
    clip_path: str,
    *,
    volume: int,
    cancel_key: str | None,
    cancel_generation: int,
) -> bool:
    if _sound_sequence_canceled(cancel_key, cancel_generation):
        return False
    sound_path = resolve_sound_path(clip_path)
    if os.name == "nt":
        try:
            play_sound_mci(sound_path, async_play=False, volume=volume)
            return not _sound_sequence_canceled(cancel_key, cancel_generation)
        except RuntimeError as exc:
            print(f"[audio timed sequence mci error] {sound_path}: {exc}")
    with _ASYNC_AUDIO_LOCK:
        if _sound_sequence_canceled(cancel_key, cancel_generation):
            return False
        play_sound(sound_path, async_play=False, volume=volume)
    return not _sound_sequence_canceled(cancel_key, cancel_generation)


def play_sound(path: str | Path, *, async_play: bool = False, volume: int = 100) -> None:
    volume = normalize_volume(volume)
    if volume <= 0:
        return

    sound_value = str(path)
    if async_play:
        if sound_value.startswith(SOUND_TIMED_SEQUENCE_PREFIX):
            thread = threading.Thread(
                target=_play_timed_sound_sequence_async_worker,
                kwargs={"path": path, "volume": volume},
                daemon=True,
            )
            thread.start()
            return
        thread = threading.Thread(
            target=_play_sound_async_worker,
            kwargs={"path": path, "volume": volume},
            daemon=True,
        )
        thread.start()
        return

    if sound_value.startswith(SOUND_SEQUENCE_PREFIX):
        sequence_value = sound_value[len(SOUND_SEQUENCE_PREFIX) :]
        parts = [
            part
            for part in sequence_value.split(SOUND_SEQUENCE_SEPARATOR)
            if part.strip()
        ]
        for part in parts:
            play_sound(part, async_play=False, volume=volume)
        return

    if sound_value.startswith(SOUND_TIMED_SEQUENCE_PREFIX):
        sequence_value = sound_value[len(SOUND_TIMED_SEQUENCE_PREFIX) :]
        try:
            sequence_payload = json.loads(sequence_value)
        except json.JSONDecodeError as exc:
            print(f"[audio timed sequence error] {exc}")
            return
        cancel_key: str | None = None
        if isinstance(sequence_payload, dict):
            cancel_key_value = sequence_payload.get("cancel_key")
            if cancel_key_value is not None:
                cancel_key = str(cancel_key_value)
            clips = sequence_payload.get("clips", [])
        else:
            clips = sequence_payload
        started_at = time.monotonic()
        cancel_generation = _sound_cancel_generation(cancel_key)
        valid_clips = [clip for clip in clips if isinstance(clip, dict)]
        for clip in sorted(valid_clips, key=lambda item: item.get("offset_seconds", 0)):
            clip_path = str(clip.get("path", "")).strip()
            if not clip_path:
                continue
            try:
                offset_seconds = max(0.0, float(clip.get("offset_seconds", 0)))
            except (TypeError, ValueError):
                offset_seconds = 0.0
            if not _sleep_until_sound_offset(
                started_at,
                offset_seconds,
                cancel_key=cancel_key,
                cancel_generation=cancel_generation,
            ):
                return
            if _sound_sequence_canceled(cancel_key, cancel_generation):
                return
            if not _play_timed_sequence_clip(
                clip_path,
                volume=volume,
                cancel_key=cancel_key,
                cancel_generation=cancel_generation,
            ):
                return
        return

    sound_path = resolve_sound_path(path)

    if os.name == "nt" and sound_path.suffix.lower() == ".wav":
        try:
            play_wav_with_volume(sound_path, async_play=async_play, volume=volume)
            return
        except RuntimeError as exc:
            print(f"[audio wav error] {sound_path}: {exc}")

    if os.name == "nt":
        try:
            play_sound_mci(sound_path, async_play=async_play, volume=volume)
            return
        except RuntimeError as exc:
            print(f"[audio mci error] {sound_path}: {exc}")

    try:
        import winsound
    except ImportError:
        print(f"[audio unavailable] {sound_path}")
        return

    flags = winsound.SND_FILENAME | winsound.SND_NODEFAULT
    if async_play:
        flags |= winsound.SND_ASYNC
    try:
        winsound.PlaySound(str(sound_path), flags)
    except RuntimeError as exc:
        print(f"[audio error] {sound_path}: {exc}")


def _play_sound_async_worker(path: str | Path, *, volume: int) -> None:
    with _ASYNC_AUDIO_LOCK:
        try:
            play_sound(path, async_play=False, volume=volume)
        except Exception as exc:
            print(f"[audio async error] {path}: {exc}")


def _play_timed_sound_sequence_async_worker(path: str | Path, *, volume: int) -> None:
    try:
        play_sound(path, async_play=False, volume=volume)
    except Exception as exc:
        print(f"[audio timed sequence async error] {path}: {exc}")


def play_wav_with_volume(path: str | Path, *, async_play: bool, volume: int) -> None:
    if async_play:
        thread = threading.Thread(
            target=play_wav_with_volume,
            kwargs={"path": path, "async_play": False, "volume": volume},
            daemon=True,
        )
        thread.start()
        return

    path = Path(path)
    if not path.is_file():
        raise RuntimeError("sound file not found")

    play_path = path
    temp_path: Path | None = None
    if normalize_volume(volume) < 100:
        temp_path = make_scaled_wav(path, normalize_volume(volume))
        play_path = temp_path

    try:
        import winsound

        winsound.PlaySound(str(play_path), winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    except ImportError as exc:
        raise RuntimeError("winsound unavailable") from exc
    except RuntimeError:
        raise
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def make_scaled_wav(path: Path, volume: int) -> Path:
    volume = normalize_volume(volume)
    factor = volume / 100.0
    try:
        with wave.open(str(path), "rb") as source:
            params = source.getparams()
            frames = source.readframes(source.getnframes())
            scaled = audioop.mul(frames, source.getsampwidth(), factor)
    except (wave.Error, audioop.error, OSError) as exc:
        raise RuntimeError(str(exc)) from exc

    handle = tempfile.NamedTemporaryFile(prefix="buffwatcher_", suffix=".wav", delete=False)
    temp_path = Path(handle.name)
    handle.close()
    try:
        with wave.open(str(temp_path), "wb") as target:
            target.setparams(params)
            target.writeframes(scaled)
    except OSError as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(str(exc)) from exc
    return temp_path


def play_sound_mci(path: str | Path, *, async_play: bool, volume: int) -> None:
    if async_play:
        thread = threading.Thread(
            target=play_sound_mci,
            kwargs={"path": path, "async_play": False, "volume": volume},
            daemon=True,
        )
        thread.start()
        return

    path = Path(path)
    if not path.is_file():
        raise RuntimeError("sound file not found")

    alias = "bw_" + uuid.uuid4().hex
    volume_value = normalize_volume(volume) * 10

    def send(command: str) -> None:
        error = ctypes.windll.winmm.mciSendStringW(command, None, 0, None)
        if error:
            buffer = ctypes.create_unicode_buffer(256)
            ctypes.windll.winmm.mciGetErrorStringW(error, buffer, len(buffer))
            raise RuntimeError(buffer.value or f"MCI error {error}")

    try:
        send(f'open "{path}" alias {alias}')
        try:
            send(f"setaudio {alias} volume to {volume_value}")
        except RuntimeError:
            pass
        send(f"play {alias} wait")
    finally:
        ctypes.windll.winmm.mciSendStringW(f"close {alias}", None, 0, None)


def print_alert(alert: FiredAlert) -> None:
    timestamp = f"{alert.at_ms / 1000:.3f}"
    remaining = "-" if alert.remaining_seconds is None else f"{alert.remaining_seconds}s"
    source = "-" if alert.ccid is None else str(alert.ccid)
    print(
        f"[{timestamp}] {alert.kind:<9} {alert.name} "
        f"(ccid={source}, remaining={remaining}) -> {alert.message}"
    )


def maybe_play(alert: FiredAlert, *, no_audio: bool) -> None:
    if no_audio:
        return
    play_sound(alert.sound, volume=alert.volume)


def cmd_replay(args: argparse.Namespace) -> int:
    raw_path = Path(args.file) if args.file else latest_raw_file(args.histories)
    loaded = load_all_specs(args.config)
    engine = AlertEngine(
        loaded.buffs,
        progress_specs=loaded.progresses,
        stat_drop_effect_specs=loaded.stat_drop_effects,
        boss_hp_alert_specs=loaded.boss_hp_alerts,
        boss_skill_burst_alert_specs=loaded.boss_skill_burst_alerts,
        boss_red_orb_alert_specs=loaded.boss_red_orb_alerts,
        boss_laser_alert_specs=loaded.boss_laser_alerts,
        key_enemy_debuff_alert=loaded.key_enemy_debuff_alert,
        magic_shield_missing=loaded.magic_shield_missing,
        tz_offset_hours=args.tz_offset_hours,
        death_clear_suppression_window_ms=loaded.death_clear_suppression_window_ms,
        death_clear_suppression_min_buffs=loaded.death_clear_suppression_min_buffs,
        death_signal_event_ids=loaded.death_signal_event_ids,
        death_signal_suppression_window_ms=loaded.death_signal_suppression_window_ms,
        music_strong_reminder_enabled=loaded.music_strong_reminder_enabled,
        music_strong_reminder_repeat_seconds=loaded.music_strong_reminder_repeat_seconds,
        music_strong_reminder_prefix_sound=loaded.music_strong_reminder_prefix_sound,
    )

    previous_at: int | None = None
    print(f"file: {raw_path}")
    print(f"config: {args.config}")

    for event in iter_raw_events(raw_path):
        at_ms = event.get("At")
        if not isinstance(at_ms, int):
            continue

        if previous_at is not None:
            if args.speed > 0 and not args.no_sleep:
                delay = (at_ms - previous_at) / 1000 / args.speed
                if delay > 0:
                    time.sleep(min(delay, args.max_sleep))
            for alert in engine.advance_time(at_ms):
                print_alert(alert)
                maybe_play(alert, no_audio=args.no_audio)

        for alert in engine.process_event(event):
            print_alert(alert)
            maybe_play(alert, no_audio=args.no_audio)

        previous_at = at_ms

    if args.drain:
        for alert in engine.drain_scheduled_alerts():
            print_alert(alert)
            maybe_play(alert, no_audio=args.no_audio)

    return 0


def cmd_test_sounds(args: argparse.Namespace) -> int:
    for label, path in [
        ("warn", args.warn_sound),
        ("critical", args.critical_sound),
        ("ended", args.ended_sound),
    ]:
        print(f"playing {label}: {path}")
        if not args.no_audio:
            play_sound(path)
        else:
            print("no-audio enabled")
    return 0


def cmd_list_enabled(args: argparse.Namespace) -> int:
    loaded = load_all_specs(args.config)
    for spec in loaded.buffs:
        linked = ",".join(str(ccid) for ccid in sorted(spec.linked_ccids)) or "-"
        stack = spec.stack_field or "-"
        stack_alert = spec.stack_alert.stacks if spec.stack_alert else "-"
        thresholds = ", ".join(str(rule.remaining_seconds) for rule in spec.alerts)
        ended = "yes" if spec.ended_alert else "no"
        clear = "yes" if spec.clear_after_stack_alert else "no"
        cooldown = (
            f"{spec.cooldown_delay_seconds:g}s" if spec.cooldown_alert else "no"
        )
        print(
            f"{spec.name}: ccid={spec.ccid}, linked={linked}, "
            f"stack={stack}, stack_alert={stack_alert}, "
            f"alerts={thresholds or '-'}, ended={ended}, "
            f"cooldown={cooldown}, clear={clear}"
        )
    for spec in loaded.progresses:
        thresholds = ", ".join(str(rule.remaining_progress) for rule in spec.alerts)
        print(
            f"{spec.name}: stat_id={spec.stat_id}, max={spec.max_value:g}, "
            f"remaining_progress_alerts={thresholds or '-'}"
        )
    for spec in loaded.stat_drop_effects:
        rules = ", ".join(
            f"{rule.stat_id}>={rule.min_drop:g}" for rule in spec.drop_rules
        )
        if spec.start_stat_matches:
            def format_stat_match_value(value: float) -> str:
                return str(int(value)) if float(value).is_integer() else f"{value:g}"

            start = ", ".join(
                f"{match.stat_id}={format_stat_match_value(match.value)}"
                if match.value is not None
                else f"{match.stat_id}"
                for match in spec.start_stat_matches
            )
            repeat = f"{spec.duration_seconds}s" if spec.repeat_timer else "no"
            thresholds = ", ".join(
                str(rule.remaining_seconds) for rule in spec.alerts
            )
            print(
                f"{spec.name}: stat_start={start}, "
                f"first={spec.start_offset_seconds:g}s, repeat={repeat}, "
                f"alerts={thresholds or '-'}, self_filter={spec.self_filter}"
            )
            continue
        print(
            f"{spec.name}: event={spec.trigger.event_id}/{spec.trigger.op}, "
            f"drops={rules or '-'}, min={spec.min_drop_count}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay and test buff alert rules.")
    parser.add_argument("--config", default="buffwatcher.config.local.json")
    parser.add_argument("--tz-offset-hours", type=int, default=DEFAULT_TZ_OFFSET_HOURS)
    subparsers = parser.add_subparsers(required=True)

    replay = subparsers.add_parser("replay", help="Replay a raw file through alert rules.")
    replay.add_argument("--histories", default=r"C:\Users\rw594\Desktop\MicoPunch\histories")
    replay.add_argument("--file")
    replay.add_argument("--speed", type=float, default=60)
    replay.add_argument("--max-sleep", type=float, default=0.25)
    replay.add_argument("--no-sleep", action="store_true")
    replay.add_argument("--no-audio", action="store_true")
    replay.add_argument(
        "--drain",
        action="store_true",
        help="After replaying events, fast-forward to all scheduled alert thresholds.",
    )
    replay.set_defaults(func=cmd_replay)

    sounds = subparsers.add_parser("test-sounds", help="Play placeholder alert sounds.")
    sounds.add_argument("--warn-sound", default=DEFAULT_WARN_SOUND)
    sounds.add_argument("--critical-sound", default=DEFAULT_CRITICAL_SOUND)
    sounds.add_argument("--ended-sound", default=DEFAULT_ENDED_SOUND)
    sounds.add_argument("--no-audio", action="store_true")
    sounds.set_defaults(func=cmd_test_sounds)

    listed = subparsers.add_parser("list-enabled", help="List enabled buff alert specs.")
    listed.set_defaults(func=cmd_list_enabled)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

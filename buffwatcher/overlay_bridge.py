from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .astrology_cards import (
    ASTROLOGY_CORE_COOLDOWN_DEFAULTS,
    ASTROLOGY_SKILLS,
    AstrologyCardTracker,
    load_astrology_card_tracker_settings,
)
from .alerting import (
    BossHpAlertState,
    BossLaserAlertState,
    BossLaserMovementCountdownState,
    BuffState,
    KeyEnemyDebuffAlertSpec,
    KeyEnemyDebuffEntityState,
    MUSIC_BUFF_CCIDS,
    MiracleOrbHpState,
    TUAN_SONG_CCID,
)
from .backend import app_root
from .hamster_buffs import HAMSTER_SETTINGS_NAME, HAMSTER_SUPERCHARGED_CCID


DEFAULT_OVERLAY_CONDITIONS = {
    192: True,
    193: True,
    680: True,
}
DEFAULT_OVERLAY_SHOW_BEFORE_SECONDS = 15.0
DEFAULT_OVERLAY_SHOW_BEFORE_SECONDS_BY_CCID = {
    192: DEFAULT_OVERLAY_SHOW_BEFORE_SECONDS,
    193: DEFAULT_OVERLAY_SHOW_BEFORE_SECONDS,
    680: DEFAULT_OVERLAY_SHOW_BEFORE_SECONDS,
}
DEFAULT_OVERLAY_ICONS_VERSION = 1
DEFAULT_OVERLAY_ICONS = {
    192: "assets/icon/visual-overlay/vivace.png",
    193: "assets/icon/visual-overlay/march-song.png",
    680: "assets/icon/visual-overlay/battlefield-overture.png",
}
OTHER_SKILL_OVERLAY_CONFIG_KEY = "experimental_other_skill_visual_overlay"
SHORT_COOLDOWN_OVERLAY_CONFIG_KEY = "experimental_short_cooldown_visual_overlay"
BRONNTANAS_HP_OVERLAY_CONFIG_KEY = (
    "experimental_bronntanas_hp_visual_overlay"
)
MIRACLE_ORB_HP_OVERLAY_CONFIG_KEY = (
    "experimental_bu3_miracle_orb_hp_visual_overlay"
)
MIRACLE_ORB_DISPLAY_ORDER = {7605: 0, 7604: 1, 7606: 2}
ROTATING_LASER_COUNTDOWN_OVERLAY_CONFIG_KEY = (
    "experimental_bu34_rotating_laser_visual_countdown"
)
BRONNTANAS_MAX_HP = 1_143_352_700
DEFAULT_BRONNTANAS_HP_OVERLAY_ICON = (
    "assets/icon/visual-overlay/boss/bronntanas.png"
)
MAGIC_CIRCLE_CCID = 10133
PALL_OF_RUINATION_CCID = 803
MANUS_POTION_CCID = 835
PURIFICATION_WAVE_CCID = 645
LIFE_TEMPERATURE_CCID = 874
IGNIS_PLUME_TRACKER_CCID = -59060
AQUA_VOLLEY_TRACKER_CCID = -59061
DEFAULT_OTHER_SKILL_OVERLAY_ITEMS = (
    (
        "magic_circle",
        "魔法阵",
        "assets/icon/visual-overlay/other-skills/magic-circle.png",
        True,
    ),
    (
        "pall_of_ruination",
        "崩坏波动",
        "assets/icon/visual-overlay/other-skills/pall-of-ruination.png",
        True,
    ),
    (
        "manus_potion",
        "马纽斯秘药",
        "assets/icon/visual-overlay/other-skills/manus-potion.png",
        True,
    ),
    (
        "purification_wave",
        "净化之浪",
        "assets/icon/visual-overlay/other-skills/purification-wave.png",
        True,
    ),
    (
        "hamster_supercharged",
        HAMSTER_SETTINGS_NAME,
        "assets/icon/visual-overlay/other-skills/hamster-supercharged.png",
        True,
    ),
    (
        "life_temperature",
        "生命的温度",
        "assets/icon/visual-overlay/life-temperature.png",
        False,
    ),
)
DEFAULT_SHORT_COOLDOWN_OVERLAY_ITEMS = (
    (
        "ignis_plume",
        "爆炎箭",
        "assets/icon/visual-overlay/short-cooldown/ignis-plume.png",
        IGNIS_PLUME_TRACKER_CCID,
        True,
    ),
    (
        "aqua_volley",
        "水流箭",
        "assets/icon/visual-overlay/short-cooldown/aqua-volley.png",
        AQUA_VOLLEY_TRACKER_CCID,
        True,
    ),
)
DEFAULT_ASTROLOGY_OVERLAY_ITEMS = (
    (
        "starry_field",
        "星辉领域",
        int(ASTROLOGY_SKILLS["starry_field"]["skill_id"]),
        "assets/icon/visual-overlay/astrology/stellar-surge.png",
    ),
    (
        "whirling_assault",
        "疾旋突袭",
        int(ASTROLOGY_SKILLS["whirling_assault"]["skill_id"]),
        "assets/icon/visual-overlay/astrology/meridian-sweep.png",
    ),
)
ASTROLOGY_SNAPSHOT_REASSERT_SECONDS = 0.5
DEFAULT_DEBUFF_OVERLAY_ITEMS = (
    (
        "bernak_magic",
        "伯雷纳克-魔法",
        "assets/icon/visual-overlay/debuff/brionac-magic.png",
    ),
    (
        "bernak_physical",
        "伯雷纳克-物理",
        "assets/icon/visual-overlay/debuff/brionac-physical.png",
    ),
    (
        "rabbit",
        "兔子增伤",
        "assets/icon/visual-overlay/debuff/rabbit-damage.png",
    ),
    (
        "damage_bonus",
        "死亡锁定增伤",
        "assets/icon/visual-overlay/debuff/death-mark.png",
    ),
    (
        "magic_break",
        "海德拉魔法保护破坏",
        "assets/icon/visual-overlay/debuff/hydra-magic-protection.png",
    ),
    (
        "physical_break",
        "升龙裂破物理保护破坏",
        "assets/icon/visual-overlay/debuff/spinning-uppercut.png",
    ),
    (
        "dragon_thunder",
        "青龙雷兽",
        "assets/icon/visual-overlay/debuff/mir-dragon.png",
    ),
    (
        "cat",
        "猫",
        "assets/icon/visual-overlay/debuff/purrling.png",
    ),
    (
        "kart_bubble",
        "卡丁车水泡",
        "assets/icon/visual-overlay/debuff/kart-water-balloon.png",
    ),
)


@dataclass(frozen=True)
class OtherSkillOverlaySettings:
    enabled: bool = False
    condition_enabled: Mapping[str, bool] = field(
        default_factory=lambda: {
            key: enabled
            for key, _name, _icon, enabled in DEFAULT_OTHER_SKILL_OVERLAY_ITEMS
        }
    )
    condition_icons: Mapping[str, str] = field(
        default_factory=lambda: {
            key: icon
            for key, _name, icon, _enabled in DEFAULT_OTHER_SKILL_OVERLAY_ITEMS
        }
    )
    left_offset_px: int = 8
    center_y_ratio: float = 0.28
    gap_px: int = 6

    def condition_is_enabled(self, key: str) -> bool:
        return bool(self.condition_enabled.get(str(key), False))

    def icon_path(self, key: str) -> str:
        return str(self.condition_icons.get(str(key), "") or "").strip()


@dataclass(frozen=True)
class ShortCooldownOverlaySettings:
    enabled: bool = False
    condition_enabled: Mapping[str, bool] = field(
        default_factory=lambda: {
            key: enabled
            for key, _name, _icon, _ccid, enabled in DEFAULT_SHORT_COOLDOWN_OVERLAY_ITEMS
        }
    )
    condition_icons: Mapping[str, str] = field(
        default_factory=lambda: {
            key: icon
            for key, _name, icon, _ccid, _enabled in DEFAULT_SHORT_COOLDOWN_OVERLAY_ITEMS
        }
    )
    center_y_ratio: float = 0.715
    gap_px: int = 6

    def condition_is_enabled(self, key: str) -> bool:
        return bool(self.condition_enabled.get(str(key), False))

    def icon_path(self, key: str) -> str:
        return str(self.condition_icons.get(str(key), "") or "").strip()


@dataclass(frozen=True)
class AstrologyOverlaySettings:
    enabled_skill_ids: frozenset[int] = field(default_factory=frozenset)
    condition_icons: Mapping[int, str] = field(
        default_factory=lambda: {
            skill_id: icon_path
            for _key, _name, skill_id, icon_path in DEFAULT_ASTROLOGY_OVERLAY_ITEMS
        }
    )
    center_y_ratio: float = 0.605
    slot_offset_px: int = 136

    @property
    def enabled(self) -> bool:
        return bool(self.enabled_skill_ids)

    def skill_is_enabled(self, skill_id: int) -> bool:
        return int(skill_id) in self.enabled_skill_ids

    def icon_path(self, skill_id: int) -> str:
        return str(self.condition_icons.get(int(skill_id), "") or "").strip()


@dataclass(frozen=True)
class BronntanasHpOverlaySettings:
    enabled: bool = False
    icon_path: str = DEFAULT_BRONNTANAS_HP_OVERLAY_ICON
    activation_percent: float = 52.0
    warning_percent: float = 50.0
    dismiss_after_ms: int = 2_000
    center_y_ratio: float = 0.89


@dataclass
class BronntanasHpOverlaySession:
    entity_id: str | None = None
    warning_started_at_ms: int | None = None
    completed: bool = False

    def reset(self) -> None:
        self.entity_id = None
        self.warning_started_at_ms = None
        self.completed = False


@dataclass(frozen=True)
class MiracleOrbHpOverlaySettings:
    enabled: bool = False
    left_x_ratio: float = 0.108
    top_y_ratio: float = 0.125
    focus_center_y_ratio: float = 0.855


@dataclass(frozen=True)
class RotatingLaserCountdownOverlaySettings:
    enabled: bool = False
    center_y_ratio: float = 0.89


@dataclass(frozen=True)
class MusicOverlaySettings:
    enabled: bool = False
    show_before_seconds: float = DEFAULT_OVERLAY_SHOW_BEFORE_SECONDS
    entity_name: str = "自己"
    width: int = 300
    toast_height: int = 72
    top_offset_px: int = 72
    gap_px: int = 6
    refresh_ms: int = 30
    hide_when_game_inactive: bool = True
    target_process_names: tuple[str, ...] = ("Client.exe",)
    target_window_titles: tuple[str, ...] = ("洛奇", "Mabinogi")
    condition_enabled: Mapping[int, bool] = field(
        default_factory=lambda: dict(DEFAULT_OVERLAY_CONDITIONS)
    )
    condition_icons: Mapping[int, str] = field(
        default_factory=lambda: dict(DEFAULT_OVERLAY_ICONS)
    )
    condition_show_before_seconds: Mapping[int, float] = field(
        default_factory=lambda: dict(DEFAULT_OVERLAY_SHOW_BEFORE_SECONDS_BY_CCID)
    )
    condition_ring_sound_enabled: Mapping[int, bool] = field(default_factory=dict)
    ring_sound_enabled: bool = False
    muted: bool = False
    tuan_silence_enabled: bool = False
    arrival_sound: str = "assets/audio/xiaoyi/music_strong_beep.wav"
    three_second_sound: str = "assets/audio/xiaoyi/music_strong_beep.wav"
    other_skill_hud: OtherSkillOverlaySettings = field(
        default_factory=OtherSkillOverlaySettings
    )
    short_cooldown_hud: ShortCooldownOverlaySettings = field(
        default_factory=ShortCooldownOverlaySettings
    )
    astrology_hud: AstrologyOverlaySettings = field(
        default_factory=AstrologyOverlaySettings
    )
    bronntanas_hp_hud: BronntanasHpOverlaySettings = field(
        default_factory=BronntanasHpOverlaySettings
    )
    miracle_orb_hp_hud: MiracleOrbHpOverlaySettings = field(
        default_factory=MiracleOrbHpOverlaySettings
    )
    rotating_laser_countdown_hud: RotatingLaserCountdownOverlaySettings = field(
        default_factory=RotatingLaserCountdownOverlaySettings
    )

    def condition_is_enabled(self, ccid: int) -> bool:
        return bool(self.condition_enabled.get(int(ccid), False))

    def icon_path(self, ccid: int) -> str:
        return str(self.condition_icons.get(int(ccid), "") or "").strip()

    def show_before_seconds_for(self, ccid: int) -> float:
        try:
            value = float(
                self.condition_show_before_seconds.get(
                    int(ccid), self.show_before_seconds
                )
            )
        except (TypeError, ValueError):
            return self.show_before_seconds
        return value if value > 0 else self.show_before_seconds

    def ring_sound_is_enabled(self, ccid: int) -> bool:
        return bool(
            self.condition_ring_sound_enabled.get(
                int(ccid), self.ring_sound_enabled
            )
        )

    def process_is_enabled(self) -> bool:
        return (
            self.enabled
            or self.other_skill_hud.enabled
            or self.short_cooldown_hud.enabled
            or self.astrology_hud.enabled
            or self.bronntanas_hp_hud.enabled
            or self.miracle_orb_hp_hud.enabled
            or self.rotating_laser_countdown_hud.enabled
        )


def load_music_overlay_settings(config_path: str | Path) -> MusicOverlaySettings:
    path = Path(config_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return MusicOverlaySettings()
    raw = data.get("experimental_music_visual_overlay")
    if not isinstance(raw, dict):
        raw = {}
    raw_other = data.get(OTHER_SKILL_OVERLAY_CONFIG_KEY)
    if not isinstance(raw_other, dict):
        raw_other = {}
    raw_short = data.get(SHORT_COOLDOWN_OVERLAY_CONFIG_KEY)
    if not isinstance(raw_short, dict):
        raw_short = {}
    raw_bronntanas = data.get(BRONNTANAS_HP_OVERLAY_CONFIG_KEY)
    bronntanas_config_present = isinstance(raw_bronntanas, dict)
    if not bronntanas_config_present:
        raw_bronntanas = {}
    raw_miracle_orb = data.get(MIRACLE_ORB_HP_OVERLAY_CONFIG_KEY)
    miracle_orb_config_present = isinstance(raw_miracle_orb, dict)
    if not miracle_orb_config_present:
        raw_miracle_orb = {}
    raw_rotating_laser = data.get(ROTATING_LASER_COUNTDOWN_OVERLAY_CONFIG_KEY)
    rotating_laser_config_present = isinstance(raw_rotating_laser, dict)
    if not rotating_laser_config_present:
        raw_rotating_laser = {}

    def _positive_float(key: str, default: float) -> float:
        try:
            value = float(raw.get(key, default))
        except (TypeError, ValueError):
            return default
        return value if value > 0 else default

    legacy_show_before_seconds = _positive_float(
        "show_before_seconds", DEFAULT_OVERLAY_SHOW_BEFORE_SECONDS
    )
    if "ring_sound_enabled" in raw:
        legacy_ring_sound_enabled = bool(raw.get("ring_sound_enabled"))
    elif "muted" in raw:
        legacy_ring_sound_enabled = not bool(raw.get("muted"))
    else:
        legacy_ring_sound_enabled = False
    try:
        condition_controls_version = int(raw.get("condition_controls_version", 0))
    except (TypeError, ValueError):
        condition_controls_version = 0

    conditions = dict(DEFAULT_OVERLAY_CONDITIONS)
    try:
        default_icons_version = int(raw.get("default_icons_version", 0))
    except (TypeError, ValueError):
        default_icons_version = 0
    condition_icons: dict[int, str] = dict(DEFAULT_OVERLAY_ICONS)
    if condition_controls_version < 1 and "show_before_seconds" in raw:
        condition_show_before_seconds = {
            ccid: legacy_show_before_seconds
            for ccid in DEFAULT_OVERLAY_SHOW_BEFORE_SECONDS_BY_CCID
        }
    else:
        condition_show_before_seconds = dict(
            DEFAULT_OVERLAY_SHOW_BEFORE_SECONDS_BY_CCID
        )
    condition_ring_sound_enabled: dict[int, bool] = {}
    raw_conditions = raw.get("conditions")
    if isinstance(raw_conditions, dict):
        for key, value in raw_conditions.items():
            try:
                ccid = int(key)
            except (TypeError, ValueError):
                continue
            if ccid not in DEFAULT_OVERLAY_CONDITIONS:
                continue
            if isinstance(value, dict):
                conditions[ccid] = bool(value.get("enabled", False))
                icon = str(value.get("icon") or "").strip()
                if "icon" in value and (
                    icon or default_icons_version >= DEFAULT_OVERLAY_ICONS_VERSION
                ):
                    condition_icons[ccid] = icon
                try:
                    show_before_seconds = float(
                        value.get(
                            "show_before_seconds", legacy_show_before_seconds
                        )
                    )
                except (TypeError, ValueError):
                    show_before_seconds = legacy_show_before_seconds
                condition_show_before_seconds[ccid] = (
                    show_before_seconds
                    if show_before_seconds > 0
                    else legacy_show_before_seconds
                )
                condition_ring_sound_enabled[ccid] = bool(
                    value.get(
                        "ring_sound_enabled", legacy_ring_sound_enabled
                    )
                )
            else:
                conditions[ccid] = bool(value)

    def _positive_int(key: str, default: int, minimum: int = 1) -> int:
        try:
            value = int(raw.get(key, default))
        except (TypeError, ValueError):
            return default
        return value if value >= minimum else default

    def _strings(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
        value = raw.get(key)
        if not isinstance(value, list):
            return default
        result = tuple(str(item).strip() for item in value if str(item).strip())
        return result or default

    other_enabled = {
        key: enabled
        for key, _name, _icon, enabled in DEFAULT_OTHER_SKILL_OVERLAY_ITEMS
    }
    other_icons = {
        key: icon
        for key, _name, icon, _enabled in DEFAULT_OTHER_SKILL_OVERLAY_ITEMS
    }
    raw_other_conditions = raw_other.get("conditions")
    if isinstance(raw_other_conditions, dict):
        for key, _name, _icon, _enabled in DEFAULT_OTHER_SKILL_OVERLAY_ITEMS:
            value = raw_other_conditions.get(key)
            if not isinstance(value, dict):
                continue
            other_enabled[key] = bool(value.get("enabled", other_enabled[key]))
            icon = str(value.get("icon") or "").strip()
            if icon:
                other_icons[key] = icon
    try:
        other_left_offset_px = max(0, int(raw_other.get("left_offset_px", 8)))
    except (TypeError, ValueError):
        other_left_offset_px = 8
    try:
        other_center_y_ratio = float(raw_other.get("center_y_ratio", 0.28))
    except (TypeError, ValueError):
        other_center_y_ratio = 0.28
    other_center_y_ratio = min(0.9, max(0.1, other_center_y_ratio))
    try:
        other_gap_px = max(0, int(raw_other.get("gap_px", 6)))
    except (TypeError, ValueError):
        other_gap_px = 6
    other_skill_hud = OtherSkillOverlaySettings(
        enabled=bool(raw_other.get("enabled", False)),
        condition_enabled=other_enabled,
        condition_icons=other_icons,
        left_offset_px=other_left_offset_px,
        center_y_ratio=other_center_y_ratio,
        gap_px=other_gap_px,
    )

    short_enabled = {
        key: enabled
        for key, _name, _icon, _ccid, enabled in DEFAULT_SHORT_COOLDOWN_OVERLAY_ITEMS
    }
    short_icons = {
        key: icon
        for key, _name, icon, _ccid, _enabled in DEFAULT_SHORT_COOLDOWN_OVERLAY_ITEMS
    }
    raw_short_conditions = raw_short.get("conditions")
    if isinstance(raw_short_conditions, dict):
        for key, _name, _icon, _ccid, _enabled in DEFAULT_SHORT_COOLDOWN_OVERLAY_ITEMS:
            value = raw_short_conditions.get(key)
            if not isinstance(value, dict):
                continue
            short_enabled[key] = bool(value.get("enabled", short_enabled[key]))
            icon = str(value.get("icon") or "").strip()
            if icon:
                short_icons[key] = icon
    try:
        short_center_y_ratio = float(raw_short.get("center_y_ratio", 0.715))
    except (TypeError, ValueError):
        short_center_y_ratio = 0.715
    short_center_y_ratio = min(0.9, max(0.1, short_center_y_ratio))
    try:
        short_gap_px = max(0, int(raw_short.get("gap_px", 6)))
    except (TypeError, ValueError):
        short_gap_px = 6
    short_cooldown_hud = ShortCooldownOverlaySettings(
        enabled=bool(raw_short.get("enabled", False)),
        condition_enabled=short_enabled,
        condition_icons=short_icons,
        center_y_ratio=short_center_y_ratio,
        gap_px=short_gap_px,
    )
    astrology_tracker_settings = load_astrology_card_tracker_settings(data)
    astrology_hud = AstrologyOverlaySettings(
        enabled_skill_ids=frozenset(
            skill_id
            for skill_id in astrology_tracker_settings.tracked_skill_ids
            if skill_id in ASTROLOGY_CORE_COOLDOWN_DEFAULTS
        )
    )
    try:
        bronntanas_activation_percent = float(
            raw_bronntanas.get("activation_percent", 52.0)
        )
    except (TypeError, ValueError):
        bronntanas_activation_percent = 52.0
    try:
        bronntanas_warning_percent = float(
            raw_bronntanas.get("warning_percent", 50.0)
        )
    except (TypeError, ValueError):
        bronntanas_warning_percent = 50.0
    try:
        bronntanas_dismiss_after_ms = max(
            1,
            int(
                round(
                    float(raw_bronntanas.get("dismiss_after_seconds", 2.0))
                    * 1000
                )
            ),
        )
    except (TypeError, ValueError):
        bronntanas_dismiss_after_ms = 2_000
    try:
        bronntanas_center_y_ratio = float(
            raw_bronntanas.get("center_y_ratio", 0.89)
        )
    except (TypeError, ValueError):
        bronntanas_center_y_ratio = 0.89
    bronntanas_hp_hud = BronntanasHpOverlaySettings(
        enabled=(
            bool(raw_bronntanas.get("enabled", True))
            if bronntanas_config_present
            else False
        ),
        icon_path=(
            str(
                raw_bronntanas.get("icon")
                or DEFAULT_BRONNTANAS_HP_OVERLAY_ICON
            ).strip()
            or DEFAULT_BRONNTANAS_HP_OVERLAY_ICON
        ),
        activation_percent=min(
            100.0, max(0.0, bronntanas_activation_percent)
        ),
        warning_percent=min(100.0, max(0.0, bronntanas_warning_percent)),
        dismiss_after_ms=bronntanas_dismiss_after_ms,
        center_y_ratio=min(0.98, max(0.1, bronntanas_center_y_ratio)),
    )
    def _miracle_ratio(key: str, default: float) -> float:
        try:
            return min(0.98, max(0.0, float(raw_miracle_orb.get(key, default))))
        except (TypeError, ValueError):
            return default

    miracle_orb_hp_hud = MiracleOrbHpOverlaySettings(
        enabled=(
            bool(raw_miracle_orb.get("enabled", True))
            if miracle_orb_config_present
            else False
        ),
        left_x_ratio=_miracle_ratio("left_x_ratio", 0.108),
        top_y_ratio=_miracle_ratio("top_y_ratio", 0.125),
        focus_center_y_ratio=_miracle_ratio("focus_center_y_ratio", 0.855),
    )
    try:
        rotating_laser_center_y_ratio = min(
            0.98,
            max(0.1, float(raw_rotating_laser.get("center_y_ratio", 0.89))),
        )
    except (TypeError, ValueError):
        rotating_laser_center_y_ratio = 0.89
    rotating_laser_countdown_hud = RotatingLaserCountdownOverlaySettings(
        enabled=(
            bool(raw_rotating_laser.get("enabled", True))
            if rotating_laser_config_present
            else False
        ),
        center_y_ratio=rotating_laser_center_y_ratio,
    )

    return MusicOverlaySettings(
        enabled=bool(raw.get("enabled", False)),
        show_before_seconds=legacy_show_before_seconds,
        entity_name=str(raw.get("entity_name") or "自己").strip() or "自己",
        width=_positive_int("width", 300, 200),
        toast_height=_positive_int("toast_height", 72, 48),
        top_offset_px=_positive_int("top_offset_px", 72, 0),
        gap_px=_positive_int("gap_px", 6, 0),
        refresh_ms=_positive_int("refresh_ms", 30, 15),
        hide_when_game_inactive=bool(raw.get("hide_when_game_inactive", True)),
        target_process_names=_strings(
            "target_process_names", ("Client.exe",)
        ),
        target_window_titles=_strings(
            "target_window_titles", ("洛奇", "Mabinogi")
        ),
        condition_enabled=conditions,
        condition_icons=condition_icons,
        condition_show_before_seconds=condition_show_before_seconds,
        condition_ring_sound_enabled=condition_ring_sound_enabled,
        ring_sound_enabled=legacy_ring_sound_enabled,
        muted=(
            bool(raw.get("muted", False))
            if condition_controls_version < 1
            else False
        ),
        tuan_silence_enabled=bool(raw.get("tuan_silence_enabled", False)),
        arrival_sound=str(
            raw.get("arrival_sound")
            or "assets/audio/xiaoyi/music_strong_beep.wav"
        ),
        three_second_sound=str(
            raw.get("three_second_sound")
            or "assets/audio/xiaoyi/music_strong_beep.wav"
        ),
        other_skill_hud=other_skill_hud,
        short_cooldown_hud=short_cooldown_hud,
        astrology_hud=astrology_hud,
        bronntanas_hp_hud=bronntanas_hp_hud,
        miracle_orb_hp_hud=miracle_orb_hp_hud,
        rotating_laser_countdown_hud=rotating_laser_countdown_hud,
    )


def command_for_music_state(
    state: BuffState,
    settings: MusicOverlaySettings,
    *,
    entity_name: str | None = None,
) -> dict[str, Any]:
    ccid = int(state.spec.ccid)
    if (
        not settings.condition_is_enabled(ccid)
        or not state.active
        or state.end_ms is None
    ):
        return {"type": "remove", "ccid": ccid}
    return {
        "type": "upsert",
        "ccid": ccid,
        "name": state.spec.name,
        "entity_name": entity_name or settings.entity_name,
        "end_ms": int(state.end_ms),
        "show_before_ms": int(settings.show_before_seconds_for(ccid) * 1000),
        "ring_sound_enabled": settings.ring_sound_is_enabled(ccid),
        "timing_source": state.last_timing_source or "unknown",
        "icon_path": settings.icon_path(ccid),
    }


def music_overlay_is_safely_covered_by_tuan(
    state: BuffState,
    states: Mapping[int, BuffState],
    *,
    now_ms: int | None = None,
) -> bool:
    if (
        state.spec.ccid not in MUSIC_BUFF_CCIDS
        or not state.active
        or state.end_ms is None
        or state.music_toan_extended
    ):
        return False
    tuan_state = states.get(TUAN_SONG_CCID)
    if (
        tuan_state is None
        or not tuan_state.active
        or tuan_state.end_ms is None
    ):
        return False
    if now_ms is not None and (
        state.end_ms <= now_ms or tuan_state.end_ms <= now_ms
    ):
        return False
    return tuan_state.end_ms > state.end_ms


def command_for_key_enemy_debuff_states(
    spec: KeyEnemyDebuffAlertSpec | None,
    entity_states: Mapping[str, KeyEnemyDebuffEntityState] | None,
) -> dict[str, Any]:
    if spec is None or not spec.visual_hud_enabled or not entity_states:
        return {"type": "debuff_clear"}
    active_states = [state for state in entity_states.values() if state.active]
    if not active_states:
        return {"type": "debuff_clear"}
    state = max(active_states, key=lambda item: item.last_seen_at_ms or 0)
    requirements: list[dict[str, Any]] = []
    for key, name, icon_path in DEFAULT_DEBUFF_OVERLAY_ITEMS:
        complete_state = state.requirements.get(key)
        expiry_state = state.expiry_requirements.get(key)
        requirements.append(
            {
                "key": key,
                "name": name,
                "icon_path": icon_path,
                "complete": bool(complete_state and complete_state.active),
                "complete_end_ms": (
                    complete_state.end_ms if complete_state is not None else None
                ),
                "expiry_active": bool(expiry_state and expiry_state.active),
                "expiry_end_ms": (
                    expiry_state.end_ms if expiry_state is not None else None
                ),
            }
        )
    return {
        "type": "debuff_snapshot",
        "entity_id": state.tracked_entity_id,
        "expiry_threshold_ms": max(0, int(spec.expiry_seconds * 1000)),
        "visual_expiry_enabled": bool(spec.visual_expiry_enabled),
        "requirements": requirements,
    }


def next_life_temperature_missing_latch(
    previous: bool,
    state: BuffState | None,
) -> bool:
    if state is None:
        return previous
    if state.active and int(state.stacks or 0) >= 5:
        return False
    if not state.active and (
        state.last_event_at_ms is not None or state.last_apply_at_ms is not None
    ):
        return True
    return previous


def _skill_cooldown_is_ready(state: BuffState | None, now_ms: int) -> bool:
    if state is None or state.cooldown_anchor_at_ms is None:
        return False
    ready_at_ms = state.cooldown_anchor_at_ms + int(
        state.spec.cooldown_delay_seconds * 1000
    )
    return now_ms >= ready_at_ms


def _observed_effect_has_ended(state: BuffState | None) -> bool:
    if state is None or state.active:
        return False
    return state.last_event_at_ms is not None or state.last_apply_at_ms is not None


def command_for_other_skill_states(
    settings: OtherSkillOverlaySettings,
    states: Mapping[int, BuffState],
    key_enemy_debuff_states: Mapping[str, KeyEnemyDebuffEntityState] | None,
    *,
    now_ms: int,
    life_temperature_missing: bool,
) -> dict[str, Any]:
    if not settings.enabled or not key_enemy_debuff_states:
        return {"type": "other_skill_clear"}
    if not any(state.active for state in key_enemy_debuff_states.values()):
        return {"type": "other_skill_clear"}

    visible = {
        "magic_circle": _skill_cooldown_is_ready(
            states.get(MAGIC_CIRCLE_CCID), now_ms
        ),
        "pall_of_ruination": _skill_cooldown_is_ready(
            states.get(PALL_OF_RUINATION_CCID), now_ms
        ),
        "manus_potion": _observed_effect_has_ended(
            states.get(MANUS_POTION_CCID)
        ),
        "purification_wave": _observed_effect_has_ended(
            states.get(PURIFICATION_WAVE_CCID)
        ),
        "hamster_supercharged": _observed_effect_has_ended(
            states.get(HAMSTER_SUPERCHARGED_CCID)
        ),
        "life_temperature": life_temperature_missing,
    }
    items = [
        {
            "key": key,
            "name": name,
            "icon_path": settings.icon_path(key) or icon_path,
        }
        for key, name, icon_path, _default_enabled in DEFAULT_OTHER_SKILL_OVERLAY_ITEMS
        if settings.condition_is_enabled(key) and visible.get(key, False)
    ]
    if not items:
        return {"type": "other_skill_clear"}
    return {"type": "other_skill_snapshot", "items": items}


def command_for_short_cooldown_states(
    settings: ShortCooldownOverlaySettings,
    states: Mapping[int, BuffState],
    key_enemy_debuff_states: Mapping[str, KeyEnemyDebuffEntityState] | None,
    *,
    now_ms: int,
    test_target_active: bool = False,
) -> dict[str, Any]:
    if not settings.enabled:
        return {"type": "short_cooldown_clear"}
    key_enemy_active = bool(
        key_enemy_debuff_states
        and any(state.active for state in key_enemy_debuff_states.values())
    )
    if not key_enemy_active and not test_target_active:
        return {"type": "short_cooldown_clear"}

    items = [
        {
            "key": key,
            "name": name,
            "icon_path": settings.icon_path(key) or icon_path,
        }
        for key, name, icon_path, tracker_ccid, _default_enabled in DEFAULT_SHORT_COOLDOWN_OVERLAY_ITEMS
        if settings.condition_is_enabled(key)
        and _skill_cooldown_is_ready(states.get(tracker_ccid), now_ms)
    ]
    if not items:
        return {"type": "short_cooldown_clear"}
    return {"type": "short_cooldown_snapshot", "items": items}


def command_for_astrology_tracker(
    settings: AstrologyOverlaySettings,
    tracker: AstrologyCardTracker | None,
    *,
    self_identity_confirmed: bool,
    tracking_context_active: bool,
) -> dict[str, Any]:
    if (
        not settings.enabled
        or not self_identity_confirmed
        or not tracking_context_active
        or tracker is None
        or not tracker.configured
    ):
        return {"type": "astrology_clear"}

    enabled = [
        item
        for item in DEFAULT_ASTROLOGY_OVERLAY_ITEMS
        if settings.skill_is_enabled(item[2])
        and tracker.settings.tracks_skill(item[2])
    ]
    if not enabled:
        return {"type": "astrology_clear"}

    items: list[dict[str, Any]] = []
    for index, (key, name, skill_id, default_icon) in enumerate(enabled):
        slot = 0 if len(enabled) == 1 else (-1 if index == 0 else 1)
        items.append(
            {
                "key": key,
                "name": name,
                "skill_id": skill_id,
                "icon_path": settings.icon_path(skill_id) or default_icon,
                "slot": slot,
                "cooldown_ready_at_ms": tracker.skill_cooldown_ready_at_ms(
                    skill_id
                ),
                "card_ready": tracker.skill_can_consume_current_card(skill_id),
            }
        )
    return {"type": "astrology_snapshot", "items": items}


def command_for_bronntanas_hp_state(
    settings: BronntanasHpOverlaySettings,
    state: BossHpAlertState | None,
    session: BronntanasHpOverlaySession,
    *,
    now_ms: int,
) -> dict[str, Any]:
    clear_command = {"type": "bronntanas_hp_clear"}
    if not settings.enabled:
        session.reset()
        return clear_command

    if state is None or not state.tracked_entity_id:
        return clear_command

    entity_id = str(state.tracked_entity_id)
    if session.entity_id != entity_id:
        session.entity_id = entity_id
        session.warning_started_at_ms = None
        session.completed = False
    if session.completed:
        return clear_command

    if (
        not state.active
        or state.last_current_hp is None
        or state.last_max_hp is None
        or state.last_max_hp <= 0
    ):
        # Do not reset a completed encounter on transient death/removal stats.
        # A different entity id (or an explicit bridge reset) starts the next
        # encounter.
        return clear_command

    percent = min(
        100.0,
        max(0.0, float(state.last_current_hp) / float(state.last_max_hp) * 100),
    )
    displayed_percent = float(f"{percent:.2f}")
    displayed_warning_percent = float(f"{settings.warning_percent:.2f}")
    if (
        session.warning_started_at_ms is None
        and displayed_percent <= displayed_warning_percent
    ):
        observed_at_ms = state.last_seen_at_ms
        session.warning_started_at_ms = (
            int(observed_at_ms)
            if observed_at_ms is not None and int(observed_at_ms) <= int(now_ms)
            else int(now_ms)
        )

    warning_started_at_ms = session.warning_started_at_ms
    if warning_started_at_ms is not None:
        dismiss_at_ms = warning_started_at_ms + settings.dismiss_after_ms
        if int(now_ms) >= dismiss_at_ms:
            session.completed = True
            return clear_command
    else:
        if percent > settings.activation_percent:
            return clear_command
        dismiss_at_ms = None

    return {
        "type": "bronntanas_hp_snapshot",
        "entity_id": entity_id,
        "percent": percent,
        "warning": warning_started_at_ms is not None,
        "warning_started_at_ms": warning_started_at_ms,
        "dismiss_at_ms": dismiss_at_ms,
        "icon_path": settings.icon_path,
    }


def command_for_miracle_orb_hp_states(
    settings: MiracleOrbHpOverlaySettings,
    states: Mapping[str, MiracleOrbHpState] | None,
    selected_entity_id: str | None,
) -> dict[str, Any]:
    if not settings.enabled or not states:
        return {"type": "miracle_orb_hp_clear"}

    items: list[dict[str, Any]] = []
    for state in sorted(
        states.values(),
        key=lambda candidate: MIRACLE_ORB_DISPLAY_ORDER.get(candidate.race_id, 99),
    ):
        if (
            not state.active
            or state.last_current_hp is None
            or state.last_max_hp is None
            or state.last_max_hp <= 0
        ):
            continue
        items.append(
            {
                "entity_id": state.entity_id,
                "race_id": state.race_id,
                "percent": min(
                    100.0,
                    max(0.0, state.last_current_hp / state.last_max_hp * 100.0),
                ),
            }
        )
    if not items:
        return {"type": "miracle_orb_hp_clear"}

    selected = next(
        (item for item in items if item["entity_id"] == selected_entity_id),
        None,
    )
    return {
        "type": "miracle_orb_hp_snapshot",
        "items": items,
        "selected": selected,
    }


def command_for_rotating_laser_countdown(
    settings: RotatingLaserCountdownOverlaySettings,
    states_by_max_hp: Mapping[int, BossLaserAlertState] | None,
    *,
    now_ms: int,
) -> dict[str, Any]:
    if not settings.enabled or not states_by_max_hp:
        return {"type": "rotating_laser_countdown_clear"}

    seen: set[int] = set()
    active: list[BossLaserMovementCountdownState] = []
    for state in states_by_max_hp.values():
        state_key = id(state)
        if state_key in seen:
            continue
        seen.add(state_key)
        movement = state.movement_countdown
        if (
            state.active
            and movement is not None
            and int(now_ms) < movement.end_at_ms
        ):
            active.append(movement)
    if not active:
        return {"type": "rotating_laser_countdown_clear"}

    movement = max(active, key=lambda item: item.start_at_ms)
    return {
        "type": "rotating_laser_countdown_snapshot",
        "boss_entity_id": movement.boss_entity_id,
        "start_at_ms": movement.start_at_ms,
        "end_at_ms": movement.end_at_ms,
        "duration_ms": movement.duration_ms,
    }


class MusicOverlayPublisher:
    def __init__(
        self,
        config_path: str | Path,
        *,
        settings: MusicOverlaySettings | None = None,
    ) -> None:
        self.config_path = Path(config_path).resolve()
        self.settings = settings or load_music_overlay_settings(self.config_path)
        self.process: subprocess.Popen[str] | None = None
        self._stderr_handle: Any = None
        self._last_commands: dict[int, str] = {}
        self._last_debuff_command: str | None = None
        self._last_other_skill_command: str | None = None
        self._last_short_cooldown_command: str | None = None
        self._last_astrology_command: str | None = None
        self._last_bronntanas_hp_command: str | None = None
        self._last_miracle_orb_hp_command: str | None = None
        self._last_rotating_laser_countdown_command: str | None = None
        self._last_astrology_sent_at = 0.0
        self._bronntanas_hp_session = BronntanasHpOverlaySession()
        self._life_temperature_missing = False
        self._reported_failure = False

    def start(self) -> None:
        if not self.settings.process_is_enabled():
            return
        if self.process is not None:
            if self.process.poll() is None:
                return
            self.process = None
            self._close_log()
        command = self._sidecar_command()
        if command is None:
            print("[overlay] disabled: BuffWatcherOverlay.exe not found")
            return
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            log_dir = app_root() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            self._stderr_handle = (log_dir / "music-overlay.log").open(
                "a", encoding="utf-8"
            )
            self.process = subprocess.Popen(
                command,
                cwd=str(app_root()),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=self._stderr_handle,
                text=True,
                encoding="utf-8",
                bufsize=1,
                creationflags=creationflags,
            )
            self._last_commands.clear()
            self._last_debuff_command = None
            self._last_other_skill_command = None
            self._last_short_cooldown_command = None
            self._last_astrology_command = None
            self._last_bronntanas_hp_command = None
            self._last_miracle_orb_hp_command = None
            self._last_rotating_laser_countdown_command = None
            self._last_astrology_sent_at = 0.0
            self._bronntanas_hp_session.reset()
            self._reported_failure = False
            print("[overlay] visual HUD sidecar enabled")
        except OSError as exc:
            self.process = None
            self._close_log()
            print(f"[overlay] failed to start: {exc}")

    def _sidecar_command(self) -> list[str] | None:
        if not getattr(sys, "frozen", False):
            return [
                sys.executable,
                "-m",
                "buffwatcher.music_overlay",
                "--config",
                str(self.config_path),
            ]
        candidates = [
            app_root().parent / "BuffWatcherOverlay" / "BuffWatcherOverlay.exe",
            app_root() / "BuffWatcherOverlay.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return [str(candidate), "--config", str(self.config_path)]
        return None

    def sync_states(
        self,
        states: Mapping[int, BuffState],
        *,
        entity_name: str | None = None,
        key_enemy_debuff_alert: KeyEnemyDebuffAlertSpec | None = None,
        key_enemy_debuff_states: Mapping[
            str, KeyEnemyDebuffEntityState
        ] | None = None,
        short_cooldown_test_target_active: bool = False,
        astrology_tracking_active: bool = False,
        self_identity_confirmed: bool = False,
        astrology_card_tracker: AstrologyCardTracker | None = None,
        boss_hp_states_by_max_hp: Mapping[int, BossHpAlertState] | None = None,
        miracle_orb_hp_states: Mapping[str, MiracleOrbHpState] | None = None,
        miracle_orb_selected_entity_id: str | None = None,
        boss_laser_states_by_max_hp: Mapping[int, BossLaserAlertState] | None = None,
    ) -> None:
        if not self.settings.process_is_enabled():
            return
        self.start()
        current_ms = int(time.time() * 1000)
        if self.settings.enabled:
            for ccid in sorted(self.settings.condition_enabled):
                state = states.get(ccid)
                if state is None:
                    command = {"type": "remove", "ccid": ccid}
                elif self.settings.tuan_silence_enabled and music_overlay_is_safely_covered_by_tuan(
                    state, states, now_ms=current_ms
                ):
                    command = {"type": "remove", "ccid": ccid}
                else:
                    command = command_for_music_state(
                        state,
                        self.settings,
                        entity_name=entity_name,
                    )
                fingerprint = json.dumps(
                    command, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                if self._last_commands.get(ccid) == fingerprint:
                    continue
                if self._send(command):
                    self._last_commands[ccid] = fingerprint
        debuff_command = command_for_key_enemy_debuff_states(
            key_enemy_debuff_alert,
            key_enemy_debuff_states,
        )
        debuff_fingerprint = json.dumps(
            debuff_command,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if self._last_debuff_command != debuff_fingerprint and self._send(
            debuff_command
        ):
            self._last_debuff_command = debuff_fingerprint

        self._life_temperature_missing = next_life_temperature_missing_latch(
            self._life_temperature_missing,
            states.get(LIFE_TEMPERATURE_CCID),
        )
        other_skill_command = command_for_other_skill_states(
            self.settings.other_skill_hud,
            states,
            key_enemy_debuff_states,
            now_ms=current_ms,
            life_temperature_missing=self._life_temperature_missing,
        )
        other_skill_fingerprint = json.dumps(
            other_skill_command,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if (
            self._last_other_skill_command != other_skill_fingerprint
            and self._send(other_skill_command)
        ):
            self._last_other_skill_command = other_skill_fingerprint

        short_cooldown_command = command_for_short_cooldown_states(
            self.settings.short_cooldown_hud,
            states,
            key_enemy_debuff_states,
            now_ms=current_ms,
            test_target_active=short_cooldown_test_target_active,
        )
        short_cooldown_fingerprint = json.dumps(
            short_cooldown_command,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if (
            self._last_short_cooldown_command != short_cooldown_fingerprint
            and self._send(short_cooldown_command)
        ):
            self._last_short_cooldown_command = short_cooldown_fingerprint

        astrology_command = command_for_astrology_tracker(
            self.settings.astrology_hud,
            astrology_card_tracker,
            self_identity_confirmed=self_identity_confirmed,
            tracking_context_active=astrology_tracking_active,
        )
        astrology_fingerprint = json.dumps(
            astrology_command,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        astrology_now = time.monotonic()
        if (
            self._last_astrology_command != astrology_fingerprint
            or astrology_now - self._last_astrology_sent_at
            >= ASTROLOGY_SNAPSHOT_REASSERT_SECONDS
        ) and self._send(astrology_command):
            self._last_astrology_command = astrology_fingerprint
            self._last_astrology_sent_at = astrology_now

        bronntanas_hp_state = (
            None
            if boss_hp_states_by_max_hp is None
            else boss_hp_states_by_max_hp.get(BRONNTANAS_MAX_HP)
        )
        bronntanas_hp_command = command_for_bronntanas_hp_state(
            self.settings.bronntanas_hp_hud,
            bronntanas_hp_state,
            self._bronntanas_hp_session,
            now_ms=current_ms,
        )
        bronntanas_hp_fingerprint = json.dumps(
            bronntanas_hp_command,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if (
            self._last_bronntanas_hp_command != bronntanas_hp_fingerprint
            and self._send(bronntanas_hp_command)
        ):
            self._last_bronntanas_hp_command = bronntanas_hp_fingerprint

        miracle_orb_hp_command = command_for_miracle_orb_hp_states(
            self.settings.miracle_orb_hp_hud,
            miracle_orb_hp_states,
            miracle_orb_selected_entity_id,
        )
        miracle_orb_hp_fingerprint = json.dumps(
            miracle_orb_hp_command,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if (
            self._last_miracle_orb_hp_command != miracle_orb_hp_fingerprint
            and self._send(miracle_orb_hp_command)
        ):
            self._last_miracle_orb_hp_command = miracle_orb_hp_fingerprint

        rotating_laser_command = command_for_rotating_laser_countdown(
            self.settings.rotating_laser_countdown_hud,
            boss_laser_states_by_max_hp,
            now_ms=current_ms,
        )
        rotating_laser_fingerprint = json.dumps(
            rotating_laser_command,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if (
            self._last_rotating_laser_countdown_command
            != rotating_laser_fingerprint
            and self._send(rotating_laser_command)
        ):
            self._last_rotating_laser_countdown_command = (
                rotating_laser_fingerprint
            )

    def clear(self) -> None:
        if self.settings.process_is_enabled():
            self._send({"type": "clear"})
        self._last_commands.clear()
        self._last_debuff_command = None
        self._last_other_skill_command = None
        self._last_short_cooldown_command = None
        self._last_astrology_command = None
        self._last_bronntanas_hp_command = None
        self._last_miracle_orb_hp_command = None
        self._last_rotating_laser_countdown_command = None
        self._last_astrology_sent_at = 0.0
        self._bronntanas_hp_session.reset()

    def _send(self, command: Mapping[str, Any]) -> bool:
        process = self.process
        if process is None or process.stdin is None or process.poll() is not None:
            if not self._reported_failure:
                print("[overlay] sidecar is not running; voice alerts continue")
                self._reported_failure = True
            return False
        try:
            process.stdin.write(json.dumps(command, ensure_ascii=False) + "\n")
            process.stdin.flush()
            return True
        except (BrokenPipeError, OSError):
            if not self._reported_failure:
                print("[overlay] sidecar disconnected; voice alerts continue")
                self._reported_failure = True
            return False

    def close(self) -> None:
        process = self.process
        if process is not None:
            self._send({"type": "shutdown"})
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            try:
                process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    pass
        self.process = None
        self._close_log()

    def _close_log(self) -> None:
        if self._stderr_handle is not None:
            try:
                self._stderr_handle.close()
            except OSError:
                pass
        self._stderr_handle = None

    def __enter__(self) -> "MusicOverlayPublisher":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

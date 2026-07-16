from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from buffwatcher.config_migration import _apply_policy_migrations
from buffwatcher.astrology_cards import (
    ASTROLOGY_CARD_TRACKER_CONFIG_KEY,
    default_astrology_card_tracker_config,
    ensure_astrology_card_tracker_config,
)


VISUAL_OVERLAY_CONFIG = {
    "enabled": True,
    "show_before_seconds": 15.0,
    "entity_name": "自己",
    "width": 300,
    "toast_height": 72,
    "top_offset_px": 72,
    "gap_px": 6,
    "refresh_ms": 30,
    "hide_when_game_inactive": True,
    "target_process_names": ["Client.exe"],
    "target_window_titles": ["洛奇", "Mabinogi"],
    "default_icons_version": 1,
    "condition_controls_version": 1,
    "tuan_silence_enabled": False,
    "conditions": {
        "192": {
            "enabled": True,
            "name": "活跃曲",
            "icon": "assets/icon/visual-overlay/vivace.png",
            "show_before_seconds": 15.0,
            "ring_sound_enabled": False,
        },
        "193": {
            "enabled": True,
            "name": "行进曲",
            "icon": "assets/icon/visual-overlay/march-song.png",
            "show_before_seconds": 15.0,
            "ring_sound_enabled": False,
        },
        "680": {
            "enabled": True,
            "name": "战争序曲",
            "icon": "assets/icon/visual-overlay/battlefield-overture.png",
            "show_before_seconds": 15.0,
            "ring_sound_enabled": False,
        },
    },
    "ring_sound_enabled": False,
    "muted": False,
    "arrival_sound": "assets/audio/xiaoyi/music_strong_beep.wav",
    "three_second_sound": "assets/audio/xiaoyi/music_strong_beep.wav",
}

OTHER_SKILL_HUD_CONFIG = {
    "enabled": False,
    "left_offset_px": 8,
    "center_y_ratio": 0.28,
    "gap_px": 6,
    "default_icons_version": 2,
    "conditions": {
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
            "name": "陈睿",
            "icon": "assets/icon/visual-overlay/other-skills/hamster-supercharged.png",
        },
        "life_temperature": {
            "enabled": False,
            "name": "生命的温度",
            "icon": "assets/icon/visual-overlay/life-temperature.png",
        },
    },
}

SHORT_COOLDOWN_HUD_CONFIG = {
    "enabled": True,
    "center_y_ratio": 0.715,
    "gap_px": 6,
    "default_icons_version": 2,
    "conditions": {
        "ignis_plume": {
            "enabled": True,
            "name": "爆炎箭",
            "icon": "assets/icon/visual-overlay/short-cooldown/ignis-plume.png",
        },
        "aqua_volley": {
            "enabled": True,
            "name": "水流箭",
            "icon": "assets/icon/visual-overlay/short-cooldown/aqua-volley.png",
        },
    },
}

BRONNTANAS_HP_HUD_CONFIG = {
    "enabled": True,
    "icon": "assets/icon/visual-overlay/boss/bronntanas.png",
    "activation_percent": 52.0,
    "warning_percent": 50.0,
    "dismiss_after_seconds": 2.0,
    "center_y_ratio": 0.89,
}

MIRACLE_ORB_HP_HUD_CONFIG = {
    "enabled": True,
    "left_x_ratio": 0.108,
    "top_y_ratio": 0.125,
    "focus_center_y_ratio": 0.855,
}

ROTATING_LASER_COUNTDOWN_HUD_CONFIG = {
    "enabled": True,
    "center_y_ratio": 0.89,
}


def merge_missing(target: dict, defaults: dict) -> None:
    for key, value in defaults.items():
        if key not in target:
            target[key] = deepcopy(value)
        elif isinstance(target[key], dict) and isinstance(value, dict):
            merge_missing(target[key], value)


def configure_visual_private(data: dict, *, preserve_existing: bool = False) -> dict:
    existing_overlay = data.get("experimental_music_visual_overlay")
    if preserve_existing and isinstance(existing_overlay, dict):
        merge_missing(existing_overlay, VISUAL_OVERLAY_CONFIG)
        overlay = existing_overlay
    else:
        overlay = deepcopy(VISUAL_OVERLAY_CONFIG)
    conditions = overlay.get("conditions")
    if isinstance(conditions, dict):
        conditions.pop("874", None)
    data["experimental_music_visual_overlay"] = overlay

    existing_other = data.get("experimental_other_skill_visual_overlay")
    if preserve_existing and isinstance(existing_other, dict):
        merge_missing(existing_other, OTHER_SKILL_HUD_CONFIG)
        other_overlay = existing_other
    else:
        other_overlay = deepcopy(OTHER_SKILL_HUD_CONFIG)
    other_conditions = other_overlay.get("conditions")
    if isinstance(other_conditions, dict):
        other_conditions.pop("hamster_adrenaline", None)
    other_overlay["default_icons_version"] = OTHER_SKILL_HUD_CONFIG[
        "default_icons_version"
    ]
    data["experimental_other_skill_visual_overlay"] = other_overlay

    existing_short = data.get("experimental_short_cooldown_visual_overlay")
    if preserve_existing and isinstance(existing_short, dict):
        merge_missing(existing_short, SHORT_COOLDOWN_HUD_CONFIG)
        short_overlay = existing_short
    else:
        short_overlay = deepcopy(SHORT_COOLDOWN_HUD_CONFIG)
    short_overlay["default_icons_version"] = SHORT_COOLDOWN_HUD_CONFIG[
        "default_icons_version"
    ]
    data["experimental_short_cooldown_visual_overlay"] = short_overlay
    existing_bronntanas = data.get(
        "experimental_bronntanas_hp_visual_overlay"
    )
    if preserve_existing and isinstance(existing_bronntanas, dict):
        merge_missing(existing_bronntanas, BRONNTANAS_HP_HUD_CONFIG)
        bronntanas_overlay = existing_bronntanas
    else:
        bronntanas_overlay = deepcopy(BRONNTANAS_HP_HUD_CONFIG)
    data["experimental_bronntanas_hp_visual_overlay"] = bronntanas_overlay
    existing_miracle_orb = data.get(
        "experimental_bu3_miracle_orb_hp_visual_overlay"
    )
    if preserve_existing and isinstance(existing_miracle_orb, dict):
        merge_missing(existing_miracle_orb, MIRACLE_ORB_HP_HUD_CONFIG)
        miracle_orb_overlay = existing_miracle_orb
    else:
        miracle_orb_overlay = deepcopy(MIRACLE_ORB_HP_HUD_CONFIG)
    data[
        "experimental_bu3_miracle_orb_hp_visual_overlay"
    ] = miracle_orb_overlay
    # This is a layout constant rather than a user preference.  Migrate old
    # local configs so the focus bar covers the game's main boss HP bar.
    miracle_orb_overlay["focus_center_y_ratio"] = MIRACLE_ORB_HP_HUD_CONFIG[
        "focus_center_y_ratio"
    ]
    existing_rotating_laser = data.get(
        "experimental_bu34_rotating_laser_visual_countdown"
    )
    if preserve_existing and isinstance(existing_rotating_laser, dict):
        merge_missing(
            existing_rotating_laser,
            ROTATING_LASER_COUNTDOWN_HUD_CONFIG,
        )
        rotating_laser_overlay = existing_rotating_laser
    else:
        rotating_laser_overlay = deepcopy(
            ROTATING_LASER_COUNTDOWN_HUD_CONFIG
        )
    data[
        "experimental_bu34_rotating_laser_visual_countdown"
    ] = rotating_laser_overlay
    existing_astrology = data.get(ASTROLOGY_CARD_TRACKER_CONFIG_KEY)
    if preserve_existing and isinstance(existing_astrology, dict):
        # Convert the former single master switch before adding the new
        # per-skill defaults, otherwise an old enabled=true would be shadowed
        # by two freshly inserted false values.
        ensure_astrology_card_tracker_config(data)
        existing_astrology = data[ASTROLOGY_CARD_TRACKER_CONFIG_KEY]
        merge_missing(existing_astrology, default_astrology_card_tracker_config())
        astrology = existing_astrology
    else:
        astrology = default_astrology_card_tracker_config()
    data[ASTROLOGY_CARD_TRACKER_CONFIG_KEY] = astrology
    data["music_tuan_silence_enabled"] = bool(
        data.get("music_tuan_silence_enabled", False)
    )
    for boss_laser in data.get("boss_laser_alerts", []):
        if isinstance(boss_laser, dict):
            boss_laser.pop("note", None)
            if boss_laser.get("name") == "布3/布4激光预警":
                boss_laser["name"] = "布3/布4激光前倒计时"
    key_enemy_debuff = data.setdefault("key_enemy_debuff_alert", {})
    if isinstance(key_enemy_debuff, dict):
        if preserve_existing:
            key_enemy_debuff.setdefault("complete_enabled", False)
            key_enemy_debuff.setdefault("visual_hud_enabled", False)
        else:
            key_enemy_debuff["complete_enabled"] = False
            key_enemy_debuff["visual_hud_enabled"] = False
            for key in (
                "physical_break_min",
                "magic_break_min",
                "damage_bonus_min",
                "rabbit_stacks_min",
            ):
                key_enemy_debuff[key] = None
        key_enemy_debuff.setdefault("visual_expiry_enabled", True)
    _apply_policy_migrations(data)
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--preserve-existing",
        action="store_true",
        help="Keep every existing local setting and only add newly introduced keys.",
    )
    args = parser.parse_args()

    source = Path(args.base)
    output = Path(args.output)
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    configure_visual_private(data, preserve_existing=args.preserve_existing)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

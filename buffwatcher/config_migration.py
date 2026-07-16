from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
from typing import Any

from .astrology_cards import (
    ASTROLOGY_CARD_TRACKER_CONFIG_KEY,
    ensure_astrology_card_tracker_config,
)
from .hamster_buffs import ensure_hamster_buff_items


DEFAULT_CONFIG_NAME = "buffwatcher.config.defaults.json"
PACKAGED_DEFAULT_CONFIG = Path("config") / DEFAULT_CONFIG_NAME
VARIABLE_DURATION_POTION_CCIDS = {62, 63, 1121, 1150}
MAGIC_CIRCLE_CCID = 10133
MAGIC_CIRCLE_DEFAULT_COOLDOWN_SECONDS = 140
PALL_OF_RUINATION_CCID = 803
PALL_OF_RUINATION_SKILL_ID = 59005
PALL_OF_RUINATION_COOLDOWN_SECONDS = 180
SHORT_COOLDOWN_OVERLAY_CONFIG_KEY = "experimental_short_cooldown_visual_overlay"
IGNIS_PLUME_TRACKER_CCID = -59060
IGNIS_PLUME_SKILL_ID = 59060
IGNIS_PLUME_COOLDOWN_SECONDS = 6
AQUA_VOLLEY_TRACKER_CCID = -59061
AQUA_VOLLEY_SKILL_ID = 59061
AQUA_VOLLEY_COOLDOWN_SECONDS = 10
SHORT_COOLDOWN_TRACKERS = (
    (
        "ignis_plume",
        "爆炎箭",
        IGNIS_PLUME_TRACKER_CCID,
        IGNIS_PLUME_SKILL_ID,
        IGNIS_PLUME_COOLDOWN_SECONDS,
        "assets/icon/visual-overlay/short-cooldown/ignis-plume.png",
    ),
    (
        "aqua_volley",
        "水流箭",
        AQUA_VOLLEY_TRACKER_CCID,
        AQUA_VOLLEY_SKILL_ID,
        AQUA_VOLLEY_COOLDOWN_SECONDS,
        "assets/icon/visual-overlay/short-cooldown/aqua-volley.png",
    ),
)
THIRD_EYE_CCID = 521
THIRD_EYE_COOLDOWN_CHOICES = {240, 300}
THIRD_EYE_DEFAULT_COOLDOWN_SECONDS = 300
LEGACY_SBT_ADJUST_SECONDS = 16.0
CURRENT_SBT_ADJUST_SECONDS = 22.5
DEATH_MARK_DAMAGE_CCID = 426
DEATH_MARK_PULL_CCID = 1166
DEATH_MARK_DAMAGE_NAME = "死亡锁定增伤"
DEATH_MARK_PULL_NAME = "牵引吸怪（非死亡锁定增伤）"


def default_config_candidates(config_path: str | Path) -> list[Path]:
    config_file = Path(config_path)
    config_dir = config_file.resolve().parent
    source_root = Path(__file__).resolve().parent.parent
    return [
        config_dir / PACKAGED_DEFAULT_CONFIG,
        config_dir / DEFAULT_CONFIG_NAME,
        source_root / DEFAULT_CONFIG_NAME,
    ]


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def _find_default_config(config_path: str | Path) -> Path | None:
    config_file = Path(config_path).resolve()
    for candidate in default_config_candidates(config_path):
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved == config_file:
            continue
        if resolved.is_file():
            return resolved
    return None


def _identity(item: Any) -> tuple[str, str] | None:
    if not isinstance(item, dict):
        return None
    for key in ("name", "short_name", "ccid", "entity_id", "effect_name", "key", "id"):
        value = item.get(key)
        if value not in (None, "", []):
            return key, json.dumps(value, ensure_ascii=False, sort_keys=True)
    return None


def _merge_missing(target: Any, defaults: Any) -> bool:
    if isinstance(target, dict) and isinstance(defaults, dict):
        changed = False
        for key, value in defaults.items():
            if key not in target:
                target[key] = deepcopy(value)
                changed = True
            else:
                changed = _merge_missing(target[key], value) or changed
        return changed

    if isinstance(target, list) and isinstance(defaults, list):
        changed = False
        target_by_identity = {
            identity: item
            for item in target
            if (identity := _identity(item)) is not None
        }
        for default_item in defaults:
            identity = _identity(default_item)
            if identity is None:
                continue
            target_item = target_by_identity.get(identity)
            if target_item is not None:
                changed = _merge_missing(target_item, default_item) or changed
        return changed

    return False


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def _apply_policy_migrations(data: dict[str, Any]) -> bool:
    changed = False
    changed = ensure_hamster_buff_items(data) or changed
    try:
        current_sbt_adjust = float(data.get("sbt_adjust_seconds"))
    except (TypeError, ValueError):
        current_sbt_adjust = None
    if current_sbt_adjust == LEGACY_SBT_ADJUST_SECONDS:
        data["sbt_adjust_seconds"] = CURRENT_SBT_ADJUST_SECONDS
        changed = True
    buffs = data.setdefault("buffs", [])
    music_overlay = data.get("experimental_music_visual_overlay")
    other_overlay_config = data.get("experimental_other_skill_visual_overlay")
    short_overlay_config = data.get(SHORT_COOLDOWN_OVERLAY_CONFIG_KEY)
    visual_overlay_present = any(
        isinstance(value, dict)
        for value in (music_overlay, other_overlay_config, short_overlay_config)
    )
    if visual_overlay_present:
        astrology_before = deepcopy(data.get(ASTROLOGY_CARD_TRACKER_CONFIG_KEY))
        astrology_after = ensure_astrology_card_tracker_config(data)
        if astrology_before != astrology_after:
            changed = True
        pall_item = next(
            (
                item
                for item in buffs
                if isinstance(item, dict)
                and (
                    item.get("name") == "崩坏波动"
                    or str(item.get("ccid")) == str(PALL_OF_RUINATION_CCID)
                )
            ),
            None,
        )
        if pall_item is None:
            pall_item = {
                "name": "崩坏波动",
                "ccid": PALL_OF_RUINATION_CCID,
                "enabled": True,
                "skill_id": PALL_OF_RUINATION_SKILL_ID,
                "self_filter": True,
                "warn_seconds": 0,
                "critical_seconds": 0,
                "alerts": [],
                "ended_alert": False,
                "cooldown_alert": False,
                "cooldown_delay_seconds": PALL_OF_RUINATION_COOLDOWN_SECONDS,
                "cooldown_from_skill_use": True,
                "audio_volume": 100,
            }
            buffs.append(pall_item)
            changed = True
        else:
            required_pall_values = {
                "name": "崩坏波动",
                "ccid": PALL_OF_RUINATION_CCID,
                "enabled": True,
                "skill_id": PALL_OF_RUINATION_SKILL_ID,
                "self_filter": True,
                "ended_alert": False,
                "cooldown_alert": False,
                "cooldown_delay_seconds": PALL_OF_RUINATION_COOLDOWN_SECONDS,
                "cooldown_from_skill_use": True,
            }
            for key, value in required_pall_values.items():
                if pall_item.get(key) != value:
                    pall_item[key] = value
                    changed = True

        for (
            _condition_key,
            tracker_name,
            tracker_ccid,
            tracker_skill_id,
            default_cooldown_seconds,
            _icon_path,
        ) in SHORT_COOLDOWN_TRACKERS:
            tracker_item = next(
                (
                    item
                    for item in buffs
                    if isinstance(item, dict)
                    and (
                        item.get("name") == tracker_name
                        or str(item.get("ccid")) == str(tracker_ccid)
                    )
                ),
                None,
            )
            required_tracker_values = {
                "name": tracker_name,
                "ccid": tracker_ccid,
                "enabled": True,
                "skill_id": tracker_skill_id,
                "self_filter": True,
                "warn_seconds": 0,
                "critical_seconds": 0,
                "alerts": [],
                "ended_alert": False,
                "cooldown_alert": False,
                "cooldown_from_skill_use": True,
                "audio_volume": 100,
            }
            if tracker_item is None:
                tracker_item = deepcopy(required_tracker_values)
                tracker_item["cooldown_delay_seconds"] = default_cooldown_seconds
                buffs.append(tracker_item)
                changed = True
            else:
                for key, value in required_tracker_values.items():
                    if tracker_item.get(key) != value:
                        tracker_item[key] = deepcopy(value)
                        changed = True
                try:
                    cooldown_seconds = float(
                        tracker_item.get("cooldown_delay_seconds")
                    )
                except (TypeError, ValueError):
                    cooldown_seconds = 0.0
                if cooldown_seconds <= 0:
                    tracker_item["cooldown_delay_seconds"] = (
                        default_cooldown_seconds
                    )
                    changed = True

        short_overlay = data.get(SHORT_COOLDOWN_OVERLAY_CONFIG_KEY)
        if not isinstance(short_overlay, dict):
            short_overlay = {}
            data[SHORT_COOLDOWN_OVERLAY_CONFIG_KEY] = short_overlay
            changed = True
        short_defaults = {
            "enabled": True,
            "center_y_ratio": 0.715,
            "gap_px": 6,
            "default_icons_version": 2,
        }
        for key, value in short_defaults.items():
            if key not in short_overlay:
                short_overlay[key] = value
                changed = True
        try:
            short_icon_version = int(short_overlay.get("default_icons_version", 0))
        except (TypeError, ValueError):
            short_icon_version = 0
        if short_icon_version < 2:
            short_overlay["default_icons_version"] = 2
            changed = True
        short_conditions = short_overlay.get("conditions")
        if not isinstance(short_conditions, dict):
            short_conditions = {}
            short_overlay["conditions"] = short_conditions
            changed = True
        for (
            condition_key,
            tracker_name,
            _tracker_ccid,
            _tracker_skill_id,
            _default_cooldown_seconds,
            icon_path,
        ) in SHORT_COOLDOWN_TRACKERS:
            condition = short_conditions.get(condition_key)
            if not isinstance(condition, dict):
                condition = {}
                short_conditions[condition_key] = condition
                changed = True
            for field_name, default_value in (
                ("enabled", True),
                ("name", tracker_name),
                ("icon", icon_path),
            ):
                if field_name not in condition:
                    condition[field_name] = default_value
                    changed = True

    if isinstance(music_overlay, dict):
        music_conditions = music_overlay.get("conditions")
        if isinstance(music_conditions, dict) and "874" in music_conditions:
            music_conditions.pop("874", None)
            changed = True

        other_overlay = data.get("experimental_other_skill_visual_overlay")
        if not isinstance(other_overlay, dict):
            other_overlay = {}
            data["experimental_other_skill_visual_overlay"] = other_overlay
            changed = True
        if "enabled" not in other_overlay:
            other_overlay["enabled"] = False
            changed = True
        other_conditions = other_overlay.get("conditions")
        if not isinstance(other_conditions, dict):
            other_conditions = {}
            other_overlay["conditions"] = other_conditions
            changed = True
        other_defaults = {
            "magic_circle": (True, "魔法阵", "assets/icon/visual-overlay/other-skills/magic-circle.png"),
            "pall_of_ruination": (True, "崩坏波动", "assets/icon/visual-overlay/other-skills/pall-of-ruination.png"),
            "manus_potion": (True, "马纽斯秘药", "assets/icon/visual-overlay/other-skills/manus-potion.png"),
            "purification_wave": (True, "净化之浪", "assets/icon/visual-overlay/other-skills/purification-wave.png"),
            "life_temperature": (False, "生命的温度", "assets/icon/visual-overlay/life-temperature.png"),
        }
        for key, (enabled, name, icon) in other_defaults.items():
            condition = other_conditions.get(key)
            if not isinstance(condition, dict):
                condition = {}
                other_conditions[key] = condition
                changed = True
            for field_name, default_value in (
                ("enabled", enabled),
                ("name", name),
                ("icon", icon),
            ):
                if field_name not in condition:
                    condition[field_name] = default_value
                    changed = True

    for item in buffs:
        if not isinstance(item, dict):
            continue
        try:
            item_ccid = int(item.get("ccid"))
        except (TypeError, ValueError):
            item_ccid = None
        if item_ccid == DEATH_MARK_DAMAGE_CCID:
            if item.get("name") != DEATH_MARK_DAMAGE_NAME:
                item["name"] = DEATH_MARK_DAMAGE_NAME
                changed = True
        if item_ccid == DEATH_MARK_PULL_CCID:
            if item.get("name") != DEATH_MARK_PULL_NAME:
                item["name"] = DEATH_MARK_PULL_NAME
                changed = True
            if item.get("enabled") is not False:
                item["enabled"] = False
                changed = True
        if item_ccid in VARIABLE_DURATION_POTION_CCIDS:
            for key in ("duration_seconds", "fixed_duration_seconds"):
                if key in item:
                    item.pop(key, None)
                    changed = True
            required_extra = item.get("required_extra")
            if isinstance(required_extra, dict) and "DURA" in required_extra:
                required_extra.pop("DURA", None)
                changed = True
            if item.get("prefer_sbt_when_duration_present") is not True:
                item["prefer_sbt_when_duration_present"] = True
                changed = True
            if item.get("use_dynamic_sbt_adjust") is not False:
                item["use_dynamic_sbt_adjust"] = False
                changed = True
        if item_ccid == MAGIC_CIRCLE_CCID or item.get("name") == "魔法阵":
            if item.get("cooldown_from_skill_use") is not True:
                item["cooldown_from_skill_use"] = True
                changed = True
            try:
                cooldown_seconds = int(float(item.get("cooldown_delay_seconds")))
            except (TypeError, ValueError):
                cooldown_seconds = None
            if cooldown_seconds != MAGIC_CIRCLE_DEFAULT_COOLDOWN_SECONDS:
                item["cooldown_delay_seconds"] = (
                    MAGIC_CIRCLE_DEFAULT_COOLDOWN_SECONDS
                )
                changed = True
            if "cooldown_from_apply" in item:
                item.pop("cooldown_from_apply", None)
                changed = True
        if item_ccid == THIRD_EYE_CCID or item.get("name") == "第三只眼":
            if item.get("cooldown_from_apply") is not True:
                item["cooldown_from_apply"] = True
                changed = True
            try:
                cooldown_seconds = int(float(item.get("cooldown_delay_seconds")))
            except (TypeError, ValueError):
                cooldown_seconds = None
            if cooldown_seconds not in THIRD_EYE_COOLDOWN_CHOICES:
                item["cooldown_delay_seconds"] = THIRD_EYE_DEFAULT_COOLDOWN_SECONDS
                changed = True
        if item.get("name") == "状态支援" and item.get(
            "prefer_sbt_when_duration_present"
        ):
            item["prefer_sbt_when_duration_present"] = False
            changed = True
    return changed


def migrate_config_file(config_path: str | Path) -> dict[str, Any]:
    config_file = Path(config_path)
    if not config_file.exists():
        default_path = _find_default_config(config_file)
        if default_path is None:
            raise FileNotFoundError(config_file)
        data = _read_json(default_path)
        _apply_policy_migrations(data)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(config_file, data)
        return data

    data = _read_json(config_file)
    default_path = _find_default_config(config_file)
    if default_path is None:
        _apply_policy_migrations(data)
        return data

    # Run policy migrations before merging new default fields. This preserves the
    # ability to distinguish a legacy config from one that already opted into a
    # new timing anchor.
    changed = _apply_policy_migrations(data)
    defaults = _read_json(default_path)
    changed = _merge_missing(data, defaults) or changed
    changed = _apply_policy_migrations(data) or changed
    if not changed:
        return data

    backup_path = config_file.with_suffix(config_file.suffix + ".bak-before-migration")
    try:
        if not backup_path.exists():
            shutil.copy2(config_file, backup_path)
        _write_json_atomic(config_file, data)
    except OSError:
        # The in-memory migrated config is still usable for this run.
        pass
    return data

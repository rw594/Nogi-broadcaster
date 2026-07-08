from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
from typing import Any


DEFAULT_CONFIG_NAME = "buffwatcher.config.defaults.json"
PACKAGED_DEFAULT_CONFIG = Path("config") / DEFAULT_CONFIG_NAME
VARIABLE_DURATION_POTION_CCIDS = {62, 63, 1121, 1150}


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
    for item in data.get("buffs", []):
        if not isinstance(item, dict):
            continue
        try:
            item_ccid = int(item.get("ccid"))
        except (TypeError, ValueError):
            item_ccid = None
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

    defaults = _read_json(default_path)
    changed = _merge_missing(data, defaults)
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

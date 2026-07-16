from __future__ import annotations

from copy import deepcopy
from typing import Any


HAMSTER_SUPERCHARGED_NAME = "超燃咚咚"
HAMSTER_ADRENALINE_NAME = "咚咚肾上腺素"
HAMSTER_BUFF_NAMES = (HAMSTER_SUPERCHARGED_NAME, HAMSTER_ADRENALINE_NAME)
HAMSTER_SETTINGS_NAME = "陈睿"
HAMSTER_REMINDER_MERGE_VERSION = 1

HAMSTER_PET_RACE_IDS = (490500, 490501)
HAMSTER_SUMMON_SKILL_ID = 50279
HAMSTER_SUPERCHARGED_CCID = 1225
HAMSTER_ADRENALINE_CCID = 1186
PURIFICATION_WAVE_CCID = 645
HAMSTER_BUFF_DURATION_SECONDS = 180
HAMSTER_DEFAULT_WARNING_SECONDS = 30


def default_hamster_buff_items() -> list[dict[str, Any]]:
    common = {
        "enabled": False,
        "duration_seconds": HAMSTER_BUFF_DURATION_SECONDS,
        "warn_seconds": HAMSTER_DEFAULT_WARNING_SECONDS,
        "critical_seconds": HAMSTER_DEFAULT_WARNING_SECONDS,
        "ended_alert": False,
        "ended_message": "{name} 结束",
        "ended_on_remove_only": True,
        "ended_grace_seconds": 0,
        "sbt_ended_lead_seconds": 0,
        "use_dynamic_sbt_adjust": False,
        "audio_volume": 100,
    }
    supercharged = {
        **common,
        "name": HAMSTER_SUPERCHARGED_NAME,
        "ccid": HAMSTER_SUPERCHARGED_CCID,
        "enabled": True,
        "remaining_enabled": True,
        "alerts": [
            {
                "remaining_seconds": HAMSTER_DEFAULT_WARNING_SECONDS,
                "sound": "assets/audio/xiaoyi/hamster_supercharged_remaining.wav",
                "message": "{name}",
            }
        ],
        "ended_alert": True,
        "ended_sound": "assets/audio/xiaoyi/hamster_supercharged_ended.wav",
        "warn_sound": "assets/audio/xiaoyi/hamster_supercharged_remaining.wav",
        "observed": {
            "pet_race_ids": list(HAMSTER_PET_RACE_IDS),
            "pet_skill_id": HAMSTER_SUMMON_SKILL_ID,
            "duration_seconds": HAMSTER_BUFF_DURATION_SECONDS,
            "extra_data": {"MCDSAD": 40, "MCDSMA": 40, "MCDSPA": 40},
            "source_session": "20260715-191607-启动日志",
        },
    }
    adrenaline = {
        **common,
        "name": HAMSTER_ADRENALINE_NAME,
        "ccid": HAMSTER_ADRENALINE_CCID,
        "alerts": [],
        "ended_sound": "assets/audio/xiaoyi/hamster_adrenaline_ended.wav",
        "warn_sound": "assets/audio/xiaoyi/hamster_adrenaline_remaining.wav",
        "observed": {
            "pet_race_ids": list(HAMSTER_PET_RACE_IDS),
            "pet_skill_id": HAMSTER_SUMMON_SKILL_ID,
            "duration_seconds": HAMSTER_BUFF_DURATION_SECONDS,
            "extra_data": {"MCDSR": 50000},
            "whale_override": {
                "purification_wave_ccid": PURIFICATION_WAVE_CCID,
                "same_timestamp_remove_observed": True,
            },
            "source_session": "20260715-191607-启动日志",
        },
    }
    return [supercharged, adrenaline]


def ensure_hamster_buff_items(data: dict[str, Any]) -> bool:
    buffs = data.setdefault("buffs", [])
    if not isinstance(buffs, list):
        buffs = []
        data["buffs"] = buffs

    original_ccids = {
        int(item.get("ccid"))
        for item in buffs
        if isinstance(item, dict) and str(item.get("ccid", "")).isdigit()
    }
    changed = False
    for default in default_hamster_buff_items():
        item = next(
            (
                candidate
                for candidate in buffs
                if isinstance(candidate, dict)
                and (
                    candidate.get("name") == default["name"]
                    or str(candidate.get("ccid")) == str(default["ccid"])
                )
            ),
            None,
        )
        if item is None:
            buffs.append(deepcopy(default))
            changed = True
            continue

        for key, value in default.items():
            if key not in item:
                item[key] = deepcopy(value)
                changed = True

        # Older builds had a separate master switch. Preserve its effective
        # state when migrating to the two-sub-switch model: an off master means
        # both reminder switches start off, while an on master keeps the
        # previously selected reminder types.
        if not bool(item.get("enabled", False)):
            if bool(item.get("ended_alert", False)):
                item["ended_alert"] = False
                changed = True
            if item.get("alerts"):
                item["alerts"] = []
                changed = True
            if bool(item.get("remaining_enabled", False)):
                item["remaining_enabled"] = False
                changed = True

        remaining_enabled = (
            bool(item.get("remaining_enabled", False))
            if "remaining_enabled" in item
            else bool(item.get("alerts"))
        )
        derived_enabled = bool(item.get("ended_alert", False) or remaining_enabled)
        if bool(item.get("enabled", False)) != derived_enabled:
            item["enabled"] = derived_enabled
            changed = True

    items_by_ccid = {
        int(item.get("ccid")): item
        for item in buffs
        if isinstance(item, dict) and str(item.get("ccid", "")).isdigit()
    }
    supercharged = items_by_ccid[HAMSTER_SUPERCHARGED_CCID]
    adrenaline = items_by_ccid[HAMSTER_ADRENALINE_CCID]

    # V1.25e exposes one combined settings row. Carry an existing adrenaline
    # selection over once, then make CCId 1225 the only source of hamster
    # reminders. CCId 1186 remains recorded for diagnostics but never speaks.
    try:
        merge_version = int(data.get("hamster_reminder_merge_version", 0))
    except (TypeError, ValueError):
        merge_version = 0
    if merge_version < HAMSTER_REMINDER_MERGE_VERSION:
        adrenaline_remaining = bool(adrenaline.get("alerts")) or bool(
            adrenaline.get("remaining_enabled", False)
        )
        use_supercharged_state = (
            HAMSTER_SUPERCHARGED_CCID in original_ccids
            or HAMSTER_ADRENALINE_CCID not in original_ccids
        )
        supercharged_remaining = (
            bool(supercharged.get("alerts"))
            or bool(supercharged.get("remaining_enabled", False))
            if use_supercharged_state
            else False
        )
        remaining_enabled = supercharged_remaining or adrenaline_remaining
        ended_enabled = (
            bool(supercharged.get("ended_alert", False))
            if use_supercharged_state
            else False
        ) or bool(adrenaline.get("ended_alert", False))
        if adrenaline_remaining and not supercharged_remaining:
            seconds = int(
                adrenaline.get(
                    "warn_seconds",
                    adrenaline.get("critical_seconds", HAMSTER_DEFAULT_WARNING_SECONDS),
                )
            )
        else:
            seconds = int(
                supercharged.get(
                    "warn_seconds",
                    supercharged.get("critical_seconds", HAMSTER_DEFAULT_WARNING_SECONDS),
                )
            )
        supercharged["ended_alert"] = ended_enabled
        supercharged["enabled"] = bool(ended_enabled or remaining_enabled)
        supercharged["warn_seconds"] = seconds
        supercharged["critical_seconds"] = seconds
        supercharged["remaining_enabled"] = remaining_enabled
        supercharged["alerts"] = (
            [
                {
                    "remaining_seconds": seconds,
                    "sound": supercharged["warn_sound"],
                    "message": "{name}",
                }
            ]
            if remaining_enabled
            else []
        )
        data["hamster_reminder_merge_version"] = HAMSTER_REMINDER_MERGE_VERSION
        changed = True

    silent_values = {
        "enabled": False,
        "ended_alert": False,
        "remaining_enabled": False,
        "alerts": [],
    }
    for key, value in silent_values.items():
        if adrenaline.get(key) != value:
            adrenaline[key] = deepcopy(value)
            changed = True
    for obsolete_key in (
        "whale_override_silence_enabled",
        "suppress_ended_if_active_ccids",
    ):
        if obsolete_key in adrenaline:
            adrenaline.pop(obsolete_key, None)
            changed = True
    return changed

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
from typing import Any

from .events import DOTNET_EPOCH_MS


CHANNEL_LOGIN_RESPONSE_OP = 20_003
ENTITY_SERVER_TIME_OP = 0x659C
VALID_MODES = frozenset({"off", "shadow", "apply"})
DEFAULT_MAX_WALL_CLOCK_SKEW_SECONDS = 300.0
DEFAULT_MAX_CALIBRATION_AGE_HOURS = 48.0
DEFAULT_MAX_APPLY_ADJUSTMENT_SECONDS = 2.0
MUSIC_DURATION_MIN_MS = 20_000
MUSIC_DURATION_MAX_MS = 1_800_000


@dataclass(frozen=True)
class ServerClockSettings:
    mode: str = "off"
    diagnostic_log: str = ""
    max_wall_clock_skew_seconds: float = DEFAULT_MAX_WALL_CLOCK_SKEW_SECONDS
    max_calibration_age_hours: float = DEFAULT_MAX_CALIBRATION_AGE_HOURS
    max_apply_adjustment_seconds: float = DEFAULT_MAX_APPLY_ADJUSTMENT_SECONDS
    tz_offset_hours: int = 8
    allow_global_fallback: bool = False

    @property
    def enabled(self) -> bool:
        return self.mode != "off"

    @property
    def applies_to_reminders(self) -> bool:
        return self.mode == "apply"


@dataclass(frozen=True)
class LoginClockCalibration:
    character_id: str
    local_at_ms: int
    server_at_ms: int
    wall_clock_skew_ms: int
    op: int = CHANNEL_LOGIN_RESPONSE_OP

    @property
    def local_minus_server_raw_ms(self) -> int:
        return self.local_at_ms - self.server_at_ms

    def local_time_for_server_ms(self, server_time_ms: int) -> int:
        return self.local_at_ms + (int(server_time_ms) - self.server_at_ms)


@dataclass(frozen=True)
class MusicTimingComparison:
    character_id: str
    calibration_character_id: str
    calibration_binding: str
    ccid: int
    event_at_ms: int
    current_end_ms: int
    calibrated_end_ms: int
    adjustment_ms: int
    calibration_age_ms: int
    eligible_to_apply: bool
    rejection_reason: str | None


@dataclass(frozen=True)
class EntityServerTimeDiagnostic:
    entity_id: str
    local_at_ms: int
    server_at_ms: int
    server_wall_clock_ms: int
    wall_clock_skew_ms: int
    within_configured_skew_limit: bool
    op: int = ENTITY_SERVER_TIME_OP


def _normalize_op(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    text = str(value or "").strip().lower()
    if not text:
        return None
    try:
        return int(text, 16) if text.startswith("0x") else int(text)
    except ValueError:
        return None


def _typed_value(item: Any, expected_type: str) -> Any | None:
    if not isinstance(item, dict):
        return None
    if str(item.get("T", "")).strip().lower() != expected_type:
        return None
    return item.get("V")


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def load_server_clock_settings(
    config_path: str | Path,
    *,
    fallback_tz_offset_hours: int = 8,
) -> ServerClockSettings:
    path = Path(config_path)
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            config = json.load(stream)
    except (OSError, json.JSONDecodeError):
        return ServerClockSettings(tz_offset_hours=fallback_tz_offset_hours)

    raw = config.get("experimental_login_server_clock")
    if not isinstance(raw, dict):
        return ServerClockSettings(tz_offset_hours=fallback_tz_offset_hours)

    mode = str(raw.get("mode", "off")).strip().lower()
    if mode not in VALID_MODES:
        mode = "off"

    diagnostic_log = str(raw.get("diagnostic_log", "") or "").strip()
    if diagnostic_log:
        diagnostic_path = Path(diagnostic_log)
        if not diagnostic_path.is_absolute():
            diagnostic_path = path.resolve().parent / diagnostic_path
        diagnostic_log = str(diagnostic_path)

    def positive_float(key: str, default: float) -> float:
        try:
            value = float(raw.get(key, default))
        except (TypeError, ValueError):
            return default
        return value if value > 0 else default

    try:
        tz_offset_hours = int(config.get("tz_offset_hours", fallback_tz_offset_hours))
    except (TypeError, ValueError):
        tz_offset_hours = fallback_tz_offset_hours

    return ServerClockSettings(
        mode=mode,
        diagnostic_log=diagnostic_log,
        max_wall_clock_skew_seconds=positive_float(
            "max_wall_clock_skew_seconds", DEFAULT_MAX_WALL_CLOCK_SKEW_SECONDS
        ),
        max_calibration_age_hours=positive_float(
            "max_calibration_age_hours", DEFAULT_MAX_CALIBRATION_AGE_HOURS
        ),
        max_apply_adjustment_seconds=positive_float(
            "max_apply_adjustment_seconds", DEFAULT_MAX_APPLY_ADJUSTMENT_SECONDS
        ),
        tz_offset_hours=tz_offset_hours,
        allow_global_fallback=_as_bool(raw.get("allow_global_fallback", False)),
    )


class ServerClockCalibrator:
    def __init__(self, settings: ServerClockSettings) -> None:
        self.settings = settings
        self.calibrations: dict[str, LoginClockCalibration] = {}
        self.latest_calibration: LoginClockCalibration | None = None
        self.latest_entity_server_time: EntityServerTimeDiagnostic | None = None
        self.entity_server_time_samples_seen = 0

    @property
    def known_character_ids(self) -> tuple[str, ...]:
        return tuple(self.calibrations)

    def observe(self, event: dict[str, Any]) -> LoginClockCalibration | None:
        if not self.settings.enabled or event.get("EventId") != 0:
            return None
        if _normalize_op(event.get("Op")) != CHANNEL_LOGIN_RESPONSE_OP:
            return None

        msg = event.get("Msg")
        if not isinstance(msg, list) or len(msg) < 3:
            return None
        success = _typed_value(msg[0], "byte")
        character = _typed_value(msg[1], "long")
        server_time = _typed_value(msg[2], "long")
        try:
            success = int(success)
            character_id = str(int(character))
            server_at_ms = int(server_time)
            local_at_ms = int(event["At"])
        except (KeyError, TypeError, ValueError):
            return None
        if success != 1 or int(character_id) <= 0:
            return None

        server_wall_clock_ms = (
            server_at_ms
            - DOTNET_EPOCH_MS
            - self.settings.tz_offset_hours * 60 * 60 * 1000
        )
        wall_clock_skew_ms = local_at_ms - server_wall_clock_ms
        max_skew_ms = int(self.settings.max_wall_clock_skew_seconds * 1000)
        if abs(wall_clock_skew_ms) > max_skew_ms:
            return None

        calibration = LoginClockCalibration(
            character_id=character_id,
            local_at_ms=local_at_ms,
            server_at_ms=server_at_ms,
            wall_clock_skew_ms=wall_clock_skew_ms,
        )
        self.calibrations[character_id] = calibration
        self.latest_calibration = calibration
        return calibration

    def observe_entity_server_time(
        self, event: dict[str, Any]
    ) -> EntityServerTimeDiagnostic | None:
        """Parse 0x659C for diagnostics without making it a timing calibration."""
        if not self.settings.enabled or event.get("EventId") != 0:
            return None
        if _normalize_op(event.get("Op")) != ENTITY_SERVER_TIME_OP:
            return None

        msg = event.get("Msg")
        if not isinstance(msg, list) or len(msg) < 3:
            return None
        success = _typed_value(msg[0], "byte")
        entity = _typed_value(msg[1], "long")
        server_time = _typed_value(msg[2], "long")
        try:
            success = int(success)
            entity_id = str(int(entity))
            server_at_ms = int(server_time)
            local_at_ms = int(event["At"])
        except (KeyError, TypeError, ValueError):
            return None
        if success != 1 or int(entity_id) <= 0 or server_at_ms <= DOTNET_EPOCH_MS:
            return None

        server_wall_clock_ms = (
            server_at_ms
            - DOTNET_EPOCH_MS
            - self.settings.tz_offset_hours * 60 * 60 * 1000
        )
        wall_clock_skew_ms = local_at_ms - server_wall_clock_ms
        max_skew_ms = int(self.settings.max_wall_clock_skew_seconds * 1000)
        diagnostic = EntityServerTimeDiagnostic(
            entity_id=entity_id,
            local_at_ms=local_at_ms,
            server_at_ms=server_at_ms,
            server_wall_clock_ms=server_wall_clock_ms,
            wall_clock_skew_ms=wall_clock_skew_ms,
            within_configured_skew_limit=abs(wall_clock_skew_ms) <= max_skew_ms,
        )
        self.latest_entity_server_time = diagnostic
        self.entity_server_time_samples_seen += 1
        return diagnostic

    def music_timing_comparison(
        self, event: dict[str, Any]
    ) -> MusicTimingComparison | None:
        if not self.settings.enabled or event.get("EventId") != 4:
            return None
        character_id = str(event.get("Id", ""))
        calibration = self.calibrations.get(character_id)
        calibration_binding = "character"
        if calibration is None and self.settings.allow_global_fallback:
            calibration = self.latest_calibration
            calibration_binding = "global"
        if calibration is None:
            return None

        extra = event.get("ExtraData")
        if not isinstance(extra, dict):
            return None
        try:
            event_at_ms = int(event["At"])
            ccid = int(event["CCId"])
            sbt = int(float(extra["SBT"]))
            mcagt = int(float(extra["MCAGT"]))
        except (KeyError, TypeError, ValueError):
            return None

        duration_ms = sbt - mcagt
        if not MUSIC_DURATION_MIN_MS <= duration_ms <= MUSIC_DURATION_MAX_MS:
            return None

        current_end_ms = event_at_ms + duration_ms
        calibrated_end_ms = calibration.local_time_for_server_ms(sbt)
        adjustment_ms = calibrated_end_ms - current_end_ms
        calibration_age_ms = event_at_ms - calibration.local_at_ms
        rejection_reason: str | None = None
        max_age_ms = int(self.settings.max_calibration_age_hours * 60 * 60 * 1000)
        max_adjustment_ms = int(self.settings.max_apply_adjustment_seconds * 1000)
        if calibration_age_ms < -5_000:
            rejection_reason = "event_precedes_login_calibration"
        elif calibration_age_ms > max_age_ms:
            rejection_reason = "login_calibration_too_old"
        elif abs(adjustment_ms) > max_adjustment_ms:
            rejection_reason = "adjustment_exceeds_safety_limit"

        return MusicTimingComparison(
            character_id=character_id,
            calibration_character_id=calibration.character_id,
            calibration_binding=calibration_binding,
            ccid=ccid,
            event_at_ms=event_at_ms,
            current_end_ms=current_end_ms,
            calibrated_end_ms=calibrated_end_ms,
            adjustment_ms=adjustment_ms,
            calibration_age_ms=calibration_age_ms,
            eligible_to_apply=rejection_reason is None,
            rejection_reason=rejection_reason,
        )

    def calibrated_music_end_ms(self, event: dict[str, Any]) -> int | None:
        if not self.settings.applies_to_reminders:
            return None
        comparison = self.music_timing_comparison(event)
        if comparison is None or not comparison.eligible_to_apply:
            return None
        return comparison.calibrated_end_ms


class ServerClockDiagnosticRecorder:
    def __init__(self, settings: ServerClockSettings) -> None:
        self.settings = settings
        self.path = Path(settings.diagnostic_log) if settings.diagnostic_log else None
        self.stream = None
        if self.path is not None and settings.enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.stream = self.path.open("a", encoding="utf-8", newline="\n")

    def _write(self, payload: dict[str, Any]) -> None:
        if self.stream is None:
            return
        self.stream.write(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        self.stream.flush()

    def write_login(self, calibration: LoginClockCalibration) -> None:
        self._write(
            {
                "Type": "login_server_clock",
                "Mode": self.settings.mode,
                **asdict(calibration),
                "local_minus_server_raw_ms": calibration.local_minus_server_raw_ms,
            }
        )

    def write_music(
        self,
        comparison: MusicTimingComparison,
        *,
        self_id: str | None,
    ) -> None:
        self._write(
            {
                "Type": "music_timing_comparison",
                "Mode": self.settings.mode,
                "Applied": (
                    self.settings.applies_to_reminders
                    and comparison.eligible_to_apply
                ),
                "SelfId": self_id,
                **asdict(comparison),
            }
        )

    def write_entity_server_time(
        self,
        diagnostic: EntityServerTimeDiagnostic,
        *,
        self_id: str | None,
    ) -> None:
        self._write(
            {
                "Type": "entity_server_time_0x659c",
                "Mode": self.settings.mode,
                "Applied": False,
                "SelfId": self_id,
                **asdict(diagnostic),
            }
        )

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None

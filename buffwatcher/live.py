from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import socket
import struct
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .alerting import (
    AlertEngine,
    FiredAlert,
    MAGIC_SHIELD_CCID,
    MUSIC_BUFF_CCIDS,
    load_all_specs,
    play_sound,
    print_alert,
)
from .events import DEFAULT_TZ_OFFSET_HOURS, sbt_to_unix_ms
from .overlay_bridge import MusicOverlayPublisher
from .server_clock import (
    ServerClockCalibrator,
    ServerClockDiagnosticRecorder,
    load_server_clock_settings,
)


DEFAULT_HISTORIES = r"C:\Users\rw594\Desktop\MicoPunch\histories"
DEFAULT_WS_HOST = "127.0.0.1"
DEFAULT_WS_PORT = 18000
DEFAULT_WS_PATH = "/ws"
MAX_RECORD_LOGS = 30
MAGIC_SHIELD_SELF_LEARN_TOGGLE_WINDOW_MS = 3000


@dataclass
class PartialEvent:
    line_number: int
    event: dict[str, Any]


def now_ms() -> int:
    return int(time.time() * 1000)


def newest_raw_file(histories: str | Path) -> Path | None:
    root = Path(histories)
    files = list(root.glob("*raw.ndjson.gz"))
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def iter_partial_raw_events(path: str | Path) -> Iterable[PartialEvent]:
    """Read as many complete JSON lines as possible from a possibly-open gzip file."""
    line_number = 0
    try:
        raw = Path(path).open("rb")
    except OSError:
        return

    with raw:
        try:
            stream = gzip.GzipFile(fileobj=raw)
            while True:
                try:
                    line = stream.readline()
                except (EOFError, gzip.BadGzipFile, OSError, zlib.error):
                    break
                if not line:
                    break
                line_number += 1
                try:
                    event = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    yield PartialEvent(line_number=line_number, event=event)
        except (EOFError, gzip.BadGzipFile, OSError, zlib.error):
            return


class GzipJsonTail:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.offset = 0
        self.line_number = 0
        self._buffer = b""
        self._decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)

    def read_events(self) -> list[PartialEvent]:
        try:
            with self.path.open("rb") as stream:
                size = self.path.stat().st_size
                if size < self.offset:
                    self._reset()
                stream.seek(self.offset)
                chunk = stream.read()
                self.offset = stream.tell()
        except OSError:
            return []

        if not chunk:
            return []

        try:
            self._buffer += self._decompress(chunk)
        except zlib.error:
            return []

        return self._pop_complete_lines(include_buffer=self._decompressor.eof)

    def _reset(self) -> None:
        self.offset = 0
        self.line_number = 0
        self._buffer = b""
        self._decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)

    def _decompress(self, chunk: bytes) -> bytes:
        output = bytearray()
        pending = chunk

        while pending:
            if self._decompressor.eof:
                self._decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)

            output.extend(self._decompressor.decompress(pending))
            pending = self._decompressor.unused_data
            if not pending:
                break

        return bytes(output)

    def _pop_complete_lines(self, *, include_buffer: bool = False) -> list[PartialEvent]:
        if b"\n" not in self._buffer and not include_buffer:
            return []

        if include_buffer:
            parts = self._buffer.split(b"\n")
            self._buffer = b""
        else:
            parts = self._buffer.split(b"\n")
            self._buffer = parts[-1]
            parts = parts[:-1]

        events: list[PartialEvent] = []

        for raw_line in parts:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            self.line_number += 1
            try:
                event = json.loads(raw_line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(PartialEvent(line_number=self.line_number, event=event))

        return events


def default_record_path() -> Path:
    name = time.strftime("%Y%m%d-%H%M%S-buffwatcher-raw.ndjson.gz")
    return Path("logs") / name


def default_alert_record_path() -> Path:
    name = time.strftime("%Y%m%d-%H%M%S-buffwatcher-alerts.ndjson")
    return Path("logs") / name


def resolve_record_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() == "auto":
        return default_record_path()
    return Path(text)


def resolve_alert_record_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() == "auto":
        return default_alert_record_path()
    return Path(text)


def prune_record_logs(directory: Path, *, keep: int = MAX_RECORD_LOGS, preserve: Path | None = None) -> None:
    if keep <= 0:
        return
    try:
        files = list(directory.glob("*buffwatcher-raw.ndjson.gz"))
    except OSError:
        return

    preserve_resolved = preserve.resolve() if preserve is not None else None

    def sort_key(path: Path) -> tuple[float, str]:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0
        return (mtime, path.name)

    files.sort(key=sort_key, reverse=True)
    kept = 0
    for path in files:
        try:
            if preserve_resolved is not None and path.resolve() == preserve_resolved:
                kept += 1
                continue
        except OSError:
            pass
        if kept < keep:
            kept += 1
            continue
        try:
            path.unlink()
        except OSError:
            continue


def prune_alert_logs(directory: Path, *, keep: int = MAX_RECORD_LOGS, preserve: Path | None = None) -> None:
    if keep <= 0:
        return
    try:
        files = list(directory.glob("*buffwatcher-alerts.ndjson"))
    except OSError:
        return

    preserve_resolved = preserve.resolve() if preserve is not None else None

    def sort_key(path: Path) -> tuple[float, str]:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0
        return (mtime, path.name)

    files.sort(key=sort_key, reverse=True)
    kept = 0
    for path in files:
        try:
            if preserve_resolved is not None and path.resolve() == preserve_resolved:
                kept += 1
                continue
        except OSError:
            pass
        if kept < keep:
            kept += 1
            continue
        try:
            path.unlink()
        except OSError:
            continue


class EventRecorder:
    def __init__(self, path: str | Path | None) -> None:
        self.path = resolve_record_path(path)
        self.stream = None
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = gzip.open(
            self.path,
            "at",
            encoding="utf-8",
            compresslevel=6,
            newline="\n",
        )
        prune_record_logs(self.path.parent, preserve=self.path)

    def write_event(self, event: dict[str, Any]) -> None:
        if self.stream is None:
            return
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        self.stream.write(line + "\n")
        self.stream.flush()

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


def format_local_ms(value: int | None) -> str | None:
    if value is None:
        return None
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value / 1000)) + (
        f".{value % 1000:03d}"
    )


def round_seconds(value: float | int | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 3)


def compact_event_for_log(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if event is None:
        return None
    extra = event.get("ExtraData") or {}
    return {
        "At": event.get("At"),
        "AtLocal": format_local_ms(event.get("At")),
        "EventId": event.get("EventId"),
        "Id": event.get("Id"),
        "TargetId": event.get("TargetId"),
        "AttackerId": event.get("AttackerId"),
        "CCId": event.get("CCId"),
        "SkillId": event.get("SkillId"),
        "ExtraKeys": sorted(str(key) for key in extra.keys()),
    }


class AlertRecorder:
    def __init__(self, path: str | Path | None) -> None:
        self.path = resolve_alert_record_path(path)
        self.stream = None
        self._error_reported = False
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a", encoding="utf-8", newline="\n")
        prune_alert_logs(self.path.parent, preserve=self.path)

    def write_alert(
        self,
        alert: FiredAlert,
        *,
        engine: AlertEngine,
        source: str,
        event: dict[str, Any] | None,
        self_id: str | None,
    ) -> None:
        if self.stream is None:
            return

        emitted_at_ms = now_ms()
        primary = engine.ccid_to_primary.get(alert.ccid) if alert.ccid is not None else None
        state = engine.states.get(primary) if primary is not None else None
        state_payload: dict[str, Any] | None = None
        if state is not None:
            remaining_basis_ms = state.end_ms or state.last_computed_end_ms
            state_payload = {
                "Active": state.active,
                "ActiveCCId": state.active_ccid,
                "Stacks": state.stacks,
                "EndAt": state.end_ms,
                "EndAtLocal": format_local_ms(state.end_ms),
                "LastComputedEndAt": state.last_computed_end_ms,
                "LastComputedEndAtLocal": format_local_ms(state.last_computed_end_ms),
                "LastApplyAt": state.last_apply_at_ms,
                "LastApplyAtLocal": format_local_ms(state.last_apply_at_ms),
                "LastEventAt": state.last_event_at_ms,
                "LastEventAtLocal": format_local_ms(state.last_event_at_ms),
                "TimingSource": state.last_timing_source,
                "RawSbtEndAt": state.last_raw_sbt_end_ms,
                "RawSbtEndAtLocal": format_local_ms(state.last_raw_sbt_end_ms),
                "SbtAdjustSeconds": round_seconds(state.last_sbt_adjust_seconds),
                "SbtAdjustSource": state.last_sbt_adjust_source,
                "EarlyRemoveReapplyGraceSeconds": round_seconds(
                    state.spec.early_remove_reapply_grace_seconds
                ),
                "RawSbtRemainingAtApplySeconds": round_seconds(
                    state.last_raw_sbt_remaining_seconds
                ),
                "AdjustedRemainingAtApplySeconds": round_seconds(
                    state.last_adjusted_remaining_seconds
                ),
                "RemainingAtAlertSeconds": round_seconds(
                    (remaining_basis_ms - alert.at_ms) / 1000
                    if remaining_basis_ms is not None
                    else None
                ),
                "LastEventMinusComputedEndSeconds": round_seconds(
                    (state.last_event_at_ms - state.last_computed_end_ms) / 1000
                    if state.last_event_at_ms is not None
                    and state.last_computed_end_ms is not None
                    else None
                ),
                "FiredThresholds": sorted(state.fired_thresholds),
            }

        record = {
            "Type": "alert",
            "EmittedAt": emitted_at_ms,
            "EmittedAtLocal": format_local_ms(emitted_at_ms),
            "AlertAt": alert.at_ms,
            "AlertAtLocal": format_local_ms(alert.at_ms),
            "EmitDelaySeconds": round_seconds((emitted_at_ms - alert.at_ms) / 1000),
            "Source": source,
            "Kind": alert.kind,
            "Name": alert.name,
            "CCId": alert.ccid,
            "RemainingSeconds": alert.remaining_seconds,
            "Message": alert.message,
            "Sound": alert.sound,
            "Volume": alert.volume,
            "Detail": alert.detail,
            "SelfId": self_id,
            "Engine": {
                "DynamicSbtAdjustSeconds": round_seconds(engine.dynamic_sbt_adjust_seconds),
                "DynamicSbtAdjustSampleCount": len(engine._dynamic_sbt_adjust_samples),
                "TzOffsetHours": engine.tz_offset_hours,
            },
            "State": state_payload,
            "CurrentEvent": compact_event_for_log(event),
        }
        try:
            self.stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            self.stream.flush()
        except OSError as exc:
            if not self._error_reported:
                print(f"[live] failed to write alert timing log: {exc}")
                self._error_reported = True

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


class SelfFilter:
    def __init__(self, engine: AlertEngine, *, self_id: str | None, disabled: bool) -> None:
        self.engine = engine
        self.self_id = self_id
        self.disabled = disabled
        self.explicit_self_id = self_id is not None
        self._last_wait_notice_at = 0.0
        self._magic_shield_learn_candidates: dict[str, tuple[int, int]] = {}
        if not self.disabled and self.self_id is not None:
            self.engine.set_self_entity_id(self.self_id)

    def observe(self, event: dict[str, Any]) -> None:
        return

    def allow(self, event: dict[str, Any], *, allow_learning: bool) -> bool:
        if self.disabled:
            return True

        target_id = event.get("Id")
        ccid = event.get("CCId")
        if target_id is None or ccid is None:
            return False

        if int(ccid) not in self.engine.ccid_to_primary:
            return False

        target_id = str(target_id)
        learning_reason = self._learning_reason(event, target_id=target_id)
        if self.self_id is None:
            if not allow_learning or learning_reason is None:
                return False
            self._set_self_id(target_id, learning_reason)
            return True

        return target_id == self.self_id

    def _learning_reason(self, event: dict[str, Any], *, target_id: str) -> str | None:
        event_id = event.get("EventId")
        ccid = int(event["CCId"])
        primary = self.engine.ccid_to_primary[ccid]
        if primary != MAGIC_SHIELD_CCID or ccid != MAGIC_SHIELD_CCID:
            return None
        if event_id not in (4, 5):
            return None
        at_ms = event.get("At")
        if not isinstance(at_ms, int):
            at_ms = now_ms()
        previous = self._magic_shield_learn_candidates.get(target_id)
        self._magic_shield_learn_candidates[target_id] = (int(event_id), at_ms)
        self._prune_magic_shield_learn_candidates(at_ms)
        if previous is None:
            return None
        previous_event_id, previous_at_ms = previous
        if previous_event_id == int(event_id):
            return None
        if at_ms - previous_at_ms > MAGIC_SHIELD_SELF_LEARN_TOGGLE_WINDOW_MS:
            return None
        return "magic shield quick toggle"

    def _prune_magic_shield_learn_candidates(self, at_ms: int) -> None:
        cutoff = at_ms - MAGIC_SHIELD_SELF_LEARN_TOGGLE_WINDOW_MS
        self._magic_shield_learn_candidates = {
            target_id: candidate
            for target_id, candidate in self._magic_shield_learn_candidates.items()
            if candidate[1] >= cutoff
        }

    def allow_self_event(self, event: dict[str, Any]) -> bool:
        if self.disabled:
            return True
        if self.self_id is None:
            return False
        event_id = event.get("Id")
        target_id = event.get("TargetId")
        return (
            (event_id is not None and str(event_id) == self.self_id)
            or (target_id is not None and str(target_id) == self.self_id)
        )

    def _set_self_id(self, target_id: str, reason: str) -> None:
        if self.self_id == target_id:
            return
        action = "learned" if self.self_id is None else "updated"
        self.self_id = target_id
        self.engine.set_self_entity_id(target_id)
        print(f"[live] {action} self id: {self.self_id} ({reason})")

    def reset_auto(self, reason: str) -> None:
        if self.disabled or self.explicit_self_id or self.self_id is None:
            return
        print(f"[live] reset self id: {self.self_id} ({reason})")
        self.self_id = None
        self.engine.set_self_entity_id(None)

    def _notice_waiting(
        self, event: dict[str, Any], *, target_id: str, attacker_id: str
    ) -> None:
        now = time.monotonic()
        if now - self._last_wait_notice_at < 5:
            return
        self._last_wait_notice_at = now
        ccid = int(event["CCId"])
        primary = self.engine.ccid_to_primary[ccid]
        spec = self.engine.states[primary].spec
        print(
            "[live] waiting for self id; ignored "
            f"{spec.name} target={target_id} attacker={attacker_id}"
        )


class LocalWebSocket:
    def __init__(
        self, *, host: str, port: int, path: str, timeout_seconds: float = 5.0
    ) -> None:
        self.host = host
        self.port = port
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.socket: socket.socket | None = None

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}{self.path}"

    def connect(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Origin: http://{self.host}:{self.port}\r\n"
            "\r\n"
        )
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout_seconds)
        sock.sendall(request.encode("ascii"))
        response = self._read_http_response(sock)
        status = response.splitlines()[0] if response else ""
        if "101" not in status:
            sock.close()
            raise ConnectionError(f"WebSocket handshake failed: {status}")

        accept = self._header_value(response, "sec-websocket-accept")
        expected = base64.b64encode(
            hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest()
        ).decode("ascii")
        if accept != expected:
            sock.close()
            raise ConnectionError("WebSocket accept header mismatch")

        sock.settimeout(0.5)
        self.socket = sock

    def close(self) -> None:
        if self.socket is not None:
            try:
                self.socket.close()
            finally:
                self.socket = None

    def recv_text(self) -> str | None:
        if self.socket is None:
            raise ConnectionError("WebSocket is not connected")

        while True:
            opcode, payload = self._recv_frame(self.socket)
            if opcode == 1:
                return payload.decode("utf-8", errors="replace")
            if opcode == 8:
                raise ConnectionError("WebSocket closed by server")
            if opcode == 9:
                self._send_control(opcode=10, payload=payload)
                continue
            if opcode in (2, 10):
                continue
            return None

    def _send_control(self, *, opcode: int, payload: bytes) -> None:
        if self.socket is None:
            return
        mask = os.urandom(4)
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length > 125:
            return
        header.append(0x80 | length)
        masked = bytes(payload[i] ^ mask[i % 4] for i in range(length))
        self.socket.sendall(bytes(header) + mask + masked)

    @staticmethod
    def _read_http_response(sock: socket.socket) -> str:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 65536:
                break
        return data.decode("latin1", errors="replace")

    @staticmethod
    def _header_value(response: str, name: str) -> str | None:
        prefix = name.lower() + ":"
        for line in response.splitlines()[1:]:
            if line.lower().startswith(prefix):
                return line.split(":", 1)[1].strip()
        return None

    @classmethod
    def _recv_frame(cls, sock: socket.socket) -> tuple[int, bytes]:
        header = cls._recv_exact(sock, 2)
        b1, b2 = header
        opcode = b1 & 0x0F
        masked = bool(b2 & 0x80)
        length = b2 & 0x7F
        if length == 126:
            length = struct.unpack("!H", cls._recv_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", cls._recv_exact(sock, 8))[0]
        mask = cls._recv_exact(sock, 4) if masked else b""
        payload = cls._recv_exact(sock, length)
        if masked:
            payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
        return opcode, payload

    @staticmethod
    def _recv_exact(sock: socket.socket, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            chunk = sock.recv(size - len(chunks))
            if not chunk:
                raise ConnectionError("socket closed")
            chunks.extend(chunk)
        return bytes(chunks)


def emit_alert(
    alert: FiredAlert,
    *,
    no_audio: bool,
    bell: bool,
    alert_recorder: AlertRecorder | None = None,
    engine: AlertEngine | None = None,
    self_filter: SelfFilter | None = None,
    source: str = "unknown",
    event: dict[str, Any] | None = None,
) -> None:
    if alert_recorder is not None and engine is not None:
        alert_recorder.write_alert(
            alert,
            engine=engine,
            source=source,
            event=event,
            self_id=None if self_filter is None else self_filter.self_id,
        )
    if bell:
        print("\a", end="")
    print_alert(alert)
    if not no_audio:
        play_sound(alert.sound, async_play=True, volume=alert.volume)


def process_event(
    engine: AlertEngine,
    self_filter: SelfFilter,
    event: dict[str, Any],
    *,
    no_audio: bool,
    bell: bool,
    suppress_alerts: bool,
    allow_learning: bool,
    verbose_events: bool,
    alert_recorder: AlertRecorder | None = None,
    server_clock: ServerClockCalibrator | None = None,
    server_clock_recorder: ServerClockDiagnosticRecorder | None = None,
    music_overlay: MusicOverlayPublisher | None = None,
) -> None:
    if server_clock is not None:
        calibration = server_clock.observe(event)
        if calibration is not None:
            print(
                "[live] login server clock: "
                f"character={calibration.character_id} "
                f"skew={calibration.wall_clock_skew_ms / 1000:+.3f}s"
            )
            if server_clock_recorder is not None:
                server_clock_recorder.write_login(calibration)
        entity_server_time = server_clock.observe_entity_server_time(event)
        if entity_server_time is not None:
            if server_clock.entity_server_time_samples_seen == 1:
                print(
                    "[live] server clock diagnostic: op=0x659c "
                    f"entity={entity_server_time.entity_id} "
                    f"skew={entity_server_time.wall_clock_skew_ms / 1000:+.3f}s "
                    "applied=false"
                )
            if server_clock_recorder is not None:
                server_clock_recorder.write_entity_server_time(
                    entity_server_time,
                    self_id=self_filter.self_id,
                )
        ccid = event.get("CCId")
        try:
            is_music_event = int(ccid) in MUSIC_BUFF_CCIDS
        except (TypeError, ValueError):
            is_music_event = False
        comparison = (
            server_clock.music_timing_comparison(event)
            if is_music_event
            else None
        )
        if comparison is not None and server_clock_recorder is not None:
            server_clock_recorder.write_music(
                comparison,
                self_id=self_filter.self_id,
            )

    self_filter.observe(event)

    ccid = event.get("CCId")
    if verbose_events and ccid is not None and int(ccid) in engine.ccid_to_primary:
        spec = engine.states[engine.ccid_to_primary[int(ccid)]].spec
        print(
            "[live] tracked event "
            f"event={event.get('EventId')} name={spec.name} ccid={ccid} "
            f"id={event.get('Id')} attacker={event.get('AttackerId')}"
        )

    is_progress_event = engine.is_progress_event(event)
    is_stat_drop_effect_event = engine.is_stat_drop_effect_event(event)
    is_unfiltered_stat_drop_effect_event = (
        engine.is_unfiltered_stat_drop_effect_event(event)
    )
    is_boss_hp_event = engine.is_boss_hp_event(event)
    is_miracle_orb_hp_event = engine.is_miracle_orb_hp_event(event)
    is_boss_red_orb_event = engine.is_boss_red_orb_event(event)
    is_boss_laser_event = engine.is_boss_laser_event(event)
    is_key_enemy_debuff_event = engine.is_key_enemy_debuff_event(event)
    is_death_signal_event = engine.is_death_signal_event(event)
    is_battle_timer_event = engine.is_battle_timer_event(event)
    is_skill_cooldown_anchor_event = engine.is_skill_cooldown_anchor_event(event)
    is_astrology_card_tracker_event = (
        engine.astrology_card_tracker.is_relevant_event(event)
    )
    is_short_cooldown_test_target_event = (
        engine.is_short_cooldown_test_target_event(event)
    )
    is_self_stats_event = (
        event.get("EventId") == 17 and self_filter.allow_self_event(event)
    )
    if (
        is_boss_hp_event
        or is_miracle_orb_hp_event
        or is_boss_red_orb_event
        or is_boss_laser_event
        or is_key_enemy_debuff_event
        or is_short_cooldown_test_target_event
        or (is_stat_drop_effect_event and is_unfiltered_stat_drop_effect_event)
    ):
        pass
    elif (
        is_progress_event
        or is_self_stats_event
        or is_death_signal_event
        or is_battle_timer_event
        or is_skill_cooldown_anchor_event
        or is_astrology_card_tracker_event
        or (is_stat_drop_effect_event and not is_unfiltered_stat_drop_effect_event)
    ):
        if not self_filter.allow_self_event(event):
            return
    elif not self_filter.allow(event, allow_learning=allow_learning):
        return

    primary = engine.ccid_to_primary.get(int(ccid)) if ccid is not None else None
    astrology_revision_before = engine.astrology_card_tracker.revision
    alerts = engine.process_event(event)
    if engine.astrology_card_tracker.revision != astrology_revision_before:
        update = engine.astrology_card_tracker.last_update
        if update is not None:
            print(
                "[live] astrology cards: "
                f"action={update.action} skill={update.skill_id} "
                f"suit={update.skill_suit} card={update.card or '-'} "
                f"held={engine.astrology_card_tracker.held_card or '-'} "
                f"count={engine.astrology_card_tracker.counter}/"
                f"{engine.astrology_card_tracker.settings.counter_threshold} "
                f"next={engine.astrology_card_tracker.next_card_number}"
            )
    if music_overlay is not None:
        music_overlay.sync_states(
            engine.states,
            key_enemy_debuff_alert=engine.key_enemy_debuff_alert,
            key_enemy_debuff_states=engine.key_enemy_debuff_entity_states,
            short_cooldown_test_target_active=(
                engine.short_cooldown_test_target_active
            ),
            astrology_tracking_active=(
                engine.astrology_tracking_context_active
            ),
            self_identity_confirmed=engine.self_entity_id is not None,
            astrology_card_tracker=engine.astrology_card_tracker,
            boss_hp_states_by_max_hp=getattr(
                engine, "boss_hp_alert_states_by_max_hp", None
            ),
            miracle_orb_hp_states=getattr(engine, "miracle_orb_hp_states", None),
            miracle_orb_selected_entity_id=getattr(
                engine, "miracle_orb_selected_entity_id", None
            ),
            boss_laser_states_by_max_hp=getattr(
                engine, "boss_laser_alert_states_by_max_hp", None
            ),
        )
    if suppress_alerts:
        return

    if (
        primary is not None
        and event.get("EventId") == 4
        and int(ccid) == primary
    ):
        state = engine.states[primary]
        if state.active and state.end_ms is not None:
            seen_at_ms = now_ms()
            event_at_ms = event.get("At")
            remaining = max(0, round((state.end_ms - seen_at_ms) / 1000))
            timing_parts = []
            if isinstance(event_at_ms, int):
                extra = event.get("ExtraData") or {}
                if "SBT" in extra:
                    sbt_adjust_seconds = engine.effective_sbt_adjust_seconds(
                        state.spec
                    )
                    raw_end_ms = sbt_to_unix_ms(extra["SBT"], engine.tz_offset_hours)
                    packet_remaining = max(
                        0,
                        round(
                            (
                                raw_end_ms
                                + int(sbt_adjust_seconds * 1000)
                                - event_at_ms
                            )
                            / 1000
                        ),
                    )
                    timing_parts.append(f"packet {packet_remaining}s")
                receive_lag = max(0, round((seen_at_ms - event_at_ms) / 1000))
                timing_parts.append(f"lag {receive_lag}s")
            sbt_adjust_seconds = engine.effective_sbt_adjust_seconds(state.spec)
            if sbt_adjust_seconds:
                timing_parts.append(f"sbt adjust +{sbt_adjust_seconds:g}s")
            stack_text = ""
            if state.stacks is not None:
                max_stacks = state.spec.max_stacks or ""
                stack_text = f" {state.stacks}/{max_stacks}层"
            timing_text = f" ({', '.join(timing_parts)})" if timing_parts else ""
            print(
                f"[live] seen {state.spec.name}{stack_text}: "
                f"{remaining}s{timing_text}"
            )

    for alert in alerts:
        emit_alert(
            alert,
            no_audio=no_audio,
            bell=bell,
            alert_recorder=alert_recorder,
            engine=engine,
            self_filter=self_filter,
            source="event",
            event=event,
        )


def advance_live_time(
    engine: AlertEngine,
    *,
    no_audio: bool,
    bell: bool,
    suppress_alerts: bool,
    alert_recorder: AlertRecorder | None = None,
    self_filter: SelfFilter | None = None,
    music_overlay: MusicOverlayPublisher | None = None,
) -> None:
    alerts = engine.advance_time(now_ms())
    if music_overlay is not None:
        music_overlay.sync_states(
            engine.states,
            key_enemy_debuff_alert=engine.key_enemy_debuff_alert,
            key_enemy_debuff_states=engine.key_enemy_debuff_entity_states,
            short_cooldown_test_target_active=(
                engine.short_cooldown_test_target_active
            ),
            astrology_tracking_active=(
                engine.astrology_tracking_context_active
            ),
            self_identity_confirmed=engine.self_entity_id is not None,
            astrology_card_tracker=engine.astrology_card_tracker,
            boss_hp_states_by_max_hp=getattr(
                engine, "boss_hp_alert_states_by_max_hp", None
            ),
            miracle_orb_hp_states=getattr(engine, "miracle_orb_hp_states", None),
            miracle_orb_selected_entity_id=getattr(
                engine, "miracle_orb_selected_entity_id", None
            ),
            boss_laser_states_by_max_hp=getattr(
                engine, "boss_laser_alert_states_by_max_hp", None
            ),
        )
    if suppress_alerts:
        return

    for alert in alerts:
        emit_alert(
            alert,
            no_audio=no_audio,
            bell=bell,
            alert_recorder=alert_recorder,
            engine=engine,
            self_filter=self_filter,
            source="advance",
            event=None,
        )


def print_status(engine: AlertEngine) -> None:
    at_ms = now_ms()
    active = []
    for state in engine.states.values():
        if not state.active or state.end_ms is None:
            continue
        remaining = max(0, round((state.end_ms - at_ms) / 1000))
        stack_text = ""
        if state.stacks is not None:
            max_stacks = state.spec.max_stacks or ""
            stack_text = f" {state.stacks}/{max_stacks}层"
        active.append(f"{state.spec.name}{stack_text}:{remaining}s")
    for state in engine.progress_states.values():
        if state.value is None:
            continue
        active.append(f"{state.spec.name}:{state.value:.1f}%")
    for state in engine.stat_drop_effect_states:
        if state.active and not state.ended_fired:
            active.append(state.spec.name)

    if active:
        print("[live] active " + " | ".join(active))
    else:
        print("[live] active -")


def make_engine(
    args: argparse.Namespace,
) -> tuple[AlertEngine, SelfFilter, ServerClockCalibrator]:
    loaded = load_all_specs(args.config)
    server_clock = ServerClockCalibrator(
        load_server_clock_settings(
            args.config,
            fallback_tz_offset_hours=args.tz_offset_hours,
        )
    )
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
        music_tuan_silence_enabled=loaded.music_tuan_silence_enabled,
        astrology_card_tracker_settings=loaded.astrology_card_tracker_settings,
        server_clock_calibrator=server_clock,
    )
    self_filter = SelfFilter(
        engine,
        self_id=args.self_id,
        disabled=args.no_self_filter,
    )
    return engine, self_filter, server_clock


def print_common_start(args: argparse.Namespace) -> None:
    print(f"[live] config: {args.config}")
    if args.no_audio:
        print("[live] audio disabled")
    if args.no_self_filter:
        print("[live] self filter disabled")
    elif args.self_id:
        print(f"[live] self id: {args.self_id}")
    else:
        print("[live] self id: auto, quickly toggle magic shield after startup")
    print("[live] press Ctrl+C to stop")


def cmd_watch_file(args: argparse.Namespace) -> int:
    engine, self_filter, server_clock = make_engine(args)
    music_overlay = MusicOverlayPublisher(args.config)
    music_overlay.start()
    recorder = EventRecorder(getattr(args, "record_events", ""))
    alert_recorder = AlertRecorder(getattr(args, "record_alerts", ""))
    server_clock_recorder = ServerClockDiagnosticRecorder(server_clock.settings)

    histories = Path(args.histories)
    current_file: Path | None = None
    current_tail: GzipJsonTail | None = None
    suppress_initial_events = False
    last_status_at = 0.0
    last_file_notice_at = 0.0
    started_at = time.time()

    print("[live] Buff watcher is running in file mode.")
    print(f"[live] histories: {histories}")
    if recorder.path is not None:
        print(f"[live] recording events: {recorder.path}")
    if alert_recorder.path is not None:
        print(f"[live] recording alert timing: {alert_recorder.path}")
    if server_clock.settings.enabled:
        print(f"[live] server clock diagnostics: {server_clock.settings.mode}")
        if server_clock_recorder.path is not None:
            print(f"[live] recording clock diagnostics: {server_clock_recorder.path}")
    print_common_start(args)

    deadline = time.monotonic() + args.max_seconds if args.max_seconds > 0 else None

    try:
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                print("[live] max seconds reached")
                return 0

            latest = newest_raw_file(histories)
            if latest is None:
                if time.monotonic() - last_file_notice_at >= 10:
                    print("[live] waiting for MicoPunch raw file...")
                    last_file_notice_at = time.monotonic()
                time.sleep(args.poll_seconds)
                continue

            if latest != current_file:
                current_file = latest
                current_tail = GzipJsonTail(latest)
                try:
                    latest_mtime = latest.stat().st_mtime
                except OSError:
                    latest_mtime = started_at
                suppress_initial_events = (
                    not args.play_existing and latest_mtime < started_at - 1
                )
                print(f"[live] following: {latest}")

            saw_new_event = False

            if current_tail is None:
                time.sleep(args.poll_seconds)
                continue

            new_items = current_tail.read_events()
            for item in new_items:
                saw_new_event = True
                recorder.write_event(item.event)
                process_event(
                    engine,
                    self_filter,
                    item.event,
                    no_audio=args.no_audio,
                    bell=not args.no_bell,
                    suppress_alerts=suppress_initial_events,
                    allow_learning=not suppress_initial_events,
                    verbose_events=args.verbose_events,
                    alert_recorder=alert_recorder,
                    server_clock=server_clock,
                    server_clock_recorder=server_clock_recorder,
                    music_overlay=music_overlay,
                )

            if new_items and suppress_initial_events:
                print(
                    "[live] caught up "
                    f"{new_items[-1].line_number} existing events without alerts"
                )
                suppress_initial_events = False

            advance_live_time(
                engine,
                no_audio=args.no_audio,
                bell=not args.no_bell,
                suppress_alerts=False,
                alert_recorder=alert_recorder,
                self_filter=self_filter,
                music_overlay=music_overlay,
            )

            if (
                args.status_interval > 0
                and time.monotonic() - last_status_at >= args.status_interval
            ):
                print_status(engine)
                last_status_at = time.monotonic()

            if not saw_new_event:
                time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("\n[live] stopped")
        return 0
    finally:
        recorder.close()
        alert_recorder.close()
        server_clock_recorder.close()
        music_overlay.close()


def cmd_watch_ws(args: argparse.Namespace) -> int:
    engine, self_filter, server_clock = make_engine(args)
    music_overlay = MusicOverlayPublisher(args.config)
    music_overlay.start()
    client = LocalWebSocket(host=args.host, port=args.port, path=args.path)
    recorder = EventRecorder(getattr(args, "record_events", ""))
    alert_recorder = AlertRecorder(getattr(args, "record_alerts", ""))
    server_clock_recorder = ServerClockDiagnosticRecorder(server_clock.settings)
    last_status_at = 0.0
    deadline = time.monotonic() + args.max_seconds if args.max_seconds > 0 else None
    backend_is_alive = getattr(args, "backend_is_alive", None)
    restart_backend = getattr(args, "restart_backend", None)

    print("[live] Buff watcher is running in WebSocket mode.")
    print(f"[live] websocket: {client.url}")
    if recorder.path is not None:
        print(f"[live] recording events: {recorder.path}")
    if alert_recorder.path is not None:
        print(f"[live] recording alert timing: {alert_recorder.path}")
    if server_clock.settings.enabled:
        print(f"[live] server clock diagnostics: {server_clock.settings.mode}")
        if server_clock_recorder.path is not None:
            print(f"[live] recording clock diagnostics: {server_clock_recorder.path}")
    print_common_start(args)

    try:
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                print("[live] max seconds reached")
                return 0

            try:
                client.connect()
                print("[live] websocket connected")
                while True:
                    if deadline is not None and time.monotonic() >= deadline:
                        print("[live] max seconds reached")
                        return 0

                    try:
                        text = client.recv_text()
                    except socket.timeout:
                        text = None

                    if callable(backend_is_alive) and not backend_is_alive():
                        raise ConnectionError("packet backend process exited")

                    if text:
                        try:
                            event = json.loads(text)
                        except json.JSONDecodeError:
                            event = None
                        if isinstance(event, dict):
                            recorder.write_event(event)
                            process_event(
                                engine,
                                self_filter,
                                event,
                                no_audio=args.no_audio,
                                bell=not args.no_bell,
                                suppress_alerts=False,
                                allow_learning=True,
                                verbose_events=args.verbose_events,
                                alert_recorder=alert_recorder,
                                server_clock=server_clock,
                                server_clock_recorder=server_clock_recorder,
                                music_overlay=music_overlay,
                            )

                    advance_live_time(
                        engine,
                        no_audio=args.no_audio,
                        bell=not args.no_bell,
                        suppress_alerts=False,
                        alert_recorder=alert_recorder,
                        self_filter=self_filter,
                        music_overlay=music_overlay,
                    )

                    if (
                        args.status_interval > 0
                        and time.monotonic() - last_status_at >= args.status_interval
                    ):
                        print_status(engine)
                        last_status_at = time.monotonic()

            except (ConnectionError, OSError) as exc:
                print(f"[live] websocket disconnected: {exc}")
                client.close()
                if (
                    callable(backend_is_alive)
                    and not backend_is_alive()
                    and callable(restart_backend)
                ):
                    print(
                        "[live] packet backend process exited; restarting "
                        "without clearing the confirmed self id"
                    )
                    new_port = int(restart_backend())
                    if new_port != client.port:
                        client.port = new_port
                        print(f"[live] websocket: {client.url}")
                time.sleep(args.reconnect_seconds)
    except KeyboardInterrupt:
        client.close()
        print("\n[live] stopped")
        return 0
    finally:
        client.close()
        recorder.close()
        alert_recorder.close()
        server_clock_recorder.close()
        music_overlay.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run buff alerts against live MicoPunch raw output.")
    parser.add_argument("--config", default="buffwatcher.config.local.json")
    parser.add_argument("--source", choices=["websocket", "file"], default="websocket")
    parser.add_argument("--histories", default=DEFAULT_HISTORIES)
    parser.add_argument("--host", default=DEFAULT_WS_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_WS_PORT)
    parser.add_argument("--path", default=DEFAULT_WS_PATH)
    parser.add_argument("--tz-offset-hours", type=int, default=DEFAULT_TZ_OFFSET_HOURS)
    parser.add_argument("--poll-seconds", type=float, default=0.1)
    parser.add_argument("--reconnect-seconds", type=float, default=3)
    parser.add_argument(
        "--idle-reconnect-seconds",
        type=float,
        default=0,
        help="Deprecated compatibility option; quiet traffic never forces reconnects.",
    )
    parser.add_argument("--status-interval", type=float, default=30.0)
    parser.add_argument("--self-id", help="Only accept buff events whose target Id matches this value.")
    parser.add_argument("--no-self-filter", action="store_true")
    parser.add_argument("--play-existing", action="store_true")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--no-bell", action="store_true")
    parser.add_argument("--verbose-events", action="store_true")
    parser.add_argument("--record-events", default="", help="Write received events to this .ndjson.gz path.")
    parser.add_argument("--record-alerts", default="", help="Write alert timing diagnostics to this .ndjson path.")
    parser.add_argument("--max-seconds", type=float, default=0)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.source == "file":
        return cmd_watch_file(args)
    return cmd_watch_ws(args)


if __name__ == "__main__":
    raise SystemExit(main())

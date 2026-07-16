from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .overlay_bridge import (
    MIRACLE_ORB_DISPLAY_ORDER,
    MusicOverlaySettings,
    load_music_overlay_settings,
)
from .theme import SETTINGS_COLORS


TRANSPARENT_COLOR = "#010101"
CARD_BACKGROUND = SETTINGS_COLORS["row"]
CARD_BORDER = SETTINGS_COLORS["input"]
ICON_BACKGROUND = SETTINGS_COLORS["title"]
PRIMARY_TEXT = SETTINGS_COLORS["text"]
SUCCESS_COLOR = SETTINGS_COLORS["accent"]
WARMTH_COLOR = SETTINGS_COLORS["accent_dark"]
PROGRESS_TRACK_COLOR = SETTINGS_COLORS["content"]
PROGRESS_FILL_COLOR = "#efb45d"
TOAST_CONTENT_HEIGHT = 48
TOAST_ICON_SIZE = 48
TOAST_ICON_GAP = 6
LIFE_TEMPERATURE_CCID = 874
DEBUFF_CELL_SIZE = 48
DEBUFF_ICON_SIZE = 42
DEBUFF_GAP_PX = 6
DEBUFF_CENTER_Y_RATIO_LOW_RES = 0.715
DEBUFF_CENTER_Y_RATIO_HIGH_RES = 0.78
DEBUFF_RESPONSIVE_LOW_HEIGHT = 1080
DEBUFF_RESPONSIVE_HIGH_HEIGHT = 2160
MIRACLE_ORB_FOCUS_LOW_RES_OFFSET = 0.07
DEBUFF_FLASH_PERIOD_MS = 1200
DEBUFF_FLASH_VISIBLE_MS = 720
ASTROLOGY_CELL_SIZE = 90
ASTROLOGY_ICON_MAX_SIDE = 88
ASTROLOGY_READY_BORDER_DARK = "#d47b2c"
ASTROLOGY_READY_BORDER_LIGHT = "#ffd58a"
BRONNTANAS_HP_CARD_WIDTH = 232
BRONNTANAS_HP_CARD_HEIGHT = 72
BRONNTANAS_HP_ICON_SIZE = 64
BRONNTANAS_HP_WARNING_COLOR = "#ff3038"
MIRACLE_ORB_BLUE = "#87cefa"
MIRACLE_ORB_ORANGE = "#ff9d30"
MIRACLE_ORB_RED = "#d00000"
MIRACLE_ORB_LEFT_BAR_WIDTH = 190
MIRACLE_ORB_LEFT_BAR_HEIGHT = 30
MIRACLE_ORB_LEFT_BAR_GAP = 6
MIRACLE_ORB_FOCUS_BAR_WIDTH = 500
MIRACLE_ORB_FOCUS_BAR_HEIGHT = 44
MIRACLE_ORB_SHORT_NAMES = {7605: "球A", 7604: "球B", 7606: "球C"}
MIRACLE_ORB_FOCUS_NAMES = {
    7605: "神迹球A",
    7604: "神迹球B",
    7606: "神迹球C",
}
ROTATING_LASER_COUNTDOWN_COLOR = "#ff9d30"


@dataclass
class OverlayCondition:
    ccid: int
    name: str
    entity_name: str
    end_ms: int
    show_before_ms: int
    timing_source: str = "unknown"
    icon_path: str = ""
    ring_sound_enabled: bool = False
    visible_since_ms: int | None = None
    toast_lifetime_ms: int | None = None
    arrival_sound_played: bool = False
    three_second_sound_played: bool = False

    def remaining_ms(self, now_ms: int) -> int:
        return self.end_ms - now_ms

    def should_show(self, now_ms: int) -> bool:
        remaining = self.remaining_ms(now_ms)
        return 0 < remaining <= self.show_before_ms

    def mark_visible(self, now_ms: int) -> None:
        if self.visible_since_ms is not None:
            return
        remaining = max(1, self.remaining_ms(now_ms))
        self.visible_since_ms = now_ms
        self.toast_lifetime_ms = remaining

    def progress(self, now_ms: int) -> float:
        remaining = max(0, self.remaining_ms(now_ms))
        lifetime = max(1, self.toast_lifetime_ms or self.show_before_ms)
        return min(1.0, max(0.0, remaining / lifetime))


@dataclass(frozen=True)
class DebuffOverlayRequirement:
    key: str
    name: str
    icon_path: str
    complete: bool
    complete_end_ms: int | None
    expiry_active: bool
    expiry_end_ms: int | None

    def visual_status(
        self,
        now_ms: int,
        *,
        visual_expiry_enabled: bool,
        expiry_threshold_ms: int,
    ) -> str | None:
        complete_now = self.complete and (
            self.complete_end_ms is None or now_ms < self.complete_end_ms
        )
        if not complete_now:
            return "missing"
        if (
            visual_expiry_enabled
            and self.expiry_active
            and self.expiry_end_ms is not None
            and 0 < self.expiry_end_ms - now_ms <= expiry_threshold_ms
        ):
            return "expiring"
        return None


@dataclass(frozen=True)
class DebuffOverlaySnapshot:
    entity_id: str
    expiry_threshold_ms: int
    visual_expiry_enabled: bool
    requirements: tuple[DebuffOverlayRequirement, ...]


@dataclass(frozen=True)
class OtherSkillOverlayItem:
    key: str
    name: str
    icon_path: str


@dataclass(frozen=True)
class AstrologyOverlayItem:
    key: str
    name: str
    skill_id: int
    icon_path: str
    slot: int
    cooldown_ready_at_ms: int | None
    card_ready: bool

    def is_ready(self, now_ms: int) -> bool:
        return (
            self.card_ready
            or self.cooldown_ready_at_ms is None
            or int(now_ms) >= self.cooldown_ready_at_ms
        )


@dataclass(frozen=True)
class BronntanasHpOverlayItem:
    entity_id: str
    percent: float
    warning: bool
    dismiss_at_ms: int | None
    icon_path: str

    def is_visible(self, now_ms: int) -> bool:
        return self.dismiss_at_ms is None or int(now_ms) < self.dismiss_at_ms


@dataclass(frozen=True)
class MiracleOrbHpOverlayItem:
    entity_id: str
    race_id: int
    percent: float


@dataclass(frozen=True)
class RotatingLaserCountdownOverlayItem:
    boss_entity_id: str
    start_at_ms: int
    end_at_ms: int
    duration_ms: int

    def is_visible(self, now_ms: int) -> bool:
        return int(now_ms) < self.end_at_ms

    def text(self, now_ms: int) -> str:
        return f"{max(0, self.end_at_ms - int(now_ms)) / 1000.0:.1f}"


def format_remaining_countdown(remaining_ms: int) -> str:
    remaining = max(0, int(remaining_ms))
    if remaining > 2000:
        return str(math.ceil(remaining / 1000))
    tenths = remaining // 100
    return f"{tenths // 10}.{tenths % 10}"


def decode_ipc_command(line: bytes | str) -> dict[str, Any] | None:
    try:
        text = line.decode("utf-8-sig") if isinstance(line, bytes) else line
        command = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return command if isinstance(command, dict) else None


if os.name == "nt":
    from ctypes import wintypes

    class _Point(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class _Rect(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]


class GameWindowTracker:
    def __init__(self, settings: MusicOverlaySettings) -> None:
        self.process_names = {name.casefold() for name in settings.target_process_names}
        self.window_titles = tuple(
            title.casefold() for title in settings.target_window_titles
        )
        self.hwnd: int | None = None

    def find(self) -> int | None:
        if os.name != "nt":
            return None
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        foreground = int(user32.GetForegroundWindow() or 0)
        process_matches: list[int] = []
        title_matches: list[int] = []
        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )

        def callback(hwnd: int, _: int) -> bool:
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True
            title_length = user32.GetWindowTextLengthW(hwnd)
            title_buffer = ctypes.create_unicode_buffer(max(1, title_length + 1))
            user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
            title = title_buffer.value.casefold()
            process_name = self._process_name(hwnd, kernel32, user32).casefold()
            if process_name in self.process_names:
                process_matches.append(int(hwnd))
            elif title and any(part in title for part in self.window_titles):
                title_matches.append(int(hwnd))
            return True

        user32.EnumWindows(callback_type(callback), 0)
        candidates = process_matches or title_matches
        if foreground in candidates:
            self.hwnd = foreground
        else:
            self.hwnd = candidates[0] if candidates else None
        return self.hwnd

    @staticmethod
    def _process_name(hwnd: int, kernel32: Any, user32: Any) -> str:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = kernel32.OpenProcess(0x1000, False, pid.value)
        if not process:
            return ""
        try:
            capacity = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(capacity.value)
            if not kernel32.QueryFullProcessImageNameW(
                process, 0, buffer, ctypes.byref(capacity)
            ):
                return ""
            return Path(buffer.value).name
        finally:
            kernel32.CloseHandle(process)

    def client_bounds(self) -> tuple[int, int, int, int] | None:
        hwnd = self.hwnd
        if os.name != "nt" or not hwnd or not ctypes.windll.user32.IsWindow(hwnd):
            hwnd = self.find()
        if not hwnd:
            return None
        user32 = ctypes.windll.user32
        rect = _Rect()
        origin = _Point(0, 0)
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            return None
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width <= 0 or height <= 0:
            return None
        return int(origin.x), int(origin.y), width, height

    def is_foreground(self) -> bool:
        if os.name != "nt" or not self.hwnd:
            return False
        return int(ctypes.windll.user32.GetForegroundWindow() or 0) == int(
            self.hwnd
        )


class MusicOverlayApp:
    def __init__(
        self,
        settings: MusicOverlaySettings,
        *,
        config_path: Path,
        preview: bool = False,
        demo_seconds: float = 0,
    ) -> None:
        import tkinter as tk

        self.tk = tk
        self.settings = settings
        self.config_path = config_path
        self.preview = preview
        self.demo_deadline = (
            time.monotonic() + demo_seconds if demo_seconds > 0 else None
        )
        self.commands: queue.Queue[dict[str, Any]] = queue.Queue()
        self.conditions: dict[int, OverlayCondition] = {}
        self.debuff_snapshot: DebuffOverlaySnapshot | None = None
        self.other_skill_items: tuple[OtherSkillOverlayItem, ...] = ()
        self.short_cooldown_items: tuple[OtherSkillOverlayItem, ...] = ()
        self.astrology_items: tuple[AstrologyOverlayItem, ...] = ()
        self.bronntanas_hp_item: BronntanasHpOverlayItem | None = None
        self.miracle_orb_hp_items: tuple[MiracleOrbHpOverlayItem, ...] = ()
        self.miracle_orb_hp_selected: MiracleOrbHpOverlayItem | None = None
        self.rotating_laser_countdown_item: (
            RotatingLaserCountdownOverlayItem | None
        ) = None
        self.tracker = GameWindowTracker(settings)
        self.last_bounds: tuple[int, int, int, int] | None = None
        self.window_visible = False
        self.icon_images: dict[tuple[str, int, bool], Any | None] = {}

        self.root = tk.Tk()
        self.root.title("BuffWatcher Music Overlay")
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(
            self.root,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.root.update_idletasks()
        self._apply_readonly_window_style()

        if not preview:
            threading.Thread(
                target=self._read_stdin,
                name="music-overlay-ipc",
                daemon=True,
            ).start()

    def _apply_readonly_window_style(self) -> None:
        if os.name != "nt":
            return
        self.root.update_idletasks()
        user32 = ctypes.windll.user32
        hwnd = self._native_hwnd(user32)
        get_window_long = user32.GetWindowLongW
        set_window_long = user32.SetWindowLongW
        get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
        get_window_long.restype = ctypes.c_long
        set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        set_window_long.restype = ctypes.c_long
        ex_style = int(get_window_long(hwnd, -20))
        ex_style |= 0x00000020  # WS_EX_TRANSPARENT
        ex_style |= 0x08000000  # WS_EX_NOACTIVATE
        ex_style |= 0x00000080  # WS_EX_TOOLWINDOW
        ex_style |= 0x00080000  # WS_EX_LAYERED (transparent color)
        set_window_long(hwnd, -20, ex_style)

    def _native_hwnd(self, user32: Any | None = None) -> int:
        hwnd = int(self.root.winfo_id())
        if os.name != "nt":
            return hwnd
        api = user32 or ctypes.windll.user32
        api.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        api.GetAncestor.restype = wintypes.HWND
        top_level = api.GetAncestor(hwnd, 2)  # GA_ROOT
        return int(top_level or hwnd)

    def _read_stdin(self) -> None:
        try:
            stdin = sys.stdin
            if stdin is None:
                return
            # The parent always writes UTF-8 JSON. On Simplified Chinese
            # Windows, TextIOWrapper defaults to cp936; reading its binary
            # buffer avoids turning Chinese names into mojibake.
            stream = getattr(stdin, "buffer", None) or stdin
            for line in stream:
                command = decode_ipc_command(line)
                if command is not None:
                    self.commands.put(command)
        finally:
            self.commands.put({"type": "shutdown"})

    def _drain_commands(self) -> bool:
        keep_running = True
        while True:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                break
            kind = command.get("type")
            if kind == "shutdown":
                keep_running = False
            elif kind == "clear":
                self.conditions.clear()
                self.debuff_snapshot = None
                self.other_skill_items = ()
                self.short_cooldown_items = ()
                self.astrology_items = ()
                self.bronntanas_hp_item = None
                self.miracle_orb_hp_items = ()
                self.miracle_orb_hp_selected = None
                self.rotating_laser_countdown_item = None
            elif kind == "remove":
                try:
                    self.conditions.pop(int(command.get("ccid")), None)
                except (TypeError, ValueError):
                    pass
            elif kind == "upsert":
                self._upsert(command)
            elif kind == "debuff_clear":
                self.debuff_snapshot = None
            elif kind == "debuff_snapshot":
                self._upsert_debuff_snapshot(command)
            elif kind == "other_skill_clear":
                self.other_skill_items = ()
            elif kind == "other_skill_snapshot":
                self._upsert_other_skill_snapshot(command)
            elif kind == "short_cooldown_clear":
                self.short_cooldown_items = ()
            elif kind == "short_cooldown_snapshot":
                self._upsert_short_cooldown_snapshot(command)
            elif kind == "astrology_clear":
                self.astrology_items = ()
            elif kind == "astrology_snapshot":
                self._upsert_astrology_snapshot(command)
            elif kind == "bronntanas_hp_clear":
                self.bronntanas_hp_item = None
            elif kind == "bronntanas_hp_snapshot":
                self._upsert_bronntanas_hp_snapshot(command)
            elif kind == "miracle_orb_hp_clear":
                self.miracle_orb_hp_items = ()
                self.miracle_orb_hp_selected = None
            elif kind == "miracle_orb_hp_snapshot":
                self._upsert_miracle_orb_hp_snapshot(command)
            elif kind == "rotating_laser_countdown_clear":
                self.rotating_laser_countdown_item = None
            elif kind == "rotating_laser_countdown_snapshot":
                self._upsert_rotating_laser_countdown_snapshot(command)
        return keep_running

    def _upsert(self, command: dict[str, Any]) -> None:
        try:
            ccid = int(command["ccid"])
            end_ms = int(command["end_ms"])
            show_before_ms = max(1, int(command["show_before_ms"]))
        except (KeyError, TypeError, ValueError):
            return
        previous = self.conditions.get(ccid)
        if (
            previous is not None
            and previous.end_ms == end_ms
            and previous.name == str(command.get("name") or ccid)
        ):
            previous.entity_name = str(
                command.get("entity_name") or previous.entity_name
            )
            previous.timing_source = str(
                command.get("timing_source") or previous.timing_source
            )
            previous.show_before_ms = show_before_ms
            previous.icon_path = str(command.get("icon_path") or "").strip()
            previous.ring_sound_enabled = bool(
                command.get(
                    "ring_sound_enabled",
                    self.settings.ring_sound_is_enabled(ccid),
                )
            )
            return
        self.conditions[ccid] = OverlayCondition(
            ccid=ccid,
            name=str(command.get("name") or ccid),
            entity_name=str(command.get("entity_name") or self.settings.entity_name),
            end_ms=end_ms,
            show_before_ms=show_before_ms,
            timing_source=str(command.get("timing_source") or "unknown"),
            icon_path=str(command.get("icon_path") or "").strip(),
            ring_sound_enabled=bool(
                command.get(
                    "ring_sound_enabled",
                    self.settings.ring_sound_is_enabled(ccid),
                )
            ),
        )

    def _upsert_debuff_snapshot(self, command: dict[str, Any]) -> None:
        raw_requirements = command.get("requirements")
        if not isinstance(raw_requirements, list):
            return
        requirements: list[DebuffOverlayRequirement] = []
        for raw in raw_requirements:
            if not isinstance(raw, dict):
                continue
            try:
                complete_end_ms = (
                    None
                    if raw.get("complete_end_ms") is None
                    else int(raw.get("complete_end_ms"))
                )
                expiry_end_ms = (
                    None
                    if raw.get("expiry_end_ms") is None
                    else int(raw.get("expiry_end_ms"))
                )
            except (TypeError, ValueError):
                continue
            requirements.append(
                DebuffOverlayRequirement(
                    key=str(raw.get("key") or ""),
                    name=str(raw.get("name") or ""),
                    icon_path=str(raw.get("icon_path") or "").strip(),
                    complete=bool(raw.get("complete", False)),
                    complete_end_ms=complete_end_ms,
                    expiry_active=bool(raw.get("expiry_active", False)),
                    expiry_end_ms=expiry_end_ms,
                )
            )
        if not requirements:
            self.debuff_snapshot = None
            return
        try:
            threshold_ms = max(0, int(command.get("expiry_threshold_ms", 0)))
        except (TypeError, ValueError):
            threshold_ms = 0
        self.debuff_snapshot = DebuffOverlaySnapshot(
            entity_id=str(command.get("entity_id") or ""),
            expiry_threshold_ms=threshold_ms,
            visual_expiry_enabled=bool(
                command.get("visual_expiry_enabled", True)
            ),
            requirements=tuple(requirements),
        )

    def _upsert_other_skill_snapshot(self, command: dict[str, Any]) -> None:
        self.other_skill_items = self._overlay_items_from_command(command)

    def _upsert_short_cooldown_snapshot(self, command: dict[str, Any]) -> None:
        self.short_cooldown_items = self._overlay_items_from_command(command)

    def _upsert_astrology_snapshot(self, command: dict[str, Any]) -> None:
        raw_items = command.get("items")
        if not isinstance(raw_items, list):
            return
        items: list[AstrologyOverlayItem] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            key = str(raw.get("key") or "").strip()
            if not key:
                continue
            try:
                skill_id = int(raw.get("skill_id"))
                slot = max(-1, min(1, int(raw.get("slot", 0))))
                ready_at_ms = (
                    None
                    if raw.get("cooldown_ready_at_ms") is None
                    else int(raw.get("cooldown_ready_at_ms"))
                )
            except (TypeError, ValueError):
                continue
            items.append(
                AstrologyOverlayItem(
                    key=key,
                    name=str(raw.get("name") or key),
                    skill_id=skill_id,
                    icon_path=str(raw.get("icon_path") or "").strip(),
                    slot=slot,
                    cooldown_ready_at_ms=ready_at_ms,
                    card_ready=bool(raw.get("card_ready", False)),
                )
            )
        self.astrology_items = tuple(items)

    def _upsert_bronntanas_hp_snapshot(self, command: dict[str, Any]) -> None:
        try:
            percent = min(100.0, max(0.0, float(command.get("percent"))))
            dismiss_at_ms = (
                None
                if command.get("dismiss_at_ms") is None
                else int(command.get("dismiss_at_ms"))
            )
        except (TypeError, ValueError):
            return
        entity_id = str(command.get("entity_id") or "").strip()
        if not entity_id:
            return
        self.bronntanas_hp_item = BronntanasHpOverlayItem(
            entity_id=entity_id,
            percent=percent,
            warning=bool(command.get("warning", False)),
            dismiss_at_ms=dismiss_at_ms,
            icon_path=str(command.get("icon_path") or "").strip(),
        )

    def _upsert_miracle_orb_hp_snapshot(self, command: dict[str, Any]) -> None:
        def parse_item(raw: Any) -> MiracleOrbHpOverlayItem | None:
            if not isinstance(raw, dict):
                return None
            entity_id = str(raw.get("entity_id") or "").strip()
            try:
                race_id = int(raw.get("race_id"))
                percent = min(100.0, max(0.0, float(raw.get("percent"))))
            except (TypeError, ValueError):
                return None
            if not entity_id:
                return None
            return MiracleOrbHpOverlayItem(
                entity_id=entity_id,
                race_id=race_id,
                percent=percent,
            )

        raw_items = command.get("items")
        if not isinstance(raw_items, list):
            return
        items = [item for item in (parse_item(raw) for raw in raw_items) if item]
        self.miracle_orb_hp_items = tuple(
            sorted(
                items,
                key=lambda item: MIRACLE_ORB_DISPLAY_ORDER.get(item.race_id, 99),
            )
        )
        self.miracle_orb_hp_selected = parse_item(command.get("selected"))

    def _upsert_rotating_laser_countdown_snapshot(
        self, command: dict[str, Any]
    ) -> None:
        boss_entity_id = str(command.get("boss_entity_id") or "").strip()
        try:
            start_at_ms = int(command.get("start_at_ms"))
            end_at_ms = int(command.get("end_at_ms"))
            duration_ms = int(command.get("duration_ms"))
        except (TypeError, ValueError):
            return
        if (
            not boss_entity_id
            or start_at_ms <= 0
            or end_at_ms <= start_at_ms
            or duration_ms <= 0
        ):
            return
        self.rotating_laser_countdown_item = RotatingLaserCountdownOverlayItem(
            boss_entity_id=boss_entity_id,
            start_at_ms=start_at_ms,
            end_at_ms=end_at_ms,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _overlay_items_from_command(
        command: dict[str, Any]
    ) -> tuple[OtherSkillOverlayItem, ...]:
        raw_items = command.get("items")
        if not isinstance(raw_items, list):
            return ()
        items: list[OtherSkillOverlayItem] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            key = str(raw.get("key") or "").strip()
            if not key:
                continue
            items.append(
                OtherSkillOverlayItem(
                    key=key,
                    name=str(raw.get("name") or key),
                    icon_path=str(raw.get("icon_path") or "").strip(),
                )
            )
        return tuple(items)

    def _preview_bounds(self) -> tuple[int, int, int, int]:
        return (
            0,
            0,
            int(self.root.winfo_screenwidth()),
            int(self.root.winfo_screenheight()),
        )

    def _target_bounds(self) -> tuple[int, int, int, int] | None:
        if self.preview:
            return self._preview_bounds()
        bounds = self.tracker.client_bounds()
        if bounds is None:
            return None
        if self.settings.hide_when_game_inactive and not self.tracker.is_foreground():
            return None
        return bounds

    def _position_window(self, bounds: tuple[int, int, int, int]) -> None:
        if bounds == self.last_bounds:
            return
        x, y, width, height = bounds
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.canvas.configure(width=width, height=height)
        self.last_bounds = bounds
        self._apply_readonly_window_style()

    def _play_sound(self, relative_path: str) -> None:
        if (
            self.settings.muted
            or not relative_path
            or os.name != "nt"
        ):
            return
        try:
            import winsound

            path = Path(relative_path)
            if not path.is_absolute():
                path = self.config_path.parent / path
            if path.is_file():
                winsound.PlaySound(
                    str(path),
                    winsound.SND_FILENAME
                    | winsound.SND_ASYNC
                    | winsound.SND_NODEFAULT,
                )
        except (OSError, RuntimeError):
            return

    def _load_icon(
        self,
        icon_path: str,
        *,
        max_side: int = DEBUFF_CELL_SIZE,
        allow_upscale: bool = False,
    ) -> Any | None:
        value = str(icon_path or "").strip()
        if not value:
            return None
        max_side = max(1, int(max_side))
        cache_key = (value, max_side, bool(allow_upscale))
        cached = self.icon_images.get(cache_key)
        if cache_key in self.icon_images:
            return cached
        path = Path(value)
        if not path.is_absolute():
            path = self.config_path.parent / path
        try:
            image = self.tk.PhotoImage(file=str(path))
            largest_side = max(int(image.width()), int(image.height()))
            # Keep near-cell-size artwork at its native resolution.  In
            # particular, the supplied Manus icon is 21x44; shrinking every
            # image above 42 px with Tk's integer subsample would turn it into
            # an unnecessarily tiny 10x22 icon even though it fits a 48 px cell.
            if largest_side > max_side:
                factor = max(1, math.ceil(largest_side / max_side))
                image = image.subsample(factor, factor)
            elif allow_upscale and largest_side < max_side:
                factor = max(1, math.floor(max_side / largest_side))
                if factor > 1:
                    image = image.zoom(factor, factor)
        except (OSError, self.tk.TclError):
            image = None
        self.icon_images[cache_key] = image
        return image

    def _visible_astrology_items(
        self, now_ms: int
    ) -> tuple[AstrologyOverlayItem, ...]:
        return tuple(item for item in self.astrology_items if item.is_ready(now_ms))

    def _visible_conditions(self, now_ms: int) -> list[OverlayCondition]:
        expired: list[int] = []
        visible: list[OverlayCondition] = []
        for ccid, condition in self.conditions.items():
            remaining = condition.remaining_ms(now_ms)
            if remaining <= 0:
                expired.append(ccid)
                continue
            if not condition.should_show(now_ms):
                continue
            condition.mark_visible(now_ms)
            if condition.ring_sound_enabled and not condition.arrival_sound_played:
                condition.arrival_sound_played = True
                self._play_sound(self.settings.arrival_sound)
            if (
                (condition.toast_lifetime_ms or 0) >= 4000
                and remaining <= 3000
                and condition.ring_sound_enabled
                and not condition.three_second_sound_played
            ):
                condition.three_second_sound_played = True
                self._play_sound(self.settings.three_second_sound)
            visible.append(condition)
        for ccid in expired:
            self.conditions.pop(ccid, None)
        return sorted(
            visible,
            key=lambda item: (item.visible_since_ms or now_ms, item.ccid),
        )

    def _visible_debuff_requirements(
        self, now_ms: int
    ) -> list[tuple[DebuffOverlayRequirement, str]]:
        snapshot = self.debuff_snapshot
        if snapshot is None:
            return []
        visible: list[tuple[DebuffOverlayRequirement, str]] = []
        for requirement in snapshot.requirements:
            status = requirement.visual_status(
                now_ms,
                visual_expiry_enabled=snapshot.visual_expiry_enabled,
                expiry_threshold_ms=snapshot.expiry_threshold_ms,
            )
            if status is not None:
                visible.append((requirement, status))
        return visible

    def _draw(
        self,
        visible: list[OverlayCondition],
        visible_debuffs: list[tuple[DebuffOverlayRequirement, str]],
        now_ms: int,
        other_skill_items: tuple[OtherSkillOverlayItem, ...] = (),
        short_cooldown_items: tuple[OtherSkillOverlayItem, ...] = (),
        astrology_items: tuple[AstrologyOverlayItem, ...] = (),
        bronntanas_hp_item: BronntanasHpOverlayItem | None = None,
        miracle_orb_hp_items: tuple[MiracleOrbHpOverlayItem, ...] = (),
        miracle_orb_hp_selected: MiracleOrbHpOverlayItem | None = None,
        rotating_laser_countdown_item: (
            RotatingLaserCountdownOverlayItem | None
        ) = None,
    ) -> None:
        self.canvas.delete("all")
        if (
            not visible
            and not visible_debuffs
            and not other_skill_items
            and not short_cooldown_items
            and not astrology_items
            and bronntanas_hp_item is None
            and not miracle_orb_hp_items
            and rotating_laser_countdown_item is None
        ) or self.last_bounds is None:
            return
        _, _, client_width, client_height = self.last_bounds
        width = self.settings.width
        height = self.settings.toast_height
        x0 = max(0, (client_width - width) // 2)
        for index, condition in enumerate(visible):
            accent_color = (
                WARMTH_COLOR
                if condition.ccid == LIFE_TEMPERATURE_CCID
                else SUCCESS_COLOR
            )
            icon_text = "♥" if condition.ccid == LIFE_TEMPERATURE_CCID else "♫"
            appear_age = max(0, now_ms - (condition.visible_since_ms or now_ms))
            appear_progress = min(1.0, appear_age / 160.0)
            slide = int(round((1.0 - appear_progress) * -8))
            y0 = (
                self.settings.top_offset_px
                + index * (height + self.settings.gap_px)
                + slide
            )
            x1 = x0 + width
            remaining = condition.remaining_ms(now_ms)
            content_y0 = y0 + max(0, (height - TOAST_CONTENT_HEIGHT) // 2)
            content_y1 = content_y0 + TOAST_CONTENT_HEIGHT
            icon_x0 = x0
            icon_y0 = content_y0
            self.canvas.create_rectangle(
                icon_x0,
                icon_y0,
                icon_x0 + TOAST_ICON_SIZE,
                icon_y0 + TOAST_ICON_SIZE,
                fill=ICON_BACKGROUND,
                outline=CARD_BORDER,
            )
            icon_image = self._load_icon(condition.icon_path)
            if icon_image is None:
                self.canvas.create_text(
                    icon_x0 + TOAST_ICON_SIZE // 2,
                    icon_y0 + TOAST_ICON_SIZE // 2,
                    text=icon_text,
                    fill=accent_color,
                    font=("Segoe UI Symbol", 22, "bold"),
                )
            else:
                self.canvas.create_image(
                    icon_x0 + TOAST_ICON_SIZE // 2,
                    icon_y0 + TOAST_ICON_SIZE // 2,
                    image=icon_image,
                    anchor="center",
                )

            bar_x0 = icon_x0 + TOAST_ICON_SIZE + TOAST_ICON_GAP
            bar_width = max(1, x1 - bar_x0)
            self.canvas.create_rectangle(
                bar_x0,
                content_y0,
                x1,
                content_y1,
                fill=PROGRESS_TRACK_COLOR,
                outline=CARD_BORDER,
                width=1,
            )
            progress_width = int(
                math.ceil(max(0, bar_width - 2) * condition.progress(now_ms))
            )
            if progress_width > 0:
                self.canvas.create_rectangle(
                    bar_x0 + 1,
                    content_y0 + 1,
                    min(x1 - 1, bar_x0 + 1 + progress_width),
                    content_y1 - 1,
                    fill=PROGRESS_FILL_COLOR,
                    outline=PROGRESS_FILL_COLOR,
                )
            self.canvas.create_text(
                bar_x0 + 12,
                content_y0 + TOAST_CONTENT_HEIGHT // 2,
                text=condition.name,
                anchor="w",
                fill=PRIMARY_TEXT,
                font=("Microsoft YaHei UI", 12, "bold"),
            )
            self.canvas.create_text(
                x1 - 10,
                content_y0 + TOAST_CONTENT_HEIGHT // 2,
                text=format_remaining_countdown(remaining),
                anchor="e",
                fill=PRIMARY_TEXT,
                font=("Segoe UI", 18, "bold"),
            )

        self._draw_debuff_row(
            visible_debuffs,
            now_ms,
            client_width=client_width,
            client_height=client_height,
        )
        self._draw_other_skill_column(
            other_skill_items,
            client_height=client_height,
        )
        self._draw_short_cooldown_row(
            short_cooldown_items,
            client_width=client_width,
            client_height=client_height,
        )
        self._draw_astrology_hud(
            astrology_items,
            now_ms=now_ms,
            client_width=client_width,
            client_height=client_height,
        )
        self._draw_bronntanas_hp_hud(
            bronntanas_hp_item,
            client_width=client_width,
            client_height=client_height,
        )
        self._draw_miracle_orb_hp_hud(
            miracle_orb_hp_items,
            miracle_orb_hp_selected,
            client_width=client_width,
            client_height=client_height,
        )
        self._draw_rotating_laser_countdown(
            rotating_laser_countdown_item,
            now_ms=now_ms,
            client_width=client_width,
            client_height=client_height,
        )

    def _draw_rotating_laser_countdown(
        self,
        item: RotatingLaserCountdownOverlayItem | None,
        *,
        now_ms: int,
        client_width: int,
        client_height: int,
    ) -> None:
        if item is None or not item.is_visible(now_ms):
            return
        center_x = client_width // 2
        center_y = int(
            round(
                client_height
                * self.settings.rotating_laser_countdown_hud.center_y_ratio
            )
        )
        text = item.text(now_ms)
        self.canvas.create_text(
            center_x + 2,
            center_y + 2,
            text=text,
            anchor="center",
            fill="#44230d",
            font=("Segoe UI", 29, "bold"),
        )
        self.canvas.create_text(
            center_x,
            center_y,
            text=text,
            anchor="center",
            fill=ROTATING_LASER_COUNTDOWN_COLOR,
            font=("Segoe UI", 29, "bold"),
        )

    def _draw_bronntanas_hp_hud(
        self,
        item: BronntanasHpOverlayItem | None,
        *,
        client_width: int,
        client_height: int,
    ) -> None:
        if item is None:
            return
        center_x = client_width // 2
        center_y = int(
            round(
                client_height
                * self.settings.bronntanas_hp_hud.center_y_ratio
            )
        )
        x0 = max(0, center_x - BRONNTANAS_HP_CARD_WIDTH // 2)
        y0 = max(0, center_y - BRONNTANAS_HP_CARD_HEIGHT // 2)
        x1 = x0 + BRONNTANAS_HP_CARD_WIDTH
        y1 = y0 + BRONNTANAS_HP_CARD_HEIGHT
        self.canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            fill=CARD_BACKGROUND,
            outline=CARD_BORDER,
            width=2,
        )
        icon_x0 = x0 + (BRONNTANAS_HP_CARD_HEIGHT - BRONNTANAS_HP_ICON_SIZE) // 2
        icon_y0 = y0 + (BRONNTANAS_HP_CARD_HEIGHT - BRONNTANAS_HP_ICON_SIZE) // 2
        icon_image = self._load_icon(
            item.icon_path,
            max_side=BRONNTANAS_HP_ICON_SIZE,
            allow_upscale=True,
        )
        if icon_image is not None:
            self.canvas.create_image(
                icon_x0 + BRONNTANAS_HP_ICON_SIZE // 2,
                icon_y0 + BRONNTANAS_HP_ICON_SIZE // 2,
                image=icon_image,
                anchor="center",
            )
        else:
            self.canvas.create_rectangle(
                icon_x0,
                icon_y0,
                icon_x0 + BRONNTANAS_HP_ICON_SIZE,
                icon_y0 + BRONNTANAS_HP_ICON_SIZE,
                fill=ICON_BACKGROUND,
                outline=CARD_BORDER,
            )
            self.canvas.create_text(
                icon_x0 + BRONNTANAS_HP_ICON_SIZE // 2,
                icon_y0 + BRONNTANAS_HP_ICON_SIZE // 2,
                text="B2",
                fill=PRIMARY_TEXT,
                font=("Segoe UI", 18, "bold"),
            )
        number_x = icon_x0 + BRONNTANAS_HP_ICON_SIZE + 12
        self.canvas.create_text(
            number_x,
            center_y,
            text=f"{item.percent:.2f}%",
            anchor="w",
            fill=(BRONNTANAS_HP_WARNING_COLOR if item.warning else "#ffffff"),
            font=("Segoe UI", 29, "bold"),
        )
    def _draw_miracle_orb_hp_hud(
        self,
        items: tuple[MiracleOrbHpOverlayItem, ...],
        selected: MiracleOrbHpOverlayItem | None,
        *,
        client_width: int,
        client_height: int,
    ) -> None:
        if not items:
            return
        settings = self.settings.miracle_orb_hp_hud
        left_x = min(
            max(8, int(round(client_width * settings.left_x_ratio))),
            max(8, client_width - MIRACLE_ORB_LEFT_BAR_WIDTH - 8),
        )
        top_y = max(8, int(round(client_height * settings.top_y_ratio)))
        for index, item in enumerate(
            sorted(
                items,
                key=lambda value: MIRACLE_ORB_DISPLAY_ORDER.get(value.race_id, 99),
            )
        ):
            y0 = top_y + index * (
                MIRACLE_ORB_LEFT_BAR_HEIGHT + MIRACLE_ORB_LEFT_BAR_GAP
            )
            self._draw_miracle_orb_bar(
                item,
                x0=left_x,
                y0=y0,
                width=MIRACLE_ORB_LEFT_BAR_WIDTH,
                height=MIRACLE_ORB_LEFT_BAR_HEIGHT,
                label=(
                    f"{MIRACLE_ORB_SHORT_NAMES.get(item.race_id, str(item.race_id))}"
                    f"   {item.percent:.2f}%"
                ),
                font_size=13,
            )

        if selected is None:
            return
        center_x = client_width // 2
        center_y = self._responsive_center_y(
            client_height,
            low_ratio=max(
                0.1,
                settings.focus_center_y_ratio - MIRACLE_ORB_FOCUS_LOW_RES_OFFSET,
            ),
            high_ratio=settings.focus_center_y_ratio,
        )
        self._draw_miracle_orb_bar(
            selected,
            x0=max(8, center_x - MIRACLE_ORB_FOCUS_BAR_WIDTH // 2),
            y0=max(8, center_y - MIRACLE_ORB_FOCUS_BAR_HEIGHT // 2),
            width=MIRACLE_ORB_FOCUS_BAR_WIDTH,
            height=MIRACLE_ORB_FOCUS_BAR_HEIGHT,
            label=(
                f"{MIRACLE_ORB_FOCUS_NAMES.get(selected.race_id, '神迹球')}"
                f"   {selected.percent:.2f}%"
            ),
            font_size=18,
        )

    def _draw_miracle_orb_bar(
        self,
        item: MiracleOrbHpOverlayItem,
        *,
        x0: int,
        y0: int,
        width: int,
        height: int,
        label: str,
        font_size: int,
    ) -> None:
        x1 = x0 + width
        y1 = y0 + height
        fill_color = self._miracle_orb_hp_color(item.percent)
        self.canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            fill=PROGRESS_TRACK_COLOR,
            outline=CARD_BORDER,
            width=2,
        )
        fill_width = int(round(max(0, width - 4) * item.percent / 100.0))
        if fill_width > 0:
            self.canvas.create_rectangle(
                x0 + 2,
                y0 + 2,
                min(x1 - 2, x0 + 2 + fill_width),
                y1 - 2,
                fill=fill_color,
                outline=fill_color,
            )
        self.canvas.create_text(
            x0 + width // 2 + 1,
            y0 + height // 2 + 1,
            text=label,
            fill="#202020",
            font=("Microsoft YaHei UI", font_size, "bold"),
        )
        self.canvas.create_text(
            x0 + width // 2,
            y0 + height // 2,
            text=label,
            fill="#ffffff",
            font=("Microsoft YaHei UI", font_size, "bold"),
        )

    @staticmethod
    def _miracle_orb_hp_color(percent: float) -> str:
        if percent < 15.0:
            return MIRACLE_ORB_RED
        if percent < 35.0:
            return MIRACLE_ORB_ORANGE
        return MIRACLE_ORB_BLUE

    def _draw_astrology_hud(
        self,
        items: tuple[AstrologyOverlayItem, ...],
        *,
        now_ms: int,
        client_width: int,
        client_height: int,
    ) -> None:
        if not items:
            return
        settings = self.settings.astrology_hud
        center_x = client_width // 2
        center_y = int(round(client_height * settings.center_y_ratio))
        y0 = max(0, center_y - ASTROLOGY_CELL_SIZE // 2)
        pulse = (math.sin(now_ms / 240.0) + 1.0) / 2.0
        dark = tuple(int(ASTROLOGY_READY_BORDER_DARK[i : i + 2], 16) for i in (1, 3, 5))
        light = tuple(int(ASTROLOGY_READY_BORDER_LIGHT[i : i + 2], 16) for i in (1, 3, 5))
        outline = "#{:02x}{:02x}{:02x}".format(
            *(round(a + (b - a) * pulse) for a, b in zip(dark, light))
        )
        for item in items:
            item_center_x = center_x + item.slot * settings.slot_offset_px
            x0 = max(0, item_center_x - ASTROLOGY_CELL_SIZE // 2)
            x1 = x0 + ASTROLOGY_CELL_SIZE
            y1 = y0 + ASTROLOGY_CELL_SIZE
            self.canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=CARD_BACKGROUND,
                outline=outline,
                width=4,
            )
            icon_image = self._load_icon(
                item.icon_path,
                max_side=ASTROLOGY_ICON_MAX_SIDE,
                allow_upscale=True,
            )
            if icon_image is not None:
                self.canvas.create_image(
                    item_center_x,
                    center_y,
                    image=icon_image,
                    anchor="center",
                )
            else:
                self.canvas.create_text(
                    item_center_x,
                    center_y,
                    text="★",
                    fill=outline,
                    font=("Segoe UI Symbol", 52, "bold"),
                )

    def _draw_short_cooldown_row(
        self,
        items: tuple[OtherSkillOverlayItem, ...],
        *,
        client_width: int,
        client_height: int,
    ) -> None:
        if not items:
            return
        settings = self.settings.short_cooldown_hud
        total_width = (
            len(items) * DEBUFF_CELL_SIZE
            + max(0, len(items) - 1) * settings.gap_px
        )
        start_x = max(0, (client_width - total_width) // 2)
        center_y = int(round(client_height * settings.center_y_ratio))
        y0 = max(0, center_y - DEBUFF_CELL_SIZE // 2)
        for index, item in enumerate(items):
            x0 = start_x + index * (DEBUFF_CELL_SIZE + settings.gap_px)
            x1 = x0 + DEBUFF_CELL_SIZE
            y1 = y0 + DEBUFF_CELL_SIZE
            self.canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=CARD_BACKGROUND,
                outline=CARD_BORDER,
                width=1,
            )
            icon_image = self._load_icon(item.icon_path)
            if icon_image is not None:
                self.canvas.create_image(
                    x0 + DEBUFF_CELL_SIZE // 2,
                    y0 + DEBUFF_CELL_SIZE // 2,
                    image=icon_image,
                    anchor="center",
                )
            else:
                self.canvas.create_text(
                    x0 + DEBUFF_CELL_SIZE // 2,
                    y0 + DEBUFF_CELL_SIZE // 2,
                    text="!",
                    fill=PRIMARY_TEXT,
                    font=("Segoe UI", 18, "bold"),
                )

    def _draw_other_skill_column(
        self,
        items: tuple[OtherSkillOverlayItem, ...],
        *,
        client_height: int,
    ) -> None:
        if not items:
            return
        settings = self.settings.other_skill_hud
        total_height = (
            len(items) * DEBUFF_CELL_SIZE
            + max(0, len(items) - 1) * settings.gap_px
        )
        center_y = int(round(client_height * settings.center_y_ratio))
        start_y = max(0, center_y - total_height // 2)
        x0 = max(0, settings.left_offset_px)
        for index, item in enumerate(items):
            y0 = start_y + index * (DEBUFF_CELL_SIZE + settings.gap_px)
            x1 = x0 + DEBUFF_CELL_SIZE
            y1 = y0 + DEBUFF_CELL_SIZE
            self.canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=CARD_BACKGROUND,
                outline=CARD_BORDER,
                width=1,
            )
            icon_image = self._load_icon(item.icon_path)
            if icon_image is not None:
                self.canvas.create_image(
                    x0 + DEBUFF_CELL_SIZE // 2,
                    y0 + DEBUFF_CELL_SIZE // 2,
                    image=icon_image,
                    anchor="center",
                )
            else:
                self.canvas.create_text(
                    x0 + DEBUFF_CELL_SIZE // 2,
                    y0 + DEBUFF_CELL_SIZE // 2,
                    text="!",
                    fill=PRIMARY_TEXT,
                    font=("Segoe UI", 18, "bold"),
                )

    def _draw_debuff_row(
        self,
        visible: list[tuple[DebuffOverlayRequirement, str]],
        now_ms: int,
        *,
        client_width: int,
        client_height: int,
    ) -> None:
        if not visible:
            return
        total_width = (
            len(visible) * DEBUFF_CELL_SIZE
            + max(0, len(visible) - 1) * DEBUFF_GAP_PX
        )
        start_x = max(0, (client_width - total_width) // 2)
        center_y = self._responsive_debuff_center_y(client_height)
        y0 = center_y - DEBUFF_CELL_SIZE // 2
        flash_visible = now_ms % DEBUFF_FLASH_PERIOD_MS < DEBUFF_FLASH_VISIBLE_MS
        for index, (requirement, status) in enumerate(visible):
            x0 = start_x + index * (DEBUFF_CELL_SIZE + DEBUFF_GAP_PX)
            x1 = x0 + DEBUFF_CELL_SIZE
            y1 = y0 + DEBUFF_CELL_SIZE
            expiring = status == "expiring"
            outline = SUCCESS_COLOR if expiring else CARD_BORDER
            self.canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=CARD_BACKGROUND,
                outline=outline,
                width=2 if expiring else 1,
            )
            if expiring and not flash_visible:
                continue
            icon_image = self._load_icon(requirement.icon_path)
            if icon_image is not None:
                self.canvas.create_image(
                    x0 + DEBUFF_CELL_SIZE // 2,
                    y0 + DEBUFF_CELL_SIZE // 2,
                    image=icon_image,
                    anchor="center",
                )
            else:
                self.canvas.create_text(
                    x0 + DEBUFF_CELL_SIZE // 2,
                    y0 + DEBUFF_CELL_SIZE // 2,
                    text="!",
                    fill=SUCCESS_COLOR if expiring else PRIMARY_TEXT,
                    font=("Segoe UI", 18, "bold"),
                )

    @staticmethod
    def _responsive_debuff_center_y(client_height: int) -> int:
        """Keep the combat icon row clear of the game HUD at common DPIs.

        Mabinogi's bottom HUD does not keep one fixed screen-height ratio when
        Windows/game UI scaling changes.  Interpolating the anchor between a
        1080p and 4K safe area preserves the intended gap on both layouts.
        """
        return MusicOverlayApp._responsive_center_y(
            client_height,
            low_ratio=DEBUFF_CENTER_Y_RATIO_LOW_RES,
            high_ratio=DEBUFF_CENTER_Y_RATIO_HIGH_RES,
        )

    @staticmethod
    def _responsive_center_y(
        client_height: int,
        *,
        low_ratio: float,
        high_ratio: float,
    ) -> int:
        height = max(1, int(client_height))
        progress = min(
            1.0,
            max(
                0.0,
                (height - DEBUFF_RESPONSIVE_LOW_HEIGHT)
                / (DEBUFF_RESPONSIVE_HIGH_HEIGHT - DEBUFF_RESPONSIVE_LOW_HEIGHT),
            ),
        )
        ratio = float(low_ratio) + progress * (float(high_ratio) - float(low_ratio))
        return int(round(height * ratio))

    def _show_or_hide(self, should_show: bool) -> None:
        if should_show and not self.window_visible:
            self.root.deiconify()
            self._apply_readonly_window_style()
            if os.name == "nt":
                user32 = ctypes.windll.user32
                user32.SetWindowPos.argtypes = [
                    wintypes.HWND,
                    wintypes.HWND,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    wintypes.UINT,
                ]
                user32.SetWindowPos.restype = wintypes.BOOL
                user32.SetWindowPos(
                    self._native_hwnd(user32),
                    wintypes.HWND(-1),  # HWND_TOPMOST
                    0,
                    0,
                    0,
                    0,
                    0x0001 | 0x0002 | 0x0010 | 0x0040,
                )
            else:
                self.root.lift()
            self.window_visible = True
        elif not should_show and self.window_visible:
            self.root.withdraw()
            self.window_visible = False

    def _tick(self) -> None:
        if not self._drain_commands():
            self.root.destroy()
            return
        if self.demo_deadline is not None and time.monotonic() >= self.demo_deadline:
            self.root.destroy()
            return
        now_ms = int(time.time() * 1000)
        visible = self._visible_conditions(now_ms)
        visible_debuffs = self._visible_debuff_requirements(now_ms)
        other_skill_items = self.other_skill_items
        short_cooldown_items = self.short_cooldown_items
        astrology_items = self._visible_astrology_items(now_ms)
        bronntanas_hp_item = self.bronntanas_hp_item
        miracle_orb_hp_items = self.miracle_orb_hp_items
        miracle_orb_hp_selected = self.miracle_orb_hp_selected
        rotating_laser_countdown_item = self.rotating_laser_countdown_item
        if (
            bronntanas_hp_item is not None
            and not bronntanas_hp_item.is_visible(now_ms)
        ):
            self.bronntanas_hp_item = None
            bronntanas_hp_item = None
        if (
            rotating_laser_countdown_item is not None
            and not rotating_laser_countdown_item.is_visible(now_ms)
        ):
            self.rotating_laser_countdown_item = None
            rotating_laser_countdown_item = None
        bounds = (
            self._target_bounds()
            if visible
            or visible_debuffs
            or other_skill_items
            or short_cooldown_items
            or astrology_items
            or bronntanas_hp_item is not None
            or miracle_orb_hp_items
            or rotating_laser_countdown_item is not None
            else None
        )
        if bounds is None:
            self._show_or_hide(False)
        else:
            self._position_window(bounds)
            self._draw(
                visible,
                visible_debuffs,
                now_ms,
                other_skill_items,
                short_cooldown_items,
                astrology_items,
                bronntanas_hp_item,
                miracle_orb_hp_items,
                miracle_orb_hp_selected,
                rotating_laser_countdown_item,
            )
            self._show_or_hide(True)
        self.root.after(self.settings.refresh_ms, self._tick)

    def run(self) -> int:
        self.root.after(0, self._tick)
        self.root.mainloop()
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Music buff visual overlay sidecar")
    parser.add_argument("--config", default="buffwatcher.config.local.json")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Show one local five-second preview without requiring the game window.",
    )
    parser.add_argument("--demo-seconds", type=float, default=7.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config).resolve()
    settings = load_music_overlay_settings(config_path)
    if args.demo:
        settings = replace(settings, enabled=True, muted=True)
    if not settings.process_is_enabled():
        return 0
    app = MusicOverlayApp(
        settings,
        config_path=config_path,
        preview=bool(args.demo),
        demo_seconds=float(args.demo_seconds) if args.demo else 0,
    )
    if args.demo:
        app.conditions[192] = OverlayCondition(
            ccid=192,
            name="活跃曲",
            entity_name=settings.entity_name,
            end_ms=int(time.time() * 1000) + 5200,
            show_before_ms=5000,
            timing_source="demo",
        )
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())

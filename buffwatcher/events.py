from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import gzip
import json
import statistics
from typing import Any, Iterable


DOTNET_EPOCH_MS = 62_135_596_800_000
DEFAULT_TZ_OFFSET_HOURS = 8


@dataclass
class CcSummary:
    ccid: int
    apply_count: int = 0
    remove_count: int = 0
    extra_keys: Counter[tuple[str, ...]] = field(default_factory=Counter)
    durations_ms: Counter[int] = field(default_factory=Counter)
    remaining_seconds: list[float] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)

    @property
    def median_remaining(self) -> float | None:
        if not self.remaining_seconds:
            return None
        return float(statistics.median(self.remaining_seconds))

    @property
    def min_remaining(self) -> float | None:
        if not self.remaining_seconds:
            return None
        return min(self.remaining_seconds)

    @property
    def max_remaining(self) -> float | None:
        if not self.remaining_seconds:
            return None
        return max(self.remaining_seconds)


def latest_raw_file(histories_dir: str | Path) -> Path:
    root = Path(histories_dir)
    files = list(root.glob("*raw.ndjson.gz"))
    if not files:
        raise FileNotFoundError(f"No *raw.ndjson.gz files found in {root}")
    return max(files, key=lambda path: path.stat().st_mtime)


def iter_raw_events(path: str | Path) -> Iterable[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as stream:
        for line_number, line in enumerate(stream, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
            if isinstance(event, dict):
                yield event


def sbt_to_unix_ms(sbt: int | float, tz_offset_hours: int = DEFAULT_TZ_OFFSET_HOURS) -> int:
    return int(sbt) - DOTNET_EPOCH_MS - (tz_offset_hours * 60 * 60 * 1000)


def event_remaining_seconds(
    event: dict[str, Any], tz_offset_hours: int = DEFAULT_TZ_OFFSET_HOURS
) -> float | None:
    extra = event.get("ExtraData") or {}
    if "SBT" not in extra or "At" not in event:
        return None
    return (sbt_to_unix_ms(extra["SBT"], tz_offset_hours) - int(event["At"])) / 1000


def summarize_events(
    events: Iterable[dict[str, Any]],
    *,
    tz_offset_hours: int = DEFAULT_TZ_OFFSET_HOURS,
    max_examples_per_cc: int = 3,
) -> dict[int, CcSummary]:
    summaries: dict[int, CcSummary] = defaultdict(lambda: CcSummary(ccid=-1))

    for event in events:
        event_id = event.get("EventId")
        ccid = event.get("CCId")
        if ccid is None:
            continue

        ccid = int(ccid)
        summary = summaries[ccid]
        summary.ccid = ccid

        if event_id == 4:
            summary.apply_count += 1
            extra = event.get("ExtraData") or {}
            summary.extra_keys[tuple(sorted(extra.keys()))] += 1

            if isinstance(extra.get("SDUR"), int):
                summary.durations_ms[int(extra["SDUR"])] += 1
            elif isinstance(extra.get("DURATION"), int):
                summary.durations_ms[int(extra["DURATION"])] += 1
            elif isinstance(extra.get("DURA"), int):
                summary.durations_ms[int(extra["DURA"])] += 1

            remaining = event_remaining_seconds(event, tz_offset_hours)
            if remaining is not None:
                summary.remaining_seconds.append(remaining)

            if len(summary.examples) < max_examples_per_cc:
                summary.examples.append(compact_event(event, tz_offset_hours))

        elif event_id == 5:
            summary.remove_count += 1
            if len(summary.examples) < max_examples_per_cc:
                summary.examples.append(compact_event(event, tz_offset_hours))

    return dict(summaries)


def compact_event(event: dict[str, Any], tz_offset_hours: int = DEFAULT_TZ_OFFSET_HOURS) -> dict[str, Any]:
    compact = {
        "EventId": event.get("EventId"),
        "At": event.get("At"),
        "Id": event.get("Id"),
        "CCId": event.get("CCId"),
    }
    if "AttackerId" in event:
        compact["AttackerId"] = event.get("AttackerId")
    if "DisableAt" in event:
        compact["DisableAt"] = event.get("DisableAt")
    remaining = event_remaining_seconds(event, tz_offset_hours)
    if remaining is not None:
        compact["RemainingSeconds"] = round(remaining, 3)
    if event.get("ExtraData"):
        compact["ExtraData"] = event["ExtraData"]
    return compact


def iter_cc_events(
    events: Iterable[dict[str, Any]],
    ccid: int,
    *,
    tz_offset_hours: int = DEFAULT_TZ_OFFSET_HOURS,
) -> Iterable[dict[str, Any]]:
    for event in events:
        if event.get("CCId") == ccid:
            yield compact_event(event, tz_offset_hours)


def format_seconds(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}s"

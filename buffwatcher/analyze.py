from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .events import (
    DEFAULT_TZ_OFFSET_HOURS,
    format_seconds,
    iter_cc_events,
    iter_raw_events,
    latest_raw_file,
    summarize_events,
)


def resolve_raw_path(args: argparse.Namespace) -> Path:
    if args.file:
        return Path(args.file)
    if args.latest:
        return latest_raw_file(args.histories)
    raise SystemExit("Provide --file or --latest with --histories.")


def cmd_summary(args: argparse.Namespace) -> int:
    raw_path = resolve_raw_path(args)
    summaries = summarize_events(
        iter_raw_events(raw_path),
        tz_offset_hours=args.tz_offset_hours,
        max_examples_per_cc=1,
    )
    rows = sorted(summaries.values(), key=lambda s: s.apply_count, reverse=True)

    print(f"file: {raw_path}")
    print(
        "CCId   apply  remove  remaining(min/median/max)    durations_ms        top_extra_keys"
    )
    print("-" * 110)
    for summary in rows[: args.limit]:
        keys = summary.extra_keys.most_common(1)
        top_keys = ",".join(keys[0][0]) if keys else ""
        durations = ",".join(
            f"{duration}:{count}" for duration, count in summary.durations_ms.most_common(3)
        )
        print(
            f"{summary.ccid:<6} "
            f"{summary.apply_count:<6} "
            f"{summary.remove_count:<7} "
            f"{format_seconds(summary.min_remaining):>7}/"
            f"{format_seconds(summary.median_remaining):>7}/"
            f"{format_seconds(summary.max_remaining):>7}    "
            f"{durations[:18]:<18} "
            f"{top_keys[:45]}"
        )
    return 0


def cmd_cc(args: argparse.Namespace) -> int:
    raw_path = resolve_raw_path(args)
    print(f"file: {raw_path}")
    count = 0
    for event in iter_cc_events(
        iter_raw_events(raw_path),
        args.ccid,
        tz_offset_hours=args.tz_offset_hours,
    ):
        print(json.dumps(event, ensure_ascii=False))
        count += 1
        if count >= args.limit:
            break
    print(f"shown: {count}")
    return 0


def cmd_export_config(args: argparse.Namespace) -> int:
    raw_path = resolve_raw_path(args)
    summaries = summarize_events(
        iter_raw_events(raw_path),
        tz_offset_hours=args.tz_offset_hours,
        max_examples_per_cc=1,
    )
    candidates: list[dict[str, Any]] = []
    for summary in sorted(summaries.values(), key=lambda s: s.apply_count, reverse=True):
        if not summary.remaining_seconds:
            continue
        max_remaining = summary.max_remaining
        if max_remaining is None or max_remaining < args.min_duration_seconds:
            continue
        candidates.append(
            {
                "name": f"cc_{summary.ccid}",
                "ccid": summary.ccid,
                "enabled": False,
                "warn_seconds": args.warn_seconds,
                "critical_seconds": args.critical_seconds,
                "observed": {
                    "apply_count": summary.apply_count,
                    "remove_count": summary.remove_count,
                    "min_remaining_seconds": round(summary.min_remaining or 0, 3),
                    "median_remaining_seconds": round(summary.median_remaining or 0, 3),
                    "max_remaining_seconds": round(max_remaining, 3),
                    "durations_ms": dict(summary.durations_ms.most_common(5)),
                    "top_extra_keys": [
                        list(keys) for keys, _count in summary.extra_keys.most_common(3)
                    ],
                },
            }
        )

    payload = {
        "source_file": str(raw_path),
        "tz_offset_hours": args.tz_offset_hours,
        "buffs": candidates[: args.limit],
    }
    output = Path(args.output)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote: {output}")
    print(f"buff candidates: {len(payload['buffs'])}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze MicoPunch raw event streams.")
    parser.add_argument(
        "--tz-offset-hours",
        type=int,
        default=DEFAULT_TZ_OFFSET_HOURS,
        help="Timezone offset used by SBT conversion. Default: 8.",
    )
    subparsers = parser.add_subparsers(required=True)

    def add_source_args(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--histories", default=r"C:\Users\rw594\Desktop\MicoPunch\histories")
        subparser.add_argument("--file")
        subparser.add_argument("--latest", action="store_true")

    summary = subparsers.add_parser("summary", help="Show CCId summary.")
    add_source_args(summary)
    summary.add_argument("--limit", type=int, default=50)
    summary.set_defaults(func=cmd_summary)

    cc = subparsers.add_parser("cc", help="Show events for one CCId.")
    add_source_args(cc)
    cc.add_argument("--ccid", type=int, required=True)
    cc.add_argument("--limit", type=int, default=20)
    cc.set_defaults(func=cmd_cc)

    export_config = subparsers.add_parser(
        "export-config", help="Export candidate buff config from observed CCIds."
    )
    add_source_args(export_config)
    export_config.add_argument("--output", default="buffwatcher.config.local.json")
    export_config.add_argument("--limit", type=int, default=80)
    export_config.add_argument("--min-duration-seconds", type=float, default=30)
    export_config.add_argument("--warn-seconds", type=int, default=60)
    export_config.add_argument("--critical-seconds", type=int, default=15)
    export_config.set_defaults(func=cmd_export_config)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

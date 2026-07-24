#!/usr/bin/env python3
"""Analyze consecutive DSA-TOPK records in a mixed vLLM log file.

Records are compared only within the same worker, layer, request, and row.
The pos_head repeat rate is defined as:

    len(current_positions & previous_positions) / len(current_positions)

This measures how much of the current logged selection was also present in the
previous logged selection. It is a one-step reuse rate, not necessarily the
actual cache hit rate of a cache that retains more than one decode step.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Iterable, Sequence


DSA_TOPK_MARKER = "[DSA-TOPK]"
DSA_TOPK_RE = re.compile(
    r"\[DSA-TOPK\]\s+"
    r"layer=(?P<layer>\S+)\s+"
    r"row=(?P<row>-?\d+)\s+"
    r"req=(?P<req>\S+)\s+"
    r"n_valid=(?P<n_valid>\d+)\s+"
    r"pos_head=\[(?P<positions>[^\]]*)\]"
)
PID_RE = re.compile(r"\bpid\s*[=:]\s*(?P<pid>\d+)\b", re.IGNORECASE)
WORKER_RE = re.compile(
    r"\b(?P<worker>(?:Worker|EngineCore)(?:_[A-Za-z0-9]+)+)\b",
    re.IGNORECASE,
)
RANK_RE = re.compile(
    r"\b(?P<kind>tp[_ -]?rank|local[_ -]?rank|rank)\s*[=:]?\s*(?P<rank>\d+)\b",
    re.IGNORECASE,
)
INTEGER_RE = re.compile(r"-?\d+")


@dataclass(frozen=True)
class TopKRecord:
    line_number: int
    source: str
    layer: str
    row: int
    request_id: str
    n_valid: int
    positions: frozenset[int]
    raw_position_count: int


@dataclass(frozen=True)
class PairMetric:
    source: str
    layer: str
    row: int
    request_id: str
    previous_line: int
    current_line: int
    previous_n_valid: int
    current_n_valid: int
    abs_n_valid_change: int
    previous_position_count: int
    current_position_count: int
    intersection_count: int
    repeat_rate: float | None


@dataclass(frozen=True)
class ParseResult:
    records: list[TopKRecord]
    marker_lines: int
    malformed_lines: list[int]


def extract_source(prefix: str) -> str:
    """Return a stable worker identity from the log prefix when available."""
    worker_match = WORKER_RE.search(prefix)
    pid_match = PID_RE.search(prefix)
    rank_match = RANK_RE.search(prefix)

    parts: list[str] = []
    if worker_match is not None:
        parts.append(worker_match.group("worker"))
    elif rank_match is not None:
        rank_kind = re.sub(r"[ _-]+", "_", rank_match.group("kind").lower())
        parts.append(f"{rank_kind}={rank_match.group('rank')}")

    if pid_match is not None:
        parts.append(f"pid={pid_match.group('pid')}")

    return "/".join(parts) if parts else "unknown"


def parse_log(lines: Iterable[str]) -> ParseResult:
    records: list[TopKRecord] = []
    malformed_lines: list[int] = []
    marker_lines = 0

    for line_number, line in enumerate(lines, start=1):
        marker_index = line.find(DSA_TOPK_MARKER)
        if marker_index < 0:
            continue

        marker_lines += 1
        match = DSA_TOPK_RE.search(line, marker_index)
        if match is None:
            malformed_lines.append(line_number)
            continue

        raw_positions = [int(value) for value in INTEGER_RE.findall(match.group("positions"))]
        positions = frozenset(value for value in raw_positions if value >= 0)
        records.append(
            TopKRecord(
                line_number=line_number,
                source=extract_source(line[:marker_index]),
                layer=match.group("layer"),
                row=int(match.group("row")),
                request_id=match.group("req"),
                n_valid=int(match.group("n_valid")),
                positions=positions,
                raw_position_count=len(raw_positions),
            )
        )

    return ParseResult(
        records=records,
        marker_lines=marker_lines,
        malformed_lines=malformed_lines,
    )


def build_pair_metrics(
    records: Sequence[TopKRecord],
    *,
    ignore_row: bool,
) -> tuple[list[PairMetric], int]:
    previous_by_key: dict[tuple[object, ...], TopKRecord] = {}
    pairs: list[PairMetric] = []
    skipped_unknown_requests = 0

    for current in records:
        if current.request_id == "?":
            skipped_unknown_requests += 1
            continue

        key: tuple[object, ...]
        if ignore_row:
            key = (current.source, current.layer, current.request_id)
        else:
            key = (current.source, current.layer, current.request_id, current.row)

        previous = previous_by_key.get(key)
        previous_by_key[key] = current
        if previous is None:
            continue

        intersection_count = len(current.positions & previous.positions)
        repeat_rate = (
            intersection_count / len(current.positions)
            if current.positions
            else None
        )
        pairs.append(
            PairMetric(
                source=current.source,
                layer=current.layer,
                row=current.row,
                request_id=current.request_id,
                previous_line=previous.line_number,
                current_line=current.line_number,
                previous_n_valid=previous.n_valid,
                current_n_valid=current.n_valid,
                abs_n_valid_change=abs(current.n_valid - previous.n_valid),
                previous_position_count=len(previous.positions),
                current_position_count=len(current.positions),
                intersection_count=intersection_count,
                repeat_rate=repeat_rate,
            )
        )

    return pairs, skipped_unknown_requests


def natural_sort_key(value: str) -> tuple[object, ...]:
    return tuple(
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", value)
    )


def average_metrics(pairs: Sequence[PairMetric]) -> tuple[float, float | None]:
    avg_n_valid_change = fmean(pair.abs_n_valid_change for pair in pairs)
    valid_rates = [pair.repeat_rate for pair in pairs if pair.repeat_rate is not None]
    avg_repeat_rate = fmean(valid_rates) if valid_rates else None
    return avg_n_valid_change, avg_repeat_rate


def format_rate(rate: float | None) -> str:
    return "N/A" if rate is None else f"{rate * 100:.4f}%"


def print_layer_table(pairs: Sequence[PairMetric]) -> None:
    pairs_by_layer: dict[str, list[PairMetric]] = defaultdict(list)
    for pair in pairs:
        pairs_by_layer[pair.layer].append(pair)

    rows: list[tuple[str, str, str, str]] = []
    for layer in sorted(pairs_by_layer, key=natural_sort_key):
        layer_pairs = pairs_by_layer[layer]
        avg_change, avg_rate = average_metrics(layer_pairs)
        rows.append(
            (
                layer,
                str(len(layer_pairs)),
                f"{avg_change:.6f}",
                format_rate(avg_rate),
            )
        )

    headers = ("layer", "pairs", "avg_abs_n_valid_change", "avg_pos_head_repeat_rate")
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    print("\nPer-layer averages:")
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def write_csv(path: Path, pairs: Sequence[PairMetric]) -> None:
    fieldnames = [
        "source",
        "layer",
        "row",
        "request_id",
        "previous_line",
        "current_line",
        "previous_n_valid",
        "current_n_valid",
        "abs_n_valid_change",
        "previous_position_count",
        "current_position_count",
        "intersection_count",
        "pos_head_repeat_rate",
    ]
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for pair in pairs:
            writer.writerow(
                {
                    "source": pair.source,
                    "layer": pair.layer,
                    "row": pair.row,
                    "request_id": pair.request_id,
                    "previous_line": pair.previous_line,
                    "current_line": pair.current_line,
                    "previous_n_valid": pair.previous_n_valid,
                    "current_n_valid": pair.current_n_valid,
                    "abs_n_valid_change": pair.abs_n_valid_change,
                    "previous_position_count": pair.previous_position_count,
                    "current_position_count": pair.current_position_count,
                    "intersection_count": pair.intersection_count,
                    "pos_head_repeat_rate": (
                        "" if pair.repeat_rate is None else f"{pair.repeat_rate:.10f}"
                    ),
                }
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare consecutive DSA-TOPK records for the same worker, layer, "
            "request, and row. Unrelated log lines are ignored."
        )
    )
    parser.add_argument("log_file", type=Path, help="Mixed text log file to analyze")
    parser.add_argument(
        "--csv",
        type=Path,
        help="Optional path for per-comparison CSV output",
    )
    parser.add_argument(
        "--ignore-row",
        action="store_true",
        help=(
            "Group by worker/layer/request only. Use this when a normal decode "
            "request can move between batch rows; do not use it for MTP logs "
            "where one request has multiple rows in one step."
        ),
    )
    parser.add_argument(
        "--no-per-layer",
        action="store_true",
        help="Do not print the per-layer averages table",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with args.log_file.open("r", encoding="utf-8", errors="replace") as log_file:
            parsed = parse_log(log_file)
    except OSError as exc:
        print(f"error: cannot read {args.log_file}: {exc}", file=sys.stderr)
        return 2

    if not parsed.records:
        print(
            f"error: no parseable {DSA_TOPK_MARKER} records found in {args.log_file}",
            file=sys.stderr,
        )
        if parsed.malformed_lines:
            print(
                "malformed marker lines: "
                + ", ".join(str(line) for line in parsed.malformed_lines[:20]),
                file=sys.stderr,
            )
        return 1

    pairs, skipped_unknown_requests = build_pair_metrics(
        parsed.records,
        ignore_row=args.ignore_row,
    )

    print(f"Log file: {args.log_file}")
    print(f"DSA-TOPK marker lines: {parsed.marker_lines}")
    print(f"Parsed records: {len(parsed.records)}")
    print(f"Malformed marker lines: {len(parsed.malformed_lines)}")
    print(f"Skipped req=? records: {skipped_unknown_requests}")
    print(f"Detected sources: {len({record.source for record in parsed.records})}")
    print(f"Comparison pairs: {len(pairs)}")
    print(
        "Repeat-rate formula: "
        "|current_pos_head intersect previous_pos_head| / |current_pos_head|"
    )

    unknown_source_records = sum(
        1 for record in parsed.records if record.source == "unknown"
    )
    if unknown_source_records:
        print(
            "WARNING: no worker/rank identity was found for "
            f"{unknown_source_records}/{len(parsed.records)} records. If multiple "
            "TP workers are interleaved, their records cannot be separated and "
            "the repeat rate may be incorrect."
        )

    incomplete_records = sum(
        1 for record in parsed.records if len(record.positions) < record.n_valid
    )
    if incomplete_records:
        avg_logged = fmean(len(record.positions) for record in parsed.records)
        avg_valid = fmean(record.n_valid for record in parsed.records)
        coverage = avg_logged / avg_valid if avg_valid else 0.0
        print(
            "WARNING: pos_head is only a subset for "
            f"{incomplete_records}/{len(parsed.records)} records "
            f"(average unique logged positions={avg_logged:.2f}, "
            f"average n_valid={avg_valid:.2f}, coverage={coverage * 100:.4f}%)."
        )
        print(
            "The repeat rate therefore describes only the logged pos_head subset, "
            "not all selected tokens."
        )

    if not pairs:
        print(
            "error: no consecutive records share the same comparison key; "
            "check worker/layer/request/row values or try --ignore-row",
            file=sys.stderr,
        )
        return 1

    avg_change, avg_rate = average_metrics(pairs)
    print("\nOverall averages:")
    print(f"  avg_abs_n_valid_change: {avg_change:.6f}")
    print(f"  avg_pos_head_repeat_rate: {format_rate(avg_rate)}")

    if not args.no_per_layer:
        print_layer_table(pairs)

    if args.csv is not None:
        try:
            write_csv(args.csv, pairs)
        except OSError as exc:
            print(f"error: cannot write {args.csv}: {exc}", file=sys.stderr)
            return 2
        print(f"\nPair details written to: {args.csv}")

    if parsed.malformed_lines:
        shown = ", ".join(str(line) for line in parsed.malformed_lines[:20])
        suffix = " ..." if len(parsed.malformed_lines) > 20 else ""
        print(f"Malformed marker line numbers: {shown}{suffix}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

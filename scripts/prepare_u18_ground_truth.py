"""Convert U18 Bepro event XML into the project's Pass/Drive GT contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


GT_FIELDS = (
    "event_id",
    "video_id",
    "match_id",
    "half",
    "source_time_sec",
    "source_timecode",
    "match_time_sec",
    "match_timecode",
    "label",
    "mapping_status",
    "bepro_code",
    "team",
    "player",
    "shirt_number",
    "x",
    "y",
    "to_x",
    "to_y",
    "distance_band",
    "pass_result",
    "annotation_window_start_sec",
    "annotation_window_end_sec",
    "evaluation_status",
    "exclusion_reason",
    "source_xml",
    "source_event_id",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/u18_gt.yaml"))
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--drive-audit-size", type=int, default=50)
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("U18 配置缺失或 schema_version 不受支持")
    if not isinstance(data.get("videos"), list) or len(data["videos"]) != 4:
        raise ValueError("U18 配置必须恰好声明四个半场视频")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def format_timecode(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def exactly_one(paths: Iterable[Path], description: str) -> Path:
    items = list(paths)
    if len(items) != 1:
        raise FileNotFoundError(f"{description} 应恰好匹配一个路径，实际为 {len(items)}：{items}")
    return items[0]


def optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"非有限数值：{value}")
    return result


def labels_for(instance: ET.Element) -> dict[str, str]:
    labels: dict[str, str] = {}
    for label in instance.findall("label"):
        group = label.findtext("group")
        text = label.findtext("text")
        if group and text is not None:
            labels[group] = text
    return labels


def evaluation_status(source_time: float, duration: float, guard: float) -> tuple[str, str]:
    if source_time < 0 or source_time > duration:
        return "excluded", "outside_video"
    if source_time < guard:
        return "excluded", "model_context_guard_start"
    if source_time > duration - guard:
        return "excluded", "model_context_guard_end"
    return "evaluable", ""


def distance_band(y: float | None, spatial: dict[str, Any]) -> str:
    if y is None:
        return "unknown"
    if not 0.0 <= y <= 1.0:
        raise ValueError(f"Bepro Y 超出 [0, 1]：{y}")
    if y < float(spatial["near_max_exclusive"]):
        return "near"
    if y >= float(spatial["far_min_inclusive"]):
        return "far"
    return "mid"


def parse_event_xml(
    xml_path: Path,
    source_root: Path,
    video: dict[str, Any],
    mapping: dict[str, dict[str, str]],
    spatial: dict[str, Any],
    guard: float,
) -> list[dict[str, Any]]:
    root = ET.parse(xml_path).getroot()
    events: list[dict[str, Any]] = []
    for instance in root.findall("./ALL_INSTANCES/instance"):
        code = (instance.findtext("code") or "").strip()
        if code not in mapping:
            continue
        labels = labels_for(instance)
        if "MATCH TIME" not in labels:
            raise ValueError(f"{xml_path.name} 的 {code} 事件缺少 MATCH TIME")
        match_time = float(labels["MATCH TIME"])
        source_time = round(match_time - float(video["match_time_offset_sec"]), 6)
        status, reason = evaluation_status(
            source_time, float(video["duration_sec"]), guard
        )
        x = optional_float(labels.get("X"))
        y = optional_float(labels.get("Y"))
        event = {
            "event_id": "",
            "video_id": video["video_id"],
            "match_id": video["match_id"],
            "half": int(video["half"]),
            "source_time_sec": source_time,
            "source_timecode": format_timecode(max(source_time, 0.0)),
            "match_time_sec": match_time,
            "match_timecode": format_timecode(match_time),
            "label": mapping[code]["label"],
            "mapping_status": mapping[code]["status"],
            "bepro_code": code,
            "team": labels.get("TEAM", ""),
            "player": labels.get("PLAYER", ""),
            "shirt_number": labels.get("SHIRT NUMBER", ""),
            "x": x,
            "y": y,
            "to_x": optional_float(labels.get("TO X")),
            "to_y": optional_float(labels.get("TO Y")),
            "distance_band": distance_band(y, spatial),
            "pass_result": labels.get("パス 結果", ""),
            "annotation_window_start_sec": optional_float(instance.findtext("start")),
            "annotation_window_end_sec": optional_float(instance.findtext("end")),
            "evaluation_status": status,
            "exclusion_reason": reason,
            "source_xml": xml_path.relative_to(source_root).as_posix(),
            "source_event_id": instance.findtext("ID") or "",
        }
        events.append(event)
    return events


def write_csv(path: Path, events: list[dict[str, Any]], fields: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(events)


def evenly_spaced(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if count >= len(items):
        return list(items)
    if count <= 0:
        return []
    indexes = [round(index * (len(items) - 1) / (count - 1)) for index in range(count)] if count > 1 else [len(items) // 2]
    return [items[index] for index in indexes]


def drive_audit_sample(events: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    drives = [event for event in events if event["label"] == "Drive"]
    video_ids = sorted({event["video_id"] for event in drives})
    base, extra = divmod(min(count, len(drives)), len(video_ids))
    selected: list[dict[str, Any]] = []
    for index, video_id in enumerate(video_ids):
        group = [event for event in drives if event["video_id"] == video_id]
        group.sort(key=lambda event: (event["y"] is None, event["y"] or 0.0, event["source_time_sec"]))
        selected.extend(evenly_spaced(group, base + (index < extra)))
    selected.sort(key=lambda event: (event["video_id"], event["source_time_sec"]))
    result: list[dict[str, Any]] = []
    for event in selected:
        row = dict(event)
        row.update(
            {
                "review_mapping": "unreviewed",
                "review_observation": "",
                "review_comment": "",
            }
        )
        result.append(row)
    return result


def count_by_label(events: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(event["label"] for event in events)
    return {label: counts.get(label, 0) for label in ("Pass", "Drive")}


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    source_root = (args.source_root or Path(config["source_root"])).resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"U18 源目录不存在：{source_root}")
    if args.output_dir.exists():
        raise FileExistsError(f"拒绝覆盖既有输出目录：{args.output_dir}")
    if args.drive_audit_size < 1:
        raise ValueError("--drive-audit-size 必须大于 0")

    mapping = config["event_mapping"]
    spatial = config["spatial_bands"]
    guard = float(config["model_context_guard_sec"])
    all_events: list[dict[str, Any]] = []
    source_inventory: list[dict[str, Any]] = []
    for video in config["videos"]:
        video_path = exactly_one(source_root.glob(video["video_glob"]), video["video_id"] + " 视频")
        if video_path.name != video["video_basename"]:
            raise ValueError(f"视频 basename 与配置不一致：{video_path.name}")
        if video_path.stat().st_size != int(video["video_size_bytes"]):
            raise ValueError(f"视频大小与配置不一致：{video_path}")
        actual_hash = sha256_file(video_path)
        if actual_hash != video["video_sha256"]:
            raise ValueError(f"视频 SHA-256 与配置不一致：{video_path}")

        xml_dir = exactly_one(
            (path for path in source_root.glob(video["event_xml_directory_glob"]) if path.is_dir()),
            video["video_id"] + " XML 目录",
        )
        xml_paths = sorted(xml_dir.glob(video["event_xml_glob"]))
        if len(xml_paths) != 2:
            raise FileNotFoundError(
                f"{video['video_id']} 应有两份球队事件 XML，实际为 {len(xml_paths)}"
            )
        for xml_path in xml_paths:
            all_events.extend(parse_event_xml(xml_path, source_root, video, mapping, spatial, guard))
        source_inventory.append(
            {
                "video_id": video["video_id"],
                "video_path": str(video_path),
                "video_size_bytes": video_path.stat().st_size,
                "video_sha256": actual_hash,
                "duration_sec": float(video["duration_sec"]),
                "event_xml": [
                    {
                        "path": path.relative_to(source_root).as_posix(),
                        "sha256": sha256_file(path),
                    }
                    for path in xml_paths
                ],
            }
        )

    all_events.sort(
        key=lambda event: (event["video_id"], event["source_time_sec"], event["label"], event["source_xml"], event["source_event_id"])
    )
    for index, event in enumerate(all_events, start=1):
        event["event_id"] = f"u18-gt-{index:06d}"
    evaluable = [event for event in all_events if event["evaluation_status"] == "evaluable"]

    actual_all = count_by_label(all_events)
    actual_evaluable = count_by_label(evaluable)
    expected = config.get("expected_counts", {})
    if actual_all != expected.get("all") or actual_evaluable != expected.get("evaluable"):
        raise ValueError(
            f"GT 数量与配置不一致：all={actual_all}, evaluable={actual_evaluable}, expected={expected}"
        )

    args.output_dir.mkdir(parents=True)
    (args.output_dir / "gt_events_all.json").write_text(
        json.dumps(all_events, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(args.output_dir / "gt_events_all.csv", all_events, GT_FIELDS)
    (args.output_dir / "gt_events_evaluable.json").write_text(
        json.dumps(evaluable, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(args.output_dir / "gt_events_evaluable.csv", evaluable, GT_FIELDS)

    audit = drive_audit_sample(evaluable, args.drive_audit_size)
    audit_fields = list(GT_FIELDS) + ["review_mapping", "review_observation", "review_comment"]
    write_csv(args.output_dir / "drive_mapping_audit.csv", audit, audit_fields)

    excluded = Counter(event["exclusion_reason"] for event in all_events if event["exclusion_reason"])
    manifest = {
        "schema_version": 1,
        "dataset_id": config["dataset_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(args.config.resolve()),
        "config_sha256": sha256_file(args.config),
        "source_root": str(source_root),
        "event_time_source": "MATCH TIME; second half subtracts 2700 seconds",
        "model_context_guard_sec": guard,
        "event_mapping": mapping,
        "spatial_bands": spatial,
        "counts_all": actual_all,
        "counts_evaluable": actual_evaluable,
        "excluded_by_reason": dict(sorted(excluded.items())),
        "drive_mapping_audit_count": len(audit),
        "source_inventory": source_inventory,
        "outputs": {
            "all_json": "gt_events_all.json",
            "all_csv": "gt_events_all.csv",
            "evaluable_json": "gt_events_evaluable.json",
            "evaluable_csv": "gt_events_evaluable.csv",
            "drive_mapping_audit_csv": "drive_mapping_audit.csv",
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: manifest[key] for key in ("counts_all", "counts_evaluable", "excluded_by_reason")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

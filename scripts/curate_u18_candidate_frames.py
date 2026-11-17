"""Build a reviewable, diverse U18 pass/reception frame shortlist."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import yaml


FIELDS = (
    "candidate_id", "event_id", "video_id", "match_id", "half", "action",
    "bepro_code", "source_time_sec", "source_timecode", "match_time_sec",
    "match_timecode", "frame_index", "frame_number", "frame_time_sec",
    "frame_offset_from_event_sec", "source_fps", "team", "player", "x", "y",
    "distance_band", "field_zone", "time_bin", "nearest_scene_hash_distance",
    "source_video", "frame_image", "preview_image", "review_status",
    "chosen_frame_index", "review_note",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/u18_gt.yaml"))
    parser.add_argument(
        "--ground-truth", type=Path,
        default=Path("artifacts/u18_ground_truth/20260930_u18_bepro_gt_spatial_v2/gt_events_evaluable.csv"),
    )
    parser.add_argument(
        "--known-review", type=Path,
        default=Path("artifacts/u18_ground_truth/20260930_u18_bepro_gt_spatial_v2/drive_mapping_audit.csv"),
    )
    parser.add_argument("--extra-exclusions", type=Path, help="CSV with event_id or video_id,source_time_sec")
    parser.add_argument("--source-root", type=Path, default=Path("U18"))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--per-match", type=int, default=60)
    parser.add_argument("--second-half-fraction", type=float, default=0.8)
    parser.add_argument("--min-gap-sec", type=float, default=15.0)
    parser.add_argument("--known-gap-sec", type=float, default=5.0)
    parser.add_argument("--max-similar-hamming", type=int, default=4)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def action_for(event: dict[str, str]) -> str:
    # The raw Bepro code is authoritative for this visual task. Drive is only
    # a provisional evaluation proxy and must not be presented as a trap label.
    codes = {"パス": "Pass", "パス(受け手)": "Reception candidate"}
    return codes.get(event["bepro_code"], "")


def field_zone(event: dict[str, str]) -> str:
    try:
        x, y = float(event["x"]), float(event["y"])
    except (TypeError, ValueError):
        return "unknown"
    if not (0 <= x <= 1 and 0 <= y <= 1):
        return "unknown"
    return f"x{min(2, int(x * 3))}_y{min(2, int(y * 3))}"


def exclusion_index(rows: list[dict[str, str]]) -> tuple[set[str], dict[str, list[float]]]:
    event_ids: set[str] = set()
    times: dict[str, list[float]] = {}
    for row in rows:
        if row.get("event_id"):
            event_ids.add(row["event_id"])
        if row.get("video_id") and row.get("source_time_sec"):
            times.setdefault(row["video_id"], []).append(float(row["source_time_sec"]))
    return event_ids, times


def is_near_exclusion(
    event: dict[str, str], event_ids: set[str], times: dict[str, list[float]], gap: float
) -> bool:
    return event["event_id"] in event_ids or any(
        abs(float(event["source_time_sec"]) - time) < gap
        for time in times.get(event["video_id"], [])
    )


def allocation(per_match: int, second_half_fraction: float) -> dict[tuple[int, str], int]:
    if per_match < 4 or per_match % 2:
        raise ValueError("--per-match must be even and at least 4")
    if not 0.5 <= second_half_fraction <= 1:
        raise ValueError("--second-half-fraction must be in [0.5, 1]")
    per_action = per_match // 2
    h2 = round(per_action * second_half_fraction)
    return {
        (1, "Pass"): per_action - h2,
        (1, "Reception candidate"): per_action - h2,
        (2, "Pass"): h2,
        (2, "Reception candidate"): h2,
    }


def scene_hash(frame: Any) -> int:
    # Focus on the pitch. Scoreboard and masked Bepro text are excluded.
    gray = cv2.cvtColor(frame[80:925], cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    result = 0
    for bit in (small[:, 1:] > small[:, :-1]).flat:
        result = (result << 1) | int(bit)
    return result


def read_frame(capture: Any, index: int) -> Any:
    if not capture.set(cv2.CAP_PROP_POS_FRAMES, index):
        raise RuntimeError(f"cannot seek to frame {index}")
    ok, frame = capture.read()
    actual_next = capture.get(cv2.CAP_PROP_POS_FRAMES)
    if not ok or frame is None or abs(actual_next - (index + 1)) > 0.5:
        raise RuntimeError(f"frame decode/index mismatch at {index}: next={actual_next}")
    return frame


def mask_frame(frame: Any, rect: list[int]) -> Any:
    result = frame.copy()
    x, y, width, height = rect
    result[y:y + height, x:x + width] = 0
    return result


def write_preview(
    capture: Any, center_index: int, center: Any, rect: list[int], fps: float, path: Path
) -> None:
    delta = round(0.3 * fps)
    frames = [read_frame(capture, center_index - delta), center, read_frame(capture, center_index + delta)]
    panels = []
    for image, label in zip(frames, ("-0.3 s", "event frame", "+0.3 s")):
        masked = mask_frame(image, rect)
        panel = cv2.resize(masked, (480, 270), interpolation=cv2.INTER_AREA)
        cv2.rectangle(panel, (0, 0), (120, 28), (20, 20, 20), -1)
        cv2.putText(panel, label, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        panels.append(panel)
    strip = cv2.hconcat(panels)
    if not cv2.imwrite(str(path), strip, [cv2.IMWRITE_JPEG_QUALITY, 85]):
        raise OSError(f"cannot write {path}")


def score_event(event: dict[str, str], selected: list[dict[str, Any]], duration: float) -> float:
    zone = field_zone(event)
    time_bin = min(5, int(float(event["source_time_sec"]) / duration * 6))
    zones = Counter(row["field_zone"] for row in selected)
    bins = Counter(row["time_bin"] for row in selected)
    teams = Counter(row["team"] for row in selected)
    jitter = int(hashlib.sha256(event["event_id"].encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return 6 / (1 + zones[zone]) + 4 / (1 + bins[time_bin]) + 2 / (1 + teams[event["team"]]) + jitter * 0.01


def select_group(
    events: list[dict[str, str]], count: int, capture: Any, fps: float, frame_count: int,
    duration: float, rect: list[int], output_dir: Path, min_gap_sec: float,
    max_similar_hamming: int, prior_selected: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    selected: list[dict[str, Any]] = []
    prior_selected = prior_selected or []
    remaining = list(events)
    rejected: Counter[str] = Counter()
    while len(selected) < count and remaining:
        eligible = [event for event in remaining if all(
            abs(float(event["source_time_sec"]) - row["source_time_sec"]) >= min_gap_sec
            for row in selected + prior_selected
        )]
        if not eligible:
            break
        event = max(eligible, key=lambda item: score_event(item, selected, duration))
        remaining.remove(event)
        event_time = float(event["source_time_sec"])
        frame_index = round(event_time * fps)
        delta = round(0.3 * fps)
        if frame_index - delta < 0 or frame_index + delta >= frame_count:
            rejected["edge"] += 1
            continue
        try:
            center = read_frame(capture, frame_index)
        except RuntimeError:
            rejected["decode"] += 1
            continue
        current_hash = scene_hash(center)
        distances = [
            (current_hash ^ row["scene_hash"]).bit_count()
            for row in selected + prior_selected
            if abs(event_time - row["source_time_sec"]) < 120
        ]
        nearest_distance = min(distances, default=64)
        if nearest_distance <= max_similar_hamming:
            rejected["similar_scene"] += 1
            continue
        masked = mask_frame(center, rect)
        frame_rel = f"frames/{event['event_id']}.jpg"
        preview_rel = f"previews/{event['event_id']}.jpg"
        if not cv2.imwrite(str(output_dir / frame_rel), masked, [cv2.IMWRITE_JPEG_QUALITY, 92]):
            raise OSError(f"cannot write {frame_rel}")
        write_preview(capture, frame_index, center, rect, fps, output_dir / preview_rel)
        selected.append({
            **event,
            "action": action_for(event),
            "source_time_sec": event_time,
            "frame_index": frame_index,
            "frame_number": frame_index + 1,
            "frame_time_sec": round(frame_index / fps, 6),
            "frame_offset_from_event_sec": round(frame_index / fps - event_time, 6),
            "source_fps": fps,
            "field_zone": field_zone(event),
            "time_bin": min(5, int(event_time / duration * 6)),
            "nearest_scene_hash_distance": nearest_distance,
            "scene_hash": current_hash,
            "frame_image": frame_rel,
            "preview_image": preview_rel,
            "review_status": "unreviewed",
            "chosen_frame_index": "",
            "review_note": "",
        })
    if len(selected) != count:
        raise RuntimeError(f"only selected {len(selected)}/{count} for {events[0]['video_id'] if events else 'empty group'}")
    return selected, rejected


def write_gallery(rows: list[dict[str, Any]], path: Path) -> None:
    cards = []
    for row in rows:
        title = f"{row['candidate_id']} · {row['action']} · {row['video_id']} · {row['match_timecode']}"
        details = f"event {row['event_id']} · frame {row['frame_index']} (0-based) · zone {row['field_zone']} · {row['team']}"
        cards.append(
            f'<article class="card" data-match="{html.escape(row["match_id"])}" '
            f'data-half="{row["half"]}" data-action="{html.escape(row["action"])}">'
            f'<label><input type="checkbox" data-id="{row["candidate_id"]}"> '
            f'<strong>{html.escape(title)}</strong></label>'
            f'<a href="{html.escape(row["frame_image"])}" target="_blank">'
            f'<img loading="lazy" src="{html.escape(row["preview_image"])}" alt="{html.escape(title)}"></a>'
            f'<small>{html.escape(details)}</small>'
            f'<div class="edits"><label>确认帧号 <input class="frame-edit" type="number" min="0" step="1" '
            f'data-id="{row["candidate_id"]}" value="{row["frame_index"]}"></label>'
            f'<input class="note-edit" data-id="{row["candidate_id"]}" placeholder="可见性 / 触球备注"></div></article>'
        )
    export_rows = [{key: row.get(key, "") for key in FIELDS} for row in rows]
    data = json.dumps(export_rows, ensure_ascii=False).replace("<", "\\u003c")
    page = """<!doctype html><html lang="zh"><meta charset="utf-8"><title>U18 候选帧审查</title>
<style>body{font:16px system-ui;margin:0;background:#f4f5f7;color:#19222b}header{position:sticky;top:0;background:#fff;padding:12px 20px;box-shadow:0 1px 7px #bbb;z-index:2}h1{font-size:20px;margin:0 0 8px}.controls,.edits{display:flex;gap:10px;flex-wrap:wrap;align-items:center}button,select,input{font:inherit;padding:5px 9px}.frame-edit{width:8ch}.note-edit{flex:1}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:14px;padding:16px}.card{background:white;padding:10px;border-radius:8px;box-shadow:0 1px 4px #ddd}.card img{width:100%;display:block;margin:7px 0}.card small{color:#52606d}.card:has(input[type=checkbox]:checked){outline:3px solid #148450}.hidden{display:none}</style>
<header><h1>U18 Pass / Reception 候选帧</h1><div class="controls"><span id="count"></span><select id="match"><option value="">两场比赛</option></select><select id="half"><option value="">全部半场</option><option value="1">前半场</option><option value="2">后半场</option></select><select id="action"><option value="">两类事件</option><option>Pass</option><option>Reception candidate</option></select><button id="export">导出已勾选 CSV</button></div><small>点图片查看原尺寸；三联预览为事件前 0.3 秒、事件帧、事件后 0.3 秒。Bepro 左下文字已遮挡。接球仅为候选，需人工确认球和首次触球。改动确认帧号后请用原视频核对，预览不会自动更新。</small></header><main>""" + "\n".join(cards) + "</main>\n<script>\nconst rows=" + data + ";\n" + """
const boxes=[...document.querySelectorAll('input[type=checkbox][data-id]')], key='u18-frame-review:'+location.pathname;
let saved={};try{saved=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){}
const edits=[...document.querySelectorAll('.frame-edit,.note-edit')];
function stateFor(id){return {selected:!!document.querySelector(`input[type=checkbox][data-id="${id}"]`).checked,chosen_frame_index:document.querySelector(`.frame-edit[data-id="${id}"]`).value,review_note:document.querySelector(`.note-edit[data-id="${id}"]`).value}}
function update(){const selected=boxes.filter(b=>b.checked).length;document.getElementById('count').textContent=`已选 ${selected} / 目标约 100（候选 ${boxes.length}）`;try{localStorage.setItem(key,JSON.stringify(Object.fromEntries(rows.map(r=>[r.candidate_id,stateFor(r.candidate_id)]))))}catch(e){}}
for(const b of boxes){const old=saved[b.dataset.id];b.checked=typeof old==='object'?!!old.selected:!!old;b.addEventListener('change',update)}
for(const input of edits){const old=saved[input.dataset.id];if(old&&typeof old==='object'){const value=input.classList.contains('frame-edit')?old.chosen_frame_index:old.review_note;if(value!==undefined)input.value=value}input.addEventListener('input',update)}
const match=document.getElementById('match'),half=document.getElementById('half'),action=document.getElementById('action');
for(const id of [...new Set(rows.map(r=>r.match_id))]){const o=document.createElement('option');o.value=id;o.textContent=id;match.append(o)}
function filter(){for(const card of document.querySelectorAll('.card'))card.classList.toggle('hidden',!!((match.value&&card.dataset.match!==match.value)||(half.value&&card.dataset.half!==half.value)||(action.value&&card.dataset.action!==action.value)))}
for(const s of [match,half,action])s.addEventListener('change',filter);
document.getElementById('export').onclick=()=>{const ids=new Set(boxes.filter(b=>b.checked).map(b=>b.dataset.id));const fields=['candidate_id','event_id','video_id','match_id','half','action','source_time_sec','source_timecode','match_time_sec','match_timecode','frame_index','frame_number','frame_time_sec','chosen_frame_index','review_note','source_video','frame_image'];const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';const csv=[fields.join(','),...rows.filter(r=>ids.has(r.candidate_id)).map(r=>{const item={...r,...stateFor(r.candidate_id)};return fields.map(f=>quote(item[f])).join(',')})].join('\\r\\n');const link=document.createElement('a');link.href=URL.createObjectURL(new Blob(['\\ufeff'+csv],{type:'text/csv;charset=utf-8'}));link.download='u18_selected_frames.csv';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000)};
update();</script></html>"""
    path.write_text(page, encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    if args.min_gap_sec <= 0 or args.known_gap_sec < 0 or not 0 <= args.max_similar_hamming <= 64:
        raise ValueError("invalid gap or hamming threshold")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    videos = {video["video_id"]: video for video in config["videos"]}
    gt = read_csv(args.ground_truth)
    known = read_csv(args.known_review)
    extra = read_csv(args.extra_exclusions) if args.extra_exclusions else []
    exclude_ids, exclude_times = exclusion_index(known + extra)
    filtered = [event for event in gt if action_for(event) and event["evaluation_status"] == "evaluable"
                and not is_near_exclusion(event, exclude_ids, exclude_times, args.known_gap_sec)]
    quotas = allocation(args.per_match, args.second_half_fraction)
    match_ids = sorted({video["match_id"] for video in videos.values()})
    if len(match_ids) != 2:
        raise ValueError("expected two matches")
    for video in videos.values():
        path = args.source_root / video["video_basename"]
        if path.stat().st_size != video["video_size_bytes"] or sha256_file(path) != video["video_sha256"]:
            raise ValueError(f"source video mismatch: {path}")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "frames").mkdir()
    (args.output_dir / "previews").mkdir()
    chosen: list[dict[str, Any]] = []
    rejected: Counter[str] = Counter()
    rect = config["inference_proxy"]["mask_source_rect_px"]
    for match_id in match_ids:
        for (half, action), count in quotas.items():
            if count == 0:
                continue
            video = next(v for v in videos.values() if v["match_id"] == match_id and v["half"] == half)
            video_id = video["video_id"]
            path = args.source_root / video["video_basename"]
            capture = cv2.VideoCapture(str(path))
            try:
                if not capture.isOpened():
                    raise RuntimeError(f"cannot open {path}")
                fps = capture.get(cv2.CAP_PROP_FPS)
                frame_count = round(capture.get(cv2.CAP_PROP_FRAME_COUNT))
                if not math.isclose(fps, 30, abs_tol=0.001) or frame_count != video["frame_count"]:
                    raise ValueError(f"video frame contract mismatch: {video_id} {fps} {frame_count}")
                group = [event for event in filtered if event["video_id"] == video_id and action_for(event) == action]
                selected, discarded = select_group(group, count, capture, fps, frame_count,
                    float(video["duration_sec"]), rect, args.output_dir, args.min_gap_sec,
                    args.max_similar_hamming,
                    [row for row in chosen if row["video_id"] == video_id])
                for row in selected:
                    row["source_video"] = str(path.resolve())
                chosen.extend(selected)
                rejected.update(discarded)
                print(f"{video_id} {action}: {len(selected)} selected; rejected={dict(discarded)}", flush=True)
            finally:
                capture.release()
    chosen.sort(key=lambda row: (row["match_id"], row["half"], row["source_time_sec"], row["action"]))
    for index, row in enumerate(chosen, start=1):
        row["candidate_id"] = f"u18-frame-{index:03d}"
    with (args.output_dir / "review.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(chosen)
    write_gallery(chosen, args.output_dir / "index.html")
    summary = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "candidate_frames_unreviewed",
        "source_config": str(args.config.resolve()),
        "source_config_sha256": sha256_file(args.config),
        "ground_truth": str(args.ground_truth.resolve()),
        "ground_truth_sha256": sha256_file(args.ground_truth),
        "known_review": str(args.known_review.resolve()),
        "known_review_sha256": sha256_file(args.known_review),
        "extra_exclusions": str(args.extra_exclusions.resolve()) if args.extra_exclusions else None,
        "extra_exclusions_sha256": sha256_file(args.extra_exclusions) if args.extra_exclusions else None,
        "known_event_count": len(known),
        "known_gap_sec": args.known_gap_sec,
        "min_gap_sec": args.min_gap_sec,
        "max_similar_hamming": args.max_similar_hamming,
        "preview_offsets_sec": [-0.3, 0, 0.3],
        "frame_index_base": 0,
        "frame_number_base": 1,
        "source_fps": 30,
        "bepro_overlay": "source rect masked before hashing and image export",
        "source_videos": {video_id: {"sha256": video["video_sha256"], "basename": video["video_basename"]} for video_id, video in videos.items()},
        "counts": dict(Counter(f"{row['video_id']}:{row['action']}" for row in chosen)),
        "field_zones": dict(Counter(row["field_zone"] for row in chosen)),
        "rejected": dict(rejected),
        "review_csv_sha256": sha256_file(args.output_dir / "review.csv"),
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(chosen)} candidates to {args.output_dir}")


if __name__ == "__main__":
    main()

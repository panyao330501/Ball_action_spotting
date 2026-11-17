"""Add masked ±5 s source-frame clips and a large frame-review gallery."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/u18_gt.yaml"))
    parser.add_argument("--ffmpeg", type=Path, default=Path(r"C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffmpeg.exe"))
    parser.add_argument("--ffprobe", type=Path, default=Path(r"C:\Users\logan\.conda\envs\ballspot-viz\Library\bin\ffprobe.exe"))
    parser.add_argument("--context-sec", type=float, default=5.0)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--crf", type=int, default=22)
    parser.add_argument("--limit", type=int, help="Render only the first N clips for a smoke test; leave the gallery unchanged")
    parser.add_argument("--gallery-only", action="store_true", help="Refresh HTML from an existing clip manifest")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def clip_contract(row: dict[str, str], video: dict[str, Any], context_sec: float) -> dict[str, Any]:
    fps = float(row["source_fps"])
    radius = round(context_sec * fps)
    center = int(row["frame_index"])
    start = max(0, center - radius)
    end = min(int(video["frame_count"]) - 1, center + radius)
    return {
        "candidate_id": row["candidate_id"],
        "event_id": row["event_id"],
        "video_id": row["video_id"],
        "path": f"clips/{row['event_id']}.mp4",
        "source_start_frame": start,
        "source_end_frame": end,
        "source_video_frame_count": int(video["frame_count"]),
        "frame_count": end - start + 1,
        "center_relative_frame": center - start,
        "source_fps": fps,
        "source_start_sec": round(start / fps, 6),
        "duration_sec": round((end - start + 1) / fps, 6),
    }


def probe_clip(ffprobe: Path, path: Path) -> dict[str, Any]:
    command = [str(ffprobe), "-v", "error", "-count_frames", "-select_streams", "v:0",
               "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames,duration",
               "-of", "json", str(path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)["streams"][0]


def verify_clip(ffprobe: Path, path: Path, contract: dict[str, Any], width: int) -> None:
    stream = probe_clip(ffprobe, path)
    expected_height = round(width * 9 / 16)
    if (int(stream["width"]), int(stream["height"])) != (width, expected_height):
        raise ValueError(f"clip size mismatch: {path}")
    if stream["r_frame_rate"] != "30/1" or int(stream["nb_read_frames"]) != contract["frame_count"]:
        raise ValueError(f"clip fps/frame count mismatch: {path}: {stream}")
    if abs(float(stream["duration"]) - contract["duration_sec"]) > 1 / 30 + 0.001:
        raise ValueError(f"clip duration mismatch: {path}")


def render_clip(
    ffmpeg: Path, ffprobe: Path, row: dict[str, str],
    contract: dict[str, Any], destination: Path, rect: list[int], width: int, crf: int,
) -> None:
    height = round(width * 9 / 16)
    x, y, rect_width, rect_height = rect
    filter_graph = (
        f"drawbox=x={x}:y={y}:w={rect_width}:h={rect_height}:color=black:t=fill,"
        f"scale={width}:{height}:flags=lanczos,fps=30"
    )
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
        "-ss", f"{contract['source_start_sec']:.6f}", "-i", row["source_video"],
        "-map", "0:v:0", "-an", "-vf", filter_graph,
        "-frames:v", str(contract["frame_count"]), "-c:v", "libx264",
        "-preset", "veryfast", "-crf", str(crf), "-g", "30", "-keyint_min", "30",
        "-sc_threshold", "0", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(destination),
    ]
    subprocess.run(command, check=True)
    verify_clip(ffprobe, destination, contract, width)


def write_gallery(rows: list[dict[str, str]], contracts: list[dict[str, Any]], path: Path) -> None:
    by_id = {item["candidate_id"]: item for item in contracts}
    cards = []
    data = []
    for row in rows:
        clip = by_id[row["candidate_id"]]
        title = f"{row['candidate_id']} · {row['action']} · {row['video_id']} · {row['match_timecode']}"
        caption = (
            f"GT {row['source_timecode']}（半场视频）/ {row['match_timecode']}（比赛）"
            f" · 建议源帧 {row['frame_index']}（从 0 开始） · {row['field_zone']} · {row['team']}"
        )
        cards.append(
            f'<article class="card" data-match="{html.escape(row["match_id"])}" '
            f'data-half="{row["half"]}" data-action="{html.escape(row["action"])}">'
            f'<h2><label><input type="checkbox" data-id="{row["candidate_id"]}"> '
            f'{html.escape(title)}</label></h2>'
            f'<p>{html.escape(caption)}</p>'
            f'<a href="{html.escape(row["frame_image"])}" target="_blank" title="打开原尺寸图片">'
            f'<img class="main-frame" loading="lazy" src="{html.escape(row["frame_image"])}" '
            f'alt="{html.escape(title)}"></a>'
            f'<div class="actions"><button type="button" class="open-clip" data-id="{row["candidate_id"]}">'
            f'打开前后 5 秒片段并逐帧选取</button>'
            f'<label>确认源帧号 <input class="frame-edit" type="number" min="0" step="1" '
            f'max="{clip["source_video_frame_count"] - 1}" data-id="{row["candidate_id"]}" '
            f'value="{row["frame_index"]}"></label>'
            f'<input class="note-edit" data-id="{row["candidate_id"]}" placeholder="可见性 / 触球备注"></div>'
            f'</article>'
        )
        data.append({
            **row,
            "clip_path": clip["path"],
            "clip_start_frame": clip["source_start_frame"],
            "clip_frame_count": clip["frame_count"],
            "clip_center_frame": clip["center_relative_frame"],
            "source_video_frame_count": clip["source_video_frame_count"],
        })
    embedded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    page = r'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>U18 大画面选帧</title>
<style>
*{box-sizing:border-box}body{font:17px system-ui;margin:0;background:#e9edf1;color:#17212b}header{position:sticky;top:0;background:white;padding:12px 24px;box-shadow:0 1px 7px #aaa;z-index:2}h1{font-size:23px;margin:0 0 6px}h2{font-size:20px;margin:0}.controls,.actions,.viewer-controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}button,select,input{font:inherit;padding:6px 10px}button{cursor:pointer}.count{font-weight:700}main{max-width:1480px;margin:0 auto;padding:18px}.card{background:white;padding:18px;margin:0 0 22px;border-radius:10px;box-shadow:0 1px 5px #ccd}.card p{margin:8px 0 12px;color:#425366}.main-frame{display:block;width:100%;height:auto;max-height:78vh;object-fit:contain;background:#111;border-radius:5px}.actions{margin-top:12px}.frame-edit{width:9ch}.note-edit{flex:1;min-width:260px}.card:has(input[type=checkbox]:checked){outline:4px solid #168b55}.hidden{display:none}dialog{width:min(96vw,1650px);max-height:98vh;overflow:auto;border:0;border-radius:10px;padding:16px;background:white;box-shadow:0 12px 40px #2228}dialog::backdrop{background:#000b}.viewer-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.viewer-head h2{font-size:19px}.video-wrap{position:relative;width:min(100%,131.56vh);aspect-ratio:16/9;background:black;margin:8px auto}.video-wrap video{display:block;width:100%;height:100%}.viewer-controls{margin-top:8px}.viewer-controls input[type=range]{flex:1;min-width:200px}#frame-info{font-variant-numeric:tabular-nums;font-weight:700}#video-error{color:#a00}
</style>
<header><h1>U18 Pass / Reception 大画面选帧</h1><div class="controls"><span id="count" class="count"></span><select id="match"><option value="">两场比赛</option></select><select id="half"><option value="">全部半场</option><option value="1">前半场</option><option value="2">后半场</option></select><select id="action"><option value="">两类事件</option><option>Pass</option><option>Reception candidate</option></select><button id="export">导出已勾选 CSV</button></div><small>主图是 GT 建议帧，点图可放大；片段覆盖前后各 5 秒，可逐帧确认实际传球/首次触球。修改确认帧号不会改变主图；导出的 source_video + chosen_frame_index 才是你选定的帧。勾选和备注会保存在当前浏览器中，请及时导出 CSV。</small></header>
<main>''' + "\n".join(cards) + r'''</main>
<dialog id="viewer"><div class="viewer-head"><h2 id="viewer-title"></h2><button id="close-viewer" type="button">关闭</button></div><div class="video-wrap"><video id="clip-video" playsinline preload="none" controls></video></div><div id="video-error" hidden>无法在此浏览器播放片段。可直接打开 <a id="clip-link" target="_blank">片段文件</a>。</div><div class="viewer-controls"><button id="minus-second" type="button">−1 秒</button><button id="minus-frame" type="button">−1 帧</button><button id="plus-frame" type="button">+1 帧</button><button id="plus-second" type="button">+1 秒</button><input id="frame-slider" type="range" min="0" value="0"><button id="use-frame" type="button">将当前帧设为确认帧号</button></div><p id="frame-info"></p><small>播放时可使用 ←/→ 逐帧、Shift+←/→ 移动 1 秒、空格播放/暂停。片段以原视频 30 FPS 重新编码；页面显示当前源帧号和两种时间。</small></dialog>
<script>const rows=''' + embedded + r''';
const byId=Object.fromEntries(rows.map(r=>[r.candidate_id,r]));
const boxes=[...document.querySelectorAll('input[type=checkbox][data-id]')];
const storageKey='u18-frame-review:'+location.pathname;
let saved={};try{saved=JSON.parse(localStorage.getItem(storageKey)||'{}')}catch(e){}
function box(id){return document.querySelector(`input[type=checkbox][data-id="${id}"]`)}
function frameInput(id){return document.querySelector(`.frame-edit[data-id="${id}"]`)}
function noteInput(id){return document.querySelector(`.note-edit[data-id="${id}"]`)}
function stateFor(id){return {selected:box(id).checked,chosen_frame_index:frameInput(id).value,review_note:noteInput(id).value}}
function update(){document.getElementById('count').textContent=`已选 ${boxes.filter(b=>b.checked).length} / 目标约 100（候选 ${boxes.length}）`;try{localStorage.setItem(storageKey,JSON.stringify(Object.fromEntries(rows.map(r=>[r.candidate_id,stateFor(r.candidate_id)]))))}catch(e){}}
for(const r of rows){const old=saved[r.candidate_id];if(old){box(r.candidate_id).checked=typeof old==='object'?!!old.selected:!!old;if(typeof old==='object'){if(old.chosen_frame_index!==undefined)frameInput(r.candidate_id).value=old.chosen_frame_index;if(old.review_note!==undefined)noteInput(r.candidate_id).value=old.review_note}}for(const el of [box(r.candidate_id),frameInput(r.candidate_id),noteInput(r.candidate_id)])el.addEventListener('input',update)}
const match=document.getElementById('match'),half=document.getElementById('half'),action=document.getElementById('action');
for(const id of [...new Set(rows.map(r=>r.match_id))]){const o=document.createElement('option');o.value=id;o.textContent=id;match.append(o)}
function filter(){for(const card of document.querySelectorAll('.card'))card.classList.toggle('hidden',!!((match.value&&card.dataset.match!==match.value)||(half.value&&card.dataset.half!==half.value)||(action.value&&card.dataset.action!==action.value)))}
for(const el of [match,half,action])el.addEventListener('change',filter);
const dialog=document.getElementById('viewer'),video=document.getElementById('clip-video'),slider=document.getElementById('frame-slider');let active=null,relativeFrame=0;
function clamp(n){return Math.max(0,Math.min(active.clip_frame_count-1,n))}
function tc(sec){const ms=Math.round(sec*1000),h=Math.floor(ms/3600000),m=Math.floor(ms/60000)%60,s=Math.floor(ms/1000)%60;return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms%1000).padStart(3,'0')}`}
function showFrame(relative){if(!active)return;relativeFrame=clamp(relative);slider.value=relativeFrame;const sourceFrame=Number(active.clip_start_frame)+relativeFrame,sourceTime=sourceFrame/30,matchTime=sourceTime+(Number(active.half)===2?2700:0);document.getElementById('frame-info').textContent=`源帧 ${sourceFrame}（从 0 开始） · 半场 ${tc(sourceTime)} · 比赛 ${tc(matchTime)} · 相对 GT ${(sourceTime-Number(active.source_time_sec)).toFixed(3)} 秒`}
function seek(relative){if(!active)return;video.pause();const target=clamp(relative);video.currentTime=Math.min((target+0.05)/30,Math.max(0,video.duration-0.001));showFrame(target)}
function openViewer(id){active=byId[id];relativeFrame=Number(active.clip_center_frame);document.getElementById('viewer-title').textContent=`${id} · ${active.action} · GT ${active.match_timecode}`;document.getElementById('video-error').hidden=true;const link=document.getElementById('clip-link');link.href=active.clip_path;slider.max=Number(active.clip_frame_count)-1;showFrame(relativeFrame);video.src=active.clip_path;video.load();dialog.showModal()}
for(const button of document.querySelectorAll('.open-clip'))button.addEventListener('click',()=>openViewer(button.dataset.id));
video.addEventListener('loadedmetadata',()=>seek(Number(active.clip_center_frame)));
video.addEventListener('error',()=>document.getElementById('video-error').hidden=false);
video.addEventListener('timeupdate',()=>{if(active&&dialog.open)showFrame(Math.floor(video.currentTime*30+0.001))});
if(video.requestVideoFrameCallback){const callback=(now,metadata)=>{if(active&&dialog.open)showFrame(Math.round(metadata.mediaTime*30));video.requestVideoFrameCallback(callback)};video.requestVideoFrameCallback(callback)}
slider.addEventListener('input',()=>seek(Number(slider.value)));
document.getElementById('minus-frame').onclick=()=>seek(relativeFrame-1);document.getElementById('plus-frame').onclick=()=>seek(relativeFrame+1);document.getElementById('minus-second').onclick=()=>seek(relativeFrame-30);document.getElementById('plus-second').onclick=()=>seek(relativeFrame+30);
document.getElementById('use-frame').onclick=()=>{frameInput(active.candidate_id).value=Number(active.clip_start_frame)+relativeFrame;update()};
document.getElementById('close-viewer').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{video.pause();video.removeAttribute('src');video.load();active=null});
dialog.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT')return;if(['ArrowLeft','ArrowRight',' '].includes(e.key)){e.preventDefault();if(e.key===' ')video.paused?video.play():video.pause();else seek(relativeFrame+(e.key==='ArrowLeft'?-1:1)*(e.shiftKey?30:1))}});
document.getElementById('export').onclick=()=>{const fields=['candidate_id','event_id','video_id','match_id','half','action','source_time_sec','source_timecode','match_time_sec','match_timecode','frame_index','frame_number','chosen_frame_index','chosen_frame_number','chosen_source_time_sec','chosen_match_time_sec','review_note','source_video','suggested_frame_image'];const chosen=rows.filter(r=>box(r.candidate_id).checked);for(const r of chosen){const frame=Number(frameInput(r.candidate_id).value);if(!frameInput(r.candidate_id).value||!Number.isInteger(frame)||frame<0||frame>=Number(r.source_video_frame_count)){alert(`请检查 ${r.candidate_id} 的确认帧号`);frameInput(r.candidate_id).focus();return}}const selected=chosen.map(r=>{const state=stateFor(r.candidate_id),frame=Number(state.chosen_frame_index);return {...r,...state,suggested_frame_image:r.frame_image,chosen_frame_number:frame+1,chosen_source_time_sec:(frame/30).toFixed(6),chosen_match_time_sec:(frame/30+(Number(r.half)===2?2700:0)).toFixed(6)}});const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';const csv=[fields.join(','),...selected.map(r=>fields.map(f=>quote(r[f])).join(','))].join('\r\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));a.download='u18_selected_frames.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
update();</script></html>'''
    path.write_text(page, encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.gallery_only and args.limit:
        raise ValueError("--gallery-only cannot be combined with --limit")
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be positive")
    if args.context_sec <= 0 or args.width < 640 or args.width % 16 or not 0 <= args.crf <= 51:
        raise ValueError("invalid context, width or CRF")
    candidate_dir = args.candidate_dir.resolve()
    rows = read_rows(candidate_dir / "review.csv")
    base = json.loads((candidate_dir / "manifest.json").read_text(encoding="utf-8"))
    if sha256_file(candidate_dir / "review.csv") != base["review_csv_sha256"]:
        raise ValueError("candidate review CSV hash mismatch")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    videos = {video["video_id"]: video for video in config["videos"]}
    rect = config["inference_proxy"]["mask_source_rect_px"]
    if not args.ffmpeg.is_file() or not args.ffprobe.is_file():
        raise FileNotFoundError("ffmpeg/ffprobe not found")
    for row in rows:
        video = videos[row["video_id"]]
        source = Path(row["source_video"])
        if source.name != video["video_basename"] or source.stat().st_size != video["video_size_bytes"]:
            raise ValueError(f"source video identity mismatch: {row['event_id']}")
    clips = candidate_dir / "clips"
    clips.mkdir(exist_ok=True)
    contracts = [clip_contract(row, videos[row["video_id"]], args.context_sec) for row in rows]
    prior_manifest = candidate_dir / "clip_manifest.json"
    if prior_manifest.exists():
        prior = json.loads(prior_manifest.read_text(encoding="utf-8"))
        for key, value in (("context_sec", args.context_sec), ("width", args.width), ("crf", args.crf)):
            if prior[key] != value:
                raise ValueError(f"existing clip manifest has different {key}; use a new run directory")
    if args.gallery_only:
        if not prior_manifest.exists() or prior["review_csv_sha256"] != base["review_csv_sha256"]:
            raise ValueError("verified clip manifest required for --gallery-only")
        if len(prior["clips"]) != len(rows):
            raise ValueError("clip manifest count mismatch")
        for item in prior["clips"]:
            if not (candidate_dir / item["path"]).is_file():
                raise FileNotFoundError(item["path"])
        write_gallery(rows, prior["clips"], candidate_dir / "index.html")
        print(f"large gallery refreshed: {candidate_dir / 'index.html'}")
        return
    for index, (row, contract) in enumerate(zip(rows, contracts), start=1):
        if args.limit and index > args.limit:
            break
        target = candidate_dir / contract["path"]
        if target.exists():
            verify_clip(args.ffprobe, target, contract, args.width)
        else:
            render_clip(args.ffmpeg, args.ffprobe, row, contract,
                        target, rect, args.width, args.crf)
        if index == 1 or index % 10 == 0 or index == len(rows):
            print(f"clips verified: {index}/{len(rows)}", flush=True)
    if args.limit:
        print("smoke limit reached; gallery unchanged")
        return
    for contract in contracts:
        contract["sha256"] = sha256_file(candidate_dir / contract["path"])
    clip_manifest = {
        "schema_version": 1,
        "review_csv_sha256": base["review_csv_sha256"],
        "context_sec": args.context_sec,
        "width": args.width,
        "height": round(args.width * 9 / 16),
        "fps": 30,
        "crf": args.crf,
        "mask_source_rect_px": rect,
        "clips": contracts,
    }
    (candidate_dir / "clip_manifest.json").write_text(
        json.dumps(clip_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    original_gallery = candidate_dir / "index.html"
    backup = candidate_dir / "index_small_v1.html"
    if not backup.exists():
        shutil.copy2(original_gallery, backup)
    write_gallery(rows, contracts, original_gallery)
    print(f"large gallery ready: {original_gallery}")


if __name__ == "__main__":
    main()

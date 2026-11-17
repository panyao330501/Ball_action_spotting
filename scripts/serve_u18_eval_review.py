"""Serve U18 review pages on loopback with video ranges and local CSV saves."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import uuid
import webbrowser
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class RangeHandler(SimpleHTTPRequestHandler):
    def send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/save-review":
            self.send_json(404, {"error": "Unknown local endpoint"})
            return
        origin = self.headers.get("Origin")
        expected_origin = f"http://127.0.0.1:{self.server.server_port}"
        if origin and origin != expected_origin:
            self.send_json(403, {"error": "Cross-origin save blocked"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2_000_000:
                raise ValueError("Invalid review size")
            request = json.loads(self.rfile.read(length).decode("utf-8"))
            mode = request["mode"]
            if mode not in {"pass", "drive"}:
                raise ValueError("Unknown review mode")
            directory = "review_site" if mode == "pass" else "drive_review_site"
            root = Path(self.directory)
            manifest = json.loads((root / directory / "manifest.json").read_text(encoding="utf-8"))
            if request["review_sha256"] != manifest["review_csv_sha256"]:
                raise ValueError("Review source hash mismatch")
            text = request["csv"]
            if not isinstance(text, str) or len(text) > 2_000_000:
                raise ValueError("Invalid review CSV")
            rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
            source = list(csv.DictReader(io.StringIO(Path(manifest["review_csv"]).read_text(encoding="utf-8-sig"))))
            id_field = "review_id" if mode == "pass" else "event_id"
            ids = [row[id_field] for row in rows]
            if len(rows) != len(source) or len(set(ids)) != len(ids) or set(ids) != {row[id_field] for row in source}:
                raise ValueError("Review rows do not match source")
            if mode == "pass":
                if any(row["human_visibility"] not in {"", "VISIBLE", "PARTIAL", "OFFSCREEN", "UNCLEAR"} or
                       row["human_judgment"] not in {"", "确有 Pass", "无 Pass", "时间偏移", "类别不符", "无法判断"}
                       for row in rows):
                    raise ValueError("Invalid Pass review choice")
            else:
                if any(row["review_mapping"] not in {"unreviewed", "accept", "reject", "unclear"} or
                       row["review_observation"] not in {
                           "", "carry_after_receive", "control_only", "one_touch_release",
                           "partial", "offscreen", "unclear",
                       } for row in rows):
                    raise ValueError("Invalid Drive review choice")
            target_dir = root / "review_exports"
            target_dir.mkdir(exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            name = f"{mode}_review_{stamp}_{uuid.uuid4().hex[:8]}.csv"
            with (target_dir / name).open("x", encoding="utf-8", newline="") as file:
                file.write(text)
            self.send_json(200, {"file": f"review_exports/{name}", "rows": len(rows)})
        except (KeyError, TypeError, ValueError, OSError, UnicodeError) as error:
            self.send_json(400, {"error": str(error)})

    def send_head(self):  # type: ignore[override]
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        value = self.headers.get("Range", "")
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", value) if value else None
        if value and not match:
            self.send_error(416, "Unsupported byte range")
            return None
        start, end = 0, size - 1
        if match:
            first, last = match.groups()
            if not first and not last:
                self.send_error(416, "Empty byte range")
                return None
            if first:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            else:
                start = max(0, size - int(last))
            if start >= size or end < start:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return None
        file = path.open("rb")
        self._range_start = start
        self._range_length = end - start + 1
        self.send_response(206 if match else 200)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(self._range_length))
        if match:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Last-Modified", self.date_time_string(path.stat().st_mtime))
        self.end_headers()
        return file

    def copyfile(self, source, outputfile):  # type: ignore[override]
        if not hasattr(self, "_range_length"):
            shutil.copyfileobj(source, outputfile)
            return
        source.seek(self._range_start)
        remaining = self._range_length
        while remaining:
            block = source.read(min(1024 * 1024, remaining))
            if not block:
                break
            try:
                outputfile.write(block)
            except (BrokenPipeError, ConnectionResetError):
                # Browsers routinely cancel a prior byte-range request when seeking.
                break
            remaining -= len(block)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", required=True, type=Path)
    parser.add_argument("--page", default="index.html", help="Page relative to site-dir to open")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the local page in the default browser")
    args = parser.parse_args()
    site_dir = args.site_dir.resolve()
    page = (site_dir / args.page).resolve()
    if not page.is_relative_to(site_dir) or not page.is_file():
        raise FileNotFoundError(f"review page missing or outside site-dir: {page}")
    handler = partial(RangeHandler, directory=str(site_dir))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        url = f"http://127.0.0.1:{server.server_port}/{page.relative_to(site_dir).as_posix()}"
        print(f"U18 Pass review: {url}", flush=True)
        print("Press Ctrl+C after exporting your review CSV.", flush=True)
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

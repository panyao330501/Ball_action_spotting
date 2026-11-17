from __future__ import annotations

import importlib.util
import json
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "serve_u18_eval_review.py"
SPEC = importlib.util.spec_from_file_location("serve_u18_eval_review", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_video_byte_ranges_support_seeking(tmp_path):
    content = bytes(range(256)) * 8
    (tmp_path / "clip.mp4").write_bytes(content)
    handler = partial(MODULE.RangeHandler, directory=str(tmp_path))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/clip.mp4"
        with urlopen(Request(url, headers={"Range": "bytes=256-511"})) as response:
            assert response.status == 206
            assert response.headers["Content-Range"] == f"bytes 256-511/{len(content)}"
            assert response.read() == content[256:512]
        with pytest.raises(HTTPError) as error:
            urlopen(Request(url, headers={"Range": "bytes=9999-"}))
        assert error.value.code == 416
        server.shutdown()
        thread.join(timeout=3)


def test_local_save_writes_versioned_review_csv(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("review_id,human_visibility,human_judgment,human_comment\ncase-1,,,\n", encoding="utf-8")
    site = tmp_path / "review_site"
    site.mkdir()
    (site / "manifest.json").write_text(json.dumps({
        "review_csv": str(source), "review_csv_sha256": "source-hash"
    }), encoding="utf-8")
    content = '\ufeffreview_id,human_visibility,human_judgment,human_comment\r\n"case-1","VISIBLE","确有 Pass",""\r\n'
    handler = partial(MODULE.RangeHandler, directory=str(tmp_path))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/save-review"
            request = Request(url, data=json.dumps({
                "mode": "pass", "review_sha256": "source-hash", "csv": content
            }).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urlopen(request) as response:
                result = json.load(response)
            assert result["rows"] == 1
            assert result["file"].startswith("review_exports/pass_review_")
            assert (tmp_path / result["file"]).read_bytes() == content.encode("utf-8")
            invalid = Request(url, data=json.dumps({
                "mode": "pass", "review_sha256": "wrong", "csv": content
            }).encode("utf-8"), headers={"Content-Type": "application/json"})
            with pytest.raises(HTTPError) as error:
                urlopen(invalid)
            assert error.value.code == 400
            assert len(list((tmp_path / "review_exports").glob("*.csv"))) == 1
        finally:
            server.shutdown()
            thread.join(timeout=3)


def test_local_save_accepts_drive_audit_fields(tmp_path):
    source = tmp_path / "drive_source.csv"
    source.write_text("event_id,review_mapping,review_observation,review_comment\nu18-gt-1,unreviewed,,\n", encoding="utf-8")
    site = tmp_path / "drive_review_site"
    site.mkdir()
    (site / "manifest.json").write_text(json.dumps({
        "review_csv": str(source), "review_csv_sha256": "drive-hash"
    }), encoding="utf-8")
    content = '\ufeffevent_id,review_mapping,review_observation,review_comment\r\n"u18-gt-1","reject","one_touch_release",""\r\n'
    handler = partial(MODULE.RangeHandler, directory=str(tmp_path))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/api/save-review",
                data=json.dumps({"mode": "drive", "review_sha256": "drive-hash", "csv": content}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request) as response:
                result = json.load(response)
            assert result["rows"] == 1
            assert result["file"].startswith("review_exports/drive_review_")
            assert (tmp_path / result["file"]).read_bytes() == content.encode("utf-8")
        finally:
            server.shutdown()
            thread.join(timeout=3)

"""Tests for harness/runway_task.py, the harness's own Runway image_to_video client. Nothing is
sent: the transport and the download are replaced by fakes.

    python -m pytest harness/test_runway_task.py
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runway_task as rt  # noqa: E402
from ladder import TASK_OUTCOME  # noqa: E402  (the refusal rule's own pattern: only FAILED may become a refusal)


class Api:
    """A fake transport: POST returns the task id; each GET returns the next status record."""
    def __init__(self, statuses, extra=None):
        self.statuses = list(statuses)
        self.extra = dict(extra or {})
        self.calls = []

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "POST":
            return {"id": "0a1b2c3d"}
        status = self.statuses.pop(0)
        rec = {"id": "0a1b2c3d", "status": status, "createdAt": "2026-11-20T09:00:00Z", **self.extra}
        if status == "SUCCEEDED":
            rec["output"] = ["https://example.invalid/signed/clip.mp4?token=secret"]
        if status == "FAILED":
            rec.update(failure="Output failed", failureCode="INTERNAL.BAD_OUTPUT.CODE01")
        return rec


def png(tmp_path, name="p.png", size=10):
    p = tmp_path / name
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * size)
    return p


def test_a_panel_is_inlined_as_a_png_data_uri_never_resampled(tmp_path):
    p = png(tmp_path)
    uri = rt.inline(p)
    assert uri.startswith("data:image/png;base64,")
    import base64
    assert base64.b64decode(uri.split(",", 1)[1]) == p.read_bytes()


def test_a_panel_too_large_to_inline_is_refused_before_anything_is_sent(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "MAX_INLINE_BYTES", 16)
    with pytest.raises(SystemExit) as e:
        rt.inline(png(tmp_path, size=64))
    assert "too large to inline" in str(e.value) and "never resampled" in str(e.value)


def test_inline_request_replaces_paths_in_both_image_forms_and_nothing_else(tmp_path):
    a, b = png(tmp_path, "a.png"), png(tmp_path, "b.png", 20)
    one = rt.inline_request({"model": "gen4.5", "promptImage": str(a), "seed": 5})
    assert one["promptImage"] == rt.inline(a) and one["seed"] == 5 and one["model"] == "gen4.5"
    two = rt.inline_request({"model": "kling_4", "promptImage": [{"uri": str(a), "position": "first"},
                                                                 {"uri": str(b), "position": "last"}]})
    assert two["promptImage"] == [{"uri": rt.inline(a), "position": "first"},
                                  {"uri": rt.inline(b), "position": "last"}]


def test_a_succeeded_task_returns_its_id_and_record(tmp_path):
    api = Api(["PENDING", "RUNNING", "SUCCEEDED"], extra={"seed": 20260812})
    tid, rec = rt.submit_and_wait({"model": "gen4.5"}, req=api, sleep=lambda s: None, log=lambda s: None)
    assert tid == "0a1b2c3d" and rec["status"] == "SUCCEEDED"
    assert api.calls[0] == ("POST", "/image_to_video", {"model": "gen4.5"})
    assert [c[1] for c in api.calls[1:]] == ["/tasks/0a1b2c3d"] * 3


def test_the_summary_keeps_scalar_fields_and_drops_the_signed_output_urls():
    rec = Api(["SUCCEEDED"], extra={"seed": 7, "modelVersion": "x", "nested": {"a": 1}})("GET", "/tasks/x")
    s = rt.task_summary(rec)
    assert s == {"id": "0a1b2c3d", "status": "SUCCEEDED", "createdAt": "2026-11-20T09:00:00Z",
                 "seed": 7, "modelVersion": "x"}
    assert "token" not in json.dumps(s)


def test_a_failed_task_exits_with_the_line_the_refusal_rule_reads():
    with pytest.raises(SystemExit) as e:
        rt.submit_and_wait({}, req=Api(["RUNNING", "FAILED"]), sleep=lambda s: None, log=lambda s: None)
    assert TASK_OUTCOME.search(str(e.value)) and str(e.value).startswith("task 0a1b2c3d FAILED: {")


@pytest.mark.parametrize("status", ["CANCELLED", "ERROR"])
def test_a_cancelled_or_errored_task_is_never_read_as_a_refusal(status):
    with pytest.raises(SystemExit) as e:
        rt.submit_and_wait({}, req=Api([status]), sleep=lambda s: None, log=lambda s: None)
    assert str(e.value).startswith(f"task 0a1b2c3d {status}: ") and not TASK_OUTCOME.search(str(e.value))


def test_a_timeout_is_a_harness_fault_not_a_refusal(monkeypatch):
    monkeypatch.setattr(rt, "POLL_TIMEOUT", 10)
    with pytest.raises(SystemExit) as e:
        rt.submit_and_wait({}, req=Api(["RUNNING"] * 5), sleep=lambda s: None, log=lambda s: None)
    assert "timed out" in str(e.value) and not TASK_OUTCOME.search(str(e.value))


def test_a_response_without_a_task_id_stops():
    with pytest.raises(SystemExit) as e:
        rt.submit_and_wait({}, req=lambda m, p, b=None: {"error": "bad"}, sleep=lambda s: None,
                           log=lambda s: None)
    assert "no task id" in str(e.value)


def test_main_downloads_the_first_output_and_prints_one_json_line(tmp_path, monkeypatch, capsys):
    panel = png(tmp_path)
    api = Api(["SUCCEEDED"], extra={"seed": 20260812})
    got = {}
    monkeypatch.setattr(rt, "_req", api)
    monkeypatch.setattr(rt.time, "sleep", lambda s: None)
    monkeypatch.setattr(rt, "download", lambda url, out: got.update(url=url, out=out))
    out = tmp_path / "clip.mp4"
    body = {"model": "gen4.5", "promptText": "p", "promptImage": str(panel), "ratio": "1280:720",
            "duration": 5, "seed": 20260812}
    assert rt.main(["--request", json.dumps(body), "--out", str(out)]) == 0
    sent = api.calls[0][2]
    assert sent["promptImage"].startswith("data:image/png;base64,") and sent["seed"] == 20260812
    assert got == {"url": "https://example.invalid/signed/clip.mp4?token=secret", "out": str(out)}
    printed = capsys.readouterr().out.strip().splitlines()
    assert len(printed) == 1
    assert json.loads(printed[0]) == {"task_id": "0a1b2c3d", "task": {
        "id": "0a1b2c3d", "status": "SUCCEEDED", "createdAt": "2026-11-20T09:00:00Z", "seed": 20260812}}


def test_main_refuses_a_success_without_an_output(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "_req", lambda m, p, b=None: {"id": "t1"} if m == "POST" else
                        {"id": "t1", "status": "SUCCEEDED", "output": []})
    monkeypatch.setattr(rt.time, "sleep", lambda s: None)
    with pytest.raises(SystemExit) as e:
        rt.main(["--request", json.dumps({"model": "kling_4"}), "--out", str(tmp_path / "c.mp4")])
    assert "no output" in str(e.value) and not TASK_OUTCOME.search(str(e.value))


def test_the_key_is_required_in_this_process(monkeypatch):
    monkeypatch.delenv("RUNWAY_API_KEY", raising=False)
    with pytest.raises(SystemExit) as e:
        rt.api_key()
    assert "RUNWAY_API_KEY" in str(e.value) and "op run" in str(e.value)


def test_the_task_id_is_logged_to_stderr_right_after_the_post_and_is_never_a_refusal():
    api, logged = Api(["RUNNING", "SUCCEEDED"]), []

    def log(line):
        logged.append((line, len(api.calls)))
    rt.submit_and_wait({"model": "kling_4"}, req=api, sleep=lambda s: None, log=log)
    assert ("submitted kling_4 as task 0a1b2c3d", 1) in logged          # after the POST, before any GET
    assert not any(TASK_OUTCOME.search(line) for line, _ in logged)

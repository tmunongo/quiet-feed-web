import importlib
import io
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def smoke(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("container_smoke")


@pytest.mark.parametrize("session_survives", [True, False])
def test_restart_waits_for_slow_arm64_startup(smoke, monkeypatch, session_survives):
    clock = SimpleNamespace(now=0, ready_at=0, restarts=0)

    def sleep(seconds):
        clock.now += seconds

    def docker(*args):
        if args[0] == "image":
            return "arm64"
        if args[0] == "start":
            clock.ready_at = clock.now
        if args[0] == "restart":
            clock.restarts += 1
            clock.ready_at = clock.now + 12
        if args[0] == "port":
            return f"127.0.0.1:{30000 + clock.restarts}"
        if args[0] == "exec":
            return "1"
        return ""

    def open_url(url, data=None, timeout=None):
        if clock.now < clock.ready_at:
            raise urllib.error.URLError("Connection refused during startup")
        if url.endswith("/healthz"):
            body = b'{"status":"ok"}'
        else:
            body = b'<input name="csrf_token" value="token">Existing story'
        response = io.BytesIO(body)
        response.status = 200
        response.geturl = lambda: (
            url
            if session_survives or not url.endswith("/feeds")
            else url.replace("/feeds", "/login")
        )
        return response

    monkeypatch.setattr(smoke, "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep))
    monkeypatch.setattr(smoke, "docker", docker)
    monkeypatch.setattr(smoke, "seed_legacy", lambda path, *_: path)
    monkeypatch.setattr(smoke.subprocess, "run", lambda *_, **__: None)
    monkeypatch.setattr(
        smoke.urllib.request, "build_opener", lambda *_: SimpleNamespace(open=open_url)
    )
    monkeypatch.setattr(sys, "argv", ["container_smoke.py"])

    if session_survives:
        smoke.main()
        assert clock.restarts == 6
    else:
        with pytest.raises(AssertionError):
            smoke.main()
        assert clock.restarts == 1


def test_readiness_times_out_with_last_connection_error(smoke, monkeypatch):
    clock = SimpleNamespace(now=0)
    error = urllib.error.URLError("Connection refused during startup")

    def sleep(seconds):
        clock.now += seconds

    def open_url(*_, **__):
        raise error

    monkeypatch.setattr(smoke, "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep))

    with pytest.raises(RuntimeError, match="within 60 seconds") as result:
        smoke.wait_until_healthy(SimpleNamespace(open=open_url), "http://127.0.0.1:3000")

    assert result.value.__cause__ is error
    assert 60 <= clock.now < 61

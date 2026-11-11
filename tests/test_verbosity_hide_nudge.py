"""TOKEN_OPTIMIZER_HIDE_NUDGE hides the nudge's on-screen echo, never the nudge.

The lean-output nudge is model-steering additionalContext. Hiding it sets the
hook's ``suppressOutput`` and leaves ``additionalContext`` untouched, so the
model is still steered. Env beats config.json ``hide_nudge``; 0/false/empty
mean "show it".
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "skills" / "token-optimizer" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

LIVE_SID = "0e37aafe-6625-457c-9d94-68e7ea73e45c"


@pytest.fixture
def m(monkeypatch, tmp_path):
    monkeypatch.setenv("TOKEN_OPTIMIZER_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.delenv("TOKEN_OPTIMIZER_HIDE_NUDGE", raising=False)
    if "measure" in sys.modules:
        del sys.modules["measure"]
    mod = importlib.import_module("measure")
    importlib.reload(mod)
    yield mod
    if "measure" in sys.modules:
        del sys.modules["measure"]


def _fire(m, monkeypatch, tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"quality-cache-{LIVE_SID}.json"
    cache_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(m, "_quality_cache_path_for", lambda fp=None: cache_path)
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps({"type": "assistant", "message": {"usage": {"output_tokens": 800}}})
                  for _ in range(3)),
        encoding="utf-8")
    cache = {"fill_pct": 47, "score": 73, "session_efficiency": 60,
             "nudge_count": 0, "last_nudge_time": 0}
    monkeypatch.setattr(m, "_read_quality_cache", lambda cp: cache)
    monkeypatch.setattr(m, "_find_current_session_jsonl", lambda: transcript)
    monkeypatch.setattr(m, "_log_savings_event", lambda *a, **k: None)
    out = m.run_verbosity_steer(transcript_path=str(transcript), quiet=True, session_id=LIVE_SID)
    assert out, "fixture sanity: the nudge should fire"
    return json.loads(out)


def test_default_shows_the_nudge(m, monkeypatch, tmp_path):
    payload = _fire(m, monkeypatch, tmp_path)
    assert "suppressOutput" not in payload
    assert payload["hookSpecificOutput"]["additionalContext"]


def test_env_hides_echo_but_keeps_steering(m, monkeypatch, tmp_path):
    monkeypatch.setenv("TOKEN_OPTIMIZER_HIDE_NUDGE", "1")
    payload = _fire(m, monkeypatch, tmp_path)
    assert payload["suppressOutput"] is True
    assert "spartan" in payload["hookSpecificOutput"]["additionalContext"], "must still steer the model"


@pytest.mark.parametrize("val", ["0", "false", "off", "no", ""])
def test_falsy_env_shows_it(m, monkeypatch, tmp_path, val):
    monkeypatch.setenv("TOKEN_OPTIMIZER_HIDE_NUDGE", val)
    assert "suppressOutput" not in _fire(m, monkeypatch, tmp_path)


def test_config_key_hides_when_env_unset(m, monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_read_config_flag", lambda key, default=None: key == "hide_nudge")
    assert _fire(m, monkeypatch, tmp_path)["suppressOutput"] is True


def test_env_beats_config(m, monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_read_config_flag", lambda key, default=None: key == "hide_nudge")
    monkeypatch.setenv("TOKEN_OPTIMIZER_HIDE_NUDGE", "0")
    assert "suppressOutput" not in _fire(m, monkeypatch, tmp_path)

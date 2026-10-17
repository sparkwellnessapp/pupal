"""[Oct 17 rulings §4] the spend guard: eval runs spend ONLY on Vertex, never on the Anthropic
direct API. No provider is called here."""
from __future__ import annotations

import os

import pytest

from tests.eval_common import eval_key


def _settings(monkeypatch, route="vertex", key=""):
    from pydantic import SecretStr

    from app.config import settings
    monkeypatch.setattr(settings, "claude_route", route)
    monkeypatch.setattr(settings, "anthropic_api_key", SecretStr(key) if key is not None else None)


def test_require_refuses_without_the_launcher(monkeypatch):
    monkeypatch.delenv("VIVI_EVAL_ROUTE", raising=False)
    _settings(monkeypatch)
    with pytest.raises(SystemExit, match="runs on Vertex unless"):
        eval_key.require_eval_key()


def test_require_refuses_the_direct_route(monkeypatch):
    monkeypatch.setenv("VIVI_EVAL_ROUTE", "vertex")
    _settings(monkeypatch, route="direct")
    with pytest.raises(SystemExit, match="Anthropic direct eval spend is ZERO"):
        eval_key.require_eval_key()


def test_require_refuses_a_visible_anthropic_key(monkeypatch):
    monkeypatch.setenv("VIVI_EVAL_ROUTE", "vertex")
    _settings(monkeypatch, key="sk-ant-test")
    with pytest.raises(SystemExit, match="must be blank"):
        eval_key.require_eval_key()


def test_require_passes_on_vertex_with_no_key(monkeypatch):
    monkeypatch.setenv("VIVI_EVAL_ROUTE", "vertex")
    _settings(monkeypatch)
    eval_key.require_eval_key()


def test_the_launcher_sets_vertex_and_blanks_the_key(monkeypatch):
    for k in ("CLAUDE_ROUTE", "ANTHROPIC_API_KEY", "VIVI_EVAL_ROUTE"):
        monkeypatch.setenv(k, "before")                 # restored at teardown
    eval_key.load_eval_route()
    assert os.environ["CLAUDE_ROUTE"] == "vertex"
    assert os.environ["ANTHROPIC_API_KEY"] == ""
    assert os.environ["VIVI_EVAL_ROUTE"] == "vertex"


# ── [owner ruling B, 2026-10-17] an owner-ruled run on the direct API, on the EVAL key only ──

def _env_file(tmp_path, body):
    p = tmp_path / "vivi-eval.env"
    p.write_text(body, encoding="utf-8")
    return p


def test_the_direct_launcher_loads_the_eval_key_from_its_file(monkeypatch, tmp_path):
    for k in ("CLAUDE_ROUTE", "ANTHROPIC_API_KEY", "VIVI_EVAL_ROUTE"):
        monkeypatch.setenv(k, "before")
    eval_key.load_direct_route(_env_file(tmp_path, '# eval only\nANTHROPIC_API_KEY="sk-ant-eval"\n'))
    assert os.environ["CLAUDE_ROUTE"] == "direct"
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-eval"
    assert os.environ["VIVI_EVAL_ROUTE"] == "direct"


@pytest.mark.parametrize("body", [None, "OTHER=1\n", "ANTHROPIC_API_KEY=\n"])
def test_the_direct_launcher_refuses_without_an_eval_key(monkeypatch, tmp_path, body):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-dotenv")    # never a fallback
    path = tmp_path / "vivi-eval.env" if body is None else _env_file(tmp_path, body)
    with pytest.raises(SystemExit, match="Nothing was spent"):
        eval_key.load_direct_route(path)


def test_require_passes_on_the_direct_route_with_the_loaded_key(monkeypatch):
    monkeypatch.setenv("VIVI_EVAL_ROUTE", "direct")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-eval")
    _settings(monkeypatch, route="direct", key="sk-ant-eval")
    eval_key.require_eval_key()


@pytest.mark.parametrize("route,key", [("vertex", "sk-ant-eval"),          # route disagrees
                                       ("direct", "sk-ant-other"),         # not the loaded key
                                       ("direct", "")])                    # no key at all
def test_require_refuses_a_direct_run_that_disagrees(monkeypatch, route, key):
    monkeypatch.setenv("VIVI_EVAL_ROUTE", "direct")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-eval")
    _settings(monkeypatch, route=route, key=key)
    with pytest.raises(SystemExit, match="Nothing was spent"):
        eval_key.require_eval_key()

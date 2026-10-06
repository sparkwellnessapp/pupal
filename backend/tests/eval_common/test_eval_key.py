"""[Oct 6 rulings §2] the spend guard: a run spends ONLY on the eval key."""
from __future__ import annotations

import pytest

from tests.eval_common import eval_key


def test_require_refuses_without_the_launcher(monkeypatch):
    monkeypatch.delenv("VIVI_EVAL_KEY_SHA256", raising=False)
    with pytest.raises(SystemExit, match="eval key"):
        eval_key.require_eval_key()


def test_require_refuses_a_different_key(monkeypatch):
    monkeypatch.setenv("VIVI_EVAL_KEY_SHA256", eval_key._sha("not-the-settings-key"))
    with pytest.raises(SystemExit, match="eval key"):
        eval_key.require_eval_key()


def test_load_reads_the_file_and_never_echoes_it(tmp_path, monkeypatch, capsys):
    f = tmp_path / "vivi-eval.env"
    f.write_text("# eval\nANTHROPIC_API_KEY=sk-test-123\n", encoding="utf-8")
    monkeypatch.setenv("VIVI_EVAL_ENV", str(f))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("VIVI_EVAL_KEY_SHA256", raising=False)   # restored at teardown
    eval_key.load_eval_key()
    import os
    assert os.environ["VIVI_EVAL_KEY_SHA256"] == eval_key._sha("sk-test-123")
    assert "sk-test-123" not in capsys.readouterr().out
    monkeypatch.setenv("VIVI_EVAL_ENV", str(tmp_path / "missing.env"))
    with pytest.raises(SystemExit, match="Nothing was spent"):
        eval_key.load_eval_key()

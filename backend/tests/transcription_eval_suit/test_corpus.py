"""corpus.py + runner.discover_fixtures — the subject / teacher layout (2026-11-09).

Built on a temporary corpus (no real student file is read):

    pdfs/cs/hobby.a.pdf  pdfs/cs/hobby.b.pdf  pdfs/cs/rec.c.pdf (no GT yet)
    pdfs/math/ori/gd.s01.pdf  pdfs/math/ori/gd.s02.pdf  pdfs/math/other/alg.x.pdf
    draft_benchmarks/cs/hobby.{a,b}.md  draft_benchmarks/math/ori/gd.s01.md
    raw_benchmarks/hobby.{a,b}.md  raw_benchmarks/gd.s01.md  raw_benchmarks/alg.x.md
"""
from __future__ import annotations

import pytest

from . import corpus
from . import runner


@pytest.fixture
def suite(tmp_path, monkeypatch):
    files = [
        "pdfs/cs/hobby.a.pdf", "pdfs/cs/hobby.b.pdf", "pdfs/cs/rec.c.pdf",
        "pdfs/math/ori/gd.s01.pdf", "pdfs/math/ori/gd.s02.pdf", "pdfs/math/other/alg.x.pdf",
        "draft_benchmarks/cs/hobby.a.md", "draft_benchmarks/cs/hobby.b.md",
        "draft_benchmarks/math/ori/gd.s01.md",
        "raw_benchmarks/hobby.a.md", "raw_benchmarks/hobby.b.md",
        "raw_benchmarks/gd.s01.md", "raw_benchmarks/alg.x.md",
    ]
    for f in files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    monkeypatch.setattr(corpus, "SUITE_DIR", tmp_path)
    return tmp_path


def test_lookup_is_by_doc_id_at_any_depth(suite):
    assert corpus.pdf_path("gd.s01") == suite / "pdfs/math/ori/gd.s01.pdf"
    assert corpus.draft_path("hobby.a") == suite / "draft_benchmarks/cs/hobby.a.md"
    assert corpus.raw_path("hobby.a") == suite / "raw_benchmarks/hobby.a.md"
    assert corpus.draft_path("rec.c") is None


def test_a_doc_id_found_twice_is_refused(suite):
    (suite / "pdfs/math/ori/hobby.a.pdf").write_text("dup", encoding="utf-8")
    with pytest.raises(corpus.CorpusError, match="unique"):
        corpus.pdf_path("hobby.a")


def test_scope_is_the_folder(suite):
    assert corpus.scope_of(suite / "pdfs/math/ori/gd.s01.pdf", "pdfs") == ("math", "ori")
    assert corpus.scope_of(suite / "draft_benchmarks/cs/hobby.a.md", "draft_benchmarks") == ("cs", None)


def test_docs_in_scope(suite):
    assert corpus.docs_in_scope("cs") == ["hobby.a", "hobby.b", "rec.c"]
    assert corpus.docs_in_scope("math", "ori") == ["gd.s01", "gd.s02"]
    assert corpus.docs_in_scope("math") == ["alg.x", "gd.s01", "gd.s02"]
    assert len(corpus.docs_in_scope()) == 6


def test_bad_scopes_are_refused(suite):
    with pytest.raises(corpus.CorpusError, match="needs its subject"):
        corpus.docs_in_scope(None, "ori")
    with pytest.raises(corpus.CorpusError, match="unknown subject"):
        corpus.docs_in_scope("physics")
    with pytest.raises(corpus.CorpusError, match="no corpus folder"):
        corpus.docs_in_scope("math", "nobody")


def test_discovery_keeps_what_the_mode_needs_and_names_the_rest(suite):
    run, skipped = runner.discover_fixtures("per_doc", subject="cs")
    assert run == ["hobby.a", "hobby.b"]
    assert skipped == {"raw": ["rec.c"], "draft": ["rec.c"]}
    run, skipped = runner.discover_fixtures("per_doc", subject="math", user="ori")
    assert run == ["gd.s01"] and skipped == {"raw": ["gd.s02"], "draft": ["gd.s02"]}
    # p1_only needs no draft GT; p2_only needs no PDF
    assert runner.discover_fixtures("p1_only", subject="math")[0] == ["alg.x", "gd.s01"]
    assert runner.discover_fixtures("p2_only")[0] == ["gd.s01", "hobby.a", "hobby.b"]


def test_no_scope_is_the_historical_default(suite):
    """Unscoped per_doc = every doc with a PDF, raw and draft GT — the old
    «all in raw_benchmarks/» set whenever every raw doc is complete."""
    run, _ = runner.discover_fixtures("per_doc")
    assert run == ["gd.s01", "hobby.a", "hobby.b"]


def test_cap_is_deterministic_and_interleaves_exams():
    docs = [f"a.{i}" for i in range(5)] + [f"b.{i}" for i in range(2)] + ["c.0"]
    kept, dropped = corpus.cap(docs, 4)
    assert kept == ["a.0", "a.1", "b.0", "c.0"]            # one of each exam, then round two
    assert dropped == ["a.2", "a.3", "a.4", "b.1"]
    assert corpus.cap(docs, 4) == (kept, dropped)            # same set every time
    assert corpus.cap(docs, 0) == (sorted(docs), [])         # 0 = no cap
    assert corpus.cap(docs, 99) == (sorted(docs), [])
    assert corpus.DEFAULT_MAX_FIXTURES == 20

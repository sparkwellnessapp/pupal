"""A-7 — the known-failures allowlist and the gate's DB rule (tests/known_failures.py)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests import known_failures as kf

BACKEND = Path(__file__).resolve().parents[1]


def test_every_pinned_name_points_at_a_real_test():
    known = kf.load_known_failures()
    assert known, "the allowlist is loaded"
    for nid in known:
        file, _, rest = nid.partition("::")
        func = re.split(r"[\[:]", rest, maxsplit=1)[0]
        path = BACKEND / file
        assert path.exists(), nid
        assert re.search(rf"^\s*(async\s+)?def {re.escape(func)}\(", path.read_text(encoding="utf-8"),
                         re.M), nid


def test_every_pinned_name_carries_a_defect_id_and_a_base_commit():
    for nid, reason in kf.load_known_failures().items():
        assert re.search(r"\bD-\d+\b", reason), nid
        assert re.search(r"\bbase [0-9a-f]{7,}\b", reason), nid


def test_the_parser_reads_ids_and_reasons_and_skips_comments(tmp_path):
    f = tmp_path / "k.txt"
    f.write_text("# header\n\n tests/a.py::t[x]   # D-1 · why · base abc1234\n"
                 "tests/b.py::u\n", encoding="utf-8")
    assert kf.load_known_failures(f) == {
        "tests/a.py::t[x]": "D-1 · why · base abc1234",
        "tests/b.py::u": "pinned in KNOWN_FAILURES.txt"}


class _Item:
    def __init__(self, nodeid):
        self.nodeid, self.markers = nodeid, []

    def add_marker(self, m):
        self.markers.append(m)


def test_only_the_exact_listed_id_is_excused():
    items = [_Item("tests/a.py::t[x]"), _Item("tests/a.py::t[y]"), _Item("tests/a.py::t")]
    marked = kf.mark_known_failures(items, {"tests/a.py::t[x]": "D-1"})
    assert marked == ["tests/a.py::t[x]"]
    (m,) = items[0].markers
    assert m.name == "xfail" and m.kwargs["strict"] is True
    assert items[1].markers == [] and items[2].markers == []


def test_a_stale_entry_is_found_only_where_its_file_was_collected_whole():
    known = {"tests/a.py::gone": "D-1", "tests/b.py::gone": "D-2", "tests/c.py::gone": "D-3"}
    collected = ["tests/a.py::t", "tests/c.py::t"]
    assert kf.stale_entries(known, collected) == ["tests/a.py::gone", "tests/c.py::gone"]
    assert kf.stale_entries(known, collected, narrowed_files=["tests/c.py"]) == ["tests/a.py::gone"]


def test_the_probe_reports_an_unreachable_database():
    why = kf.probe_database("postgresql+asyncpg://u:p@127.0.0.1:1/x", timeout_s=3)
    assert why is not None and why
    assert kf.probe_database(None) == "no DATABASE_URL"


@pytest.mark.parametrize("value,gate", [("", False), ("0", False), ("false", False),
                                        ("1", True), ("yes", True)])
def test_the_gate_switch(monkeypatch, value, gate):
    monkeypatch.setenv(kf.GATE_ENV, value)
    assert kf.is_gate_run() is gate

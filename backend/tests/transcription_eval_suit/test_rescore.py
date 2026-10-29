"""rescore.py reads what runner._write_outputs wrote: the key spelling must invert."""
import json

from .rescore import _key
from .runner import _write_outputs


def test_answer_keys_round_trip_through_the_outputs_file(tmp_path):
    keys = [(1, "א"), (2, None), (3, "ב.2")]
    _write_outputs(tmp_path, {"doc__rep0": {"pages": {1: "x"}, "answers": {k: "t" for k in keys}}})
    written = json.loads((tmp_path / "outputs" / "doc__rep0.json").read_text(encoding="utf-8"))
    assert sorted(_key(k) for k in written["answers"]) == sorted(keys, key=str) or \
        set(_key(k) for k in written["answers"]) == set(keys)

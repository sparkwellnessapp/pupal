"""[grader-v6 MVC] the frontend's v6 review fixture is a CAPTURE of what the server
returns (`GradedTestV6Response` for a real v6 draft), never a hand-written mirror: it is
regenerated here and compared byte for byte, so a change to the response shape, the
review model or the pricer that the frontend has not seen fails this test."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gen_v6_review_fixture.py"


def test_v6_review_fixture_regenerates_clean():
    spec = importlib.util.spec_from_file_location("gen_v6_review_fixture", SCRIPT)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    assert gen.OUT.exists(), "v6_review_hobby.json missing — run scripts/gen_v6_review_fixture.py"
    assert gen.OUT.read_text(encoding="utf-8") == gen.build(), (
        "v6_review_hobby.json is stale — run scripts/gen_v6_review_fixture.py")

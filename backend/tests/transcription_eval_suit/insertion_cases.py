"""
insertion_cases.py — load and VALIDATE the owner's arrow ground truth.

`insertion_cases.json` is owner-authored and complete (MISSION §3). This module
never edits it; it answers one question per case — is this case consistent with
the raw GT it points into and the draft GT it claims to produce? — and reports
every failure BY CASE ID, so the owner knows exactly which anchor or which GT
file to fix (§3.4).

The location checks run the PRODUCTION relocation function (relocation.py)
rather than a second implementation: if the validator and the function
disagreed about what a well-formed case is, the metrics built on them would
measure the disagreement instead of the model.

Usage (from backend/):
    python -m tests.transcription_eval_suit.insertion_cases          # validate all
Exit 0 = every case valid, 1 = at least one failure.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.services.transcription.normalize import normalize
from app.services.transcription.two_phase.relocation import (
    ATTACH_CLOSE, ATTACH_OPEN, ATTACHMENT, INSERTION, Instruction, find_all,
    relocate, strip_ws,
)

from .ground_truth import load_ground_truth, load_page_ground_truth
from .keys import normalize_key

SUITE_DIR = Path(__file__).parent
CASES_PATH = SUITE_DIR / "insertion_cases.json"
ID_RE = re.compile(r"^[a-z0-9_.]+#\d{2}$")
KINDS = (INSERTION, ATTACHMENT, "decoy")
MARKERS = ("arrow", "asterisk", "caret", "numbered_star", "continuation_note", "other")


@dataclass(frozen=True)
class Case:
    raw: dict

    @property
    def id(self) -> str:
        return self.raw.get("id", "")

    @property
    def fixture(self) -> str:
        return self.raw.get("fixture", "")

    @property
    def kind(self) -> str:
        return self.raw.get("kind", "")

    def instruction(self) -> Instruction:
        """The case as the relocation function's input (non-decoys only)."""
        src, tgt = self.raw["source"], self.raw["target"]
        return Instruction(
            id=self.id, kind=self.kind,
            source_page=int(src["page"]), target_page=int(tgt["page"]),
            source_text=src["text"],
            after=tgt.get("after"), before=tgt.get("before"), line=tgt.get("line"),
            marker=self.raw.get("marker", "other"),
        )


@dataclass
class Report:
    failures: dict[str, list[str]] = field(default_factory=dict)
    checked: int = 0

    def fail(self, case_id: str, msg: str) -> None:
        self.failures.setdefault(case_id or "<no id>", []).append(msg)

    @property
    def ok(self) -> bool:
        return not self.failures


def load_cases(path: Path = CASES_PATH) -> list[Case]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Case(c) for c in data.get("cases", [])]


def cases_for(fixture: str, path: Path = CASES_PATH) -> list[Case]:
    return [c for c in load_cases(path) if c.fixture == fixture]


def _draft_answer(fixture: str, answer_key: str) -> str | None:
    m = re.fullmatch(r"Q(\d+)(?:\.(.+))?", answer_key.strip())
    if not m:
        return None
    want = normalize_key((int(m.group(1)), m.group(2)))
    doc = load_ground_truth(SUITE_DIR / "draft_benchmarks" / f"{fixture}.md")
    for a in doc.answers:
        if normalize_key(a.key) == want:
            return a.answer_text
    return None


def _norm(s: str) -> str:
    return normalize(s, strip_illegible=False)


def validate(path: Path = CASES_PATH) -> Report:
    rep = Report()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        rep.fail("<file>", f"cannot load {path.name}: {e}")
        return rep
    if data.get("version") != 1:
        rep.fail("<file>", f"version is {data.get('version')!r}, expected 1")
    cases = [Case(c) for c in data.get("cases", [])]
    seen: set[str] = set()
    by_fixture: dict[str, list[Case]] = {}

    for c in cases:
        rep.checked += 1
        cid = c.id
        # --- schema + identity ---
        if not ID_RE.match(cid or ""):
            rep.fail(cid, f"id {cid!r} does not match {ID_RE.pattern}")
        elif cid.split("#")[0] != c.fixture:
            rep.fail(cid, f"id prefix {cid.split('#')[0]!r} != fixture {c.fixture!r}")
        if cid in seen:
            rep.fail(cid, "duplicate id")
        seen.add(cid)
        if c.kind not in KINDS:
            rep.fail(cid, f"kind {c.kind!r} not in {KINDS}")
            continue
        if c.raw.get("marker") not in MARKERS:
            rep.fail(cid, f"marker {c.raw.get('marker')!r} not in {MARKERS}")
        raw_p = SUITE_DIR / "raw_benchmarks" / f"{c.fixture}.md"
        if not raw_p.exists():
            rep.fail(cid, f"fixture {c.fixture!r} has no raw GT")
            continue
        pages = load_page_ground_truth(raw_p).as_dict()
        by_fixture.setdefault(c.fixture, []).append(c)

        if c.kind == "decoy":
            page, near = c.raw.get("page"), c.raw.get("near", "")
            if page not in pages:
                rep.fail(cid, f"decoy page {page!r} not in raw GT")
            elif len(find_all(pages[page], near)) != 1:
                rep.fail(cid, f"decoy `near` occurs {len(find_all(pages[page], near))} "
                              f"times on raw page {page} (needs exactly one)")
            continue

        # --- non-decoy: required fields ---
        try:
            src, tgt = c.raw["source"], c.raw["target"]
            sp, tp = int(src["page"]), int(tgt["page"])
            stext = src["text"]
        except (KeyError, TypeError, ValueError) as e:
            rep.fail(cid, f"schema: missing/invalid field ({e})")
            continue
        if c.kind == INSERTION and not ("after" in tgt and "before" in tgt):
            rep.fail(cid, "schema: insertion target needs `after` and `before`")
            continue
        if c.kind == ATTACHMENT and "line" not in tgt:
            rep.fail(cid, "schema: attachment target needs `line`")
            continue
        answer_key = c.raw.get("answer_key", "")
        draft_body = _draft_answer(c.fixture, answer_key)
        if draft_body is None:
            rep.fail(cid, f"answer_key {answer_key!r} not in the draft GT")

        # --- verbatim location against the raw GT ---
        if sp not in pages or tp not in pages:
            rep.fail(cid, f"source page {sp} or target page {tp} not in raw GT")
            continue
        n_src = len(find_all(pages[sp], stext))
        if n_src != 1:
            rep.fail(cid, f"source.text occurs {n_src} times on raw page {sp} "
                          f"(needs exactly one): {stext!r}")
        if c.kind == INSERTION:
            after, before = tgt.get("after") or "", tgt.get("before") or ""
            if not strip_ws(after) and not strip_ws(before):
                rep.fail(cid, "insertion target: both `after` and `before` empty")
            else:
                n = len(find_all(pages[tp], after + before))
                if n != 1:
                    rep.fail(cid, f"target after+before occurs {n} times on raw page "
                                  f"{tp} (needs exactly one): after={after!r} "
                                  f"before={before!r}")
        else:
            want = strip_ws(tgt.get("line") or "")
            n = sum(1 for ln in pages[tp].split("\n") if strip_ws(ln) == want)
            if n != 1:
                rep.fail(cid, f"target.line is a complete line {n} times on raw page "
                              f"{tp} (needs exactly one): {tgt.get('line')!r}")

        # --- draft conformance, LOCAL to the answer (§3.4) ---
        if draft_body is not None:
            body = draft_body
            if c.kind == INSERTION:
                want = _norm((tgt.get("after") or "") + stext + (tgt.get("before") or ""))
                label = "after + source + before"
                # §3.4 checks each case LOCALLY, which does not compose when an
                # attachment ends the very line an insertion follows (itay_katav:
                # `…count]; ⟦note⟧` then the inserted loop). An attachment is
                # orthogonal content, so the insertion is checked with ⟦…⟧ removed.
                body = re.sub(f"\\s*{ATTACH_OPEN}[^{ATTACH_CLOSE}]*{ATTACH_CLOSE}", "", body)
            else:
                want = _norm((tgt.get("line") or "") + ATTACH_OPEN + stext + ATTACH_CLOSE)
                label = "line + ⟦source⟧"
            if want not in _norm(body):
                rep.fail(cid, f"draft conformance: normalized `{label}` is not a "
                              f"substring of draft {answer_key}")

    # --- §3.3 step 2 over each fixture's full case set (incl. cross-case overlap) ---
    for fixture, fcases in by_fixture.items():
        live = [c for c in fcases if c.kind in (INSERTION, ATTACHMENT)]
        if not live:
            continue
        pages = load_page_ground_truth(
            SUITE_DIR / "raw_benchmarks" / f"{fixture}.md").as_dict()
        try:
            res = relocate(pages, [c.instruction() for c in live])
        except (KeyError, TypeError, ValueError) as e:
            rep.fail(fixture, f"relocation could not run: {e}")
            continue
        for r in res.rejected:
            rep.fail(r.id, f"§3.3 step 2 rejects it: {r.reason}")
    return rep


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    rep = validate()
    print(f"insertion_cases.json — {rep.checked} case(s) checked")
    if rep.ok:
        print("VALID: every case locates, applies, and conforms to its draft GT.")
        return 0
    for cid, msgs in rep.failures.items():
        print(f"\n✗ {cid}")
        for m in dict.fromkeys(msgs):
            print(f"    - {m}")
    print(f"\n{len(rep.failures)} case(s) failing. The file and the GT are the "
          f"owner's (§17.7): surface with evidence, never edit.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

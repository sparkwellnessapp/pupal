"""
corpus.py — where a fixture's files live: the ONE place that spells the corpus layout.

    pdfs/<subject>[/<user>]/<doc_id>.pdf
    draft_benchmarks/<subject>[/<user>]/<doc_id>.md
    raw_benchmarks/<doc_id>.md          (not mirrored yet; any depth resolves the same)

`<subject>` is one of SUBJECTS; `<user>` is an optional teacher folder (`math/ori_yefet`).
A doc_id is UNIQUE across the whole corpus — every lookup is by doc_id at any depth, so a
file can move between folders without its fixtures, exams or results changing, and a
doc_id found twice is refused rather than guessed (two ground truths for one document).

The scope (subject, user) is read from the folder a doc's PDF or draft GT sits in.
raw_benchmarks/ is flat, so it never decides a scope — a scoped run takes its docs from
pdfs/ and draft_benchmarks/, then keeps only those carrying the GT its mode needs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

SUITE_DIR = Path(__file__).resolve().parent
SUBJECTS = ("cs", "math")

#: The fixtures one trial (one repeat) runs when the caller names no doc_ids.
DEFAULT_MAX_FIXTURES = 20


class CorpusError(ValueError):
    pass


def _matches(root: Path, doc_id: str, suffix: str) -> list[Path]:
    if not root.exists():
        return []
    want = doc_id.lower()
    return [p for p in root.rglob(f"*{suffix}") if p.stem.lower() == want]


def _one(root: Path, doc_id: str, suffix: str) -> Optional[Path]:
    hits = _matches(root, doc_id, suffix)
    if len(hits) > 1:
        raise CorpusError(f"{doc_id}: found {len(hits)} times under {root.name}/ "
                          f"({', '.join(str(h.relative_to(root)) for h in hits)}) — a doc_id is unique")
    return hits[0] if hits else None


def pdf_path(doc_id: str, pdf_dir: str = "pdfs") -> Optional[Path]:
    """The source PDF, at any depth under `pdf_dir` (a flat variant corpus works too)."""
    return _one(SUITE_DIR / pdf_dir, doc_id, ".pdf")


def draft_path(doc_id: str) -> Optional[Path]:
    return _one(SUITE_DIR / "draft_benchmarks", doc_id, ".md")


def raw_path(doc_id: str) -> Optional[Path]:
    return _one(SUITE_DIR / "raw_benchmarks", doc_id, ".md")


def draft_paths() -> list[Path]:
    """Every draft GT in the corpus, sorted by doc_id."""
    root = SUITE_DIR / "draft_benchmarks"
    return sorted(root.rglob("*.md"), key=lambda p: p.stem) if root.exists() else []


def scope_of(path: Path, root_name: str) -> tuple[Optional[str], Optional[str]]:
    """(subject, user) from where `path` sits under SUITE_DIR/<root_name>."""
    parts = path.resolve().relative_to((SUITE_DIR / root_name).resolve()).parts[:-1]
    return (parts[0] if parts else None, parts[1] if len(parts) > 1 else None)


def _scope_root(root_name: str, subject: Optional[str], user: Optional[str]) -> Path:
    root = SUITE_DIR / root_name
    if subject:
        root = root / subject
    if user:
        root = root / user
    return root


def docs_in_scope(subject: Optional[str] = None, user: Optional[str] = None,
                  pdf_dir: str = "pdfs") -> list[str]:
    """Every doc_id in the scope: no scope = the whole corpus (PDFs, draft and raw GT);
    a scope = the docs whose PDF or draft GT sits under <root>/<subject>[/<user>]."""
    if user and not subject:
        raise CorpusError("a user folder needs its subject (e.g. --subject math --user ori_yefet)")
    if subject and subject not in SUBJECTS:
        raise CorpusError(f"unknown subject {subject!r}; known: {', '.join(SUBJECTS)}")
    roots = [_scope_root(pdf_dir, subject, user), _scope_root("draft_benchmarks", subject, user)]
    if not subject:
        roots.append(SUITE_DIR / "raw_benchmarks")
    if subject and not any(r.exists() for r in roots):
        raise CorpusError(f"no corpus folder for {'/'.join(x for x in (subject, user) if x)} "
                          f"under {pdf_dir}/ or draft_benchmarks/")
    ids = {p.stem for r in roots if r.exists() for p in r.rglob("*")
           if p.suffix.lower() in (".pdf", ".md") and p.is_file()}
    return sorted(ids)


def cap(doc_ids: Iterable[str], limit: int) -> tuple[list[str], list[str]]:
    """(kept, dropped): at most `limit` docs (0 = no cap), deterministic, interleaved across
    exams (the doc_id prefix before the first '.') so a cap never fills up from one exam.
    Every repeat of a run gets the SAME kept set — repeats must compare like with like."""
    by_exam: dict[str, list[str]] = {}
    for d in sorted(doc_ids):
        by_exam.setdefault(d.split(".", 1)[0], []).append(d)
    order: list[str] = []
    while any(by_exam.values()):
        for exam in sorted(by_exam):
            if by_exam[exam]:
                order.append(by_exam[exam].pop(0))
    if limit <= 0 or len(order) <= limit:
        return sorted(order), []
    return sorted(order[:limit]), sorted(order[limit:])

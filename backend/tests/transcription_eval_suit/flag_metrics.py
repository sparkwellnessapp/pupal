"""
flag_metrics.py — the TRUST-GATE instrument: score the trust layer's flags
against raw GT.

Separate from scoring.py ON PURPOSE: scoring.py measures the transcription
(accuracy gate, locked); this module measures the FLAGS (does every real error
carry a flag the teacher will see, at what burden). It never touches the
accuracy gate.

Labels: token-diff spans between the baseline P1 pages and raw GT — the same
alignment machinery the flag layer itself uses (app flagging), so labels and
flags live on the same token coordinates. A label is COVERED when any flag
span overlaps it (±1 token slack).

Definitions:
  error_recall      — covered labels / all labels
  critical_recall   — covered code-kind labels / all code-kind labels (the
                      trust-gate number: a critical label is a span whose
                      diff touches operators/structural chars/identifier content)
  flags/doc         — teacher burden, split by severity tier
  precision         — flags overlapping any label / all flags

The correlated-miss tail (all readers reproduce the baseline's error) is the
measured limit of this instrument (~8% of criticals on the golden set); the
brace lint recovers part of it and the rest is documented, not hidden.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.transcription.flagging import (
    FlagSpan,
    LintFinding,
    diff_spans,
    merge_adjacent,
    spans_overlap,
    tokenize,
    _span_kind,  # deliberate package-internal reuse: labels share flag semantics
)

from .ground_truth import GoldPageDocument


@dataclass
class DocFlagScore:
    doc_id: str
    n_labels: int = 0
    n_labels_critical: int = 0
    covered: int = 0
    covered_critical: int = 0
    covered_critical_high: int = 0   # critical labels covered by a WARNING-tier flag
    n_flags: int = 0
    n_flags_high: int = 0
    n_flags_medium: int = 0
    n_flags_info: int = 0
    true_flags: int = 0
    true_flags_high: int = 0         # WARNING-tier flags overlapping any label
    lint_findings: int = 0
    missed_critical: list[dict] = field(default_factory=list)

    @property
    def error_recall(self) -> float:
        return self.covered / self.n_labels if self.n_labels else 1.0

    @property
    def critical_recall(self) -> float:
        return (self.covered_critical / self.n_labels_critical
                if self.n_labels_critical else 1.0)

    @property
    def critical_recall_high(self) -> float:
        """Critical labels covered by the WARNING tier — what the teacher's
        first pass catches (the burden/coverage trade lives here)."""
        return (self.covered_critical_high / self.n_labels_critical
                if self.n_labels_critical else 1.0)

    @property
    def precision(self) -> float:
        return self.true_flags / self.n_flags if self.n_flags else 1.0

    @property
    def precision_high(self) -> float:
        return (self.true_flags_high / self.n_flags_high
                if self.n_flags_high else 1.0)

    def as_dict(self) -> dict:
        return {
            "n_labels": self.n_labels,
            "n_labels_critical": self.n_labels_critical,
            "covered": self.covered,
            "covered_critical": self.covered_critical,
            "covered_critical_high": self.covered_critical_high,
            "error_recall": self.error_recall,
            "critical_recall": self.critical_recall,
            "critical_recall_high": self.critical_recall_high,
            "n_flags": self.n_flags,
            "flags_by_severity": {"high": self.n_flags_high,
                                  "medium": self.n_flags_medium,
                                  "info": self.n_flags_info},
            "precision": self.precision,
            "precision_high": self.precision_high,
            "true_flags": self.true_flags,
            "true_flags_high": self.true_flags_high,
            "lint_findings": self.lint_findings,
            "missed_critical": self.missed_critical,
        }


def score_flags(
    doc_id: str,
    base_pages: dict[int, str],
    raw_gold: GoldPageDocument,
    flags: tuple[FlagSpan, ...] | list[FlagSpan],
    lint: tuple[LintFinding, ...] | list[LintFinding] = (),
) -> DocFlagScore:
    """Pure. Labels are computed per page on the baseline's token stream, then
    matched to the flags' base-side token ranges on the same page."""
    sc = DocFlagScore(doc_id=doc_id)
    gold = raw_gold.as_dict()
    flags_by_page: dict[int, list[FlagSpan]] = {}
    for f in flags:
        flags_by_page.setdefault(f.page, []).append(f)
        sc.n_flags += 1
        if f.severity == "high":
            sc.n_flags_high += 1
        elif f.severity == "medium":
            sc.n_flags_medium += 1
        else:
            sc.n_flags_info += 1
    sc.lint_findings = len(lint)

    flagged_true: set[tuple[int, int, int]] = set()
    flagged_true_high: set[tuple[int, int, int]] = set()
    for pno, gtext in sorted(gold.items()):
        btext = base_pages.get(pno, "")
        if not btext.strip():
            continue  # missing page: a coverage failure, not a flag question
        b_toks = tokenize(btext)
        labels = merge_adjacent(diff_spans(b_toks, tokenize(gtext)))
        page_flags = flags_by_page.get(pno, [])
        for lab in labels:
            kind = _span_kind(lab["base"], lab["other"])
            critical = kind == "code"
            sc.n_labels += 1
            sc.n_labels_critical += critical
            hits = [f for f in page_flags
                    if spans_overlap(lab["i1"], lab["i2"], f.i1, f.i2)]
            if hits:
                sc.covered += 1
                sc.covered_critical += critical
                if critical and any(f.severity == "high" for f in hits):
                    sc.covered_critical_high += 1
                for f in hits:
                    flagged_true.add((f.page, f.i1, f.i2))
                    if f.severity == "high":
                        flagged_true_high.add((f.page, f.i1, f.i2))
            elif critical:
                sc.missed_critical.append({
                    "page": pno,
                    "base": " ".join(lab["base"])[:60],
                    "gt": " ".join(lab["other"])[:60],
                })
    sc.true_flags = len(flagged_true)
    sc.true_flags_high = len(flagged_true_high)
    return sc


def aggregate_flag_scores(scores: list[DocFlagScore]) -> dict:
    """Across docs (and repeats): totals + the trust-gate verdict inputs."""
    tot = DocFlagScore(doc_id="__all__")
    for s in scores:
        tot.n_labels += s.n_labels
        tot.n_labels_critical += s.n_labels_critical
        tot.covered += s.covered
        tot.covered_critical += s.covered_critical
        tot.n_flags += s.n_flags
        tot.n_flags_high += s.n_flags_high
        tot.n_flags_medium += s.n_flags_medium
        tot.n_flags_info += s.n_flags_info
        tot.true_flags += s.true_flags
        tot.lint_findings += s.lint_findings
    n = max(len(scores), 1)
    return {
        "error_recall": tot.error_recall,
        "critical_recall": tot.critical_recall,
        "precision": tot.precision,
        "flags_per_doc": tot.n_flags / n,
        "high_per_doc": tot.n_flags_high / n,
        "medium_per_doc": tot.n_flags_medium / n,
        "info_per_doc": tot.n_flags_info / n,
        "lint_per_doc": tot.lint_findings / n,
        "missed_critical_total": sum(len(s.missed_critical) for s in scores),
    }

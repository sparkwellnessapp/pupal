"""
The pure scoring engine for the transcription eval suite.

Subject-agnostic. Takes a prediction (dict keyed by (q, sub) -> text), a
GoldDocument, and a CriticalProfile; returns a DocumentScore. No I/O.

Three families of measurement:

  1. ACCURACY — normalized difflib ratio, document-level.
       strict  : "[?]" counts as a miss (real teacher-review cost).
       lenient : "[?]" excluded (accuracy of what the model committed to).

  2. SEGMENTATION — coverage + missed/extra keys, AFTER canonical key
     normalization (keys.py), so label-format mismatches ("a" vs "א") don't
     pollute the metric and remaining misses are real routing errors.

  3. CRITICAL TOKENS (V1) — grading-critical fidelity, scored PER ANSWER and
     micro-averaged. Per-answer scoring is load-bearing: a dropped ";" in one
     answer must NOT cancel against a spurious ";" in another, which is exactly
     what a document-level multiset comparison would allow.

THE GATE is a conjunction, not difflib alone (a 0.9959-difflib document was
demonstrated to carry three grading-critical errors):
    doc_ratio_strict >= 0.98
    AND coverage == 1.0
    AND critical-token recalls >= floors AND no abbreviations_altered
gate_pass() encodes it; thresholds live in GateConfig (calibratable, one place).

THE ERROR LABEL (what a flag detector must fire on) is likewise a disjunction:
    is_error = ratio_strict < 0.98  OR  any critical-token miss in the answer.
The difflib clause alone is length-dependent (one bad char in a short answer
trips it; the same char in a long answer does not) and provably misses
grading-critical single-char errors; the critical-token clause is
length-independent and catches them.
"""
from __future__ import annotations

import difflib
from collections import Counter
from dataclasses import dataclass, field

from app.services.transcription.normalize import normalize

from .critical_tokens import CriticalProfile, extract_signature
from .ground_truth import GoldDocument
from .keys import Key, normalize_key

# Difflib threshold used both in the gate and in the per-answer error label.
ERROR_THRESHOLD = 0.98


@dataclass(frozen=True)
class ScoringPolicy:
    """Named, run-stamped knobs that change what the instrument treats as
    grade-relevant. Distinct from PipelineConfig (which configures the
    model-facing pipeline): this configures the SCORER. Recorded verbatim in
    results.json so every run states which scoring semantics produced it.

    case_insensitive_keywords (Change B): fold the letter-case of C# keywords
        (profile.keywords) before token comparison. Defaults ON. This is an
        instrument-semantics change: prior baselines were case-SENSITIVE on
        keywords, so a run with this on is NOT comparable on method_call_recall
        to a run with it off — the RUNLOG marks that break. Folds case only; an
        identifier-content misread stays a miss.

    case_insensitive_method_calls (Change C): fold the letter-case of ALL
        method-call identifiers (not just keywords) before comparison. Defaults
        ON, per Noam's 2026-06-27 ruling that method-name CASE is not a Bagrut
        deduction (this REVERSES the earlier identifier-case-sensitive lock). It
        supersedes case_insensitive_keywords for method_calls. Folds case ONLY —
        a content misread (GetArrShows->GetArrShow) still misses. Another
        comparability break on method_call_recall vs case-SENSITIVE baselines;
        the RUNLOG marks it.
    """
    case_insensitive_keywords: bool = True
    case_insensitive_method_calls: bool = True


# --- result shapes ---------------------------------------------------------------

@dataclass(frozen=True)
class AnswerCritical:
    """Per-answer critical-token comparison (gold vs pred), case-sensitive."""
    operator_recall: float
    operator_precision: float
    structural_recall: float
    structural_precision: float
    method_call_recall: float
    method_call_precision: float
    missed_operators: tuple[str, ...]      # gold tokens absent from pred (with multiplicity)
    missed_structural: tuple[str, ...]
    missed_method_calls: tuple[str, ...]
    abbreviations_altered: tuple[str, ...]  # gold abbreviation count > pred count

    @property
    def has_miss(self) -> bool:
        return bool(
            self.missed_operators
            or self.missed_structural
            or self.missed_method_calls
            or self.abbreviations_altered
        )


@dataclass(frozen=True)
class AnswerScore:
    key: Key
    ratio_strict: float
    ratio_lenient: float
    critical: AnswerCritical
    is_error: bool  # ratio_strict < ERROR_THRESHOLD  OR  critical.has_miss


@dataclass(frozen=True)
class CriticalTokenScore:
    """Document-level micro-average over per-answer comparisons."""
    operator_recall: float
    operator_precision: float
    structural_recall: float
    structural_precision: float
    method_call_recall: float
    method_call_precision: float
    abbreviations_altered: tuple[str, ...]  # union across answers


@dataclass(frozen=True)
class DocumentScore:
    doc_id: str
    doc_ratio_strict: float
    doc_ratio_lenient: float
    coverage: float                 # |matched gold keys| / |gold keys|, canonical keys
    missed_keys: tuple[Key, ...]
    extra_keys: tuple[Key, ...]
    answers: tuple[AnswerScore, ...]
    critical: CriticalTokenScore


@dataclass(frozen=True)
class GateConfig:
    """The conjunctive pass/fail gate. Thresholds calibratable in ONE place.

    Critical-token floors start at 1.0 (zero tolerated misses) — under the
    Bagrut deduction rules every miss is a potential mis-grade, so the burden
    of proof is on relaxing them (with eval evidence), not on meeting them.
    """
    min_doc_ratio_strict: float = ERROR_THRESHOLD
    min_coverage: float = 1.0
    min_operator_recall: float = 1.0
    min_structural_recall: float = 1.0
    min_method_call_recall: float = 1.0
    allow_abbreviation_alteration: bool = False


def gate_pass(score: DocumentScore, cfg: GateConfig = GateConfig()) -> tuple[bool, list[str]]:
    """Evaluate the conjunctive gate. Returns (passed, list of failure reasons)."""
    failures: list[str] = []
    if score.doc_ratio_strict < cfg.min_doc_ratio_strict:
        failures.append(
            f"doc_ratio_strict {score.doc_ratio_strict:.4f} < {cfg.min_doc_ratio_strict}"
        )
    if score.coverage < cfg.min_coverage:
        failures.append(f"coverage {score.coverage:.2f} < {cfg.min_coverage}")
    c = score.critical
    if c.operator_recall < cfg.min_operator_recall:
        failures.append(f"operator_recall {c.operator_recall:.3f} < {cfg.min_operator_recall}")
    if c.structural_recall < cfg.min_structural_recall:
        failures.append(
            f"structural_recall {c.structural_recall:.3f} < {cfg.min_structural_recall}"
        )
    if c.method_call_recall < cfg.min_method_call_recall:
        failures.append(
            f"method_call_recall {c.method_call_recall:.3f} < {cfg.min_method_call_recall}"
        )
    if c.abbreviations_altered and not cfg.allow_abbreviation_alteration:
        failures.append(f"abbreviations_altered: {c.abbreviations_altered}")
    return (not failures, failures)


# --- internals -------------------------------------------------------------------

def _ratio(a: str, b: str) -> float:
    # autojunk=False is LOAD-BEARING. difflib's default (True) silently junks
    # any character occurring in >1% of a sequence >=200 chars — on
    # whitespace-stripped code/Hebrew text that is most characters, and it
    # destroyed real ratios (measured: a 0.88-similar page scored 0.21).
    # Short unit-test strings never trip it; only real pages do.
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _counter_missed(gold: Counter, pred: Counter) -> tuple[str, ...]:
    """Tokens in gold not covered by pred, with multiplicity."""
    missing = gold - pred  # Counter subtraction keeps positive counts only
    out: list[str] = []
    for tok, n in sorted(missing.items()):
        out.extend([tok] * n)
    return tuple(out)


def _score_answer_critical(gold_text: str, pred_text: str,
                           profile: CriticalProfile,
                           policy: ScoringPolicy) -> AnswerCritical:
    fold = policy.case_insensitive_keywords
    fold_id = policy.case_insensitive_method_calls
    g = extract_signature(gold_text, profile, fold_keyword_case=fold, fold_identifier_case=fold_id)
    p = extract_signature(pred_text, profile, fold_keyword_case=fold, fold_identifier_case=fold_id)

    def pr(gold_c: Counter, pred_c: Counter) -> tuple[float, float]:
        matched = sum((gold_c & pred_c).values())
        gn, pn = sum(gold_c.values()), sum(pred_c.values())
        return (matched / pn if pn else 1.0, matched / gn if gn else 1.0)

    op_p, op_r = pr(g.operators, p.operators)
    st_p, st_r = pr(g.structural, p.structural)

    mc_inter = g.method_calls & p.method_calls
    mc_r = len(mc_inter) / len(g.method_calls) if g.method_calls else 1.0
    mc_p = len(mc_inter) / len(p.method_calls) if p.method_calls else 1.0

    return AnswerCritical(
        operator_recall=op_r, operator_precision=op_p,
        structural_recall=st_r, structural_precision=st_p,
        method_call_recall=mc_r, method_call_precision=mc_p,
        missed_operators=_counter_missed(g.operators, p.operators),
        missed_structural=_counter_missed(g.structural, p.structural),
        missed_method_calls=tuple(sorted(g.method_calls - p.method_calls)),
        abbreviations_altered=tuple(
            a for a in profile.abbreviations
            if p.abbreviations[a] < g.abbreviations[a]
        ),
    )


@dataclass
class _MicroAgg:
    """Micro-average accumulator: sums of matched/gold/pred counts over answers."""
    matched_r: int = 0
    total_g: int = 0
    matched_p: int = 0
    total_p: int = 0

    def add(self, gold_c: Counter, pred_c: Counter) -> None:
        m = sum((gold_c & pred_c).values())
        self.matched_r += m
        self.total_g += sum(gold_c.values())
        self.matched_p += m
        self.total_p += sum(pred_c.values())

    def add_sets(self, gold_s: frozenset, pred_s: frozenset) -> None:
        m = len(gold_s & pred_s)
        self.matched_r += m
        self.total_g += len(gold_s)
        self.matched_p += m
        self.total_p += len(pred_s)

    @property
    def recall(self) -> float:
        return self.matched_r / self.total_g if self.total_g else 1.0

    @property
    def precision(self) -> float:
        return self.matched_p / self.total_p if self.total_p else 1.0


# --- entry point -----------------------------------------------------------------

def score_document(
    pred: dict[Key, str],
    gold: GoldDocument,
    *,
    profile: CriticalProfile,
    policy: ScoringPolicy = ScoringPolicy(),
) -> DocumentScore:
    """Score one predicted transcription against ground truth. Pure."""
    # Canonical key normalization on BOTH sides before joining (keys.py).
    gold_map: dict[Key, str] = {}
    gold_order: list[Key] = []
    for a in gold.answers:
        k = normalize_key(a.key)
        gold_map[k] = a.answer_text
        gold_order.append(k)

    pred_map: dict[Key, str] = {}
    for k, v in pred.items():
        nk = normalize_key(k)
        if nk in pred_map:
            # Same canonical key predicted twice (e.g. chunk-boundary fragments
            # upstream failed to merge): concatenate in iteration order rather
            # than silently dropping content.
            pred_map[nk] = pred_map[nk] + "\n" + v
        else:
            pred_map[nk] = v

    gold_keys = set(gold_map)
    pred_keys = set(pred_map)
    matched = [k for k in gold_order if k in pred_keys]
    missed = tuple(k for k in gold_order if k not in pred_keys)
    extra = tuple(sorted(pred_keys - gold_keys, key=lambda k: (k[0], k[1] or "")))
    coverage = len(matched) / len(gold_keys) if gold_keys else 1.0

    # --- per-answer: accuracy + critical tokens + error label ---
    answer_scores: list[AnswerScore] = []
    op_agg, st_agg, mc_agg = _MicroAgg(), _MicroAgg(), _MicroAgg()
    abbrevs_altered: set[str] = set()

    for k in matched:
        g_text, p_text = gold_map[k], pred_map[k]
        rs = _ratio(normalize(g_text, strip_illegible=False),
                    normalize(p_text, strip_illegible=False))
        rl = _ratio(normalize(g_text, strip_illegible=True),
                    normalize(p_text, strip_illegible=True))
        crit = _score_answer_critical(g_text, p_text, profile, policy)

        fold = policy.case_insensitive_keywords
        fold_id = policy.case_insensitive_method_calls
        gs = extract_signature(g_text, profile, fold_keyword_case=fold, fold_identifier_case=fold_id)
        ps = extract_signature(p_text, profile, fold_keyword_case=fold, fold_identifier_case=fold_id)
        op_agg.add(gs.operators, ps.operators)
        st_agg.add(gs.structural, ps.structural)
        mc_agg.add_sets(gs.method_calls, ps.method_calls)
        abbrevs_altered.update(crit.abbreviations_altered)

        answer_scores.append(AnswerScore(
            key=k, ratio_strict=rs, ratio_lenient=rl, critical=crit,
            is_error=(rs < ERROR_THRESHOLD) or crit.has_miss,
        ))

    # --- document accuracy ---
    gold_concat = "\n".join(gold_map[k] for k in gold_order)
    pred_concat = "\n".join(
        [pred_map.get(k, "") for k in gold_order] + [pred_map[k] for k in extra]
    )
    doc_strict = _ratio(normalize(gold_concat, strip_illegible=False),
                        normalize(pred_concat, strip_illegible=False))
    doc_lenient = _ratio(normalize(gold_concat, strip_illegible=True),
                         normalize(pred_concat, strip_illegible=True))

    critical = CriticalTokenScore(
        operator_recall=op_agg.recall, operator_precision=op_agg.precision,
        structural_recall=st_agg.recall, structural_precision=st_agg.precision,
        method_call_recall=mc_agg.recall, method_call_precision=mc_agg.precision,
        abbreviations_altered=tuple(sorted(abbrevs_altered)),
    )

    return DocumentScore(
        doc_id=gold.doc_id,
        doc_ratio_strict=doc_strict,
        doc_ratio_lenient=doc_lenient,
        coverage=coverage,
        missed_keys=missed,
        extra_keys=extra,
        answers=tuple(answer_scores),
        critical=critical,
    )


# ---------------------------------------------------------------------------
# Phase-1 (raw / per-page) scoring
# ---------------------------------------------------------------------------
#
# Phase 1 is a PERCEPTION instrument: image -> verbatim page text. Its scoring
# is the per-question engine minus segmentation-by-key (a page has nothing to
# route): per-page difflib strict/lenient + per-page critical tokens, with the
# same micro-averaged document aggregate and the same error-label disjunction.
#
# PageDocumentScore deliberately exposes the same field names the gate reads
# (doc_ratio_strict, coverage, critical), so gate_pass() applies to both
# phases unchanged. "coverage" here = matched pages / gold pages: a missing
# page is catastrophic and must fail the gate the same way a missing answer
# does.

from .ground_truth import GoldPageDocument  # noqa: E402


@dataclass(frozen=True)
class PageScore:
    page_number: int
    ratio_strict: float
    ratio_lenient: float
    critical: AnswerCritical
    is_error: bool  # ratio_strict < ERROR_THRESHOLD  OR  critical.has_miss


@dataclass(frozen=True)
class PageDocumentScore:
    doc_id: str
    doc_ratio_strict: float
    doc_ratio_lenient: float
    coverage: float                    # |matched pages| / |gold pages|
    missing_pages: tuple[int, ...]     # in gold, absent from prediction
    extra_pages: tuple[int, ...]       # predicted, absent from gold
    pages: tuple[PageScore, ...]
    critical: CriticalTokenScore


def score_page_document(
    pred: dict[int, str],
    gold: GoldPageDocument,
    *,
    profile: CriticalProfile,
    policy: ScoringPolicy = ScoringPolicy(),
) -> PageDocumentScore:
    """Score a Phase-1 per-page prediction against per-page ground truth. Pure."""
    gold_map = gold.as_dict()
    gold_nums = sorted(gold_map)
    # A degraded-empty prediction (parse failure -> "") is a MISSING page, not a
    # matched one: an empty page must fail coverage loudly, not hide behind a
    # 0.0 ratio while coverage reads 1.0 (gap found in the first real run).
    pred_nums = {n for n, t in pred.items()
                 if normalize(t, strip_illegible=False)}

    matched = [n for n in gold_nums if n in pred_nums]
    missing = tuple(n for n in gold_nums if n not in pred_nums)
    extra = tuple(sorted(pred_nums - set(gold_nums)))
    coverage = len(matched) / len(gold_nums) if gold_nums else 1.0

    page_scores: list[PageScore] = []
    op_agg, st_agg, mc_agg = _MicroAgg(), _MicroAgg(), _MicroAgg()
    abbrevs_altered: set[str] = set()

    for n in matched:
        g_text, p_text = gold_map[n], pred[n]
        rs = _ratio(normalize(g_text, strip_illegible=False),
                    normalize(p_text, strip_illegible=False))
        rl = _ratio(normalize(g_text, strip_illegible=True),
                    normalize(p_text, strip_illegible=True))
        crit = _score_answer_critical(g_text, p_text, profile, policy)

        fold = policy.case_insensitive_keywords
        fold_id = policy.case_insensitive_method_calls
        gs = extract_signature(g_text, profile, fold_keyword_case=fold, fold_identifier_case=fold_id)
        ps = extract_signature(p_text, profile, fold_keyword_case=fold, fold_identifier_case=fold_id)
        op_agg.add(gs.operators, ps.operators)
        st_agg.add(gs.structural, ps.structural)
        mc_agg.add_sets(gs.method_calls, ps.method_calls)
        abbrevs_altered.update(crit.abbreviations_altered)

        page_scores.append(PageScore(
            page_number=n, ratio_strict=rs, ratio_lenient=rl, critical=crit,
            is_error=(rs < ERROR_THRESHOLD) or crit.has_miss,
        ))

    gold_concat = "\n".join(gold_map[n] for n in gold_nums)
    pred_concat = "\n".join(
        [pred.get(n, "") for n in gold_nums] + [pred[n] for n in extra]
    )
    doc_strict = _ratio(normalize(gold_concat, strip_illegible=False),
                        normalize(pred_concat, strip_illegible=False))
    doc_lenient = _ratio(normalize(gold_concat, strip_illegible=True),
                         normalize(pred_concat, strip_illegible=True))

    critical = CriticalTokenScore(
        operator_recall=op_agg.recall, operator_precision=op_agg.precision,
        structural_recall=st_agg.recall, structural_precision=st_agg.precision,
        method_call_recall=mc_agg.recall, method_call_precision=mc_agg.precision,
        abbreviations_altered=tuple(sorted(abbrevs_altered)),
    )

    return PageDocumentScore(
        doc_id=gold.doc_id,
        doc_ratio_strict=doc_strict,
        doc_ratio_lenient=doc_lenient,
        coverage=coverage,
        missing_pages=missing,
        extra_pages=extra,
        pages=tuple(page_scores),
        critical=critical,
    )


# ---------------------------------------------------------------------------
# Correction measurement — the referee that decides whether a correction tier
# is safe. Alignment-free: uses GT identifier-token membership as the oracle.
# A correction moved the prediction TOWARD or AWAY from what the student wrote.
# ---------------------------------------------------------------------------

import re as _re_corr  # local alias; scoring.py top already imports re-free

_CORR_TOKEN_RE = _re_corr.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _ident_tokens(text: str) -> "Counter":
    return Counter(_CORR_TOKEN_RE.findall(text or ""))


@dataclass(frozen=True)
class CorrectionMeasure:
    """Per-run correction safety, measured against faithful GT.

    true_fix:   corrected token IS in GT, original was NOT  -> moved toward GT.
    false_fix:  original token WAS in GT, corrected is NOT   -> overwrote faithful
                content. THIS IS THE KILL-CRITERION COUNT.
    neutral:    neither (both absent, or both present elsewhere) -> can't credit.
    ratio_delta: sum over scopes of (ratio_after - ratio_before); net fidelity
                 effect of applying corrections (positive = net helped).
    trustworthy: false-fix rate is only meaningful at n>=10 fixtures WITH
                 deliberately-included student-spec-errors; below that it is
                 underpowered and must not be read as "safe".
    """
    n_corrections: int
    true_fix: int
    false_fix: int
    neutral: int
    ratio_delta: float
    by_tier: dict           # tier -> {"true_fix","false_fix","neutral","n"}
    trustworthy: bool

    @property
    def false_fix_rate(self) -> float:
        return self.false_fix / self.n_corrections if self.n_corrections else 0.0


def measure_corrections(
    per_scope: list,            # list of (gold_text, raw_pred_text, corrected_pred_text, corrections)
    *,
    n_fixtures: int,
) -> CorrectionMeasure:
    """Score corrections against faithful GT per scope. `corrections` is the
    tuple[Correction-like] with .original/.corrected/.tier applied to that scope.
    Pure; no alignment — GT token membership is the oracle.
    """
    true_fix = false_fix = neutral = n_corr = 0
    ratio_delta = 0.0
    by_tier: dict = {}

    for gold_text, raw_pred, corr_pred, corrections in per_scope:
        gold_tokens = _ident_tokens(gold_text)
        before = _ratio(normalize(gold_text, strip_illegible=False),
                        normalize(raw_pred, strip_illegible=False))
        after = _ratio(normalize(gold_text, strip_illegible=False),
                       normalize(corr_pred, strip_illegible=False))
        ratio_delta += (after - before)

        for c in corrections:
            n_corr += 1
            t = by_tier.setdefault(
                c.tier, {"true_fix": 0, "false_fix": 0, "neutral": 0, "n": 0}
            )
            t["n"] += 1
            orig_in = gold_tokens.get(c.original, 0) > 0
            corr_in = gold_tokens.get(c.corrected, 0) > 0
            if corr_in and not orig_in:
                true_fix += 1; t["true_fix"] += 1
            elif orig_in and not corr_in:
                false_fix += 1; t["false_fix"] += 1
            else:
                neutral += 1; t["neutral"] += 1

    return CorrectionMeasure(
        n_corrections=n_corr, true_fix=true_fix, false_fix=false_fix,
        neutral=neutral, ratio_delta=ratio_delta, by_tier=by_tier,
        trustworthy=n_fixtures >= 10,
    )

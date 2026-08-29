"""
CascadeGrader — Stage-3 router (mission §3, ratified; built in FP2, R-rulings
2026-08-29): a cheap BASE verifier answers every check; scopes whose base
verdicts look contestable are re-verified in full by the CHAMPION, whose
verdicts then replace the base's for that scope. Deterministic router, no
model ever sees a point value, pricing unchanged (pricer.py).

Router v1 (thresholds PRE-REGISTERED in the run's HYPOTHESIZE line; the
SC-disagreement arm of the ratified design is deliberately omitted in v1 —
it doubles base cost for a signal the confidence arm largely subsumes; a v2
adds it if the routed set misses kills):
  route(scope) ⇔ any check verdict has confidence < conf_threshold
              ∪ any verdict is partially_met            (the rule-6-governed class)
              ∪ any met/partially_met whose evidence span does not verify
                against the answer                       (the refusal class)

COST TRUTH: a cascade bills two tiers. The draft carries `cascade_usage`
(per-model token split) so the runner prices each tier by its OWN registry
card; served_models carries both provider-reported ids. Merged per-scope
token counts remain on the outcomes (production display), and every routed
scope is annotated `cascade_routed` with its trigger — auditable per draft.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.agents.grader.grader import _scope_target_id
from app.agents.grader.grader_v5 import PlanVerifyGrader
from app.agents.grader.plan_schemas import CheckVerdict, GradingPlan, TerminalPlan
from app.agents.grader.validator import quote_match_status
from app.schemas.gradable import GradableScope
from app.schemas.graded_test_draft import GradingAnnotation
from app.schemas.ontology_types import AnnotationSeverity, NumericPolicy, QuoteValidationStatus

ROUTER_CONF_THRESHOLD_DEFAULT = 0.80


class CascadeGrader(PlanVerifyGrader):
    """grade(gradable_test) -> GradedTestDraft, same contract as the parents.

    Inherits the whole Plan/Verify/Price scope pipeline; only _verify_scope is
    layered: base verdicts -> deterministic router -> optional champion
    re-verification. Skip/failure/pricing/assembly are untouched parent code.
    """

    def __init__(self,
                 plan: GradingPlan,
                 numeric_policy: Optional[NumericPolicy] = None,
                 *,
                 base_llm,
                 champion_llm,
                 base_model_version: str,
                 champion_model_version: str,
                 conf_threshold: float = ROUTER_CONF_THRESHOLD_DEFAULT,
                 sc_n: int = 1) -> None:
        super().__init__(plan, numeric_policy, llm=base_llm,
                         model_version=f"cascade:{base_model_version}+{champion_model_version}",
                         sc_n=sc_n)
        self._champion_llm = champion_llm.with_structured_output(
            type(self)._response_schema(), include_raw=True)
        self._base_model_version = base_model_version
        self._champion_model_version = champion_model_version
        self._conf_threshold = conf_threshold
        # [COST_TRUTH] per-tier token split, model_id-keyed
        self.cascade_usage: Dict[str, Dict[str, int]] = {
            base_model_version: {"input": 0, "output": 0, "cached": 0},
            champion_model_version: {"input": 0, "output": 0, "cached": 0},
        }
        self.routed_scopes: List[str] = []
        self.total_scope_count: int = 0

    @staticmethod
    def _response_schema():
        from app.agents.grader.plan_schemas import ScopeVerificationResponse
        return ScopeVerificationResponse

    # ── the router (pure, deterministic) ────────────────────────────────────
    def _route(self, scope: GradableScope,
               consensus: Dict[str, CheckVerdict]) -> Optional[str]:
        """Return the trigger name when the scope must escalate, else None."""
        answer = scope.student_answer_text or ""
        for v in consensus.values():
            if v.confidence < self._conf_threshold:
                return f"confidence<{self._conf_threshold} ({v.check_id}={v.confidence:.2f})"
            if v.verdict == "partially_met":
                return f"partially_met ({v.check_id})"
            if v.verdict in ("met", "partially_met"):
                st = quote_match_status(v.evidence_quote, answer)
                if st not in (QuoteValidationStatus.EXACT, QuoteValidationStatus.FUZZY):
                    return f"unverified-span met-claim ({v.check_id})"
        return None

    # ── layered verification ────────────────────────────────────────────────
    async def _verify_scope(self, scope: GradableScope,
                            terminal_plans: List[TerminalPlan]
                            ) -> Tuple[Dict[str, CheckVerdict], List[GradingAnnotation],
                                       int, int, Optional[int]]:
        self.total_scope_count += 1
        base = self.cascade_usage[self._base_model_version]
        champ = self.cascade_usage[self._champion_model_version]

        consensus, anns, in_tok, out_tok, cached = await super()._verify_scope(
            scope, terminal_plans)
        base["input"] += in_tok
        base["output"] += out_tok
        base["cached"] += cached or 0

        trigger = self._route(scope, consensus)
        if trigger is None:
            return consensus, anns, in_tok, out_tok, cached

        # escalate: the champion re-verifies the WHOLE scope; its verdicts win
        target = _scope_target_id(scope)
        self.routed_scopes.append(target)
        base_runner = self._structured_llm
        try:
            self._structured_llm = self._champion_llm
            c_consensus, c_anns, c_in, c_out, c_cached = await super()._verify_scope(
                scope, terminal_plans)
        finally:
            self._structured_llm = base_runner
        champ["input"] += c_in
        champ["output"] += c_out
        champ["cached"] += c_cached or 0

        route_ann = GradingAnnotation(
            severity=AnnotationSeverity.INFO,
            target_id=target,
            annotation_type="cascade_routed",
            message=f"הסעיף הועבר לאימות חוזר על-ידי המודל הראשי (טריגר: {trigger})",
            metadata={"trigger": trigger,
                      "base_model": self._base_model_version,
                      "champion_model": self._champion_model_version},
        )
        merged_cached = ((cached or 0) + (c_cached or 0)) or None
        return (c_consensus, c_anns + [route_ann],
                in_tok + c_in, out_tok + c_out, merged_cached)

    async def grade(self, gradable_test):
        draft = await super().grade(gradable_test)
        return draft.model_copy(update={
            "cascade_usage": {k: dict(v) for k, v in self.cascade_usage.items()},
        })

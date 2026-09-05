"""
PLAN COMPILER v2 — "Compile · Segment · Route" (app/agents/plan_gen/PR_plan_compiler_v2.md).

    skeleton.py   Stage-1 output types (Slot / TerminalSkeleton / PlanSkeleton)
    compile.py    Stage 1: contract → PlanSkeleton, pure, zero spend (C1–C7)
    assemble.py   Stage 3: PlanSkeleton (+ wording) → validated GradingPlan
    segment.py    Stage 2: the segmenter (Haiku) — wording only            [P6]
    route.py      Stage 2b: the monolith decomposer (Sonnet) — names only  [P6]

The model never emits a number, a kind, an amount, an anchor, or a count.
"""
from .compile import COMPILER_VERSION, compile_contract, compile_terminal
from .skeleton import CompilerBug, Flag, PlanSkeleton, Slot, TerminalSkeleton

__all__ = ["COMPILER_VERSION", "compile_contract", "compile_terminal",
           "CompilerBug", "Flag", "PlanSkeleton", "Slot", "TerminalSkeleton"]

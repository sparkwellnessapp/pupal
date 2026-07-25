"""
Harness-agnostic LLM tracelog for the docx_v3 extraction pipeline.

A trace is a TREE OF SPANS. There are exactly two span KINDS, each with a fixed
schema, so the log format is invariant to the harness shape — a single reasoning
call with retries and a 3-step prompt chain are just different span TREES over the
same two schemas:

  - generation : one LLM interaction (prompt, params, parsed output, raw output,
                 usage {in/out/reasoning/cached}, reasoning summary, finish_reason)
  - operation  : one deterministic step (render, validate, retry_decision, build,
                 tier_a, diff, ...) with inputs/outputs/status

Design rules (mirroring the pipeline's on_progress seam — see pipeline.py §382):
  1. INJECTED, never imported into control flow. Default is NULL_TRACER (a no-op),
     so a None / off tracer is byte-identical to no tracing.
  2. BEST-EFFORT. Every tracer call is try/except-swallowed — a tracing failure
     must never fail or alter the extraction. (Same rule as _emit_progress.)
  3. THIN. Large payloads (prompts, raw responses, the render) are content-addressed
     into a sidecar blob store and referenced by sha; the skeleton (spans + small
     attrs + validation issues + tokens/timing) is always cheap. Full payloads are
     RETAINED on finish() per policy: "on_failure" (default) | "all" | "never".

Two sinks from one emitter: a local JSONL file (greppable, offline, survives
headless/cron) and — when enabled — a LangSmith run-tree mirror (hosted). The two
share the span model, so you never choose. LLM calls ALSO auto-trace to LangSmith
via LangChain when LANGCHAIN_TRACING_V2 is set; the mirror adds the operation and
validation spans that are not function calls.

CLI:  python -m app.services.docx_v3.trace <trace.jsonl>   # pretty-print a trace
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

_MONO = time.monotonic


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


@dataclass
class _Blob:
    sha: str
    content: str
    tier: str  # "skeleton" (kept even on a passing run) | "full" (kept per retain policy)


class Span:
    """One node in the trace tree. Returned by Tracer.span()/generation()/operation().
    All setters are best-effort and return self for chaining."""

    __slots__ = ("_t", "span_id", "parent_id", "kind", "name", "attrs",
                 "status", "error", "t_start", "blobs")

    def __init__(self, tracer: "Tracer", span_id: str, parent_id: Optional[str],
                 kind: str, name: str, attrs: Dict[str, Any]):
        self._t = tracer
        self.span_id = span_id
        self.parent_id = parent_id
        self.kind = kind
        self.name = name
        self.attrs: Dict[str, Any] = dict(attrs)
        self.status = "ok"
        self.error: Optional[str] = None
        self.t_start = _MONO()
        self.blobs: Dict[str, str] = {}  # logical key -> blob sha

    def set(self, **attrs: Any) -> "Span":
        """Record small scalar attributes (tokens, finish_reason, counts, digests)."""
        try:
            self.attrs.update({k: v for k, v in attrs.items() if v is not None})
        except Exception:
            pass
        return self

    def blob(self, key: str, content: Any, *, tier: str = "full") -> "Span":
        """Record a large payload (prompt, raw response, render) content-addressed.
        tier='skeleton' survives a passing run; tier='full' is retained per policy."""
        try:
            if content is None:
                return self
            s = content if isinstance(content, str) else _dumps(content)
            self.blobs[key] = self._t._put_blob(s, tier)
        except Exception:
            pass
        return self

    def fail(self, exc: BaseException) -> "Span":
        try:
            self.status = "error"
            self.error = f"{type(exc).__name__}: {exc}"
        except Exception:
            pass
        return self


class Tracer:
    """Buffered span-tree tracer. Construct one per logical trace (per extraction /
    per eval trial). Emit spans with `with tracer.generation(...)` / `.operation(...)`.
    Call finish(out_dir, status=..., retain=...) exactly once at the end."""

    def __init__(self, trace_id: Optional[str] = None, *,
                 meta: Optional[Dict[str, Any]] = None, langsmith: bool = False):
        self.trace_id = trace_id or uuid.uuid4().hex[:16]
        self.meta: Dict[str, Any] = dict(meta or {})
        self.events: List[Dict[str, Any]] = []
        self.blobs: Dict[str, _Blob] = {}
        self._stack: List[str] = []
        self._ls = _LangSmithMirror(self.trace_id, self.meta) if langsmith else None

    def _put_blob(self, content: str, tier: str) -> str:
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        b = self.blobs.get(sha)
        if b is None:
            self.blobs[sha] = _Blob(sha=sha, content=content, tier=tier)
        elif tier == "full" and b.tier == "skeleton":
            b.tier = "full"  # promote if referenced at both tiers
        return sha

    @contextlib.contextmanager
    def span(self, name: str, kind: str = "operation", **attrs: Any):
        span_id = uuid.uuid4().hex[:12]
        parent = self._stack[-1] if self._stack else None
        sp = Span(self, span_id, parent, kind, name, attrs)
        self._stack.append(span_id)
        ls_ctx = None
        if self._ls is not None:
            ls_ctx = self._ls.start(sp)
        try:
            yield sp
        except Exception as e:  # record then re-raise — tracing never swallows real errors
            sp.fail(e)
            raise
        finally:
            try:
                self._stack.pop()
            except Exception:
                pass
            self.events.append({
                "span_id": span_id, "parent_id": parent, "kind": kind, "name": name,
                "dur_s": round(_MONO() - sp.t_start, 4), "status": sp.status,
                "error": sp.error, "attrs": sp.attrs, "blobs": sp.blobs,
            })
            if self._ls is not None:
                try:
                    self._ls.end(sp, ls_ctx)
                except Exception:
                    pass

    def generation(self, name: str, **attrs: Any):
        return self.span(name, kind="generation", **attrs)

    def operation(self, name: str, **attrs: Any):
        return self.span(name, kind="operation", **attrs)

    def finish(self, out_dir, *, status: str = "ok", retain: str = "on_failure") -> Optional[Path]:
        """Write the trace. `retain`: 'all' keeps every blob; 'on_failure' keeps full
        blobs only when status != 'ok'; 'never' keeps skeleton-tier blobs only.
        The skeleton (spans + attrs + issues + tokens) is ALWAYS written."""
        try:
            write_full = retain == "all" or (retain == "on_failure" and status != "ok")
            out = Path(out_dir)
            out.mkdir(parents=True, exist_ok=True)
            header = {"phase": "trace", "trace_id": self.trace_id, "meta": self.meta,
                      "status": status, "retain": retain, "full_retained": write_full}
            lines = [_dumps(header)]
            for ev in self.events:
                lines.append(_dumps({"trace_id": self.trace_id, **ev}))
            path = out / f"{self.trace_id}.jsonl"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            keep = self.blobs.values() if write_full else \
                [b for b in self.blobs.values() if b.tier == "skeleton"]
            keep = list(keep)
            if keep:
                bdir = out / "blobs"
                bdir.mkdir(exist_ok=True)
                for b in keep:
                    (bdir / b.sha).write_text(b.content, encoding="utf-8")
            return path
        except Exception:
            return None


class _NullSpan:
    def set(self, **attrs: Any) -> "_NullSpan":
        return self

    def blob(self, *a: Any, **k: Any) -> "_NullSpan":
        return self

    def fail(self, exc: BaseException) -> "_NullSpan":
        return self


_NULL_SPAN = _NullSpan()


class _NullTracer(Tracer):
    """No-op tracer. Zero cost, byte-identical to no tracing. The default."""

    def __init__(self):
        super().__init__(trace_id="null")

    @contextlib.contextmanager
    def span(self, name: str, kind: str = "operation", **attrs: Any):
        yield _NULL_SPAN

    def finish(self, *a: Any, **k: Any) -> Optional[Path]:
        return None


NULL_TRACER = _NullTracer()


def resolve(tracer: Optional[Tracer]) -> Tracer:
    """Pipeline convenience: None -> the no-op tracer, so call sites stay unconditional."""
    return tracer or NULL_TRACER


class _LangSmithMirror:
    """Best-effort LangSmith run-tree mirror. Lazy-imported and fully guarded: if the
    SDK is absent or its API differs, every method degrades to a no-op and the local
    JSONL trace is unaffected. Nesting rides the same LIFO order as the span stack."""

    def __init__(self, trace_id: str, meta: Dict[str, Any]):
        self._ok = False
        self._trace = None
        try:
            from langsmith import trace as _ls_trace  # context-manager API (recent SDK)
            self._trace = _ls_trace
            self._ok = True
        except Exception:
            self._ok = False

    def start(self, sp: Span):
        if not self._ok:
            return None
        try:
            run_type = "llm" if sp.kind == "generation" else "chain"
            cm = self._trace(name=sp.name, run_type=run_type, inputs=dict(sp.attrs))
            handle = cm.__enter__()
            return (cm, handle)
        except Exception:
            return None

    def end(self, sp: Span, ctx) -> None:
        if not ctx:
            return
        cm, handle = ctx
        try:
            try:
                handle.add_outputs({"attrs": sp.attrs, "status": sp.status,
                                    "error": sp.error, "blobs": sp.blobs})
            except Exception:
                pass
            cm.__exit__(None, None, None)
        except Exception:
            try:
                cm.__exit__(None, None, None)
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# Reader / pretty-printer
# --------------------------------------------------------------------------- #

def format_trace(jsonl_path) -> str:
    """Render a saved trace.jsonl as an indented tree for eyeballing what happened."""
    p = Path(jsonl_path)
    rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    header = next((r for r in rows if r.get("phase") == "trace"), {})
    spans = [r for r in rows if r.get("phase") != "trace"]
    by_parent: Dict[Optional[str], List[dict]] = {}
    for s in spans:
        by_parent.setdefault(s.get("parent_id"), []).append(s)

    out: List[str] = []
    out.append(f"TRACE {header.get('trace_id')}  status={header.get('status')}  "
               f"full_retained={header.get('full_retained')}")
    if header.get("meta"):
        out.append(f"  meta: {header['meta']}")

    def walk(parent: Optional[str], depth: int):
        for s in by_parent.get(parent, []):
            pad = "  " * depth
            mark = "!" if s.get("status") == "error" else ("*" if s.get("kind") == "generation" else "-")
            line = f"{pad}{mark} {s.get('name')} [{s.get('kind')}]  {s.get('dur_s')}s"
            attrs = s.get("attrs") or {}
            keybits = []
            for k in ("attempt", "finish_reason", "input_tokens", "output_tokens",
                      "reasoning_tokens", "cached_tokens", "retry", "n_issues", "trigger_codes"):
                if k in attrs:
                    keybits.append(f"{k}={attrs[k]}")
            if keybits:
                line += "  " + " ".join(keybits)
            out.append(line)
            if s.get("error"):
                out.append(f"{pad}    ERROR: {s['error']}")
            # surface validation issues inline — the "why a retry fired"
            issues = attrs.get("issues")
            if issues:
                for iss in issues:
                    out.append(f"{pad}    · [{iss.get('code')}] retryable={iss.get('retryable')} "
                               f"{iss.get('message', '')[:90]}")
            if s.get("blobs"):
                out.append(f"{pad}    blobs: {s['blobs']}")
            walk(s.get("span_id"), depth + 1)

    walk(None, 0)
    return "\n".join(out)


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) != 2:
        print("usage: python -m app.services.docx_v3.trace <trace.jsonl>")
        raise SystemExit(2)
    print(format_trace(sys.argv[1]))

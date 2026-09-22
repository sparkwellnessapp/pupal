"""
OD-B4 — production logs carry IDS, never filenames or students' names.

Why this is a rule and not a style (PURGE_CENSUS row 9). Cloud Logging keeps
30 days and cannot be scrubbed line by line. Teachers name scans after the
student («noa_levi.pdf»), so a filename in a log line IS the student's name,
held in a store the purge can never reach. The transcription pipeline used the
original filename as its `doc_id`, and prefixed EVERY pipeline line with it —
so a single batch wrote each student's name dozens of times.

Two tests:

  * a STRUCTURAL scan of `app/`: no logging call and no network-diagnosis
    label (whose text `net_diag` logs) may reference a filename- or
    name-shaped identifier. The exemptions are DEAD code or false positives,
    each with its reason — and each exemption is re-verified here as still
    dead, so an exemption cannot quietly outlive the reason it was granted;
  * a BEHAVIOURAL check on the identity pass, the one path that must keep the
    filename as an INPUT (the model judges it, the fallback reads it): it
    logs the doc id and neither the filename nor the name it found.
"""
from __future__ import annotations

import ast
import asyncio
import json
import logging
import pathlib
import re
from unittest.mock import patch

from PIL import Image

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

LOG_LEVELS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
#: Identifiers that hold a filename or a student's name.
PII = re.compile(r"(^|_)(filename|file_name|fname|student_name|full_name|pdf_path)$")

#: Whole modules nothing imports. Their logs cannot run.
DEAD_MODULES = {
    "document_parser.py": "app.document_parser",
    "grading_agent.py": "app.grading_agent",
    "grading_orchestrator.py": "app.grading_orchestrator",
    "services/grading_agent.py": "app.services.grading_agent",
}
#: (module, function) pairs that are dead, offline, or false positives.
EXEMPT_FUNCTIONS = {
    # Uncalled parsers inside a LIVE module (the module is imported for
    # pdf_to_images); pinned below as having no caller.
    ("services/document_parser.py", "parse_student_test"): "dead: no caller",
    ("services/document_parser.py", "parse_student_test_with_mappings"): "dead: no caller",
    # The legacy engine's command-line accuracy benchmark: developer console,
    # never Cloud Logging. Pinned below as unreferenced by the service.
    ("services/handwriting_transcription_service.py", "test_transcription_accuracy"): "offline CLI",
    ("services/handwriting_transcription_service.py", "main"): "offline CLI",
    # False positives: `.name` of files this code names itself —
    # `page_{n}_{timestamp}.txt` and `{sha256}_{timestamp}.pdf`.
    ("services/handwriting_transcription_service.py", "_save_debug_response"): "self-named debug file",
    ("services/temp_storage_service.py", "cleanup_expired"): "self-named temp file",
}


def _idents(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            yield sub.id
        elif isinstance(sub, ast.Attribute):
            yield sub.attr
            if sub.attr == "name":
                # `<something path/file-ish>.name` is a filename too.
                yield "filename" if re.search(r"path|file", ast.unparse(sub.value), re.I) else "name"
        elif isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant) \
                and isinstance(sub.slice.value, str):
            yield sub.slice.value


def _is_log_or_diag_call(call: ast.Call) -> bool:
    f = call.func
    if isinstance(f, ast.Attribute) and f.attr in LOG_LEVELS:
        base = f.value
        name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
        return "log" in name.lower()
    # net_diag logs its label verbatim.
    return (isinstance(f, ast.Name) and f.id == "diagnose_transport_failure") or \
        (isinstance(f, ast.Attribute) and f.attr == "diagnose_transport_failure")


def _enclosing_functions(tree):
    spans = []
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append((fn.lineno, fn.end_lineno, fn.name))
    return spans


def _offenders() -> list[str]:
    found = []
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(APP).as_posix()
        if rel in DEAD_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        spans = _enclosing_functions(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _is_log_or_diag_call(node)):
                continue
            args = list(node.args) + [k.value for k in node.keywords]
            bad = sorted({i for a in args for i in _idents(a) if PII.search(i)})
            if not bad:
                continue
            inner = [n for (a, b, n) in spans if a <= node.lineno <= b]
            if any((rel, fn) in EXEMPT_FUNCTIONS for fn in inner):
                continue
            found.append(f"app/{rel}:{node.lineno} {bad}")
    return found


def test_no_production_log_line_carries_a_filename_or_a_students_name():
    assert _offenders() == [], (
        "a log call (or a net_diag label) references a filename or a student's "
        "name — log the job / transcription / graded-test id instead (OD-B4)")


def _imported_modules(rel: str, tree: ast.AST) -> set[str]:
    """Every module this file imports, as absolute dotted names, relative
    imports resolved against the file's own package."""
    package = ["app"] + rel.split("/")[:-1]
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[:len(package) - (node.level - 1)]
                mod = ".".join(base + (node.module.split(".") if node.module else []))
            else:
                mod = node.module or ""
            out.add(mod)
            out.update(f"{mod}.{a.name}" for a in node.names)
    return out


def _called_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            names.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""))
    return names


def test_every_exemption_is_still_dead():
    """An exemption names code that cannot write to Cloud Logging. If that code
    comes back to life, the exemption must go — this test says so. Imports and
    calls are read from the AST (relative imports resolved), and a DEAD module
    importing another dead module does not bring either to life."""
    trees = {p.relative_to(APP).as_posix(): ast.parse(p.read_text(encoding="utf-8"))
             for p in APP.rglob("*.py")}
    live = {rel: t for rel, t in trees.items() if rel not in DEAD_MODULES}
    for rel, dotted in DEAD_MODULES.items():
        importers = [f for f, t in live.items() if dotted in _imported_modules(f, t)]
        assert importers == [], f"{rel} is imported by {importers}: it is no longer dead"
    for (rel, fn), why in EXEMPT_FUNCTIONS.items():
        assert any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fn
                   for n in ast.walk(trees[rel])), f"exemption {rel}::{fn} names nothing — remove it"
        if why.startswith("dead"):
            callers = [f for f, t in live.items() if fn in _called_names(t)]
            assert callers == [], f"{rel}::{fn} is called from {callers}: it is no longer dead"
        elif why == "offline CLI":
            # `main` is every script's name, so a CALL by that name proves
            # nothing; what would bring these to life is another module
            # IMPORTING them from this one.
            dotted = "app." + rel[:-3].replace("/", ".")
            importers = [f for f, t in live.items()
                         if f != rel and f"{dotted}.{fn}" in _imported_modules(f, t)]
            assert importers == [], f"{rel}::{fn} is imported by {importers}: no longer offline"


def test_the_identity_pass_logs_its_doc_id_never_the_filename_nor_the_name(caplog):
    """The one path that must keep the filename as an INPUT. Success and the
    filename fallback both log the doc id — and neither the filename nor the
    name read from the page or the file."""
    from app.services.transcription.identity import extract_student_name
    from app.services.transcription.providers.fake import FakeProvider

    filename, name, doc_id = "ploni_almoni.pdf", "פלוני אלמוני", "job-7f3a"
    render = patch("app.services.transcription.identity.render_pdf_page",
                   return_value=Image.new("RGB", (800, 1000), "white"))

    fake = FakeProvider(script=[FakeProvider.ok(json.dumps(
        {"student_name": name, "source": "handwriting"}, ensure_ascii=False))])
    with render, caplog.at_level(logging.INFO):
        got = asyncio.run(extract_student_name(b"%PDF", filename, fake, doc_id=doc_id))
    assert got == name
    assert filename in fake.calls[0].user          # still an INPUT to the model
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert doc_id in text
    assert filename not in text and name not in text

    caplog.clear()

    class _Down:
        async def complete(self, **_):
            raise RuntimeError("provider down")
    with render, caplog.at_level(logging.INFO), \
            patch("app.services.net_diag.diagnose_transport_failure",
                  side_effect=lambda label, exc: _record(label)):
        # A HEBREW two-token stem: the only shape the fallback accepts.
        got = asyncio.run(extract_student_name(
            b"%PDF", "פלונית_אלמונית.pdf", _Down(), doc_id=doc_id))
    text = "\n".join(r.getMessage() for r in caplog.records) + "\n".join(_labels)
    assert got == "פלונית אלמונית"                   # the filename fallback still works…
    assert "פלונית" not in text                      # …and neither it nor the file is logged
    assert doc_id in text


_labels: list[str] = []


async def _record(label):
    _labels.append(label)

"""
STRUCTURAL GUARD — a module-private helper that is CALLED must be DEFINED.

Why this exists. A refactor replaced a byte-range of `rubric_extraction_jobs.py`
and silently took two helpers with it (`_enqueue_or_fail`, `_status_response`)
because they happened to live inside the replaced span. Every existing gate
passed:

  * `import app.main` succeeded — Python resolves globals at CALL time, so a
    missing module-level function is invisible to import. The repo's sanity gate
    (CLAUDE.md §12: "python -c 'import app.main'") is STRUCTURALLY BLIND to this.
  * `pytest --collect-only` succeeded, for the same reason.
  * The unit tests covered the new pure module, not the endpoint bodies.

It surfaced as a 500 on the first real POST — i.e. the teacher found it. A
one-line NameError that reaches production because "it imported fine" is exactly
the class worth a cheap, dependency-free check (no ruff/pyflakes in requirements).

Scope is deliberately narrow — module-private (`_name`) CALLS only — so it has no
false positives on dynamic attribute access and needs no type inference.
"""
import ast
import builtins
import importlib
import pathlib

import pytest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

# Modules that cannot be imported in a test process (optional deps / side effects).
_SKIP_IMPORT = set()


def _module_files():
    return sorted(p for p in APP.rglob("*.py") if p.name != "__init__.py")


def _bound_names(tree: ast.AST) -> set[str]:
    """Every name BOUND anywhere in the file: defs (incl. nested), classes,
    assignments, imports, comprehension targets, with/except aliases."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                out.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            out.add(node.id)
        elif isinstance(node, ast.arg):
            out.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            out.add(node.name)
    return out


def _private_calls(tree: ast.AST) -> set[str]:
    """Names invoked as `_foo(...)` — a bare Name call, not an attribute call."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name.startswith("_") and not name.startswith("__"):
                out.add(name)
    return out


def undefined_private_calls(path: pathlib.Path) -> list[str]:
    """The check itself, exposed so it can be run against arbitrary source."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bound = _bound_names(tree) | set(dir(builtins))
    return sorted(n for n in _private_calls(tree) if n not in bound)


@pytest.mark.parametrize("path", _module_files(), ids=lambda p: p.name)
def test_every_private_helper_called_is_defined(path: pathlib.Path):
    missing = undefined_private_calls(path)
    assert not missing, (
        f"{path.relative_to(APP.parent)} calls module-private helper(s) that are "
        f"defined nowhere in the file: {missing}. This raises NameError at RUNTIME "
        f"only — the import gate cannot see it. A refactor most likely deleted them."
    )


def test_the_guard_actually_catches_a_deleted_helper(tmp_path):
    """Pin the DETECTOR, not just the codebase — a guard that cannot fail is not a
    guard. This is the exact shape of the regression: the call survives, the def
    does not."""
    broken = tmp_path / "broken.py"
    broken.write_text(
        "async def handler():\n"
        "    await _enqueue_or_fail(1)\n"
        "    return _status_response(2)\n",
        encoding="utf-8",
    )
    assert undefined_private_calls(broken) == ["_enqueue_or_fail", "_status_response"]

    fixed = tmp_path / "fixed.py"
    fixed.write_text(
        "def _enqueue_or_fail(x): return x\n"
        "def _status_response(x): return x\n"
        "async def handler():\n"
        "    await _enqueue_or_fail(1)\n"
        "    return _status_response(2)\n",
        encoding="utf-8",
    )
    assert undefined_private_calls(fixed) == []


def test_import_alone_would_NOT_have_caught_it(tmp_path):
    """Documents WHY the existing gate missed this: a module calling an undefined
    helper imports perfectly. The failure waits for the first request."""
    mod = tmp_path / "importable_but_broken.py"
    mod.write_text("def handler():\n    return _gone()\n", encoding="utf-8")
    import sys

    sys.path.insert(0, str(tmp_path))
    try:
        m = importlib.import_module("importable_but_broken")   # succeeds!
        with pytest.raises(NameError):
            m.handler()                                        # fails only when CALLED
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("importable_but_broken", None)

"""Identidad determinista del build de runtime de AKIRA.

La huella depende del código Python de producción y de requirements.txt.
Los módulos de pruebas se excluyen para que cambios de CI/tests no invaliden
la evidencia de runtime cuando la lógica desplegada no cambia.
No incluye secretos ni depende de la presencia de .git en runtime.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def _is_runtime_source(path: Path) -> bool:
    """Return whether a repository file contributes to the runtime fingerprint."""
    if ".git" in path.parts or "__pycache__" in path.parts:
        return False
    if any(part.lower() in {"test", "tests"} for part in path.parts[:-1]):
        return False
    if path.name == "requirements.txt":
        return True
    if path.suffix != ".py":
        return False
    name = path.name.lower()
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return False
    return True


def runtime_build_ref() -> str:
    root = Path(__file__).resolve().parent.parent
    digest = hashlib.sha256()
    paths = sorted(
        p for p in root.rglob("*")
        if p.is_file() and _is_runtime_source(p)
    )
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(bytes((0,)))
        digest.update(path.read_bytes())
        digest.update(bytes((0,)))
    return "sha256:" + digest.hexdigest()[:48]

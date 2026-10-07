"""Identidad determinista del build de runtime de AKIRA.

La huella depende del codigo Python y de requirements.txt desplegados.
No incluye secretos ni depende de la presencia de .git en runtime.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def runtime_build_ref() -> str:
    root = Path(__file__).resolve().parent.parent
    digest = hashlib.sha256()
    paths = sorted(
        p for p in root.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and "__pycache__" not in p.parts
        and (p.suffix == ".py" or p.name == "requirements.txt")
    )
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()[:48]

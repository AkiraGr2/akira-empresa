"""Contrato y validación del motor de absorción autónoma de Akira.

Este módulo define SOLO el contrato de decisión. No persiste memoria,
no crea nodos y no decide por sí mismo qué debe aprender Akira.
La integración con chat y el Learning Engine se hará en fases posteriores.

Regla fundamental:
    conversación != memoria

Una decisión distinta de CANDIDATE/UPDATE/REINFORCE/CONFLICT no debe
materializar conocimiento por este contrato.
"""

from __future__ import annotations

from typing import Any, Mapping
import hashlib


"""Contrato y validación del motor de absorción autónoma de Akira.

Este módulo define SOLO el contrato de decisión. No persiste memoria,
no crea nodos y no decide por sí mismo qué debe aprender Akira.
La persistencia de candidatos se orquesta desde chat mediante un modo explícito y controlado.

Regla fundamental:
    conversación != memoria

Una decisión distinta de CANDIDATE/UPDATE/REINFORCE/CONFLICT no debe
materializar conocimiento por este contrato.
"""

from __future__ import annotations
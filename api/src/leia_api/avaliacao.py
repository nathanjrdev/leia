"""Métricas e casos de avaliação da busca (relevância binária).

Recall@k aqui é a taxa de acerto: 1 se algum livro esperado aparece entre os k primeiros.
nDCG@k mede a qualidade da ordenação considerando todos os livros relevantes.
"""

import json
import math
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from leia_api.busca import ResultadoBusca


@dataclass(frozen=True)
class Caso:
    id: str
    tipo: str  # titulo | autor | intencao
    consulta: str
    esperados: list[str] = field(default_factory=list)
    autor_esperado: str | None = None


def recall_at_k(relevancias: Sequence[bool], k: int) -> float:
    return 1.0 if any(relevancias[:k]) else 0.0


def ndcg_at_k(relevancias: Sequence[bool], k: int, total_relevantes: int) -> float:
    dcg = sum(1.0 / math.log2(i + 2) for i, r in enumerate(relevancias[:k]) if r)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(total_relevantes, k)))
    return dcg / ideal if ideal else 0.0


def _chave(texto: str) -> str:
    """Compara títulos sem depender de maiúsculas nem da forma de normalização Unicode."""
    return unicodedata.normalize("NFC", texto).casefold()


def relevancias(caso: Caso, resultados: Sequence[ResultadoBusca]) -> list[bool]:
    esperados = {_chave(t) for t in caso.esperados}
    autor = _chave(caso.autor_esperado) if caso.autor_esperado else None
    return [
        _chave(r.titulo) in esperados
        or (autor is not None and any(_chave(a) == autor for a in r.autores))
        for r in resultados
    ]


def carregar_casos(caminho: Path) -> list[Caso]:
    return [
        Caso(**json.loads(linha))
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]

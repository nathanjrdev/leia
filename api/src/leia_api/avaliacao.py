"""Métricas e casos de avaliação da busca (relevância binária).

Recall@k aqui é a taxa de acerto: 1 se algum livro esperado aparece entre os k primeiros.
nDCG@k mede a qualidade da ordenação considerando todos os livros relevantes.
"""

import json
import math
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


METRICAS_GATE = ("recall@5", "ndcg@10")
# Um caso a menos em 73 baixa o Recall@5 geral em ~0,014: diferença de um caso é sinal fraco
# (ruído), não regressão. Acima disso, o gate reprova.
TOLERANCIA_GATE = 0.015


def regressoes(
    base: Mapping[str, Any], atual: Mapping[str, Any], tolerancia: float = TOLERANCIA_GATE
) -> list[str]:
    """Quedas da média geral além da tolerância, por configuração (com e sem reranker).

    `base` e `atual` têm o formato do relatório de `evals/run_busca.py`. Só compara as
    configurações e métricas presentes nos dois; uma configuração que sumiu do relatório
    atual também é regressão (o gate não pode passar por omissão).
    """
    achadas: list[str] = []
    for config, anterior in base.items():
        if not isinstance(anterior, Mapping) or "resumo" not in anterior:
            continue
        novo = atual.get(config)
        if not isinstance(novo, Mapping) or "resumo" not in novo:
            achadas.append(f"{config}: ausente no relatório atual")
            continue
        geral_antes, geral_agora = anterior["resumo"]["geral"], novo["resumo"]["geral"]
        for metrica in METRICAS_GATE:
            if metrica not in geral_antes:
                continue
            antes, agora = float(geral_antes[metrica]), float(geral_agora.get(metrica, 0.0))
            if antes - agora > tolerancia:
                achadas.append(f"{config} {metrica}: {antes:.3f} → {agora:.3f}")
    return achadas


def carregar_casos(caminho: Path) -> list[Caso]:
    return [
        Caso(**json.loads(linha))
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]

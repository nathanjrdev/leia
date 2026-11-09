"""Funções compartilhadas pelos scripts de ajuste fino de embeddings.

Coloque esta pasta em `evals/embeddings/` do repositório da Leia.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CATALOGO = RAIZ / "data" / "catalogo.json"
CASOS_MANUAIS = RAIZ / "evals" / "busca_casos.jsonl"
RESULTADOS = RAIZ / "evals" / "resultados"
SAIDA = Path(__file__).resolve().parent / "saida"

# Mesmo encoder e mesmo limite de tokens de api/src/leia_api/embeddings.py.
MODELO_BASE = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
MAX_TOKENS = 256
SEMENTE = 42
FRACAO_VALIDACAO = 0.2


def norm(texto: str) -> str:
    return unicodedata.normalize("NFC", texto).casefold().strip()


def ler_jsonl(caminho: Path) -> list[dict]:
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def escrever_jsonl(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        for linha in linhas:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")


def documento(livro: dict) -> str:
    """Mesmo formato de `documento_do_livro` em embeddings.py."""
    partes = [
        livro["titulo"],
        "Autor: " + ", ".join(livro.get("autores") or []),
        "Categorias: " + ", ".join(livro.get("categorias") or []),
        livro.get("sinopse") or "",
    ]
    return "\n".join(p for p in partes if p.strip())


def carregar_catalogo() -> list[dict]:
    with open(CATALOGO, encoding="utf-8") as f:
        livros = json.load(f)
    for livro in livros:
        livro["doc"] = documento(livro)
    return livros


def em_validacao(titulo: str) -> bool:
    """Divisão por livro, determinística: ~20% dos livros nunca entram no treino."""
    h = int(hashlib.sha1(norm(titulo).encode("utf-8")).hexdigest(), 16)
    return (h % 100) < int(FRACAO_VALIDACAO * 100)


def metricas(rankings: list[list[str]], esperados: list[set[str]]) -> dict:
    """rankings: títulos normalizados em ordem de similaridade. Relevância binária."""
    n = len(rankings)
    acertos = 0
    ndcg_total = 0.0
    for top, certos in zip(rankings, esperados, strict=True):
        if any(t in certos for t in top[:5]):
            acertos += 1
        dcg = sum(1 / math.log2(i + 2) for i, t in enumerate(top[:10]) if t in certos)
        ideal = sum(1 / math.log2(i + 2) for i in range(min(len(certos), 10)))
        ndcg_total += dcg / ideal if ideal else 0.0
    return {
        "n": n,
        "recall@5": round(acertos / n, 3) if n else None,
        "ndcg@10": round(ndcg_total / n, 3) if n else None,
    }

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


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def pares_do_catalogo(livros: list[dict], casos_manuais: list[dict]) -> list[dict]:
    """Pedidos simples de título e de autor, gerados do catálogo (sem LLM).

    Os pares sintéticos de `gerar_pares.py` nunca citam título nem autor, e o modelo ajustado só
    com eles esquece como casar "Saramago" com os livros dele. Estes pares ensinam esse tipo de
    pedido de volta, sem contaminar a avaliação:
    - só livros de treino (os de validação continuam nunca vistos);
    - nenhum livro de caso manual de título nem autor de caso manual de autor entra, para que
      `casos_manuais/titulo` e `casos_manuais/autor` meçam a habilidade em livros e autores
      novos, e não a memória do treino;
    - pedidos idênticos a um caso manual são descartados.
    """
    excl_titulos = {
        norm(e) for c in casos_manuais if c.get("tipo") == "titulo" for e in c.get("esperados", [])
    }
    excl_autores = {norm(c["autor_esperado"]) for c in casos_manuais if c.get("autor_esperado")}
    proibidas = {norm(c["consulta"]) for c in casos_manuais}
    vistos: set[tuple[str, str]] = set()
    pares: list[dict] = []

    def _add(livro: dict, consulta: str, origem: str) -> None:
        chave = (norm(livro["titulo"]), norm(consulta))
        if chave in vistos or norm(consulta) in proibidas:
            return
        vistos.add(chave)
        pares.append({"livro": livro["titulo"], "consulta": consulta, "origem": origem})

    for livro in livros:
        if em_validacao(livro["titulo"]):
            continue
        titulo = livro["titulo"]
        if norm(titulo) not in excl_titulos:
            _add(livro, titulo, "catalogo-titulo")
            _add(livro, _sem_acento(titulo).lower(), "catalogo-titulo")  # como se digita
        for autor in livro.get("autores") or []:
            if norm(autor) in excl_autores:
                continue
            _add(livro, autor, "catalogo-autor")
            _add(livro, f"livros de {autor}", "catalogo-autor")
    return pares


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

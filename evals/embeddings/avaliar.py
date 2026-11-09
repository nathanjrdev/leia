"""Mede Recall@5 e nDCG@10 do encoder base e do ajustado, lado a lado.

Uso:  python evals/embeddings/avaliar.py

Dois conjuntos de avaliação:
  - validacao_livros_nao_vistos: pedidos sintéticos de livros que ficaram FORA do treino.
    É o número que mostra se o modelo generaliza.
  - casos_manuais: evals/busca_casos.jsonl (feitos por você). Atenção: alguns livros
    destes casos podem ter aparecido no treino (com outros pedidos).

A busca é só por vetor, sem reranker nem busca por palavra-chave. Por isso os números
são diferentes dos de evals/resultados/busca*.json, que medem o pipeline completo.
Saída: evals/resultados/embeddings_ajuste_<data>.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date

import numpy as np

from comum import (
    CASOS_MANUAIS,
    MAX_TOKENS,
    MODELO_BASE,
    RESULTADOS,
    SAIDA,
    carregar_catalogo,
    ler_jsonl,
    metricas,
    norm,
)


def ranquear(codificar, livros: list[dict], consultas: list[str], k: int = 10) -> list[list[str]]:
    """Devolve, para cada consulta, os k títulos (normalizados) mais parecidos."""
    docs = codificar([livro["doc"] for livro in livros])
    qs = codificar(consultas)
    sims = qs @ docs.T
    titulos = [norm(livro["titulo"]) for livro in livros]
    ordem = np.argsort(-sims, axis=1)[:, :k]
    return [[titulos[j] for j in linha] for linha in ordem]


def avaliar_conjunto(codificar, livros, consultas, esperados) -> dict:
    return metricas(ranquear(codificar, livros, consultas), esperados)


def avaliar_modelo(codificar, livros) -> dict:
    resultado: dict[str, dict] = {}

    validacao = ler_jsonl(SAIDA / "pares_validacao.jsonl")
    resultado["validacao_livros_nao_vistos"] = avaliar_conjunto(
        codificar,
        livros,
        [p["consulta"] for p in validacao],
        [{norm(p["livro"])} for p in validacao],
    )

    casos = ler_jsonl(CASOS_MANUAIS)
    por_tipo: dict[str, list[dict]] = defaultdict(list)
    for caso in casos:
        por_tipo[caso["tipo"]].append(caso)
    por_tipo["geral"] = casos
    for tipo, grupo in sorted(por_tipo.items()):
        resultado[f"casos_manuais/{tipo}"] = avaliar_conjunto(
            codificar,
            livros,
            [c["consulta"] for c in grupo],
            [{norm(e) for e in c["esperados"]} for c in grupo],
        )
    return resultado


def codificador(caminho_ou_nome: str):
    from sentence_transformers import SentenceTransformer

    modelo = SentenceTransformer(caminho_ou_nome)
    modelo.max_seq_length = MAX_TOKENS
    return lambda textos: modelo.encode(
        textos, normalize_embeddings=True, batch_size=32, show_progress_bar=False
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ajustado", default=str(SAIDA / "modelo"))
    args = ap.parse_args()

    livros = carregar_catalogo()
    antes = avaliar_modelo(codificador(MODELO_BASE), livros)
    depois = avaliar_modelo(codificador(args.ajustado), livros)

    print(f"{'conjunto':<34}{'n':>5}{'R@5 antes':>11}{'R@5 depois':>12}{'nDCG antes':>12}{'nDCG depois':>13}")
    for chave in antes:
        a, d = antes[chave], depois[chave]
        print(
            f"{chave:<34}{a['n']:>5}{a['recall@5']:>11}{d['recall@5']:>12}"
            f"{a['ndcg@10']:>12}{d['ndcg@10']:>13}"
        )

    RESULTADOS.mkdir(parents=True, exist_ok=True)
    destino = RESULTADOS / f"embeddings_ajuste_{date.today().isoformat()}.json"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(
            {
                "data": date.today().isoformat(),
                "modelo_base": MODELO_BASE,
                "busca": "somente vetor (cosseno), sem reranker",
                "antes": antes,
                "depois": depois,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nResultados em {destino}")


if __name__ == "__main__":
    main()

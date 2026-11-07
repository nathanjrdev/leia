"""Roda a suíte de avaliação da busca, com e sem reranker, e imprime/grava o relatório.

Uso (em api/):
  uv run --group ml python ../evals/run_busca.py            # resumo
  uv run --group ml python ../evals/run_busca.py --falhas   # lista cada caso que errou
"""

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from leia_api.avaliacao import Caso, carregar_casos, ndcg_at_k, recall_at_k, relevancias
from leia_api.busca import Reranker, buscar_livros
from leia_api.config import settings
from leia_api.modelos import MODELO_RERANKER, CrossEncoderReranker, EncoderST
from leia_api.models import Autor, livro_autor

AQUI = Path(__file__).parent
K_RECALL, K_NDCG = 5, 10


def _total_relevantes(session: Session, caso: Caso) -> int:
    if caso.autor_esperado:
        return int(
            session.scalar(
                select(func.count())
                .select_from(livro_autor)
                .join(Autor, Autor.id == livro_autor.c.autor_id)
                .where(Autor.nome == caso.autor_esperado)
            )
            or 0
        )
    return len(caso.esperados)


def avaliar(
    session: Session, casos: list[Caso], encoder: EncoderST, reranker: Reranker | None
) -> dict[str, object]:
    por_tipo: dict[str, list[tuple[float, float]]] = defaultdict(list)
    detalhes = []
    for caso in casos:
        resultados = buscar_livros(session, caso.consulta, encoder, limite=10, reranker=reranker)
        rel = relevancias(caso, resultados)
        r5 = recall_at_k(rel, K_RECALL)
        nd = ndcg_at_k(rel, K_NDCG, _total_relevantes(session, caso))
        por_tipo[caso.tipo].append((r5, nd))
        posicao = next((i + 1 for i, ok in enumerate(rel) if ok), None)
        detalhes.append(
            {
                "id": caso.id,
                "tipo": caso.tipo,
                "consulta": caso.consulta,
                "primeira_relevante": posicao,
                "top5": [r.titulo for r in resultados[:5]],
                "esperados": caso.esperados or [f"(autor) {caso.autor_esperado}"],
            }
        )
    todos = [par for pares in por_tipo.values() for par in pares]

    def media(pares: list[tuple[float, float]], i: int) -> float:
        return round(sum(p[i] for p in pares) / len(pares), 3) if pares else 0.0

    resumo = {
        t: {"n": len(p), "recall@5": media(p, 0), "ndcg@10": media(p, 1)}
        for t, p in por_tipo.items()
    }
    resumo["geral"] = {"n": len(todos), "recall@5": media(todos, 0), "ndcg@10": media(todos, 1)}
    return {"resumo": resumo, "casos": detalhes}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--falhas", action="store_true", help="lista os casos fora do top 5")
    args = ap.parse_args()

    casos = carregar_casos(AQUI / "busca_casos.jsonl")
    print(f"{len(casos)} casos. Carregando modelos...", flush=True)
    encoder = EncoderST()
    configs: dict[str, Reranker | None] = {
        "sem_reranker": None,
        "com_reranker": CrossEncoderReranker(),
    }

    relatorio: dict[str, object] = {"data": date.today().isoformat(), "reranker": MODELO_RERANKER}
    with Session(create_engine(settings.database_url)) as session:
        for nome, reranker in configs.items():
            resultado = avaliar(session, casos, encoder, reranker)
            relatorio[nome] = resultado
            print(f"\n== {nome} ==")
            for tipo, m in resultado["resumo"].items():  # type: ignore[attr-defined]
                print(
                    f"  {tipo:9} n={m['n']:2}  Recall@5={m['recall@5']:.3f}"
                    f"  nDCG@10={m['ndcg@10']:.3f}"
                )
            if args.falhas:
                for c in resultado["casos"]:  # type: ignore[attr-defined]
                    if not c["primeira_relevante"] or c["primeira_relevante"] > K_RECALL:
                        print(
                            f"  ✗ {c['id']} «{c['consulta']}»\n"
                            f"      esperado {c['esperados']}\n      obtido   {c['top5']}"
                        )

    saida = AQUI / "resultados" / "busca.json"
    saida.parent.mkdir(exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRelatório gravado em {saida}")


if __name__ == "__main__":
    main()

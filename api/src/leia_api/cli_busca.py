"""Busca manual no catálogo, para testar e validar na mão.

Uso (em api/):
  uv run --group ml python -m leia_api.cli_busca "um romance sobre memória"
  uv run --group ml python -m leia_api.cli_busca --reranker --limite 8 "Torto Arado"
  uv run --group ml python -m leia_api.cli_busca            # modo interativo
"""

import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from leia_api.busca import Reranker, buscar_livros
from leia_api.config import settings
from leia_api.modelos import CrossEncoderReranker, EncoderST


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Busca manual no catálogo do Léia")
    ap.add_argument("consulta", nargs="?", help="sem consulta, abre o modo interativo")
    ap.add_argument("--limite", type=int, default=5)
    ap.add_argument("--reranker", action="store_true", help="reordena com o cross-encoder")
    ap.add_argument("--categoria", help="slug, ex.: poesia, romance, contos, infantojuvenil")
    ap.add_argument("--ano-min", type=int)
    ap.add_argument("--ano-max", type=int)
    ap.add_argument("--disponiveis", action="store_true", help="só livros com exemplar livre")
    args = ap.parse_args(argv)

    print("Carregando modelos...", flush=True)
    encoder = EncoderST()
    reranker: Reranker | None = CrossEncoderReranker() if args.reranker else None

    with Session(create_engine(settings.database_url)) as session:

        def buscar(consulta: str) -> None:
            resultados = buscar_livros(
                session,
                consulta,
                encoder,
                limite=args.limite,
                categoria=args.categoria,
                ano_min=args.ano_min,
                ano_max=args.ano_max,
                apenas_disponiveis=args.disponiveis,
                reranker=reranker,
            )
            if not resultados:
                print("  (nenhum resultado)")
            for i, r in enumerate(resultados, 1):
                disp = f"{r.livres} livre(s)" if r.livres else f"indisponível, fila {r.fila}"
                print(f"  {i}. {r.titulo} — {', '.join(r.autores)} ({r.ano or 's/d'}) | {disp}")

        if args.consulta:
            buscar(args.consulta)
            return
        print("Digite uma consulta (linha vazia ou Ctrl-D para sair).")
        while True:
            try:
                consulta = input("busca> ").strip()
            except EOFError:
                break
            if not consulta:
                break
            buscar(consulta)


if __name__ == "__main__":
    main()

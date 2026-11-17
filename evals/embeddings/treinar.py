"""Ajuste fino do encoder da Leia com perda contrastiva.

Uso:  python evals/embeddings/treinar.py --epocas 3

Entrada: saida/pares_treino.jsonl (de gerar_pares.py)
Saída:   saida/modelo/  (modelo ajustado, pronto para avaliar e publicar)

Dica: com CPU, ~1.000 pares levam alguns minutos a algumas dezenas de minutos.
Com GPU (Colab ou Kaggle gratuitos), menos de 5 minutos.
"""

from __future__ import annotations

import argparse

from comum import (
    CASOS_MANUAIS,
    MAX_TOKENS,
    MODELO_BASE,
    SAIDA,
    SEMENTE,
    carregar_catalogo,
    ler_jsonl,
    norm,
    pares_do_catalogo,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epocas", type=int, default=3)
    ap.add_argument("--lote", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument(
        "--com-catalogo",
        action="store_true",
        help="acrescenta pedidos de título e de autor gerados do catálogo (ver comum.py)",
    )
    args = ap.parse_args()

    import torch
    from datasets import Dataset
    from sentence_transformers import (
        SentenceTransformer,
        SentenceTransformerTrainer,
        SentenceTransformerTrainingArguments,
        losses,
    )
    from sentence_transformers.training_args import BatchSamplers

    livros = carregar_catalogo()
    docs = {norm(livro["titulo"]): livro["doc"] for livro in livros}
    pares = [p for p in ler_jsonl(SAIDA / "pares_treino.jsonl") if norm(p["livro"]) in docs]
    if args.com_catalogo:
        extras = pares_do_catalogo(livros, ler_jsonl(CASOS_MANUAIS))
        n_tit = sum(1 for p in extras if p["origem"] == "catalogo-titulo")
        print(f"+ {len(extras)} pares do catálogo ({n_tit} de título, {len(extras) - n_tit} de autor)")
        pares += extras
    if len(pares) < 100:
        raise SystemExit(f"Só {len(pares)} pares. Rode gerar_pares.py primeiro.")
    print(f"{len(pares)} pares de treino | {len({norm(p['livro']) for p in pares})} livros")

    treino = Dataset.from_dict(
        {
            "anchor": [p["consulta"] for p in pares],
            "positive": [docs[norm(p["livro"])] for p in pares],
        }
    )

    modelo = SentenceTransformer(MODELO_BASE)
    modelo.max_seq_length = MAX_TOKENS
    perda = losses.MultipleNegativesRankingLoss(modelo)

    treino_args = SentenceTransformerTrainingArguments(
        output_dir=str(SAIDA / "checkpoints"),
        num_train_epochs=args.epocas,
        per_device_train_batch_size=args.lote,
        learning_rate=args.lr,
        warmup_ratio=0.1,
        fp16=torch.cuda.is_available(),
        # Vários pedidos do mesmo livro não podem cair no mesmo lote:
        # um serviria de "negativo" para o outro e atrapalharia o treino.
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        save_strategy="no",
        logging_steps=10,
        report_to="none",
        seed=SEMENTE,
    )
    SentenceTransformerTrainer(
        model=modelo, args=treino_args, train_dataset=treino, loss=perda
    ).train()

    destino = SAIDA / "modelo"
    modelo.save(str(destino))
    print(f"Modelo salvo em {destino}")


if __name__ == "__main__":
    main()

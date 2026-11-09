"""Publica o dataset e o modelo no Hugging Face (privados por padrão).

Uso:
    python evals/embeddings/publicar_hf.py                 # simulação: só mostra o que enviaria
    python evals/embeddings/publicar_hf.py --confirmar     # envia como repositórios PRIVADOS
    python evals/embeddings/publicar_hf.py --confirmar --publico   # envia já públicos

Lê o token de HF_TOKEN (variável de ambiente ou .env). Nunca imprime o token.
Exige ter rodado avaliar.py antes: os números do model card vêm do JSON de resultados.
Por padrão o dataset NÃO inclui as sinopses (parte delas veio da Wikipedia, CC BY-SA, e as
demais foram redigidas por IA). Use --incluir-sinopses só depois de conferir as licenças.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil

from comum import MODELO_BASE, RAIZ, RESULTADOS, SAIDA, carregar_catalogo, ler_jsonl, escrever_jsonl


def ultimo_resultado() -> dict:
    arquivos = sorted(RESULTADOS.glob("embeddings_ajuste_*.json"))
    if not arquivos:
        raise SystemExit("Rode avaliar.py antes de publicar: o model card precisa dos números.")
    with open(arquivos[-1], encoding="utf-8") as f:
        return json.load(f)


def tabela(res: dict) -> str:
    linhas = ["| Conjunto | n | Recall@5 antes | Recall@5 depois | nDCG@10 antes | nDCG@10 depois |",
              "| --- | --- | --- | --- | --- | --- |"]
    for chave, a in res["antes"].items():
        d = res["depois"][chave]
        linhas.append(
            f"| {chave} | {a['n']} | {a['recall@5']} | {d['recall@5']} | {a['ndcg@10']} | {d['ndcg@10']} |"
        )
    return "\n".join(linhas)


def montar_dataset(destino, incluir_sinopses: bool) -> None:
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    for nome in ("pares_treino", "pares_validacao"):
        shutil.copy(SAIDA / f"{nome}.jsonl", destino / f"{nome}.jsonl")
    shutil.copy(RAIZ / "evals" / "busca_casos.jsonl", destino / "casos_manuais.jsonl")
    campos = ["titulo", "autores", "ano", "isbn", "categorias"] + (
        ["sinopse", "sinopse_fonte"] if incluir_sinopses else []
    )
    escrever_jsonl(destino / "catalogo.jsonl", [{c: l.get(c) for c in campos} for l in carregar_catalogo()])
    licenca = "cc-by-sa-4.0" if incluir_sinopses else "cc-by-4.0"
    (destino / "README.md").write_text(
        f"""---
language:
- pt
license: {licenca}
task_categories:
- sentence-similarity
- text-retrieval
size_categories:
- n<1K
tags:
- livros
- busca-semantica
- sintetico
---

# Leia: pedidos de livros em português

Pares "pedido de leitor → livro" usados para ajustar o encoder da Leia, assistente de IA
para locação de livros ([github.com/nathanjrdev/leia](https://github.com/nathanjrdev/leia)).

## Conteúdo

- `pares_treino.jsonl` e `pares_validacao.jsonl`: pedidos **sintéticos** em português, gerados
  por um LLM a partir dos metadados de cada livro. A divisão é por livro: nenhum livro de
  validação aparece no treino.
- `casos_manuais.jsonl`: casos de teste escritos à mão (título, autor, intenção).
- `catalogo.jsonl`: {len(carregar_catalogo())} livros (título, autores, ano, ISBN, categorias{', sinopse' if incluir_sinopses else ''}).

## Limitações

- Catálogo pequeno ({len(carregar_catalogo())} livros), com foco em literatura brasileira.
- Os pedidos são sintéticos e podem soar mais "limpos" do que pedidos reais.
- Metadados vêm da Open Library; confira os termos de cada fonte antes de reutilizar.
""",
        encoding="utf-8",
    )


def montar_modelo(destino, res: dict) -> None:
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(SAIDA / "modelo", destino)
    (destino / "README.md").write_text(
        f"""---
language:
- pt
license: apache-2.0
library_name: sentence-transformers
base_model: {MODELO_BASE}
pipeline_tag: sentence-similarity
tags:
- sentence-transformers
- embeddings
- busca-semantica
- livros
---

# leia-embeddings-pt

Ajuste fino de `{MODELO_BASE}` para encontrar livros a partir de pedidos em português
(ex.: "um romance curto sobre ciúme"). Usado na busca da Leia
([github.com/nathanjrdev/leia](https://github.com/nathanjrdev/leia)).

## Como foi treinado

- Pares (pedido sintético em português, documento do livro), perda contrastiva
  `MultipleNegativesRankingLoss`, lotes sem duplicatas.
- Divisão **por livro**: os livros de validação nunca foram vistos no treino.
- Dados: [leia-busca-livros-pt](https://huggingface.co/datasets/nathanjrdev/leia-busca-livros-pt).

## Resultados

Busca somente por vetor (cosseno) sobre o catálogo inteiro, sem reranker.

{tabela(res)}

## Como usar

```python
from sentence_transformers import SentenceTransformer

modelo = SentenceTransformer("nathanjrdev/leia-embeddings-pt")
consulta = modelo.encode("um suspense curto para o fim de semana", normalize_embeddings=True)
```

## Limitações

- Treinado e avaliado num catálogo pequeno; não generaliza por conta própria para acervos de
  outros domínios sem nova avaliação.
- Os pedidos de treino são sintéticos. Os conjuntos de avaliação são pequenos, então diferenças
  de poucos pontos podem ser ruído.
""",
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--usuario", default="nathanjrdev")
    ap.add_argument("--confirmar", action="store_true", help="envia de verdade")
    ap.add_argument("--publico", action="store_true", help="cria os repositórios públicos")
    ap.add_argument("--incluir-sinopses", action="store_true")
    args = ap.parse_args()

    res = ultimo_resultado()
    ds_dir, md_dir = SAIDA / "hf_dataset", SAIDA / "hf_modelo"
    montar_dataset(ds_dir, args.incluir_sinopses)
    montar_modelo(md_dir, res)

    repo_ds = f"{args.usuario}/leia-busca-livros-pt"
    repo_md = f"{args.usuario}/leia-embeddings-pt"
    print(f"Dataset montado em {ds_dir} -> {repo_ds}")
    print(f"Modelo montado em  {md_dir} -> {repo_md}")
    print("Revise os dois README.md antes de enviar.")
    if not args.confirmar:
        print("\nSimulação. Nada foi enviado. Use --confirmar para enviar.")
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(RAIZ / ".env")
        load_dotenv(RAIZ / "api" / ".env")
    except ImportError:
        pass
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN não encontrado no ambiente nem no .env.")

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    privado = not args.publico
    for repo, tipo, pasta in ((repo_ds, "dataset", ds_dir), (repo_md, "model", md_dir)):
        api.create_repo(repo, repo_type=tipo, private=privado, exist_ok=True)
        api.upload_folder(repo_id=repo, repo_type=tipo, folder_path=str(pasta))
        print(f"Enviado: https://huggingface.co/{'datasets/' if tipo == 'dataset' else ''}{repo} "
              f"({'privado' if privado else 'público'})")


if __name__ == "__main__":
    main()

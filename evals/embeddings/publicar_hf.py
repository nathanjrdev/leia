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
from pathlib import Path

from comum import MODELO_BASE, RAIZ, RESULTADOS, SAIDA, carregar_catalogo, ler_jsonl, escrever_jsonl


def ultimo_resultado() -> dict:
    arquivos = sorted(RESULTADOS.glob("embeddings_ajuste_*.json"))
    if not arquivos:
        raise SystemExit("Rode avaliar.py antes de publicar: o model card precisa dos números.")
    with open(arquivos[-1], encoding="utf-8") as f:
        return json.load(f)


ROTULOS = {
    "validacao_livros_nao_vistos": "Livros nunca vistos no treino (pedidos sintéticos)",
    "casos_manuais/intencao": "Casos manuais: intenção",
    "casos_manuais/titulo": "Casos manuais: título",
    "casos_manuais/autor": "Casos manuais: autor",
    "casos_manuais/geral": "Casos manuais: geral",
}
CARDS = Path(__file__).resolve().parent / "cards"


def _f(valor) -> str:
    return f"{valor:.3f}" if isinstance(valor, int | float) else str(valor)


def tabela(res: dict) -> str:
    linhas = [
        "| Conjunto | n | Recall@5 antes | Recall@5 depois | nDCG@10 antes | nDCG@10 depois |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for chave in [c for c in ROTULOS if c in res["antes"]]:
        a, d = res["antes"][chave], res["depois"][chave]
        linhas.append(
            f"| {ROTULOS[chave]} | {a['n']} | {_f(a['recall@5'])} | {_f(d['recall@5'])} "
            f"| {_f(a['ndcg@10'])} | {_f(d['ndcg@10'])} |"
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
    # Card versionado em cards/dataset.md (contagens, geradores, filtros e limitações). Se os
    # dados mudarem, atualize o card antes de publicar. A licença muda com as sinopses.
    card = (CARDS / "dataset.md").read_text(encoding="utf-8")
    if incluir_sinopses:
        card = card.replace("license: cc-by-4.0", f"license: {licenca}", 1)
    (destino / "README.md").write_text(card, encoding="utf-8")


def montar_modelo(destino, res: dict) -> None:
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(SAIDA / "modelo", destino)
    # Card versionado em cards/modelo.md; só a tabela vem do último resultado de avaliar.py.
    card = (CARDS / "modelo.md").read_text(encoding="utf-8").replace("{TABELA}", tabela(res))
    (destino / "README.md").write_text(card, encoding="utf-8")


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

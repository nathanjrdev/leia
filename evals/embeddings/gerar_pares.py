"""Gera pedidos sintéticos em português para cada livro do catálogo.

Uso (na raiz do repositório, com o venv da api ativo):
    python evals/embeddings/gerar_pares.py --por-livro 8

Usa o modelo de LEIA_MODEL (LiteLLM). Para custo zero, deixe o Gemini Flash Lite.
É retomável: livros já gerados em saida/pares_todos.jsonl são pulados.
Ao final, divide por LIVRO em treino e validação (os livros de validação
nunca aparecem no treino) e remove pedidos que citam título ou autor.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time

from comum import (
    CASOS_MANUAIS,
    RAIZ,
    SAIDA,
    carregar_catalogo,
    em_validacao,
    escrever_jsonl,
    ler_jsonl,
    norm,
)

PROMPT = """Você simula leitores brasileiros pedindo um livro a uma bibliotecária.
Escreva {n} pedidos DIFERENTES entre si, em português do Brasil, para o livro abaixo.

Regras:
- Cada pedido deve levar a ESTE livro, mas NUNCA citar o título, o autor, nomes de personagens
  nem nomes de lugares ou instituições fictícios da obra: um leitor que ainda não leu não os sabe.
- Todo pedido precisa trazer pelo menos um elemento específico deste livro (tema, enredo, tom,
  época, ambiente ou situação), para distingui-lo dos outros livros do acervo. É PROIBIDO pedido
  genérico que serviria para qualquer livro, como "um clássico curto" ou "um livro brasileiro".
- NÃO comece com saudação ("Oi", "Olá", "Moça", "Bom dia"). Vá direto ao pedido, como numa
  mensagem de chat. Varie as aberturas: não repita "Tem aquele" nem "Quero" em vários pedidos.
- Varie o estilo e o tamanho: tema ou sentimento vago; situação de uso ("para o fim de semana");
  frase curta de 4 a 7 palavras; frase longa e natural; restrição (curto, época, país) sempre
  combinada com um tema.
- Não copie trechos da sinopse. Fale como um leitor comum.
- Responda SOMENTE com um array JSON de strings, sem texto antes ou depois.

Título: {titulo}
Autor: {autores}
Categorias: {categorias}
Sinopse: {sinopse}
"""


def extrair_lista(texto: str) -> list[str]:
    texto = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.MULTILINE).strip()
    inicio, fim = texto.find("["), texto.rfind("]")
    if inicio < 0 or fim < 0:
        return []
    try:
        dados = json.loads(texto[inicio : fim + 1])
    except json.JSONDecodeError:
        return []
    return [d.strip() for d in dados if isinstance(d, str) and d.strip()]


def vaza_titulo_ou_autor(consulta: str, livro: dict) -> bool:
    q = norm(consulta)
    if norm(livro["titulo"]) in q:
        return True
    for autor in livro.get("autores") or []:
        partes = norm(autor).split()
        if partes and len(partes[-1]) >= 4 and partes[-1] in q:
            return True
    return False


def gerar(modelo: str, livro: dict, n: int) -> list[str]:
    from litellm import completion

    prompt = PROMPT.format(
        n=n,
        titulo=livro["titulo"],
        autores=", ".join(livro.get("autores") or []),
        categorias=", ".join(livro.get("categorias") or []),
        sinopse=livro.get("sinopse") or "",
    )
    for tentativa in range(3):
        try:
            resp = completion(
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
            )
            lista = extrair_lista(resp.choices[0].message.content or "")
            if lista:
                return lista
        except Exception as e:  # limite de taxa, rede etc.
            print(f"  tentativa {tentativa + 1} falhou: {type(e).__name__}")
        time.sleep(15 * 2**tentativa)  # 15s, 30s, 60s: limite de taxa de plano gratuito
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--por-livro", type=int, default=8)
    ap.add_argument("--pausa", type=float, default=4.0, help="segundos entre chamadas")
    ap.add_argument("--limite", type=int, default=0, help="só os N primeiros livros (teste)")
    args = ap.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(RAIZ / ".env")
        load_dotenv(RAIZ / "api" / ".env")
    except ImportError:
        pass
    modelo = os.environ.get("LEIA_MODEL")
    if not modelo:
        raise SystemExit("Defina LEIA_MODEL no .env (ex.: gemini/gemini-flash-lite-latest).")

    livros = carregar_catalogo()
    if args.limite:
        livros = livros[: args.limite]
    arquivo = SAIDA / "pares_todos.jsonl"
    existentes = ler_jsonl(arquivo) if arquivo.exists() else []
    feitos = {norm(p["livro"]) for p in existentes}

    for i, livro in enumerate(livros, 1):
        if norm(livro["titulo"]) in feitos:
            continue
        print(f"[{i}/{len(livros)}] {livro['titulo']}")
        for consulta in gerar(modelo, livro, args.por_livro):
            existentes.append({"livro": livro["titulo"], "consulta": consulta})
        escrever_jsonl(arquivo, existentes)  # grava a cada livro: pode interromper e retomar
        time.sleep(args.pausa)

    # Filtros e divisão por livro.
    por_titulo = {norm(l["titulo"]): l for l in livros}
    proibidas = {norm(c["consulta"]) for c in ler_jsonl(CASOS_MANUAIS)}
    vistas: set[tuple[str, str]] = set()
    treino, validacao, descartadas = [], [], 0
    for p in existentes:
        livro = por_titulo.get(norm(p["livro"]))
        chave = (norm(p["livro"]), norm(p["consulta"]))
        if livro is None or chave in vistas or norm(p["consulta"]) in proibidas:
            descartadas += 1
            continue
        if len(p["consulta"].split()) < 4 or vaza_titulo_ou_autor(p["consulta"], livro):
            descartadas += 1
            continue
        vistas.add(chave)
        (validacao if em_validacao(p["livro"]) else treino).append(p)

    escrever_jsonl(SAIDA / "pares_treino.jsonl", treino)
    escrever_jsonl(SAIDA / "pares_validacao.jsonl", validacao)
    livros_val = len({norm(p["livro"]) for p in validacao})
    print(
        f"\nTreino: {len(treino)} pares | Validação: {len(validacao)} pares "
        f"({livros_val} livros nunca vistos no treino) | Descartados: {descartadas}"
    )
    print("Leia uma amostra de saida/pares_treino.jsonl antes de treinar.")


if __name__ == "__main__":
    main()

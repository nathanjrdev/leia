"""Roda a suíte de avaliação do agente (evals/casos/*.jsonl) contra o modelo de LEIA_MODEL.

Uso (em api/, com PYTHONUTF8=1 no Windows, banco no ar e carregado, chave no .env da raiz):
  uv run --group ml python ../evals/run_agente.py                       # tudo
  uv run --group ml python ../evals/run_agente.py --categoria seguranca # uma categoria
  uv run --group ml python ../evals/run_agente.py --id seguranca-003    # um caso
  uv run --group ml python ../evals/run_agente.py --falhas              # detalha cada reprovação
  uv run --group ml python ../evals/run_agente.py --gate                # exit 1 se uma meta falhar

Só usuários fictícios (@leia.example): o plano grátis do Gemini usa os dados. Cada caso zera o
estado do leitor de teste e desfaz o que preparou. Relatório em evals/resultados/agente.json.
"""

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from leia_api.agente import Agente, ConfigAgente
from leia_api.avaliacao_agente import (
    CasoAgente,
    GravadorLLM,
    ResultadoCaso,
    carregar_casos_agente,
    executar_caso,
    resumir,
    resumir_desempenho,
    rodada_valida,
)
from leia_api.busca import Reranker
from leia_api.cli_conversa import carregar_env, exigir_chave
from leia_api.config import settings
from leia_api.llm import ClienteLiteLLM
from leia_api.locacao import RegrasLocacao

AQUI = Path(__file__).parent
RAIZ = AQUI.parent
CASOS = AQUI / "casos"
RELATORIO = AQUI / "resultados" / "agente.json"


def selecionar(categoria: str | None, caso_id: str | None) -> list[CasoAgente]:
    casos = [c for arquivo in sorted(CASOS.glob("*.jsonl")) for c in carregar_casos_agente(arquivo)]
    if categoria:
        casos = [c for c in casos if c.categoria == categoria]
    if caso_id:
        casos = [c for c in casos if c.id == caso_id]
    return casos


def imprimir_resumo(resumo: dict[str, dict[str, Any]]) -> None:
    print("\ncategoria    n  passou  taxa   meta   ok")
    for categoria, r in resumo.items():
        meta = f"{r['meta']:.2f}" if "meta" in r else "  - "
        ok = {True: "sim", False: "NÃO"}.get(r.get("ok"), "-")
        print(f"{categoria:<11} {r['n']:>2}  {r['passou']:>6}  {r['taxa']:.2f}  {meta}  {ok}")


def imprimir_desempenho(d: dict[str, Any]) -> None:
    def seg(v: float | None) -> str:
        return "-" if v is None else f"{v:.2f}s"

    print(
        f"\ndesempenho: {d['turnos']} turnos, latência p50 {seg(d['latencia_p50_s'])} / "
        f"p95 {seg(d['latencia_p95_s'])}; tokens {d['tokens_entrada']} entrada, "
        f"{d['tokens_saida']} saída; custo de referência US$ {d['custo_referencia_usd']:.4f}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Suíte de avaliação do agente Léia")
    ap.add_argument("--categoria", help="ferramenta | grounding | tarefa | seguranca | qualidade")
    ap.add_argument("--id", dest="caso_id", help="roda só este caso")
    ap.add_argument("--pausa", type=float, default=4.0, help="segundos antes de cada turno")
    ap.add_argument("--sem-reranker", action="store_true", help="busca sem cross-encoder")
    ap.add_argument("--falhas", action="store_true", help="detalha os casos reprovados")
    ap.add_argument("--gate", action="store_true", help="sai com código 1 se alguma meta falhar")
    ap.add_argument("--saida", type=Path, default=RELATORIO, help="onde gravar o relatório JSON")
    args = ap.parse_args()

    casos = selecionar(args.categoria, args.caso_id)
    if not casos:
        sys.exit("Nenhum caso selecionado.")

    carregar_env(RAIZ / ".env")
    exigir_chave()

    print(f"Carregando modelos... ({len(casos)} casos, modelo {settings.leia_model})", flush=True)
    from leia_api.modelos import CrossEncoderReranker, EncoderST

    encoder = EncoderST()
    reranker: Reranker | None = None if args.sem_reranker else CrossEncoderReranker()
    gravador = GravadorLLM(ClienteLiteLLM())
    agente = Agente(gravador, ConfigAgente.da_config())
    regras = RegrasLocacao.da_config()

    resultados: list[ResultadoCaso] = []
    with Session(create_engine(settings.database_url)) as session:
        for i, caso in enumerate(casos, 1):
            r = executar_caso(
                caso, agente, gravador, session, encoder, reranker, regras, pausa=args.pausa
            )
            resultados.append(r)
            print(f"[{i}/{len(casos)}] {'ok   ' if r.passou else 'FALHA'} {r.id}", flush=True)
            if not r.passou and args.falhas:
                for falha in r.falhas:
                    print(f"        - {falha}")

    resumo = resumir(resultados)
    imprimir_resumo(resumo)
    desempenho = resumir_desempenho(
        resultados,
        settings.custo_referencia_entrada_usd_por_milhao,
        settings.custo_referencia_saida_usd_por_milhao,
    )
    imprimir_desempenho(desempenho)

    # `agente.json` é a última rodada COMPLETA e VÁLIDA: rodada parcial (filtro) ou invalidada por
    # falha de infraestrutura (erro_llm, timeout) vai para `agente_parcial.json`.
    completa = not (args.categoria or args.caso_id)
    saida = args.saida
    if saida == RELATORIO and not (completa and rodada_valida(resultados)):
        saida = RELATORIO.with_name("agente_parcial.json")
        motivo = "filtro de casos" if not completa else "falha de infraestrutura (erro_llm/timeout)"
        print(f"\nRodada não oficial ({motivo}): {RELATORIO.name} fica como estava.")
    saida.parent.mkdir(parents=True, exist_ok=True)
    relatorio = {
        "data": datetime.now().isoformat(timespec="seconds"),
        "modelo": settings.leia_model,
        "prompt": settings.prompt_versao,
        "reranker": reranker is not None,
        "valida": rodada_valida(resultados),
        "resumo": resumo,
        "desempenho": desempenho,
        "casos": [asdict(r) for r in resultados],
    }
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRelatório: {saida}")

    if args.gate and any(r.get("ok") is False for r in resumo.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()

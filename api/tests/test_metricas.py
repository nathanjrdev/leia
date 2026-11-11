"""Resumo de latência do turno: só números e nomes, nunca o texto do leitor."""

import json
import logging

import pytest

from leia_api.agente import ChamadaAuditada, ChamadaLLMMedida, MetricasTurno
from leia_api.metricas import registrar_turno, resumo_do_turno

SEGREDO = "texto-do-leitor-que-nao-pode-vazar"


def _metricas() -> MetricasTurno:
    return MetricasTurno(
        latencia_ms=4200,
        chamadas_llm=[
            ChamadaLLMMedida(latencia_ms=900, tokens_entrada=1800, tokens_saida=20, ferramentas=1),
            ChamadaLLMMedida(
                latencia_ms=1100, tokens_entrada=2600, tokens_saida=150, ferramentas=0
            ),
        ],
        regeracoes=0,
    )


def _auditoria() -> list[ChamadaAuditada]:
    return [
        ChamadaAuditada(
            nome="buscar_livros",
            argumentos={"consulta": SEGREDO},
            resultado={"ok": True, "resultados": [{"titulo": SEGREDO}]},
            latencia_ms=2100,
            etapas_ms={"encode": 40, "reranker": 1900},
        )
    ]


def test_resumo_tem_tempos_tokens_e_contagens() -> None:
    r = resumo_do_turno(
        _metricas(), _auditoria(), total_ms=4500, origem="mensagem", erro=None, conversa_id=7
    )

    assert r["evento"] == "turno"
    assert r["conversa_id"] == 7 and r["origem"] == "mensagem" and r["erro"] is None
    assert r["total_ms"] == 4500 and r["agente_ms"] == 4200
    assert r["llm_ms"] == 2000 and r["n_llm"] == 2 and r["llm_lista_ms"] == [900, 1100]
    assert r["tokens_entrada"] == 4400 and r["tokens_saida"] == 170
    assert r["regeracoes"] == 0
    assert r["ferramentas"] == [
        {"nome": "buscar_livros", "ms": 2100, "etapas_ms": {"encode": 40, "reranker": 1900}}
    ]
    assert r["ferramentas_ms"] == 2100


def test_resumo_nao_leva_texto_do_leitor_nem_resultado() -> None:
    r = resumo_do_turno(
        _metricas(), _auditoria(), total_ms=1, origem="clique", erro="timeout", conversa_id=1
    )
    assert SEGREDO not in json.dumps(r, ensure_ascii=False)


def test_tokens_desconhecidos_somam_como_nulos() -> None:
    m = MetricasTurno(
        latencia_ms=10,
        chamadas_llm=[ChamadaLLMMedida(latencia_ms=10, tokens_entrada=None, tokens_saida=None)],
        regeracoes=0,
    )
    r = resumo_do_turno(m, [], total_ms=12, origem="mensagem", erro=None, conversa_id=1)
    assert r["tokens_entrada"] is None and r["tokens_saida"] is None


def test_resumo_leva_a_causa_das_falhas_do_llm() -> None:
    m = MetricasTurno(
        latencia_ms=10,
        chamadas_llm=[
            ChamadaLLMMedida(10, None, None, erro="erro_llm", causa="RateLimitError:429"),
        ],
        regeracoes=0,
    )
    r = resumo_do_turno(m, [], total_ms=12, origem="mensagem", erro="erro_llm", conversa_id=1)
    assert r["llm_causas"] == ["RateLimitError:429"]
    sem_falha = resumo_do_turno(
        _metricas(), [], total_ms=1, origem="mensagem", erro=None, conversa_id=1
    )
    assert sem_falha["llm_causas"] == []


def test_registrar_turno_loga_uma_linha_json(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="leia_api.metricas"):
        registrar_turno({"evento": "turno", "total_ms": 3})
    linhas = [r for r in caplog.records if r.name == "leia_api.metricas"]
    assert len(linhas) == 1
    assert json.loads(linhas[0].getMessage()) == {"evento": "turno", "total_ms": 3}

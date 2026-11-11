"""Latência do turno do chat, como uma linha de log JSON (logger `leia_api.metricas`).

Só números e nomes de ferramenta: nem o texto do leitor, nem os argumentos, nem o resultado
das ferramentas (a consulta da busca é texto do leitor). Serve para medir onde o turno gasta
tempo (LLM, busca por etapa, banco) sem mudar o comportamento do agente.
"""

import json
import logging
import sys
from typing import Any, Literal

from leia_api.agente import ChamadaAuditada, MetricasTurno

log = logging.getLogger(__name__)

Origem = Literal["mensagem", "clique"]


def resumo_do_turno(
    metricas: MetricasTurno,
    auditoria: list[ChamadaAuditada],
    *,
    total_ms: int,
    origem: Origem,
    erro: str | None,
    conversa_id: int,
) -> dict[str, Any]:
    ferramentas = [
        {"nome": c.nome, "ms": c.latencia_ms, "etapas_ms": c.etapas_ms} for c in auditoria
    ]
    return {
        "evento": "turno",
        "conversa_id": conversa_id,
        "origem": origem,
        "erro": erro,
        "total_ms": total_ms,  # da rota: banco + agente (antes de transmitir a resposta)
        "agente_ms": metricas.latencia_ms,
        "llm_ms": metricas.llm_ms,
        "n_llm": len(metricas.chamadas_llm),
        "llm_lista_ms": [c.latencia_ms for c in metricas.chamadas_llm],
        # tipo da exceção e status HTTP das chamadas que falharam (ex.: "RateLimitError:429")
        "llm_causas": [c.causa for c in metricas.chamadas_llm if c.causa],
        "tokens_entrada": metricas.tokens_entrada,
        "tokens_saida": metricas.tokens_saida,
        "regeracoes": metricas.regeracoes,
        "ferramentas_ms": sum(c.latencia_ms for c in auditoria),
        "ferramentas": ferramentas,
    }


def registrar_turno(resumo: dict[str, Any]) -> None:
    log.info(json.dumps(resumo, ensure_ascii=False))


def configurar_log() -> None:
    """Faz as linhas de métrica aparecerem no console do uvicorn (ele só configura os seus)."""
    if log.handlers:
        return
    saida = logging.StreamHandler(sys.stderr)
    saida.setFormatter(logging.Formatter("%(asctime)s %(name)s %(message)s"))
    log.addHandler(saida)
    log.setLevel(logging.INFO)

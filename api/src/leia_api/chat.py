"""Rotas do chat: conversas, mensagens com resposta por SSE e confirmação por clique.

Eventos do stream, nesta ordem: `ferramenta`* (uma por ferramenta que o agente vai usar),
`acao` (só no clique: resultado da confirmação), `resposta`* (a resposta em pedaços),
`propostas` (botões de confirmação, se houver) e `fim` (`erro` nulo ou o código).

O clique NUNCA é texto: a rota executa a ação e o agente recebe um `EventoApp` (ver `canal.py`).
O turno roda numa thread própria com sessão de banco própria e termina (e persiste) mesmo que o
navegador feche a conexão no meio.
"""

import json
import logging
import queue
import re
import threading
from collections.abc import Callable, Iterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.orm import Session

from leia_api import conversas
from leia_api.agente import Agente
from leia_api.auth import erro_json, usuario_atual
from leia_api.busca import Reranker
from leia_api.canal import EventoApp, evento_de_cancelamento, evento_de_confirmacao
from leia_api.config import settings
from leia_api.contas import Conta
from leia_api.db import get_session
from leia_api.dependencias import get_agente, get_encoder, get_fabrica_sessao, get_reranker
from leia_api.embeddings import Encoder
from leia_api.ferramentas import AcaoPendente, ContextoFerramentas, cancelar_acao, confirmar_acao
from leia_api.locacao import RegrasLocacao

log = logging.getLogger(__name__)
router = APIRouter(prefix="/conversas", tags=["conversas"])

Decisao = Literal["confirmar", "cancelar"]
Emitir = Callable[[str, dict[str, Any]], None]
Fabrica = Callable[[], Session]


class _Corpo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MensagemIn(_Corpo):
    texto: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=settings.mensagem_max_caracteres
        ),
    ]


class DecisaoIn(_Corpo):
    decisao: Decisao


def _pedacos(texto: str, tamanho: int) -> Iterator[str]:
    atual = ""
    for palavra in re.findall(r"\S+\s*", texto):
        if atual and len(atual) + len(palavra) > tamanho:
            yield atual
            atual = ""
        atual += palavra
    if atual:
        yield atual


def _turno(
    fabrica: Fabrica,
    agente: Agente,
    encoder: Encoder,
    reranker: Reranker | None,
    conversa_id: int,
    usuario_id: int,
    emitir: Emitir,
    texto: str | None,
    clique: tuple[str, AcaoPendente, Decisao] | None,
) -> None:
    with fabrica() as s:
        conversa = conversas.obter(s, conversa_id, usuario_id)
        if conversa is None:  # a conversa sumiu entre a checagem e o turno
            emitir("fim", {"erro": "conversa_inexistente"})
            return
        if texto is not None:  # mensagem nova invalida os botões anteriores
            conversas.invalidar_pendentes(s, conversa_id)
        ctx = ContextoFerramentas(
            session=s,
            usuario_id=usuario_id,
            encoder=encoder,
            reranker=reranker,
            regras=RegrasLocacao.da_config(),
            livros_vistos={int(i) for i in conversa.livros_vistos},
            pendentes=conversas.carregar_pendentes(s, conversa_id),
        )
        eventos: list[EventoApp] = []
        if clique is not None:
            token, pendente, decisao = clique
            ctx.pendentes[token] = pendente
            if decisao == "confirmar":
                resultado = confirmar_acao(ctx, token)
                eventos = [evento_de_confirmacao([resultado])]
                emitir(
                    "acao",
                    {
                        "decisao": decisao,
                        "ok": bool(resultado.get("ok")),
                        "erro": resultado.get("erro"),
                    },
                )
            else:
                cancelar_acao(ctx, token)
                eventos = [evento_de_cancelamento([pendente.resumo])]
                emitir("acao", {"decisao": decisao, "ok": True, "erro": None})
        historico = conversas.historico_para_agente(s, conversa_id)
        resposta = agente.responder(ctx, historico, texto, eventos, observador=emitir)
        if texto is not None:
            conversas.registrar(s, conversa_id, "usuario", resposta.historico[-2]["content"])
        else:
            conversas.registrar(s, conversa_id, "sistema", "\n".join(eventos[0].linhas))
        conversas.registrar(s, conversa_id, "assistente", resposta.texto)
        conversa.livros_vistos = sorted(ctx.livros_vistos)
        conversas.sincronizar_pendentes(s, conversa_id, ctx)  # faz o commit
    for pedaco in _pedacos(resposta.texto, settings.stream_pedaco_caracteres):
        emitir("resposta", {"texto": pedaco})
    if resposta.propostas:
        emitir(
            "propostas",
            {
                "propostas": [
                    {"confirmacao_id": p.confirmacao_id, "resumo": p.resumo}
                    for p in resposta.propostas
                ]
            },
        )
    emitir("fim", {"erro": resposta.erro})


def _stream(**turno: Any) -> StreamingResponse:
    fila: queue.Queue[tuple[str, dict[str, Any]] | None] = queue.Queue()

    def emitir(evento: str, dados: dict[str, Any]) -> None:
        fila.put((evento, dados))

    def trabalho() -> None:
        try:
            _turno(emitir=emitir, **turno)
        except Exception as erro:  # noqa: BLE001 - nada de detalhe interno para o navegador
            log.error("falha no turno do chat: %s", type(erro).__name__)
            emitir("fim", {"erro": "erro_interno"})
        finally:
            fila.put(None)

    threading.Thread(target=trabalho, daemon=True).start()

    def gerar() -> Iterator[str]:
        while (item := fila.get()) is not None:
            evento, dados = item
            yield f"event: {evento}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _conversa_inexistente() -> JSONResponse:
    return erro_json(404, "conversa_inexistente", "Conversa não encontrada.")


@router.post("", status_code=201)
def criar(
    conta: Annotated[Conta, Depends(usuario_atual)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    return {"id": conversas.criar(session, conta.id)}


@router.get("/{conversa_id}/mensagens", response_model=None)
def historico(
    conversa_id: int,
    conta: Annotated[Conta, Depends(usuario_atual)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, str]] | JSONResponse:
    if conversas.obter(session, conversa_id, conta.id) is None:
        return _conversa_inexistente()
    return conversas.historico_publico(session, conversa_id)


@router.post("/{conversa_id}/mensagens", response_model=None)
def mensagem(
    conversa_id: int,
    corpo: MensagemIn,
    conta: Annotated[Conta, Depends(usuario_atual)],
    session: Annotated[Session, Depends(get_session)],
    fabrica: Annotated[Fabrica, Depends(get_fabrica_sessao)],
    agente: Annotated[Agente, Depends(get_agente)],
    encoder: Annotated[Encoder, Depends(get_encoder)],
    reranker: Annotated[Reranker | None, Depends(get_reranker)],
) -> StreamingResponse | JSONResponse:
    if conversas.obter(session, conversa_id, conta.id) is None:
        return _conversa_inexistente()
    return _stream(
        fabrica=fabrica,
        agente=agente,
        encoder=encoder,
        reranker=reranker,
        conversa_id=conversa_id,
        usuario_id=conta.id,
        texto=corpo.texto,
        clique=None,
    )


@router.post("/{conversa_id}/confirmacoes/{confirmacao_id}", response_model=None)
def confirmacao(
    conversa_id: int,
    confirmacao_id: str,
    corpo: DecisaoIn,
    conta: Annotated[Conta, Depends(usuario_atual)],
    session: Annotated[Session, Depends(get_session)],
    fabrica: Annotated[Fabrica, Depends(get_fabrica_sessao)],
    agente: Annotated[Agente, Depends(get_agente)],
    encoder: Annotated[Encoder, Depends(get_encoder)],
    reranker: Annotated[Reranker | None, Depends(get_reranker)],
) -> StreamingResponse | JSONResponse:
    if conversas.obter(session, conversa_id, conta.id) is None:
        return _conversa_inexistente()
    pendente = conversas.reivindicar(session, conversa_id, conta.id, confirmacao_id)
    if pendente is None:
        return erro_json(404, "confirmacao_inexistente", "Não há ação pendente com esse código.")
    return _stream(
        fabrica=fabrica,
        agente=agente,
        encoder=encoder,
        reranker=reranker,
        conversa_id=conversa_id,
        usuario_id=conta.id,
        texto=None,
        clique=(confirmacao_id, pendente, corpo.decisao),
    )

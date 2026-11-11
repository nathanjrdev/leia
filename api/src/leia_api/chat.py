"""Rotas do chat: conversas, mensagens com resposta por SSE e confirmação por clique.

Eventos do stream, nesta ordem: `acao` (só no clique: resultado da confirmação, antes de tudo),
`ferramenta`* (uma por ferramenta que o agente vai usar) e `etapa`* (`escrevendo` depois das
ferramentas, `revisando` se o grounding mandou regerar), intercalados conforme o andamento;
`resposta`* (a resposta em pedaços: com `STREAM_TOKENS`, enquanto o modelo escreve, cada
título entre aspas só depois de conferido; sem, a resposta já validada no fim), `descartar` (a
tela apaga o texto parcial: a resposta vai ser refeita ou trocada pela final),
`livros` (cartões dos livros que a resposta cita, dados do banco; só se citar algum),
`propostas` (botões de confirmação, se houver) e `fim` (`erro` nulo ou o código).

O clique NUNCA é texto: a rota executa a ação e o agente recebe um `EventoApp` (ver `canal.py`).
O turno roda numa thread própria com sessão de banco própria e termina (e persiste) mesmo que o
navegador feche a conexão no meio.
"""

import dataclasses
import json
import logging
import queue
import re
import secrets
import threading
import time
import unicodedata
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
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
from leia_api.metricas import registrar_turno, resumo_do_turno

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


class AcaoIn(_Corpo):
    """Clique no cartão de um livro citado na conversa (o cartão já pediu a confirmação)."""

    acao: Literal["locar", "reservar"]
    livro_id: Annotated[int, Field(ge=1)]


class TurnosEmAndamento:
    """Conversas com um turno rodando agora: um turno por vez em cada conversa.

    Dois envios quase juntos (duplo Enter, clique duplo) gerariam duas respostas e
    embaralhariam o histórico. Vale para um processo só (o deploy roda um worker); com mais de
    um, a trava teria de ir para o banco.
    """

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._ocupadas: set[int] = set()

    def ocupar(self, conversa_id: int) -> bool:
        with self._trava:
            if conversa_id in self._ocupadas:
                return False
            self._ocupadas.add(conversa_id)
            return True

    def liberar(self, conversa_id: int) -> None:
        with self._trava:
            self._ocupadas.discard(conversa_id)

    def ocupada(self, conversa_id: int) -> bool:
        with self._trava:
            return conversa_id in self._ocupadas


turnos = TurnosEmAndamento()


def _data_local(iso: str) -> str:
    """dd/mm/aaaa no fuso de Brasília (o mesmo dia que a tela mostra), ou UTC sem tzdata."""
    momento = datetime.fromisoformat(iso)
    try:
        momento = momento.astimezone(ZoneInfo("America/Sao_Paulo"))
    except ZoneInfoNotFoundError:
        pass
    return momento.strftime("%d/%m/%Y")


def aviso_da_acao(resultado: dict[str, Any]) -> str | None:
    """Texto fixo de uma ação concluída, para quando o LLM falha depois dela.

    A ação já aconteceu: o leitor precisa ver isso, não "tive um problema".
    """
    if not resultado.get("ok") or not resultado.get("titulo"):
        return None
    titulo = resultado["titulo"]
    if resultado.get("acao") == "locar" and resultado.get("prevista_em"):
        return (
            f"Pronto! “{titulo}” está com você. "
            f"Devolução até {_data_local(resultado['prevista_em'])}. Boa leitura!"
        )
    if resultado.get("acao") == "reservar" and resultado.get("posicao"):
        return f"Pronto! Você entrou na fila de “{titulo}”, na posição {resultado['posicao']}."
    return None


def _pedacos(texto: str, tamanho: int) -> Iterator[str]:
    atual = ""
    for palavra in re.findall(r"\S+\s*", texto):
        if atual and len(atual) + len(palavra) > tamanho:
            yield atual
            atual = ""
        atual += palavra
    if atual:
        yield atual


def _normalizar(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)
    )
    return " ".join(sem_acento.casefold().split())


def _cartoes_citados(cartoes: dict[int, dict[str, Any]], texto: str) -> list[dict[str, Any]]:
    """Cartões dos livros que o texto cita (título inteiro, sem acento nem caixa).

    Saem na ordem em que aparecem no texto. Os dados vêm do banco via ferramenta; o LLM só
    decide quais livros menciona.
    """
    corpo = _normalizar(texto)
    achados: list[tuple[int, dict[str, Any]]] = []
    for cartao in cartoes.values():
        titulo = _normalizar(cartao["titulo"])
        if not titulo:
            continue
        achou = re.search(rf"(?<!\w){re.escape(titulo)}(?!\w)", corpo)
        if achou:
            achados.append((achou.start(), cartao))
    achados.sort(key=lambda par: par[0])
    return [cartao for _, cartao in achados[: settings.cartoes_por_resposta]]


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
    inicio = time.perf_counter()
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
        aviso_fixo: str | None = None  # se o LLM falhar depois de uma ação concluída
        if clique is not None:
            token, pendente, decisao = clique
            ctx.pendentes[token] = pendente
            if decisao == "confirmar":
                resultado = confirmar_acao(ctx, token)
                aviso_fixo = aviso_da_acao(resultado)
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
        transmitido: list[str] = []  # o que o streaming já pôs na tela (após `descartar`)

        def observar(evento: str, dados: dict[str, Any]) -> None:
            if evento == "resposta":
                transmitido.append(str(dados["texto"]))
            elif evento == "descartar":
                transmitido.clear()
            emitir(evento, dados)

        resposta = agente.responder(ctx, historico, texto, eventos, observador=observar)
        if aviso_fixo is not None and resposta.erro in ("erro_llm", "timeout"):
            resposta = dataclasses.replace(resposta, texto=aviso_fixo)
        if texto is not None:
            conversas.registrar(s, conversa_id, "usuario", resposta.historico[-2]["content"])
        else:
            conversas.registrar(s, conversa_id, "sistema", "\n".join(eventos[0].linhas))
        conversas.registrar(s, conversa_id, "assistente", resposta.texto)
        conversas.auditar(s, conversa_id, resposta.auditoria)
        conversa.livros_vistos = sorted(ctx.livros_vistos)
        cartoes_do_turno = dict(ctx.cartoes)
        conversas.sincronizar_pendentes(s, conversa_id, ctx)  # faz o commit
    registrar_turno(
        resumo_do_turno(
            resposta.metricas,
            resposta.auditoria,
            total_ms=round((time.perf_counter() - inicio) * 1000),
            origem="mensagem" if texto is not None else "clique",
            erro=resposta.erro,
            conversa_id=conversa_id,
        )
    )
    # A resposta final (já validada) é a que vale. O streaming costuma tê-la mostrado inteira;
    # se mostrou só o começo, completa; se o final for outro (resposta segura, erro), troca.
    na_tela = "".join(transmitido).lstrip()  # o que o leitor está vendo, como foi enviado
    if na_tela.strip() == resposta.texto:
        falta = ""  # já está inteira (o final só perde espaços das pontas)
    elif na_tela.strip() and resposta.texto.startswith(na_tela):
        falta = resposta.texto[len(na_tela) :]
    else:
        if na_tela.strip():
            emitir("descartar", {})
        falta = resposta.texto
    pedacos = list(_pedacos(falta, settings.stream_pedaco_caracteres))
    if pedacos and (espaco := falta[: len(falta) - len(falta.lstrip())]):
        pedacos[0] = espaco + pedacos[0]  # ao completar um parcial, não cola as palavras
    for pedaco in pedacos:
        emitir("resposta", {"texto": pedaco})
    if cartoes := _cartoes_citados(cartoes_do_turno, resposta.texto):
        emitir("livros", {"livros": cartoes})
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
            turnos.liberar(turno["conversa_id"])  # a rota ocupou a conversa antes do turno
            fila.put(None)

    threading.Thread(target=trabalho, daemon=True).start()

    def gerar() -> Iterator[str]:
        while (item := fila.get()) is not None:
            evento, dados = item
            yield f"event: {evento}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        # no-transform: proxies que comprimem (o do Next com gzip) acumulam o SSE até o fim;
        # com ele, o andamento e o texto chegam ao navegador durante o turno.
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


def _conversa_inexistente() -> JSONResponse:
    return erro_json(404, "conversa_inexistente", "Conversa não encontrada.")


def _turno_em_andamento() -> JSONResponse:
    return erro_json(
        409, "turno_em_andamento", "A Léia ainda está respondendo. Espere a resposta terminar."
    )


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
    if conversas.mensagens_do_dia(session, conta.id) >= settings.mensagens_por_dia:
        return erro_json(
            429, "limite_diario", "Você atingiu o limite de mensagens de hoje. Volte amanhã."
        )
    if not turnos.ocupar(conversa_id):
        return _turno_em_andamento()
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
    if not turnos.ocupar(conversa_id):  # antes de reivindicar: o token não se perde no 409
        return _turno_em_andamento()
    pendente = conversas.reivindicar(session, conversa_id, conta.id, confirmacao_id)
    if pendente is None:
        turnos.liberar(conversa_id)
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


@router.post("/{conversa_id}/acoes", response_model=None)
def acao_do_cartao(
    conversa_id: int,
    corpo: AcaoIn,
    conta: Annotated[Conta, Depends(usuario_atual)],
    session: Annotated[Session, Depends(get_session)],
    fabrica: Annotated[Fabrica, Depends(get_fabrica_sessao)],
    agente: Annotated[Agente, Depends(get_agente)],
    encoder: Annotated[Encoder, Depends(get_encoder)],
    reranker: Annotated[Reranker | None, Depends(get_reranker)],
) -> StreamingResponse | JSONResponse:
    """Locar/reservar pelo cartão do livro no chat, com a resposta da Léia na conversa.

    O cartão já fez a confirmação em duas etapas; aqui a ação segue o mesmo caminho do botão
    Confirmar (serviço valida a regra, o agente recebe um `EventoApp`, nunca texto).
    """
    if conversas.obter(session, conversa_id, conta.id) is None:
        return _conversa_inexistente()
    if not turnos.ocupar(conversa_id):
        return _turno_em_andamento()
    pendente = AcaoPendente(
        usuario_id=conta.id,
        ferramenta=corpo.acao,
        argumentos={"livro_id": corpo.livro_id},
        resumo=f"{corpo.acao} pelo cartão do livro",
        criada_em=datetime.now(UTC),
    )
    return _stream(
        fabrica=fabrica,
        agente=agente,
        encoder=encoder,
        reranker=reranker,
        conversa_id=conversa_id,
        usuario_id=conta.id,
        texto=None,
        clique=(secrets.token_urlsafe(16), pendente, "confirmar"),
    )

"""Conversas: histórico, estado do grounding e ações pendentes persistidos por conversa.

As ações pendentes (botões de confirmação) pertencem a UMA conversa e a UM usuário. Cada
mensagem nova do leitor invalida as anteriores. O clique as reivindica com um DELETE atômico
(`reivindicar`): dois cliques simultâneos no mesmo botão nunca executam duas vezes.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from leia_api.agente import ChamadaAuditada
from leia_api.config import settings
from leia_api.ferramentas import AcaoPendente as Pendente
from leia_api.ferramentas import ContextoFerramentas
from leia_api.models import AcaoPendente as LinhaPendente
from leia_api.models import ChamadaFerramenta, Conversa, Mensagem


def criar(session: Session, usuario_id: int) -> int:
    conversa = Conversa(usuario_id=usuario_id)
    session.add(conversa)
    session.commit()
    return conversa.id


def obter(session: Session, conversa_id: int, usuario_id: int) -> Conversa | None:
    """Só devolve a conversa se for do usuário; dono errado é igual a inexistente."""
    return session.scalar(
        select(Conversa).where(Conversa.id == conversa_id, Conversa.usuario_id == usuario_id)
    )


def mensagens_do_dia(session: Session, usuario_id: int, agora: datetime | None = None) -> int:
    """Quantas mensagens o usuário mandou ao agente desde as 00:00 UTC de hoje."""
    momento = agora or datetime.now(UTC)
    inicio = momento.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        session.scalar(
            select(func.count())
            .select_from(Mensagem)
            .join(Conversa, Conversa.id == Mensagem.conversa_id)
            .where(
                Conversa.usuario_id == usuario_id,
                Mensagem.papel == "usuario",
                Mensagem.criada_em >= inicio,
            )
        )
        or 0
    )


def registrar(session: Session, conversa_id: int, papel: str, conteudo: str) -> None:
    session.add(Mensagem(conversa_id=conversa_id, papel=papel, conteudo=conteudo))


def auditar(session: Session, conversa_id: int, chamadas: list[ChamadaAuditada]) -> None:
    """Trilha de auditoria: uma linha por chamada de ferramenta (tokens ficam nulos por ora)."""
    for c in chamadas:
        session.add(
            ChamadaFerramenta(
                conversa_id=conversa_id,
                ferramenta=c.nome,
                argumentos=c.argumentos,
                resultado=c.resultado,
                latencia_ms=c.latencia_ms,
            )
        )


_PAPEL_LLM = {"usuario": "user", "assistente": "assistant"}


def historico_para_agente(session: Session, conversa_id: int) -> list[dict[str, Any]]:
    """Últimas mensagens de usuário e assistente, em ordem. Eventos do sistema não entram."""
    linhas = session.scalars(
        select(Mensagem)
        .where(Mensagem.conversa_id == conversa_id, Mensagem.papel.in_(_PAPEL_LLM))
        .order_by(Mensagem.id.desc())
        .limit(settings.historico_mensagens_limite)
    ).all()
    return [{"role": _PAPEL_LLM[m.papel], "content": m.conteudo} for m in reversed(linhas)]


def historico_publico(session: Session, conversa_id: int) -> list[dict[str, str]]:
    linhas = session.scalars(
        select(Mensagem)
        .where(Mensagem.conversa_id == conversa_id, Mensagem.papel.in_(_PAPEL_LLM))
        .order_by(Mensagem.id)
    ).all()
    return [{"papel": m.papel, "conteudo": m.conteudo} for m in linhas]


# ---------- ações pendentes ----------


def _pendente(linha: LinhaPendente) -> Pendente:
    return Pendente(
        usuario_id=linha.usuario_id,
        ferramenta=linha.ferramenta,
        argumentos=dict(linha.argumentos),
        resumo=linha.resumo,
        criada_em=linha.criada_em,
    )


def carregar_pendentes(session: Session, conversa_id: int) -> dict[str, Pendente]:
    linhas = session.scalars(select(LinhaPendente).where(LinhaPendente.conversa_id == conversa_id))
    return {linha.token: _pendente(linha) for linha in linhas}


def invalidar_pendentes(session: Session, conversa_id: int) -> None:
    session.execute(delete(LinhaPendente).where(LinhaPendente.conversa_id == conversa_id))
    session.commit()


def reivindicar(session: Session, conversa_id: int, usuario_id: int, token: str) -> Pendente | None:
    """Retira a ação do banco de forma atômica. Só uma requisição ganha; as outras recebem None."""
    linha = session.execute(
        delete(LinhaPendente)
        .where(
            LinhaPendente.token == token,
            LinhaPendente.conversa_id == conversa_id,
            LinhaPendente.usuario_id == usuario_id,
        )
        .returning(LinhaPendente)
    ).scalar_one_or_none()
    pendente = None if linha is None else _pendente(linha)  # antes do commit, que expira a linha
    session.commit()
    return pendente


def sincronizar_pendentes(session: Session, conversa_id: int, ctx: ContextoFerramentas) -> None:
    """Deixa o banco igual ao `ctx.pendentes` no fim do turno (novas propostas, consumidas)."""
    atuais = set(ctx.pendentes)
    session.execute(
        delete(LinhaPendente).where(
            LinhaPendente.conversa_id == conversa_id, LinhaPendente.token.not_in(atuais)
        )
    )
    existentes = set(
        session.scalars(select(LinhaPendente.token).where(LinhaPendente.conversa_id == conversa_id))
    )
    for token, p in ctx.pendentes.items():
        if token not in existentes:
            session.add(
                LinhaPendente(
                    conversa_id=conversa_id,
                    usuario_id=p.usuario_id,
                    token=token,
                    ferramenta=p.ferramenta,
                    argumentos=p.argumentos,
                    resumo=p.resumo,
                    criada_em=p.criada_em,
                )
            )
    session.commit()

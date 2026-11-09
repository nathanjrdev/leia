"""Sessões de login: token aleatório no cookie; no banco, só o SHA-256 dele.

Vazar o banco não entrega sessões válidas. O `usuario_id` de toda requisição autenticada sai
daqui, nunca do corpo da requisição nem do texto da conversa.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from leia_api.models import Sessao


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar(session: Session, usuario_id: int, ttl: timedelta, agora: datetime | None = None) -> str:
    """Abre uma sessão e devolve o token (a única vez que ele existe em claro no servidor)."""
    momento = agora or datetime.now(UTC)
    session.execute(delete(Sessao).where(Sessao.expira_em <= momento))  # faxina das vencidas
    token = secrets.token_urlsafe(32)
    session.add(Sessao(usuario_id=usuario_id, token_hash=_hash(token), expira_em=momento + ttl))
    session.commit()
    return token


def usuario_id_da(session: Session, token: str, agora: datetime | None = None) -> int | None:
    momento = agora or datetime.now(UTC)
    return session.scalar(
        select(Sessao.usuario_id).where(
            Sessao.token_hash == _hash(token), Sessao.expira_em > momento
        )
    )


def encerrar(session: Session, token: str) -> None:
    session.execute(delete(Sessao).where(Sessao.token_hash == _hash(token)))
    session.commit()

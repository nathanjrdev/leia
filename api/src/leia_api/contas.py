"""Contas de leitor: cadastro e autenticação. Regras aqui; o HTTP fica em `auth.py`."""

from dataclasses import dataclass
from functools import cache

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from leia_api.models import Usuario
from leia_api.senha import gerar_hash, verificar


class EmailEmUso(Exception):
    pass


@dataclass(frozen=True)
class Conta:
    id: int
    nome: str
    email: str


def normalizar_email(email: str) -> str:
    return email.strip().lower()


@cache
def _hash_falso() -> str:
    """Hash descartável: login de e-mail inexistente gasta o mesmo tempo que o de senha errada."""
    return gerar_hash("senha-que-ninguem-tem")


def cadastrar(session: Session, nome: str, email: str, senha: str) -> Conta:
    """Cria sempre um leitor. Papel e id nunca vêm do chamador."""
    email = normalizar_email(email)
    if session.scalar(select(Usuario.id).where(Usuario.email == email)) is not None:
        raise EmailEmUso
    usuario = Usuario(nome=nome.strip(), email=email, senha_hash=gerar_hash(senha))
    session.add(usuario)
    try:
        session.commit()
    except IntegrityError as erro:  # corrida: outro cadastro com o mesmo e-mail venceu
        session.rollback()
        raise EmailEmUso from erro
    return Conta(usuario.id, usuario.nome, usuario.email)


def autenticar(session: Session, email: str, senha: str) -> Conta | None:
    usuario = session.scalar(select(Usuario).where(Usuario.email == normalizar_email(email)))
    if usuario is None:
        verificar(senha, _hash_falso())
        return None
    if not verificar(senha, usuario.senha_hash):
        return None
    return Conta(usuario.id, usuario.nome, usuario.email)


def conta_por_id(session: Session, usuario_id: int) -> Conta | None:
    usuario = session.get(Usuario, usuario_id)
    return None if usuario is None else Conta(usuario.id, usuario.nome, usuario.email)

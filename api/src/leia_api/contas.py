"""Contas de leitor: cadastro e autenticação. Regras aqui; o HTTP fica em `auth.py`."""

from dataclasses import dataclass
from functools import cache

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from leia_api.models import IdentidadeExterna, Usuario
from leia_api.oauth import Identidade
from leia_api.senha import gerar_hash, verificar


class EmailEmUso(Exception):
    pass


# Conta criada pelo Google/Microsoft não tem senha. `verificar` devolve False para este valor
# (não é um hash scrypt), então o login por senha simplesmente não funciona para ela.
SEM_SENHA = "!sem-senha"


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


def entrar_com_identidade(session: Session, ident: Identidade, _repetir: bool = True) -> Conta:
    """Acha (ou cria) a conta de quem entrou pelo Google/Microsoft.

    1. Já vinculada (provedor + sub): entra nela, mesmo que o e-mail tenha mudado.
    2. Existe conta com o mesmo e-mail: vincula. Seguro porque `oauth` só entrega identidade
       com e-mail VERIFICADO pelo provedor.
    3. Nada: cria um leitor sem senha e vincula.
    """
    vinculo = session.scalar(
        select(IdentidadeExterna).where(
            IdentidadeExterna.provedor == ident.provedor,
            IdentidadeExterna.sujeito == ident.sujeito,
        )
    )
    if vinculo is not None:
        conta = conta_por_id(session, vinculo.usuario_id)
        if conta is not None:
            return conta
    email = normalizar_email(ident.email)
    usuario = session.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is None:
        usuario = Usuario(nome=ident.nome, email=email, senha_hash=SEM_SENHA)
        session.add(usuario)
        session.flush()
    session.add(
        IdentidadeExterna(usuario_id=usuario.id, provedor=ident.provedor, sujeito=ident.sujeito)
    )
    try:
        session.commit()
    except IntegrityError:  # corrida: o mesmo login chegou duas vezes; o outro já vinculou
        session.rollback()
        if not _repetir:
            raise
        return entrar_com_identidade(session, ident, _repetir=False)
    return Conta(usuario.id, usuario.nome, usuario.email)

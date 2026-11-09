"""Rotas de conta e a dependência que entrega o usuário da sessão às demais rotas.

`usuario_atual` é a ÚNICA fonte de `usuario_id` da API. Nenhum corpo, query ou texto de conversa
carrega esse valor. Cookie `HttpOnly` + `SameSite=Lax`; os POSTs só aceitam JSON, o que, junto com
o SameSite, barra CSRF de formulário entre sites.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from leia_api import contas, sessao
from leia_api.config import settings
from leia_api.contas import Conta
from leia_api.db import get_session

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
Email = Annotated[str, StringConstraints(pattern=_EMAIL, max_length=254, strip_whitespace=True)]


class NaoAutenticado(Exception):
    pass


def erro_json(status: int, codigo: str, mensagem: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"erro": codigo, "mensagem": mensagem})


async def tratar_nao_autenticado(_: Request, __: Exception) -> JSONResponse:
    return erro_json(401, "nao_autenticado", "Entre na sua conta para continuar.")


class _Corpo(BaseModel):
    model_config = ConfigDict(extra="forbid")  # `papel` e `usuario_id` no corpo viram 422


class CadastroIn(_Corpo):
    nome: str = Field(min_length=1, max_length=160)
    email: Email
    senha: str = Field(
        min_length=settings.senha_min_caracteres, max_length=settings.senha_max_caracteres
    )


class LoginIn(_Corpo):
    email: Email
    senha: str = Field(min_length=1, max_length=settings.senha_max_caracteres)


class ContaOut(BaseModel):
    nome: str
    email: str


def _abrir_sessao(response: Response, session: Session, conta: Conta) -> None:
    ttl = timedelta(hours=settings.sessao_ttl_horas)
    token = sessao.criar(session, conta.id, ttl)
    response.set_cookie(
        settings.sessao_cookie_nome,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_seguro,
        path="/",
    )


def usuario_atual(
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str | None, Cookie(alias=settings.sessao_cookie_nome)] = None,
) -> Conta:
    """Usuário dono da sessão do cookie; 401 se não houver sessão válida."""
    usuario_id = sessao.usuario_id_da(session, token) if token else None
    conta = None if usuario_id is None else contas.conta_por_id(session, usuario_id)
    if conta is None:
        raise NaoAutenticado
    return conta


@router.post("/cadastro", status_code=201, response_model=ContaOut)
def cadastro(
    corpo: CadastroIn, response: Response, session: Annotated[Session, Depends(get_session)]
) -> Response | ContaOut:
    try:
        conta = contas.cadastrar(session, corpo.nome, corpo.email, corpo.senha)
    except contas.EmailEmUso:
        return erro_json(409, "email_em_uso", "Já existe uma conta com esse e-mail.")
    _abrir_sessao(response, session, conta)
    return ContaOut(nome=conta.nome, email=conta.email)


@router.post("/login", response_model=ContaOut)
def login(
    corpo: LoginIn, response: Response, session: Annotated[Session, Depends(get_session)]
) -> Response | ContaOut:
    conta = contas.autenticar(session, corpo.email, corpo.senha)
    if conta is None:
        return erro_json(401, "credenciais_invalidas", "E-mail ou senha incorretos.")
    _abrir_sessao(response, session, conta)
    return ContaOut(nome=conta.nome, email=conta.email)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str | None, Cookie(alias=settings.sessao_cookie_nome)] = None,
) -> None:
    if token:
        sessao.encerrar(session, token)
    response.delete_cookie(settings.sessao_cookie_nome, path="/")


@router.get("/eu", response_model=ContaOut)
def eu(conta: Annotated[Conta, Depends(usuario_atual)]) -> ContaOut:
    return ContaOut(nome=conta.nome, email=conta.email)

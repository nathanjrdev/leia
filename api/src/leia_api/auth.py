"""Rotas de conta e a dependência que entrega o usuário da sessão às demais rotas.

`usuario_atual` é a ÚNICA fonte de `usuario_id` da API. Nenhum corpo, query ou texto de conversa
carrega esse valor. Cookie `HttpOnly` + `SameSite=Lax`; os POSTs só aceitam JSON, o que, junto com
o SameSite, barra CSRF de formulário entre sites.
"""

import secrets
from datetime import timedelta
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from leia_api import contas, limite, oauth, sessao
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
    corpo: LoginIn,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> Response | ContaOut:
    janela = settings.login_janela_segundos
    chave_email = f"email:{contas.normalizar_email(corpo.email)}"
    chave_ip = f"ip:{request.client.host if request.client else 'desconhecido'}"
    if limite.LOGIN.excedeu(chave_email, settings.login_max_falhas, janela) or limite.LOGIN.excedeu(
        chave_ip, settings.login_max_falhas_por_ip, janela
    ):
        return erro_json(
            429, "muitas_tentativas", "Muitas tentativas de entrada. Tente de novo mais tarde."
        )
    conta = contas.autenticar(session, corpo.email, corpo.senha)
    if conta is None:
        limite.LOGIN.registrar(chave_email, settings.login_max_falhas, janela)
        limite.LOGIN.registrar(chave_ip, settings.login_max_falhas_por_ip, janela)
        return erro_json(401, "credenciais_invalidas", "E-mail ou senha incorretos.")
    limite.LOGIN.zerar(chave_email)
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


# ---------- Entrar com Google / Microsoft ----------

COOKIE_OAUTH = "leia_oauth"
_COOKIE_OAUTH_TTL = 600  # 10 min para o leitor escolher a conta no provedor


def _cliente_http() -> httpx.Client:
    """Dependência própria para os testes trocarem o provedor por um falso."""
    return httpx.Client(timeout=settings.oauth_timeout_segundos)


def _voltar_para_entrar(codigo: str) -> RedirectResponse:
    resp = RedirectResponse(f"/entrar?{urlencode({'erro': codigo})}", status_code=303)
    resp.delete_cookie(COOKIE_OAUTH, path="/")
    return resp


class ProvedoresOut(BaseModel):
    provedores: list[str]


@router.get("/provedores", response_model=ProvedoresOut)
def provedores() -> ProvedoresOut:
    """Quais botões de "Entrar com…" a tela deve mostrar."""
    return ProvedoresOut(provedores=list(oauth.disponiveis()))


@router.get("/oauth/{nome}/iniciar")
def oauth_iniciar(nome: str) -> RedirectResponse:
    p = oauth.provedor(nome)
    if p is None:
        return _voltar_para_entrar("provedor_indisponivel")
    tentativa = oauth.nova_tentativa(p.nome)
    resp = RedirectResponse(oauth.url_de_login(p, tentativa), status_code=303)
    resp.set_cookie(
        COOKIE_OAUTH,
        tentativa.serializar(),
        max_age=_COOKIE_OAUTH_TTL,
        httponly=True,
        samesite="lax",  # Lax: o cookie volta no GET de topo que o provedor redireciona
        secure=settings.cookie_seguro,
        path="/",
    )
    return resp


@router.get("/oauth/{nome}/retorno")
def oauth_retorno(
    nome: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    cliente: Annotated[httpx.Client, Depends(_cliente_http)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    leia_oauth: Annotated[str | None, Cookie(alias=COOKIE_OAUTH)] = None,
) -> RedirectResponse:
    p = oauth.provedor(nome)
    if p is None:
        return _voltar_para_entrar("provedor_indisponivel")
    if error:  # o leitor fechou/cancelou na tela do provedor
        return _voltar_para_entrar("cancelado" if error == "access_denied" else "oauth_falhou")
    tentativa = oauth.Tentativa.ler(leia_oauth)
    if (
        tentativa is None
        or tentativa.provedor != p.nome
        or not code
        or not state
        or not secrets.compare_digest(state, tentativa.state)
    ):
        return _voltar_para_entrar("oauth_falhou")
    chave_ip = f"ip:{request.client.host if request.client else 'desconhecido'}"
    janela = settings.login_janela_segundos
    if limite.LOGIN.excedeu(chave_ip, settings.login_max_falhas_por_ip, janela):
        return _voltar_para_entrar("muitas_tentativas")
    try:
        id_token = oauth.trocar_codigo(p, code, tentativa, cliente)
        identidade = oauth.identidade_do_token(p, id_token, tentativa.nonce)
    except oauth.FalhaOAuth as falha:
        limite.LOGIN.registrar(chave_ip, settings.login_max_falhas_por_ip, janela)
        return _voltar_para_entrar(falha.codigo)
    conta = contas.entrar_com_identidade(session, identidade)
    resp = RedirectResponse("/conversa", status_code=303)
    resp.delete_cookie(COOKIE_OAUTH, path="/")
    _abrir_sessao(resp, session, conta)
    return resp

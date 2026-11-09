"""Catálogo (leitura pública) e estante do leitor (autenticada), mais as ações diretas da tela.

- `GET /categorias`, `GET /livros`, `GET /livros/busca`, `GET /livros/{id}`: sem sessão.
- `GET /estante`: locações ativas, reservas e histórico do usuário DA SESSÃO.
- `POST /livros/{id}/locar|reservar` e `POST /locacoes/{id}/renovar|devolver`: o clique do leitor
  na tela, sem LLM. Exigem corpo `{"confirmo": true}`: a confirmação explícita é parte do
  contrato da API, não só da interface. O `usuario_id` nunca aparece na rota nem no corpo.

Regras de negócio (limites, prazos) ficam em `locacao.py` e na configuração, não aqui.
"""

from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from leia_api import catalogo, locacao
from leia_api.auth import erro_json, usuario_atual
from leia_api.busca import Reranker, buscar_livros
from leia_api.config import settings
from leia_api.contas import Conta
from leia_api.db import get_session
from leia_api.dependencias import get_encoder, get_reranker
from leia_api.embeddings import Encoder
from leia_api.locacao import ErroLocacao, RegrasLocacao
from leia_api.models import Categoria

router = APIRouter(tags=["acervo"])

_NAO_ENCONTRADO = {"livro_inexistente", "locacao_inexistente", "reserva_inexistente"}
Slug = Annotated[str | None, Query(max_length=60, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
Ano = Annotated[int | None, Query(ge=1000, le=2100)]
Sessao = Annotated[Session, Depends(get_session)]
Logado = Annotated[Conta, Depends(usuario_atual)]


class Confirmacao(BaseModel):
    """Corpo exigido nas escritas: `{"confirmo": true}` e nada mais."""

    model_config = ConfigDict(extra="forbid", strict=True)
    confirmo: Literal[True]  # false, "sim" ou ausente viram 422 antes de qualquer ação


def _erro_de_regra(erro: ErroLocacao) -> JSONResponse:
    status = 404 if erro.codigo in _NAO_ENCONTRADO else 409
    return erro_json(status, erro.codigo, erro.mensagem)


def _item(i: catalogo.ItemListagem) -> dict[str, Any]:
    return {
        "id": i.livro_id,
        "titulo": i.titulo,
        "autores": i.autores,
        "ano": i.ano,
        "capa_url": i.capa_url,
        "livres": i.livres,
        "fila": i.fila,
    }


# ---------- catálogo ----------


@router.get("/categorias")
def categorias(session: Sessao) -> list[dict[str, str]]:
    linhas = session.scalars(select(Categoria).order_by(Categoria.nome))
    return [{"slug": c.slug, "nome": c.nome} for c in linhas]


@router.get("/livros")
def listar(
    session: Sessao,
    categoria: Slug = None,
    ano_min: Ano = None,
    ano_max: Ano = None,
    apenas_disponiveis: bool = False,
    pagina: Annotated[int, Query(ge=1)] = 1,
    limite: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict[str, Any]:
    itens, total = catalogo.listar_livros(
        session,
        categoria=categoria,
        ano_min=ano_min,
        ano_max=ano_max,
        apenas_disponiveis=apenas_disponiveis,
        pagina=pagina,
        limite=limite,
    )
    return {"itens": [_item(i) for i in itens], "total": total, "pagina": pagina}


@router.get("/livros/busca")
def buscar(
    session: Sessao,
    encoder: Annotated[Encoder, Depends(get_encoder)],
    reranker: Annotated[Reranker | None, Depends(get_reranker)],
    q: Annotated[str, Query(min_length=1, max_length=300)],
    categoria: Slug = None,
    ano_min: Ano = None,
    ano_max: Ano = None,
    apenas_disponiveis: bool = False,
    limite: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    achados = buscar_livros(
        session,
        q.strip(),
        encoder,
        limite=min(limite, settings.busca_limite_maximo),
        categoria=categoria,
        ano_min=ano_min,
        ano_max=ano_max,
        apenas_disponiveis=apenas_disponiveis,
        reranker=reranker,
    )
    itens = [
        {
            "id": r.livro_id,
            "titulo": r.titulo,
            "autores": r.autores,
            "ano": r.ano,
            "capa_url": r.capa_url,
            "livres": r.livres,
            "fila": r.fila,
        }
        for r in achados
    ]
    return {"itens": itens, "total": len(itens), "pagina": 1}


@router.get("/livros/{livro_id}", response_model=None)
def ficha(livro_id: int, session: Sessao) -> dict[str, Any] | JSONResponse:
    try:
        f = catalogo.detalhar_livro(session, livro_id)
    except ErroLocacao as erro:
        return _erro_de_regra(erro)
    d = f.disponibilidade
    return {
        "id": f.livro_id,
        "titulo": f.titulo,
        "autores": f.autores,
        "categorias": f.categorias,
        "sinopse": f.sinopse,
        "ano": f.ano,
        "editora": f.editora,
        "paginas": f.paginas,
        "capa_url": f.capa_url,
        "exemplares": d.total,
        "livres": d.livres,
        "fila": d.fila,
    }


# ---------- estante e ações da tela ----------


@router.get("/estante")
def estante(conta: Logado, session: Sessao) -> dict[str, Any]:
    meu = locacao.minhas_locacoes(session, conta.id)
    return {
        "ativas": [asdict(x) for x in meu.ativas],
        "reservas": [asdict(x) for x in meu.reservas],
        "historico": [asdict(x) for x in meu.historico],
    }


@router.post("/livros/{livro_id}/locar", response_model=None)
def locar(
    livro_id: int, _: Confirmacao, conta: Logado, session: Sessao
) -> dict[str, Any] | JSONResponse:
    try:
        return asdict(locacao.locar(session, conta.id, livro_id, RegrasLocacao.da_config()))
    except ErroLocacao as erro:
        return _erro_de_regra(erro)


@router.post("/livros/{livro_id}/reservar", response_model=None)
def reservar(
    livro_id: int, _: Confirmacao, conta: Logado, session: Sessao
) -> dict[str, Any] | JSONResponse:
    try:
        return asdict(locacao.reservar(session, conta.id, livro_id))
    except ErroLocacao as erro:
        return _erro_de_regra(erro)


@router.post("/reservas/{reserva_id}/cancelar", response_model=None)
def cancelar(
    reserva_id: int, _: Confirmacao, conta: Logado, session: Sessao
) -> dict[str, Any] | JSONResponse:
    try:
        return asdict(locacao.cancelar_reserva(session, conta.id, reserva_id))
    except ErroLocacao as erro:
        return _erro_de_regra(erro)


@router.post("/locacoes/{locacao_id}/renovar", response_model=None)
def renovar(
    locacao_id: int, _: Confirmacao, conta: Logado, session: Sessao
) -> dict[str, Any] | JSONResponse:
    try:
        return asdict(locacao.renovar(session, conta.id, locacao_id, RegrasLocacao.da_config()))
    except ErroLocacao as erro:
        return _erro_de_regra(erro)


@router.post("/locacoes/{locacao_id}/devolver", response_model=None)
def devolver(
    locacao_id: int, _: Confirmacao, conta: Logado, session: Sessao
) -> dict[str, Any] | JSONResponse:
    try:
        return asdict(locacao.devolver(session, conta.id, locacao_id))
    except ErroLocacao as erro:
        return _erro_de_regra(erro)

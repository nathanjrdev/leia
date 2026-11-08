"""Carga do catálogo de semente e de dados fictícios (apenas desenvolvimento).

O catálogo vem de `data/catalogo.json` (gerado por `data/fetch_catalog.py`).
Usuários e locações são fictícios, de modo que a camada grátis de LLMs nunca
vê dados reais.
"""

import json
import random
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from leia_api.config import settings
from leia_api.models import Autor, Categoria, Exemplar, Livro, LivroEmbedding, Locacao, Usuario

CATALOGO_PADRAO = Path(__file__).resolve().parents[3] / "data" / "catalogo.json"
# Hash inválido de propósito: usuários fictícios não fazem login.
SENHA_HASH_FICTICIA = "!usuario-ficticio"


def _slug(texto: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")


def _autor(session: Session, nome: str) -> Autor:
    autor = session.scalars(select(Autor).where(Autor.nome == nome)).first()
    if autor is None:
        autor = Autor(nome=nome)
        session.add(autor)
        session.flush()
    return autor


def _categoria(session: Session, nome: str) -> Categoria:
    categoria = session.scalars(select(Categoria).where(Categoria.slug == _slug(nome))).first()
    if categoria is None:
        categoria = Categoria(nome=nome, slug=_slug(nome))
        session.add(categoria)
        session.flush()
    return categoria


def _nfc(item: dict[str, Any]) -> dict[str, Any]:
    """Título e autores em NFC: fontes às vezes trazem acentos decompostos (NFD)."""
    return {
        **item,
        "titulo": unicodedata.normalize("NFC", item["titulo"]),
        "autores": [unicodedata.normalize("NFC", nome) for nome in item["autores"]],
    }


def _existente(session: Session, item: dict[str, Any]) -> Livro | None:
    """Livro já carregado: pelo ISBN (sobrevive a renomear o título) ou por título + autor."""
    if item.get("isbn"):
        por_isbn = session.scalars(select(Livro).where(Livro.isbn == item["isbn"])).first()
        if por_isbn is not None:
            return por_isbn
    return session.scalars(
        select(Livro)
        .join(Livro.autores)
        .where(Livro.titulo == item["titulo"], Autor.nome == item["autores"][0])
    ).first()


def carregar_catalogo(session: Session, livros: list[dict[str, Any]], *, seed: int = 42) -> int:
    """Insere os livros que ainda não existem (idempotente). Devolve quantos entraram."""
    rng = random.Random(seed)  # noqa: S311 - dados fictícios, não é criptografia
    novos = 0
    for item in map(_nfc, livros):
        if _existente(session, item) is not None:
            continue
        livro = Livro(
            titulo=item["titulo"],
            isbn=item.get("isbn"),
            sinopse=item["sinopse"],
            sinopse_fonte=item.get("sinopse_fonte"),
            ano=item.get("ano"),
            editora=item.get("editora"),
            paginas=item.get("paginas"),
            capa_url=item.get("capa_url"),
        )
        livro.autores = [_autor(session, nome) for nome in item["autores"]]
        livro.categorias = [_categoria(session, nome) for nome in item.get("categorias", [])]
        session.add(livro)
        session.flush()
        for n in range(1, rng.randint(1, 3) + 1):
            session.add(Exemplar(livro_id=livro.id, codigo=f"L{livro.id:05d}-{n}"))
        novos += 1
    session.flush()
    return novos


_CAMPOS_SIMPLES = ("isbn", "sinopse", "sinopse_fonte", "ano", "editora", "paginas", "capa_url")


def atualizar_livros(session: Session, livros: list[dict[str, Any]]) -> int:
    """Propaga edições do catálogo para livros já carregados. Devolve quantos mudaram.

    O livro é achado pelo ISBN ou por título + autor principal. Livros que não estão no banco
    são ignorados (quem insere é `carregar_catalogo`). O embedding é apagado só quando muda algo
    que entra no documento (título, autores, categorias, sinopse), para que `gerar_embeddings`
    o recalcule; ano, editora, capa etc. não mexem no vetor.
    """
    mudados = 0
    for item in map(_nfc, livros):
        livro = _existente(session, item)
        if livro is None:
            continue
        mudou_texto = livro.titulo != item["titulo"]
        mudou = mudou_texto
        livro.titulo = item["titulo"]
        for campo in _CAMPOS_SIMPLES:
            novo = item.get(campo)
            if getattr(livro, campo) != novo:
                mudou = True
                mudou_texto = mudou_texto or campo == "sinopse"
                setattr(livro, campo, novo)
        # A ordem dos autores não é persistida (tabela de associação), então compara como conjunto.
        if {a.nome for a in livro.autores} != set(item["autores"]):
            livro.autores = [_autor(session, nome) for nome in item["autores"]]
            mudou = mudou_texto = True
        categorias = item.get("categorias", [])
        if sorted(c.slug for c in livro.categorias) != sorted(_slug(n) for n in categorias):
            livro.categorias = [_categoria(session, nome) for nome in categorias]
            mudou = mudou_texto = True
        if mudou_texto:
            session.execute(delete(LivroEmbedding).where(LivroEmbedding.livro_id == livro.id))
        mudados += mudou
    session.flush()
    return mudados


def livros_fora_do_catalogo(session: Session, livros: list[dict[str, Any]]) -> list[str]:
    """Livros do banco que não aparecem no catálogo ("título | autor"), para revisão manual.

    Nunca apaga: exemplares podem ter locações e histórico. Aparecer aqui costuma ser um livro
    removido de propósito ou um título editado sem ISBN (que duplicaria o livro). O autor mostrado
    é o primeiro que o banco devolve, pois a ordem dos autores não é persistida.
    """
    ids_no_catalogo = {
        livro.id for item in map(_nfc, livros) if (livro := _existente(session, item)) is not None
    }
    return [
        f"{livro.titulo} | {livro.autores[0].nome if livro.autores else '?'}"
        for livro in session.scalars(select(Livro).order_by(Livro.id))
        if livro.id not in ids_no_catalogo
    ]


def carregar_catalogo_json(session: Session, caminho: Path = CATALOGO_PADRAO) -> int:
    return carregar_catalogo(session, json.loads(caminho.read_text(encoding="utf-8")))


def criar_usuarios_ficticios(session: Session, quantidade: int = 20) -> None:
    session.add(
        Usuario(
            nome="Administradora",
            email="admin@leia.example",
            senha_hash=SENHA_HASH_FICTICIA,
            papel="admin",
        )
    )
    for i in range(1, quantidade + 1):
        session.add(
            Usuario(
                nome=f"Leitor {i}",
                email=f"leitor{i}@leia.example",
                senha_hash=SENHA_HASH_FICTICIA,
            )
        )
    session.flush()


def criar_locacoes_ficticias(session: Session, *, seed: int = 42, taxa_ativas: float = 0.3) -> None:
    """Histórico passado devolvido e algumas locações ativas, sem violar as regras."""
    rng = random.Random(seed)  # noqa: S311 - dados fictícios, não é criptografia
    leitores = list(session.scalars(select(Usuario).where(Usuario.papel == "leitor")))
    exemplares = list(session.scalars(select(Exemplar)))
    rng.shuffle(exemplares)
    agora = datetime.now(UTC)
    ativas_por_leitor: dict[int, int] = {}
    prazo = timedelta(days=settings.prazo_locacao_dias)
    for exemplar in exemplares:
        if not leitores:
            break
        leitor = rng.choice(leitores)
        retirada = agora - timedelta(days=rng.randint(1, 120))
        ativa = (
            rng.random() < taxa_ativas
            and ativas_por_leitor.get(leitor.id, 0) < settings.max_locacoes_simultaneas
            and retirada + prazo >= agora  # sem atraso: leitor em atraso não loca
        )
        if ativa:
            ativas_por_leitor[leitor.id] = ativas_por_leitor.get(leitor.id, 0) + 1
        session.add(
            Locacao(
                exemplar_id=exemplar.id,
                usuario_id=leitor.id,
                retirada_em=retirada,
                prevista_em=retirada + prazo,
                devolvida_em=None if ativa else retirada + timedelta(days=rng.randint(3, 14)),
            )
        )
    session.flush()

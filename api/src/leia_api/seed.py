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

from sqlalchemy import select
from sqlalchemy.orm import Session

from leia_api.config import settings
from leia_api.models import Autor, Categoria, Exemplar, Livro, Locacao, Usuario

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


def carregar_catalogo(session: Session, livros: list[dict[str, Any]], *, seed: int = 42) -> int:
    """Insere os livros que ainda não existem (idempotente). Devolve quantos entraram."""
    rng = random.Random(seed)  # noqa: S311 - dados fictícios, não é criptografia
    novos = 0
    for item in livros:
        principal = item["autores"][0]
        existe = session.scalars(
            select(Livro.id)
            .join(Livro.autores)
            .where(Livro.titulo == item["titulo"], Autor.nome == principal)
        ).first()
        if existe is not None:
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

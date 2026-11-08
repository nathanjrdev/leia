from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from leia_api.embeddings import (
    CHAVE_EMBEDDING,
    MAX_TOKENS_ENCODER,
    MODELO_PADRAO,
    documento_do_livro,
    gerar_embeddings,
)
from leia_api.models import EMBEDDING_DIM, LivroEmbedding
from leia_api.seed import carregar_catalogo
from tests.integration.test_seed import CATALOGO


class FakeEncoder:
    """Encoder determinístico: não baixa modelo nenhum."""

    def __init__(self) -> None:
        self.chamadas = 0

    def encode(self, textos: list[str]) -> list[list[float]]:
        self.chamadas += 1
        return [[float(len(t) % 7)] * EMBEDDING_DIM for t in textos]


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with engine.connect() as conn:
        outer = conn.begin()
        with Session(conn, join_transaction_mode="create_savepoint") as s:
            yield s
        outer.rollback()


def test_document_combines_title_author_categories_and_synopsis(session: Session) -> None:
    carregar_catalogo(session, CATALOGO)
    from sqlalchemy import select as sel

    from leia_api.models import Livro

    livro = session.scalars(sel(Livro).where(Livro.titulo == "Dom Casmurro")).one()
    doc = documento_do_livro(livro)
    assert "Dom Casmurro" in doc
    assert "Machado de Assis" in doc
    assert "Romance" in doc
    assert "Capitu" in doc


def test_generates_one_embedding_per_book(session: Session) -> None:
    carregar_catalogo(session, CATALOGO)
    criados = gerar_embeddings(session, FakeEncoder(), modelo="fake-768")
    assert criados == 2
    assert session.scalar(select(func.count()).select_from(LivroEmbedding)) == 2


def test_second_run_skips_books_already_embedded(session: Session) -> None:
    carregar_catalogo(session, CATALOGO)
    encoder = FakeEncoder()
    gerar_embeddings(session, encoder, modelo="fake-768")
    chamadas = encoder.chamadas
    assert gerar_embeddings(session, encoder, modelo="fake-768") == 0
    assert encoder.chamadas == chamadas


def test_default_key_carries_token_limit_so_old_vectors_are_replaced(session: Session) -> None:
    carregar_catalogo(session, CATALOGO)
    # Vetores gravados antes de o limite de tokens subir: só o nome do modelo, sem versão.
    gerar_embeddings(session, FakeEncoder(), modelo=MODELO_PADRAO)
    assert str(MAX_TOKENS_ENCODER) in CHAVE_EMBEDDING
    assert gerar_embeddings(session, FakeEncoder()) == 2
    assert set(session.scalars(select(LivroEmbedding.modelo))) == {CHAVE_EMBEDDING}


def test_changing_model_regenerates_embeddings(session: Session) -> None:
    carregar_catalogo(session, CATALOGO)
    gerar_embeddings(session, FakeEncoder(), modelo="modelo-a")
    assert gerar_embeddings(session, FakeEncoder(), modelo="modelo-b") == 2
    modelos = set(session.scalars(select(LivroEmbedding.modelo)))
    assert modelos == {"modelo-b"}

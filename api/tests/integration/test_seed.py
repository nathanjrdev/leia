import unicodedata
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from leia_api.models import EMBEDDING_DIM, Autor, Exemplar, Livro, LivroEmbedding, Locacao, Usuario
from leia_api.seed import (
    atualizar_sinopses,
    carregar_catalogo,
    criar_locacoes_ficticias,
    criar_usuarios_ficticios,
)

CATALOGO = [
    {
        "titulo": "Dom Casmurro",
        "autores": ["Machado de Assis"],
        "ano": 1899,
        "paginas": 256,
        "editora": "Garnier",
        "isbn": "9788535911664",
        "capa_url": "https://covers.openlibrary.org/b/id/1-L.jpg",
        "sinopse": "Bentinho narra a dúvida sobre a fidelidade de Capitu." * 3,
        "sinopse_fonte": "Open Library: https://openlibrary.org/works/OL1W",
        "categorias": ["Romance", "Ficção"],
    },
    {
        "titulo": "Quincas Borba",
        "autores": ["Machado de Assis"],
        "ano": 1891,
        "paginas": None,
        "editora": None,
        "isbn": None,
        "capa_url": None,
        "sinopse": "Rubião herda a fortuna de Quincas Borba e a filosofia do Humanitismo." * 2,
        "sinopse_fonte": "Open Library: https://openlibrary.org/works/OL2W",
        "categorias": ["Romance"],
    },
]


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with engine.connect() as conn:
        outer = conn.begin()
        with Session(conn, join_transaction_mode="create_savepoint") as s:
            yield s
        outer.rollback()


def test_loads_books_authors_and_copies(session: Session) -> None:
    carregar_catalogo(session, CATALOGO)
    assert session.scalar(select(func.count()).select_from(Livro)) == 2
    # Os dois livros compartilham o mesmo autor.
    assert session.scalar(select(func.count()).select_from(Autor)) == 1
    livro = session.scalars(select(Livro).where(Livro.titulo == "Dom Casmurro")).one()
    assert livro.sinopse_fonte is not None
    assert livro.sinopse_fonte.startswith("Open Library")
    copies = session.scalar(
        select(func.count()).select_from(Exemplar).where(Exemplar.livro_id == livro.id)
    )
    assert copies is not None and 1 <= copies <= 3


def _com_embeddings(session: Session) -> None:
    for livro in session.scalars(select(Livro)):
        session.add(LivroEmbedding(livro_id=livro.id, modelo="m", vetor=[0.0] * EMBEDDING_DIM))
    session.flush()


def test_update_synopses_changes_text_and_invalidates_only_that_embedding(
    session: Session,
) -> None:
    carregar_catalogo(session, CATALOGO)
    _com_embeddings(session)
    revisado = [
        {**CATALOGO[0], "sinopse": "Nova sinopse do enredo.", "sinopse_fonte": "Revisão Léia"},
        CATALOGO[1],
    ]

    assert atualizar_sinopses(session, revisado) == 1

    dom = session.scalars(select(Livro).where(Livro.titulo == "Dom Casmurro")).one()
    quincas = session.scalars(select(Livro).where(Livro.titulo == "Quincas Borba")).one()
    assert dom.sinopse == "Nova sinopse do enredo."
    assert dom.sinopse_fonte == "Revisão Léia"
    assert session.get(LivroEmbedding, dom.id) is None
    assert session.get(LivroEmbedding, quincas.id) is not None


def test_update_synopses_ignores_books_not_in_database(session: Session) -> None:
    carregar_catalogo(session, CATALOGO[:1])
    assert atualizar_sinopses(session, [{**CATALOGO[1], "sinopse": "outra"}]) == 0
    assert session.scalar(select(func.count()).select_from(Livro)) == 1


def test_loading_normalizes_title_and_author_to_nfc(session: Session) -> None:
    nfd = {
        **CATALOGO[0],
        "titulo": unicodedata.normalize("NFD", "Bangüê"),
        "autores": [unicodedata.normalize("NFD", "José Lins do Rego")],
    }
    carregar_catalogo(session, [nfd])
    livro = session.scalars(select(Livro)).one()
    assert livro.titulo == "Bangüê"
    assert livro.autores[0].nome == "José Lins do Rego"
    # A mesma entrada em NFD é reconhecida como já carregada.
    assert carregar_catalogo(session, [nfd]) == 0
    assert atualizar_sinopses(session, [{**nfd, "sinopse": "outra"}]) == 1


def test_loading_twice_is_idempotent(session: Session) -> None:
    carregar_catalogo(session, CATALOGO)
    carregar_catalogo(session, CATALOGO)
    assert session.scalar(select(func.count()).select_from(Livro)) == 2


def test_fake_users_and_rentals_respect_integrity(session: Session) -> None:
    carregar_catalogo(session, CATALOGO)
    criar_usuarios_ficticios(session, quantidade=5)
    criar_locacoes_ficticias(session, seed=1)
    assert session.scalar(select(func.count()).select_from(Usuario)) == 6  # 5 leitores + admin
    # Nenhum exemplar com mais de uma locação ativa (o índice parcial garantiria o erro).
    ativas = session.scalars(select(Locacao).where(Locacao.devolvida_em.is_(None))).all()
    assert len({loc.exemplar_id for loc in ativas}) == len(ativas)

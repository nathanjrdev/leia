from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from leia_api.models import Autor, Exemplar, Livro, Locacao, Usuario
from leia_api.seed import carregar_catalogo, criar_locacoes_ficticias, criar_usuarios_ficticios

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

import unicodedata

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

NFD = unicodedata.normalize("NFD", "Os sertões")
AUTOR_NFD = unicodedata.normalize("NFD", "Euclides da Cunha Júnior")


def test_0003_normalizes_existing_titles_and_author_names_to_nfc(
    alembic_cfg: Config, engine: Engine
) -> None:
    command.downgrade(alembic_cfg, "0002")
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO livros (titulo, sinopse) VALUES (:t, 's')"), {"t": NFD})
            conn.execute(text("INSERT INTO autores (nome) VALUES (:n)"), {"n": AUTOR_NFD})
        command.upgrade(alembic_cfg, "head")
        with engine.connect() as conn:
            titulo = conn.execute(
                text("SELECT titulo FROM livros WHERE titulo = :t"), {"t": "Os sertões"}
            ).scalar_one()
            nome = conn.execute(
                text("SELECT nome FROM autores WHERE nome = :n"),
                {"n": "Euclides da Cunha Júnior"},
            ).scalar_one()
        assert unicodedata.is_normalized("NFC", titulo)
        assert unicodedata.is_normalized("NFC", nome)
    finally:
        command.upgrade(alembic_cfg, "head")
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM livros WHERE titulo = 'Os sertões'"))
            conn.execute(text("DELETE FROM autores WHERE nome = 'Euclides da Cunha Júnior'"))

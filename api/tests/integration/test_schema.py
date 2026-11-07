import pytest
from sqlalchemy import Connection, Engine, inspect, text
from sqlalchemy.exc import IntegrityError

EXPECTED_TABLES = {
    "autores", "categorias", "livros", "livro_autor", "livro_categoria", "exemplares",
    "usuarios", "locacoes", "reservas", "livro_embeddings", "avaliacoes",
    "conversas", "mensagens", "chamadas_ferramenta",
}


def _livro(conn: Connection, titulo: str = "Torto Arado") -> int:
    return int(conn.execute(
        text("INSERT INTO livros (titulo, sinopse) VALUES (:t, 'sinopse') RETURNING id"),
        {"t": titulo},
    ).scalar_one())


def _exemplar(conn: Connection, livro_id: int, codigo: str) -> int:
    return int(conn.execute(
        text("INSERT INTO exemplares (livro_id, codigo) VALUES (:l, :c) RETURNING id"),
        {"l": livro_id, "c": codigo},
    ).scalar_one())


def _usuario(conn: Connection, email: str) -> int:
    return int(conn.execute(
        text("INSERT INTO usuarios (nome, email, senha_hash) VALUES ('U', :e, 'x') RETURNING id"),
        {"e": email},
    ).scalar_one())


def _locar(conn: Connection, exemplar_id: int, usuario_id: int) -> None:
    conn.execute(
        text(
            "INSERT INTO locacoes (exemplar_id, usuario_id, prevista_em) "
            "VALUES (:e, :u, now() + interval '14 days')"
        ),
        {"e": exemplar_id, "u": usuario_id},
    )


def test_all_tables_exist(engine: Engine) -> None:
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_exemplar_has_at_most_one_active_rental(engine: Engine) -> None:
    with engine.connect() as conn:
        ex = _exemplar(conn, _livro(conn, "A"), "A-1")
        u1, u2 = _usuario(conn, "a1@x.com"), _usuario(conn, "a2@x.com")
        _locar(conn, ex, u1)
        with pytest.raises(IntegrityError):
            _locar(conn, ex, u2)
        conn.rollback()


def test_exemplar_can_be_rented_again_after_return(engine: Engine) -> None:
    with engine.connect() as conn:
        ex = _exemplar(conn, _livro(conn, "B"), "B-1")
        u1, u2 = _usuario(conn, "b1@x.com"), _usuario(conn, "b2@x.com")
        _locar(conn, ex, u1)
        conn.execute(
            text("UPDATE locacoes SET devolvida_em = now() WHERE exemplar_id = :e"), {"e": ex}
        )
        _locar(conn, ex, u2)
        conn.rollback()


def test_availability_view_is_computed(engine: Engine) -> None:
    with engine.connect() as conn:
        livro = _livro(conn, "C")
        e1, _e2, _e3 = (_exemplar(conn, livro, f"C-{i}") for i in range(3))
        _locar(conn, e1, _usuario(conn, "c1@x.com"))
        row = conn.execute(
            text("SELECT total, livres FROM disponibilidade_livro WHERE livro_id = :l"),
            {"l": livro},
        ).one()
        assert (row.total, row.livres) == (3, 2)
        conn.rollback()


def test_embedding_has_768_dimensions(engine: Engine) -> None:
    vec = "[" + ",".join(["0.1"] * 768) + "]"
    with engine.connect() as conn:
        livro = _livro(conn, "D")
        conn.execute(
            text("INSERT INTO livro_embeddings (livro_id, modelo, vetor) VALUES (:l, 'm', :v)"),
            {"l": livro, "v": vec},
        )
        with pytest.raises(Exception, match="dimensions"):
            conn.execute(
                text(
                    "INSERT INTO livro_embeddings (livro_id, modelo, vetor) "
                    "VALUES (:l, 'm', '[1,2]')"
                ),
                {"l": _livro(conn, "E")},
            )
        conn.rollback()

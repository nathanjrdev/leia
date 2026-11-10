import hashlib
import math
import re
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from leia_api.busca import ResultadoBusca, buscar_livros, fundir_rrf, ranking_texto
from leia_api.embeddings import gerar_embeddings
from leia_api.models import EMBEDDING_DIM, Exemplar, Livro, Locacao, Usuario
from leia_api.seed import carregar_catalogo


class HashEncoder:
    """Bag-of-words em vetor de 768 dims: a similaridade segue a sobreposição de palavras."""

    def encode(self, textos: list[str]) -> list[list[float]]:
        saida = []
        for texto in textos:
            vetor = [0.0] * EMBEDDING_DIM
            for palavra in re.findall(r"[a-zà-ú]+", texto.lower()):
                vetor[
                    int(hashlib.md5(palavra.encode(), usedforsecurity=False).hexdigest(), 16)
                    % EMBEDDING_DIM
                ] += 1.0
            norma = math.sqrt(sum(x * x for x in vetor)) or 1.0
            saida.append([x / norma for x in vetor])
        return saida


def _livro(
    titulo: str, autor: str, sinopse: str, categorias: list[str], ano: int
) -> dict[str, Any]:
    return {
        "titulo": titulo,
        "autores": [autor],
        "ano": ano,
        "paginas": None,
        "editora": None,
        "isbn": None,
        "capa_url": None,
        "sinopse": sinopse,
        "sinopse_fonte": "teste",
        "categorias": categorias,
    }


CATALOGO = [
    _livro(
        "Dom Casmurro",
        "Machado de Assis",
        "Bentinho duvida da fidelidade de Capitu, sua esposa, e narra a memória do ciúme.",
        ["Romance"],
        1899,
    ),
    _livro(
        "Vidas Secas",
        "Graciliano Ramos",
        "Uma família de retirantes foge da seca no sertão do Nordeste brasileiro.",
        ["Romance"],
        1938,
    ),
    _livro(
        "Claro Enigma",
        "Carlos Drummond de Andrade",
        "Livro de poemas sobre o tempo, a memória e a perda.",
        ["Poesia"],
        1951,
    ),
    _livro(
        "O Gato e o Escuro",
        "Mia Couto",
        "Um gatinho tem medo da noite e descobre a beleza do escuro.",
        ["Infantojuvenil"],
        2008,
    ),
]


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with engine.connect() as conn:
        outer = conn.begin()
        with Session(conn, join_transaction_mode="create_savepoint") as s:
            carregar_catalogo(s, CATALOGO)
            gerar_embeddings(s, HashEncoder(), modelo="hash")
            yield s
        outer.rollback()


def _titulos(resultados: list[ResultadoBusca]) -> list[str]:
    return [r.titulo for r in resultados]


def test_rrf_rewards_items_present_in_several_lists() -> None:
    fundido = fundir_rrf([[1, 2, 3], [3, 1]])
    assert [x for x, _ in fundido] == [1, 3, 2]


def test_finds_book_by_title_word(session: Session) -> None:
    assert _titulos(buscar_livros(session, "casmurro", HashEncoder()))[0] == "Dom Casmurro"


def test_finds_book_by_author_name(session: Session) -> None:
    assert _titulos(buscar_livros(session, "Graciliano Ramos", HashEncoder()))[0] == "Vidas Secas"


def test_finds_book_by_intent_in_synopsis(session: Session) -> None:
    resultados = buscar_livros(session, "família que foge da seca no sertão", HashEncoder())
    assert _titulos(resultados)[0] == "Vidas Secas"


class EncoderNeutro:
    """Puxa toda consulta para "O Gato e o Escuro": só a busca textual leva outro livro ao topo."""

    def encode(self, textos: list[str]) -> list[list[float]]:
        return HashEncoder().encode(["gatinho medo noite escuro" for _ in textos])


def test_text_search_matches_any_word_not_all(session: Session) -> None:
    # "traição" não aparece em nenhuma sinopse; com E entre os termos, nada casaria.
    resultados = buscar_livros(session, "romance de ciúme e traição", EncoderNeutro())
    assert _titulos(resultados)[0] == "Dom Casmurro"


class EncoderPoemas:
    """Puxa toda consulta para "Claro Enigma", que também casa com "memória" no texto."""

    def encode(self, textos: list[str]) -> list[list[float]]:
        return HashEncoder().encode(["livro de poemas sobre o tempo e a perda" for _ in textos])


def test_book_matching_every_term_beats_book_in_two_lists_by_partial_match(
    session: Session,
) -> None:
    # "Claro Enigma" casa só com "memória" (texto) e lidera o vetor: duas listas.
    # Só "Dom Casmurro" tem todos os termos; a correspondência estrita precisa compensar.
    resultados = buscar_livros(session, "memória ciúme", EncoderPoemas())
    assert _titulos(resultados)[0] == "Dom Casmurro"


def test_negated_term_does_not_widen_the_or_text_list(session: Session) -> None:
    # "-ciúme" vira `!ciúm` e, com E trocado por OU, casaria com quase todos os livros.
    ids = ranking_texto(session, "memória -ciúme")
    titulos = set(session.scalars(select(Livro.titulo).where(Livro.id.in_(ids))))
    assert titulos == {"Dom Casmurro", "Claro Enigma"}  # só quem tem "memória"


class EncoderCasmurro:
    """Puxa toda consulta para "Dom Casmurro": só a lista de autor leva outro livro ao topo."""

    def encode(self, textos: list[str]) -> list[list[float]]:
        return HashEncoder().encode(["Bentinho duvida da fidelidade de Capitu" for _ in textos])


def test_author_list_works_when_query_has_extra_words(session: Session) -> None:
    resultados = buscar_livros(session, "obras de Mia Couto", EncoderCasmurro())
    assert _titulos(resultados)[0] == "O Gato e o Escuro"


def test_text_search_ignores_tsquery_syntax_in_user_text(session: Session) -> None:
    resultados = buscar_livros(session, "ciúme | & ! ( ) : * '", EncoderNeutro())
    assert _titulos(resultados)[0] == "Dom Casmurro"


def test_category_filter(session: Session) -> None:
    resultados = buscar_livros(session, "memória", HashEncoder(), categoria="poesia")
    assert _titulos(resultados) == ["Claro Enigma"]


def test_year_filter(session: Session) -> None:
    resultados = buscar_livros(session, "memória", HashEncoder(), ano_min=1950)
    assert "Dom Casmurro" not in _titulos(resultados)


def test_result_reports_availability(session: Session) -> None:
    resultado = buscar_livros(session, "casmurro", HashEncoder())[0]
    assert resultado.livres >= 1
    assert resultado.fila == 0


def test_only_available_excludes_fully_rented_books(session: Session) -> None:
    usuario = Usuario(nome="U", email="u@x.com", senha_hash="x")
    session.add(usuario)
    session.flush()
    alvo = buscar_livros(session, "casmurro", HashEncoder())[0]
    copias = session.scalars(select(Exemplar).where(Exemplar.livro_id == alvo.livro_id)).all()
    for copia in copias:
        session.add(
            Locacao(
                exemplar_id=copia.id,
                usuario_id=usuario.id,
                prevista_em=datetime.now(UTC) + timedelta(days=14),
            )
        )
    session.flush()
    resultados = buscar_livros(session, "casmurro", HashEncoder(), apenas_disponiveis=True)
    assert "Dom Casmurro" not in _titulos(resultados)


def test_reranker_promotes_its_favourite_but_is_fused_not_absolute(session: Session) -> None:
    sem = _titulos(buscar_livros(session, "memória", HashEncoder()))
    assert len(sem) > 2
    favorito = sem[-1]

    class Prefere:
        def score(self, consulta: str, documentos: list[str]) -> Sequence[float]:
            return [1.0 if favorito in doc else 0.0 for doc in documentos]

    com = _titulos(buscar_livros(session, "memória", HashEncoder(), reranker=Prefere()))
    assert com.index(favorito) < sem.index(favorito)  # subiu
    assert com[0] == sem[0]  # mas a fusão com o RRF impede que o reranker sozinho mande no topo


def test_tempos_por_etapa_sao_preenchidos_sem_mudar_o_resultado(session: Session) -> None:
    class Constante:
        def score(self, consulta: str, documentos: list[str]) -> Sequence[float]:
            return [0.0 for _ in documentos]

    sem_medir = buscar_livros(session, "memória", HashEncoder(), reranker=Constante())
    tempos: dict[str, int] = {}
    medindo = buscar_livros(session, "memória", HashEncoder(), reranker=Constante(), tempos=tempos)

    assert medindo == sem_medir
    assert set(tempos) == {
        "sql_texto",
        "sql_texto_estrito",
        "sql_autor",
        "encode",
        "sql_vetor",
        "carregar_livros",
        "reranker",
        "disponibilidade",
    }
    assert all(isinstance(v, int) and v >= 0 for v in tempos.values())


def test_tempos_sem_reranker_nao_tem_etapa_de_reranker(session: Session) -> None:
    tempos: dict[str, int] = {}
    buscar_livros(session, "memória", HashEncoder(), tempos=tempos)
    assert "reranker" not in tempos and "encode" in tempos

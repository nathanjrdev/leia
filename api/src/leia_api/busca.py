"""Busca híbrida do catálogo: texto (tsvector) + vetores (pgvector), fundidos por RRF.

Fluxo: quatro listas ranqueadas (título/sinopse em OU, título/sinopse com todos os termos,
nome de autor, similaridade vetorial)
→ Reciprocal Rank Fusion → os N primeiros candidatos → reranker opcional (cross-encoder),
cuja ordem é fundida de novo por RRF com a anterior (não a substitui) → top `limite`.
Na busca textual qualquer termo da consulta basta (OU); o ranking premia quem casa mais.
Disponibilidade vem da view `disponibilidade_livro`, nunca de coluna.
Somente leitura: o LLM chega aqui por ferramenta, nunca por SQL próprio.
"""

import re
import time
import unicodedata
from collections.abc import Callable, Hashable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from leia_api.config import settings
from leia_api.embeddings import Encoder, documento_do_livro
from leia_api.models import Livro

RRF_K = 60
CANDIDATOS_POR_LISTA = 50


# Precisa ser idêntica à expressão do índice GIN `ix_livros_busca_texto`.
_TSVECTOR = "to_tsvector('portuguese', coalesce(l.titulo, '') || ' ' || coalesce(l.sinopse, ''))"
# Consulta em linguagem natural: qualquer termo basta (OU); `ts_rank_cd` premia quem casa mais.
# `websearch_to_tsquery` nunca falha com o texto do usuário; só trocamos o E por OU. Termos
# negados (`-guerra`) saem antes: na tsquery viram `!guerr` e, com o OU, casariam com quase tudo.
# (A lista estrita, em E, respeita a negação.)
_TSQUERY_OU = (
    "(SELECT CAST(replace(CAST(websearch_to_tsquery('portuguese', "
    r"regexp_replace(:q, '(^|\s)-\S+', ' ', 'g')) AS text), ' & ', ' | ')"
    " AS tsquery) AS q) AS t"
)
# Todos os termos (E), com a negação interpretada pelo próprio `websearch_to_tsquery`.
_TSQUERY_E = "(SELECT websearch_to_tsquery('portuguese', :q) AS q) AS t"


class Reranker(Protocol):
    def score(self, consulta: str, documentos: list[str]) -> Sequence[float]: ...


@dataclass(frozen=True)
class ResultadoBusca:
    livro_id: int
    titulo: str
    autores: list[str]
    ano: int | None
    capa_url: str | None
    livres: int
    fila: int
    score: float


def fundir_rrf[T: Hashable](listas: Sequence[Sequence[T]], k: int = RRF_K) -> list[tuple[T, float]]:
    """Reciprocal Rank Fusion: soma 1/(k+posição) de cada lista; empates mantêm a ordem."""
    pontos: dict[T, float] = {}
    for lista in listas:
        for posicao, item in enumerate(lista, start=1):
            pontos[item] = pontos.get(item, 0.0) + 1.0 / (k + posicao)
    return sorted(pontos.items(), key=lambda par: -par[1])


def _filtros(
    categoria: str | None, ano_min: int | None, ano_max: int | None, apenas_disponiveis: bool
) -> tuple[str, dict[str, object]]:
    condicoes: list[str] = []
    params: dict[str, object] = {}
    if categoria:
        condicoes.append(
            "EXISTS (SELECT 1 FROM livro_categoria lc JOIN categorias c ON c.id = lc.categoria_id "
            "WHERE lc.livro_id = l.id AND c.slug = :categoria)"
        )
        params["categoria"] = categoria
    if ano_min is not None:
        condicoes.append("l.ano >= :ano_min")
        params["ano_min"] = ano_min
    if ano_max is not None:
        condicoes.append("l.ano <= :ano_max")
        params["ano_max"] = ano_max
    if apenas_disponiveis:
        condicoes.append(
            "EXISTS (SELECT 1 FROM disponibilidade_livro d "
            "WHERE d.livro_id = l.id AND d.livres > 0)"
        )
    return "".join(f" AND {c}" for c in condicoes), params


def _ids(session: Session, sql: str, params: dict[str, object]) -> list[int]:
    return [int(linha[0]) for linha in session.execute(text(sql), params)]


def _ranking_texto(
    session: Session,
    tsquery: str,
    consulta: str,
    filtro: str,
    params: dict[str, object] | None,
    n: int,
) -> list[int]:
    """`tsquery` é uma das constantes `_TSQUERY_*` deste módulo, nunca texto do usuário."""
    return _ids(
        session,
        f"""SELECT l.id FROM livros l, {tsquery}
            WHERE {_TSVECTOR} @@ t.q {filtro}
            ORDER BY ts_rank_cd({_TSVECTOR}, t.q) DESC LIMIT :n""",  # noqa: S608
        {**(params or {}), "q": consulta, "n": n},
    )


def ranking_texto(
    session: Session,
    consulta: str,
    *,
    filtro: str = "",
    params: dict[str, object] | None = None,
    n: int = CANDIDATOS_POR_LISTA,
) -> list[int]:
    """Ids dos livros cuja título/sinopse casa com algum termo da consulta, melhor primeiro."""
    return _ranking_texto(session, _TSQUERY_OU, consulta, filtro, params, n)


def ranking_texto_estrito(
    session: Session,
    consulta: str,
    *,
    filtro: str = "",
    params: dict[str, object] | None = None,
    n: int = CANDIDATOS_POR_LISTA,
) -> list[int]:
    """Ids dos livros cuja título/sinopse contém TODOS os termos da consulta (E), melhor primeiro.

    Sinal forte que a busca em OU dilui: quem casa tudo ganha crédito extra na fusão.
    """
    return _ranking_texto(session, _TSQUERY_E, consulta, filtro, params, n)


def ranking_autor(
    session: Session,
    consulta: str,
    *,
    filtro: str = "",
    params: dict[str, object] | None = None,
    n: int = CANDIDATOS_POR_LISTA,
) -> list[int]:
    """Ids dos livros de autores cujo nome casa com algum termo da consulta.

    Termos soltos, sem stopwords ("livros de Clarice Lispector" acha Clarice), sem radical
    (para "branca" não casar com "Castelo Branco"). Quem casa mais termos do nome vem antes.
    """
    return _ids(
        session,
        f"""WITH termos AS (
                SELECT w FROM unnest(tsvector_to_array(to_tsvector('simple', :q))) AS w
                WHERE to_tsvector('portuguese', w) <> ''::tsvector
            )
            SELECT l.id FROM livros l
            JOIN livro_autor la ON la.livro_id = l.id
            JOIN autores a ON a.id = la.autor_id
            JOIN LATERAL (
                SELECT count(*) AS casados FROM termos
                WHERE to_tsvector('simple', a.nome) @@ plainto_tsquery('simple', termos.w)
            ) m ON m.casados > 0
            WHERE true {filtro}
            GROUP BY l.id ORDER BY max(m.casados) DESC, l.id LIMIT :n""",  # noqa: S608
        {**(params or {}), "q": consulta, "n": n},
    )


def _chave_titulo(texto: str) -> str:
    """Título comparável: sem acento, caixa, pontuação nem espaços repetidos."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return " ".join(re.sub(r"[^\w\s]", " ", sem_acento.casefold()).split())


@contextmanager
def _etapa(
    tempos: dict[str, int] | None, nome: str, cronometro: Callable[[], float] = time.perf_counter
) -> Iterator[None]:
    """Mede uma etapa em ms em `tempos` (se dado). Só observa: não muda a busca."""
    if tempos is None:
        yield
        return
    inicio = cronometro()
    try:
        yield
    finally:
        tempos[nome] = max(0, round((cronometro() - inicio) * 1000))


def buscar_livros(
    session: Session,
    consulta: str,
    encoder: Encoder,
    *,
    limite: int = 10,
    categoria: str | None = None,
    ano_min: int | None = None,
    ano_max: int | None = None,
    apenas_disponiveis: bool = False,
    reranker: Reranker | None = None,
    tempos: dict[str, int] | None = None,
    candidatos_reranker: int | None = None,
) -> list[ResultadoBusca]:
    """Busca híbrida. `tempos`, se dado, recebe a duração de cada etapa em ms (medição).

    `candidatos_reranker` (padrão: `settings.reranker_candidatos`) é quantos itens da fusão
    seguem para o reranker; sem reranker, é também o teto antes do corte em `limite`.
    """
    n_candidatos = candidatos_reranker or settings.reranker_candidatos
    filtro, params = _filtros(categoria, ano_min, ano_max, apenas_disponiveis)
    base = {**params, "q": consulta, "n": CANDIDATOS_POR_LISTA}

    with _etapa(tempos, "sql_texto"):
        por_texto = ranking_texto(session, consulta, filtro=filtro, params=params)
    with _etapa(tempos, "sql_texto_estrito"):
        por_texto_estrito = ranking_texto_estrito(session, consulta, filtro=filtro, params=params)
    with _etapa(tempos, "sql_autor"):
        por_autor = ranking_autor(session, consulta, filtro=filtro, params=params)
    with _etapa(tempos, "encode"):
        vetor = "[" + ",".join(f"{x:.6f}" for x in encoder.encode([consulta])[0]) + "]"
    with _etapa(tempos, "sql_vetor"):
        por_vetor = _ids(
            session,
            f"""SELECT l.id FROM livro_embeddings e JOIN livros l ON l.id = e.livro_id
                WHERE true {filtro}
                ORDER BY e.vetor <=> CAST(:v AS vector) LIMIT :n""",  # noqa: S608
            {**base, "v": vetor},
        )

    listas = [por_texto, por_texto_estrito, por_autor, por_vetor]
    fundidos = fundir_rrf(listas)[:n_candidatos]
    if not fundidos:
        return []

    ids = [livro_id for livro_id, _ in fundidos]
    with _etapa(tempos, "carregar_livros"):
        consulta_livros = select(Livro).where(Livro.id.in_(ids))
        livros = {livro.id: livro for livro in session.scalars(consulta_livros)}
    pontuacao = dict(fundidos)
    chave = _chave_titulo(consulta)
    exatos = [i for i in ids if chave and _chave_titulo(livros[i].titulo) == chave]
    if reranker is not None and exatos:
        # Atalho: a consulta é o título de um livro. O reranker (~1,4 s em CPU) não mudaria o
        # que o leitor pediu; o livro vem primeiro e o resto segue a ordem da fusão.
        with _etapa(tempos, "atalho_titulo"):
            ids = exatos + [i for i in ids if i not in exatos]
            pontuacao = {i: pontuacao[i] + (1.0 if i in exatos else 0.0) for i in ids}
    elif reranker is not None:
        with _etapa(tempos, "reranker"):
            notas = reranker.score(consulta, [documento_do_livro(livros[i]) for i in ids])
        ordem_reranker = [i for i, _ in sorted(zip(ids, notas, strict=True), key=lambda p: -p[1])]
        fundidos = fundir_rrf([ids, ordem_reranker])
        ids = [livro_id for livro_id, _ in fundidos]
        pontuacao = dict(fundidos)

    with _etapa(tempos, "disponibilidade"):
        disponibilidade = {
            int(r.livro_id): (int(r.livres), int(r.fila))
            for r in session.execute(
                text(
                    "SELECT livro_id, livres, fila FROM disponibilidade_livro "
                    "WHERE livro_id IN :ids"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": ids},
            )
        }
    return [
        ResultadoBusca(
            livro_id=i,
            titulo=livros[i].titulo,
            autores=[a.nome for a in livros[i].autores],
            ano=livros[i].ano,
            capa_url=livros[i].capa_url,
            livres=disponibilidade.get(i, (0, 0))[0],
            fila=disponibilidade.get(i, (0, 0))[1],
            score=pontuacao[i],
        )
        for i in ids[:limite]
    ]

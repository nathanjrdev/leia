"""Busca híbrida do catálogo: texto (tsvector) + vetores (pgvector), fundidos por RRF.

Fluxo: três listas ranqueadas (título/sinopse, nome de autor, similaridade vetorial)
→ Reciprocal Rank Fusion → os N primeiros candidatos → reranker opcional (cross-encoder)
→ top `limite`. Disponibilidade vem da view `disponibilidade_livro`, nunca de coluna.
Somente leitura: o LLM chega aqui por ferramenta, nunca por SQL próprio.
"""

from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from leia_api.embeddings import Encoder, documento_do_livro
from leia_api.models import Livro

RRF_K = 60
CANDIDATOS_POR_LISTA = 50
CANDIDATOS_RERANKER = 20


# Precisa ser idêntica à expressão do índice GIN `ix_livros_busca_texto`.
_TSVECTOR = "to_tsvector('portuguese', coalesce(l.titulo, '') || ' ' || coalesce(l.sinopse, ''))"


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
) -> list[ResultadoBusca]:
    filtro, params = _filtros(categoria, ano_min, ano_max, apenas_disponiveis)
    base = {**params, "q": consulta, "n": CANDIDATOS_POR_LISTA}

    por_texto = _ids(
        session,
        f"""SELECT l.id FROM livros l, websearch_to_tsquery('portuguese', :q) q
            WHERE {_TSVECTOR} @@ q {filtro}
            ORDER BY ts_rank_cd({_TSVECTOR}, q) DESC LIMIT :n""",  # noqa: S608
        base,
    )
    por_autor = _ids(
        session,
        f"""SELECT DISTINCT l.id FROM livros l
            JOIN livro_autor la ON la.livro_id = l.id
            JOIN autores a ON a.id = la.autor_id, websearch_to_tsquery('simple', :q) q
            WHERE to_tsvector('simple', a.nome) @@ q {filtro}
            ORDER BY l.id LIMIT :n""",  # noqa: S608
        base,
    )
    vetor = "[" + ",".join(f"{x:.6f}" for x in encoder.encode([consulta])[0]) + "]"
    por_vetor = _ids(
        session,
        f"""SELECT l.id FROM livro_embeddings e JOIN livros l ON l.id = e.livro_id
            WHERE true {filtro}
            ORDER BY e.vetor <=> CAST(:v AS vector) LIMIT :n""",  # noqa: S608
        {**base, "v": vetor},
    )

    fundidos = fundir_rrf([por_texto, por_autor, por_vetor])[:CANDIDATOS_RERANKER]
    if not fundidos:
        return []

    ids = [livro_id for livro_id, _ in fundidos]
    livros = {livro.id: livro for livro in session.scalars(select(Livro).where(Livro.id.in_(ids)))}
    pontuacao = dict(fundidos)
    if reranker is not None:
        notas = reranker.score(consulta, [documento_do_livro(livros[i]) for i in ids])
        pontuacao = {i: float(n) for i, n in zip(ids, notas, strict=True)}
        ids = sorted(ids, key=lambda i: -pontuacao[i])

    disponibilidade = {
        int(r.livro_id): (int(r.livres), int(r.fila))
        for r in session.execute(
            text(
                "SELECT livro_id, livres, fila FROM disponibilidade_livro WHERE livro_id IN :ids"
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

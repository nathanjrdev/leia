"""Pipeline de embeddings do catálogo.

Cada livro vira um documento (título, autor, categorias, sinopse) e um vetor
guardado em `livro_embeddings`. O encoder é injetado: em produção é o
sentence-transformers; nos testes, um falso determinístico.
"""

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from leia_api.models import Livro, LivroEmbedding

MODELO_PADRAO = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


class Encoder(Protocol):
    def encode(self, textos: list[str]) -> Sequence[Sequence[float]]: ...


def documento_do_livro(livro: Livro) -> str:
    partes = [
        livro.titulo,
        "Autor: " + ", ".join(a.nome for a in livro.autores),
        "Categorias: " + ", ".join(c.nome for c in livro.categorias),
        livro.sinopse or "",
    ]
    return "\n".join(p for p in partes if p.strip())


def gerar_embeddings(
    session: Session, encoder: Encoder, *, modelo: str = MODELO_PADRAO, lote: int = 32
) -> int:
    """Gera embeddings dos livros sem vetor do `modelo` informado. Devolve quantos criou."""
    com_modelo = select(LivroEmbedding.livro_id).where(LivroEmbedding.modelo == modelo)
    pendentes = list(session.scalars(select(Livro).where(Livro.id.not_in(com_modelo))))
    for inicio in range(0, len(pendentes), lote):
        grupo = pendentes[inicio : inicio + lote]
        vetores = encoder.encode([documento_do_livro(livro) for livro in grupo])
        for livro, vetor in zip(grupo, vetores, strict=True):
            existente = session.get(LivroEmbedding, livro.id)
            if existente is None:
                session.add(LivroEmbedding(livro_id=livro.id, modelo=modelo, vetor=list(vetor)))
            else:  # troca de modelo: substitui o vetor antigo
                existente.modelo = modelo
                existente.vetor = list(vetor)
        session.flush()
    return len(pendentes)

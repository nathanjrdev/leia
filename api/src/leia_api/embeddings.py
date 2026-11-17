"""Pipeline de embeddings do catálogo.

Cada livro vira um documento (título, autor, categorias, sinopse) e um vetor
guardado em `livro_embeddings`. O encoder é injetado: em produção é o
sentence-transformers; nos testes, um falso determinístico.
"""

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from leia_api.config import settings
from leia_api.models import Livro, LivroEmbedding

MODELO_PADRAO = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
# O padrão do modelo é 128 tokens e cortava o fim da sinopse (onde ficam os temas) em 150 dos
# 153 documentos do catálogo (maior: 193 tokens). 256 cobre o documento inteiro.
MAX_TOKENS_ENCODER = 256


# Chave gravada em `livro_embeddings.modelo`. Leva o limite de tokens para que mudá-lo invalide os
# vetores antigos: `gerar_embeddings` só pula livros que já têm vetor desta mesma chave.
def chave_embedding(modelo: str) -> str:
    return f"{modelo}@{MAX_TOKENS_ENCODER}"


# Chave do modelo base. Com outro `ENCODER_MODELO`, a chave muda e `gerar_embeddings` regera tudo.
CHAVE_EMBEDDING = chave_embedding(MODELO_PADRAO)


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
    session: Session, encoder: Encoder, *, modelo: str | None = None, lote: int = 32
) -> int:
    """Gera embeddings dos livros sem vetor do `modelo` informado. Devolve quantos criou."""
    modelo = modelo or chave_embedding(settings.encoder_modelo)
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

"""Consultas de leitura do catálogo para as ferramentas do agente: ficha e disponibilidade.

Disponibilidade vem da view `disponibilidade_livro`, nunca de coluna.
"""

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from leia_api.locacao import ErroLocacao
from leia_api.models import Livro


@dataclass(frozen=True)
class Disponibilidade:
    livro_id: int
    total: int
    livres: int
    fila: int


@dataclass(frozen=True)
class FichaLivro:
    livro_id: int
    titulo: str
    autores: list[str]
    categorias: list[str]
    sinopse: str | None
    ano: int | None
    editora: str | None
    paginas: int | None
    capa_url: str | None
    disponibilidade: Disponibilidade


def verificar_disponibilidade(session: Session, livro_id: int) -> Disponibilidade:
    linha = session.execute(
        text("SELECT total, livres, fila FROM disponibilidade_livro WHERE livro_id = :l"),
        {"l": livro_id},
    ).one_or_none()
    if linha is None:
        raise ErroLocacao("livro_inexistente", "Livro não encontrado no acervo.")
    return Disponibilidade(
        livro_id=livro_id, total=int(linha[0]), livres=int(linha[1]), fila=int(linha[2])
    )


def detalhar_livro(session: Session, livro_id: int) -> FichaLivro:
    livro = session.scalars(select(Livro).where(Livro.id == livro_id)).one_or_none()
    if livro is None:
        raise ErroLocacao("livro_inexistente", "Livro não encontrado no acervo.")
    return FichaLivro(
        livro_id=livro.id,
        titulo=livro.titulo,
        autores=[a.nome for a in livro.autores],
        categorias=[c.nome for c in livro.categorias],
        sinopse=livro.sinopse,
        ano=livro.ano,
        editora=livro.editora,
        paginas=livro.paginas,
        capa_url=livro.capa_url,
        disponibilidade=verificar_disponibilidade(session, livro_id),
    )

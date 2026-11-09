"""Consultas de leitura do catálogo para as ferramentas do agente: ficha e disponibilidade.

Disponibilidade vem da view `disponibilidade_livro`, nunca de coluna.
"""

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from leia_api.busca import _filtros as filtros_sql
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


@dataclass(frozen=True)
class ItemListagem:
    livro_id: int
    titulo: str
    autores: list[str]
    ano: int | None
    capa_url: str | None
    livres: int
    fila: int


def listar_livros(
    session: Session,
    *,
    categoria: str | None = None,
    ano_min: int | None = None,
    ano_max: int | None = None,
    apenas_disponiveis: bool = False,
    pagina: int = 1,
    limite: int = 20,
) -> tuple[list[ItemListagem], int]:
    """Navegação paginada do acervo (ordem alfabética). Devolve (itens da página, total)."""
    filtro, params = filtros_sql(categoria, ano_min, ano_max, apenas_disponiveis)
    total = int(
        session.execute(
            text(f"SELECT count(*) FROM livros l WHERE true{filtro}"),  # noqa: S608 - filtro vem de _filtros, só com parâmetros nomeados
            params,
        ).scalar_one()
    )
    linhas = session.execute(
        text(
            "SELECT l.id, COALESCE(d.livres, 0), COALESCE(d.fila, 0) FROM livros l "  # noqa: S608
            "LEFT JOIN disponibilidade_livro d ON d.livro_id = l.id "
            f"WHERE true{filtro} ORDER BY l.titulo, l.id LIMIT :limite OFFSET :deslocamento"
        ),
        {**params, "limite": limite, "deslocamento": (pagina - 1) * limite},
    ).all()
    disponibilidade = {int(i): (int(livres), int(fila)) for i, livres, fila in linhas}
    ordem = list(disponibilidade)
    livros = {
        livro.id: livro
        for livro in session.scalars(select(Livro).where(Livro.id.in_(ordem))).unique()
    }
    itens = [
        ItemListagem(
            livro_id=i,
            titulo=livros[i].titulo,
            autores=[a.nome for a in livros[i].autores],
            ano=livros[i].ano,
            capa_url=livros[i].capa_url,
            livres=disponibilidade[i][0],
            fila=disponibilidade[i][1],
        )
        for i in ordem
    ]
    return itens, total

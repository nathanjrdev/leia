"""Normaliza para NFC títulos de livros e nomes de autores já gravados

Alguns títulos vieram das fontes com acentos decompostos (NFD) e não casavam
com o texto digitado pelo leitor (NFC), nem na busca textual nem por igualdade.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE livros SET titulo = normalize(titulo, NFC) WHERE titulo IS NOT NFC NORMALIZED")
    op.execute("UPDATE autores SET nome = normalize(nome, NFC) WHERE nome IS NOT NFC NORMALIZED")


def downgrade() -> None:
    # Migração só de dados: a forma NFD original não é recuperável nem desejável.
    pass

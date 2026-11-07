"""livros.sinopse_fonte: atribuição da sinopse (Open Library ou Wikipedia, CC BY-SA)

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("livros", sa.Column("sinopse_fonte", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("livros", "sinopse_fonte")

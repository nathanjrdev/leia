"""identidades_externas: entrar com Google/Microsoft (vínculo provedor + sub -> usuário)

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identidades_externas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provedor", sa.String(20), nullable=False),
        sa.Column("sujeito", sa.String(255), nullable=False),
        sa.Column(
            "criada_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("provedor", "sujeito", name="uq_identidades_provedor_sujeito"),
        sa.CheckConstraint(
            "provedor IN ('google', 'microsoft')", name="ck_identidades_externas_provedor"
        ),
    )
    op.create_index(
        "ix_identidades_externas_usuario_id", "identidades_externas", ["usuario_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_identidades_externas_usuario_id", table_name="identidades_externas")
    op.drop_table("identidades_externas")

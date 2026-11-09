"""acoes_pendentes (confirmações por conversa) e conversas.livros_vistos (grounding entre turnos)

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversas",
        sa.Column("livros_vistos", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.create_table(
        "acoes_pendentes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversa_id",
            sa.Integer(),
            sa.ForeignKey("conversas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("ferramenta", sa.String(20), nullable=False),
        sa.Column("argumentos", JSONB(), nullable=False),
        sa.Column("resumo", sa.Text(), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token", name="uq_acoes_pendentes_token"),
        sa.CheckConstraint(
            "ferramenta IN ('locar', 'renovar', 'devolver', 'reservar')",
            name="ck_acoes_pendentes_ferramenta",
        ),
    )
    op.create_index("ix_acoes_pendentes_conversa_id", "acoes_pendentes", ["conversa_id"])
    op.create_index("ix_acoes_pendentes_usuario_id", "acoes_pendentes", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_acoes_pendentes_usuario_id", table_name="acoes_pendentes")
    op.drop_index("ix_acoes_pendentes_conversa_id", table_name="acoes_pendentes")
    op.drop_table("acoes_pendentes")
    op.drop_column("conversas", "livros_vistos")

"""reservas: pronta_em (início do prazo de retirada) e status 'expirada'

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reservas", sa.Column("pronta_em", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("ck_reservas_status", "reservas", type_="check")
    op.create_check_constraint(
        "ck_reservas_status",
        "reservas",
        "status IN ('ativa', 'atendida', 'cancelada', 'expirada')",
    )


def downgrade() -> None:
    op.execute("UPDATE reservas SET status = 'cancelada' WHERE status = 'expirada'")
    op.drop_constraint("ck_reservas_status", "reservas", type_="check")
    op.create_check_constraint(
        "ck_reservas_status", "reservas", "status IN ('ativa', 'atendida', 'cancelada')"
    )
    op.drop_column("reservas", "pronta_em")

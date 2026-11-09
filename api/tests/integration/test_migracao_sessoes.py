from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect


def test_0004_cria_sessoes_e_o_downgrade_desfaz(alembic_cfg: Config, engine: Engine) -> None:
    try:
        command.downgrade(alembic_cfg, "0003")
        assert "sessoes" not in inspect(engine).get_table_names()

        command.upgrade(alembic_cfg, "head")
        insp = inspect(engine)
        colunas = {c["name"] for c in insp.get_columns("sessoes")}
        indices = {i["name"] for i in insp.get_indexes("sessoes")}
        assert colunas == {"id", "usuario_id", "token_hash", "criada_em", "expira_em"}
        assert {"ix_sessoes_usuario_id", "ix_sessoes_expira_em"} <= indices
        unicas = {tuple(u["column_names"]) for u in insp.get_unique_constraints("sessoes")}
        assert ("token_hash",) in unicas
    finally:
        command.upgrade(alembic_cfg, "head")

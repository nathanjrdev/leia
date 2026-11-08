import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from testcontainers.community.postgres import PostgresContainer

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")


@pytest.fixture(scope="session")
def alembic_cfg() -> Iterator[Config]:
    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as pg:
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", pg.get_connection_url())
        command.upgrade(cfg, "head")
        yield cfg


@pytest.fixture(scope="session")
def engine(alembic_cfg: Config) -> Iterator[Engine]:
    eng = create_engine(alembic_cfg.get_main_option("sqlalchemy.url") or "")
    yield eng
    eng.dispose()

"""Conexão com o Postgres para a API. Os testes trocam `get_session` por uma sessão do container."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from leia_api.config import settings


@lru_cache(maxsize=1)
def engine() -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão por requisição."""
    with Session(engine()) as session:
        yield session

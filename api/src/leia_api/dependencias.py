"""Dependências pesadas da API (modelos de ML, cliente de LLM), criadas uma vez e sob demanda.

Os testes as substituem por falsos com `app.dependency_overrides`; o código de produção só
importa `sentence_transformers` na primeira requisição que precisa dele.
"""

from collections.abc import Callable
from functools import lru_cache

from sqlalchemy.orm import Session

from leia_api import db
from leia_api.agente import Agente, ConfigAgente
from leia_api.busca import Reranker
from leia_api.embeddings import Encoder
from leia_api.llm import cliente_padrao


@lru_cache(maxsize=1)
def get_agente() -> Agente:
    return Agente(cliente_padrao(), ConfigAgente.da_config())


@lru_cache(maxsize=1)
def get_encoder() -> Encoder:
    from leia_api.modelos import EncoderST

    return EncoderST()


@lru_cache(maxsize=1)
def get_reranker() -> Reranker | None:
    from leia_api.modelos import CrossEncoderReranker

    return CrossEncoderReranker()


def get_fabrica_sessao() -> Callable[[], Session]:
    """Abre sessões próprias para o trabalho que continua depois da resposta HTTP (o stream)."""
    return lambda: Session(db.engine())

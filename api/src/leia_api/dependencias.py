"""Dependências pesadas da API (modelos de ML, cliente de LLM), criadas uma vez e sob demanda.

Os testes as substituem por falsos com `app.dependency_overrides`; o código de produção só
importa `sentence_transformers` na primeira requisição que precisa dele.
"""

from collections.abc import Callable
from functools import lru_cache

from sqlalchemy.orm import Session

from leia_api import db, llm
from leia_api.agente import Agente, ConfigAgente
from leia_api.busca import Reranker
from leia_api.config import settings
from leia_api.embeddings import Encoder
from leia_api.llm import cliente_padrao


@lru_cache(maxsize=1)
def get_agente() -> Agente:
    if settings.modo_teste:
        from leia_api.modo_teste import LLMDeTeste

        return Agente(LLMDeTeste(), ConfigAgente.da_config())
    return Agente(cliente_padrao(), ConfigAgente.da_config())


@lru_cache(maxsize=1)
def get_encoder() -> Encoder:
    if settings.modo_teste:
        from leia_api.modo_teste import EncoderDeTeste

        return EncoderDeTeste()
    from leia_api.modelos import EncoderST

    return EncoderST()


@lru_cache(maxsize=1)
def get_reranker() -> Reranker | None:
    if settings.modo_teste:
        return None
    from leia_api.modelos import CrossEncoderReranker

    return CrossEncoderReranker()


def aquecer_llm() -> None:
    """Deixa o cliente de LLM pronto antes da 1ª mensagem (o import do litellm é lento)."""
    if settings.modo_teste:
        return
    llm.aquecer()


def get_fabrica_sessao() -> Callable[[], Session]:
    """Abre sessões próprias para o trabalho que continua depois da resposta HTTP (o stream)."""
    return lambda: Session(db.engine())

"""Configuração comum a todos os testes.

Os testes não dependem do .env de quem roda: com AQUECER_MODELOS=true (o padrão do .env de
desenvolvimento), todo `TestClient(app)` dispararia o aquecimento na subida da app, carregando o
encoder e o reranker de verdade. Sem o grupo `ml` instalado (`uv sync` sozinho remove o
sentence-transformers) isso vira erro em todos os testes que sobem a API.
"""

from collections.abc import Iterator

import pytest

from leia_api.config import settings


@pytest.fixture(autouse=True)
def _sem_aquecimento(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "aquecer_modelos", False)
    yield

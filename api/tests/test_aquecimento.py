"""Aquecimento dos modelos de busca na subida da API (evita a primeira mensagem lenta)."""

import pytest
from fastapi.testclient import TestClient

from leia_api import dependencias
from leia_api.config import settings
from leia_api.main import app


@pytest.fixture
def chamadas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    vistas: list[str] = []
    monkeypatch.setattr(dependencias, "get_encoder", lambda: vistas.append("encoder"))
    monkeypatch.setattr(dependencias, "get_reranker", lambda: vistas.append("reranker"))
    return vistas


def test_desligado_nao_carrega_modelos(
    monkeypatch: pytest.MonkeyPatch, chamadas: list[str]
) -> None:
    monkeypatch.setattr(settings, "aquecer_modelos", False)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
    assert chamadas == []


def test_ligado_carrega_encoder_e_reranker_antes_de_atender(
    monkeypatch: pytest.MonkeyPatch, chamadas: list[str]
) -> None:
    monkeypatch.setattr(settings, "aquecer_modelos", True)
    with TestClient(app) as c:
        assert chamadas == ["encoder", "reranker"]
        assert c.get("/health").status_code == 200

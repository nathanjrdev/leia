"""Aquecimento dos modelos de busca na subida da API (evita a primeira mensagem lenta)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from leia_api import dependencias
from leia_api.config import settings
from leia_api.main import app


@pytest.fixture
def chamadas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    vistas: list[str] = []
    monkeypatch.setattr(dependencias, "get_encoder", lambda: vistas.append("encoder"))
    monkeypatch.setattr(dependencias, "get_reranker", lambda: vistas.append("reranker"))
    monkeypatch.setattr(dependencias, "aquecer_llm", lambda: vistas.append("llm"))
    return vistas


def test_desligado_nao_carrega_modelos(
    monkeypatch: pytest.MonkeyPatch, chamadas: list[str]
) -> None:
    monkeypatch.setattr(settings, "aquecer_modelos", False)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
    assert chamadas == []


def test_ligado_carrega_encoder_reranker_e_cliente_llm_antes_de_atender(
    monkeypatch: pytest.MonkeyPatch, chamadas: list[str]
) -> None:
    monkeypatch.setattr(settings, "aquecer_modelos", True)
    with TestClient(app) as c:
        # o import do litellm leva ~10-13 s; sem isto a 1ª mensagem pagava a conta
        assert chamadas == ["encoder", "reranker", "llm"]
        assert c.get("/health").status_code == 200


def test_aquecer_llm_importa_o_cliente_sem_chamar_o_provedor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from leia_api import llm

    vistas: list[str] = []
    monkeypatch.setattr(llm, "aquecer", lambda: vistas.append("import"))
    monkeypatch.setattr(settings, "modo_teste", False)
    # a chave vem do Settings; sem ela o aquecimento falha (test_config_chaves.py)
    monkeypatch.setattr(settings, "leia_model", "gemini/gemini-flash-lite-latest")
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("g-teste"))
    dependencias.aquecer_llm()
    assert vistas == ["import"]


def test_aquecer_llm_no_modo_teste_nao_importa_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    from leia_api import llm

    vistas: list[str] = []
    monkeypatch.setattr(llm, "aquecer", lambda: vistas.append("import"))
    monkeypatch.setattr(settings, "modo_teste", True)
    dependencias.aquecer_llm()
    assert vistas == []

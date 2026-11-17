"""Encoder da busca configurável (ENCODER_MODELO), com o modelo base como padrão."""

import pytest

from leia_api import embeddings
from leia_api.config import Settings, settings
from leia_api.embeddings import CHAVE_EMBEDDING, MAX_TOKENS_ENCODER, MODELO_PADRAO, chave_embedding


def _settings() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_padrao_do_settings_e_o_modelo_base() -> None:
    assert _settings().encoder_modelo == MODELO_PADRAO


def test_encoder_vem_do_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCODER_MODELO", "nathanjrdev/leia-embeddings-pt")
    assert _settings().encoder_modelo == "nathanjrdev/leia-embeddings-pt"


def test_chave_leva_modelo_e_limite_de_tokens() -> None:
    assert chave_embedding("x/y") == f"x/y@{MAX_TOKENS_ENCODER}"
    assert CHAVE_EMBEDDING == chave_embedding(MODELO_PADRAO)


def test_gerar_embeddings_usa_a_chave_do_encoder_configurado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem `modelo`, a chave vem do ENCODER_MODELO: trocar o encoder invalida os vetores."""
    monkeypatch.setattr(settings, "encoder_modelo", "outro/modelo")
    vistas: list[object] = []

    class _Sessao:
        def scalars(self, consulta: object) -> list[object]:
            vistas.append(consulta)
            return []

    assert embeddings.gerar_embeddings(_Sessao(), encoder=None) == 0  # type: ignore[arg-type]
    sql = str(vistas[0].compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]
    assert f"outro/modelo@{MAX_TOKENS_ENCODER}" in sql

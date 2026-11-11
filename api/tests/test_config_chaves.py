"""Chave do provedor de LLM: vem do `Settings` (explícita), nunca de efeito colateral de import.

Antes, a chave chegava ao LiteLLM porque ele mesmo procurava um `.env` subindo pelas pastas ao
ser importado (`load_dotenv` com `LITELLM_MODE=DEV`). Funcionava por acaso: dependia de onde
ficava o `.venv` e da versão da biblioteca.
"""

import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from leia_api import dependencias
from leia_api.config import Settings, settings


def _config(**campos: Any) -> Settings:
    return Settings(_env_file=None, **campos)  # type: ignore[call-arg]


def test_chave_do_modelo_vem_do_campo_do_provedor() -> None:
    c = _config(leia_model="anthropic/claude-haiku-5-5", anthropic_api_key="sk-ant-x")
    assert c.chave_do_modelo() == "sk-ant-x"
    assert c.exigir_chave_do_modelo() == "sk-ant-x"

    g = _config(leia_model="gemini/gemini-flash-lite-latest", gemini_api_key="g-x")
    assert g.chave_do_modelo() == "g-x"


def test_sem_a_chave_do_provedor_a_mensagem_diz_qual_variavel_falta() -> None:
    c = _config(leia_model="anthropic/claude-haiku-5-5", gemini_api_key="g-x")

    assert c.chave_do_modelo() is None
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY") as erro:
        c.exigir_chave_do_modelo()
    assert "g-x" not in str(erro.value)


def test_provedor_sem_chave_conhecida_nao_exige_nada() -> None:
    # ex.: um modelo local; o LiteLLM decide sozinho
    assert _config(leia_model="ollama/llama3").exigir_chave_do_modelo() is None


def test_chave_nao_aparece_no_repr_nem_no_dump() -> None:
    c = _config(anthropic_api_key="sk-ant-segredo")
    assert "sk-ant-segredo" not in repr(c)
    assert "sk-ant-segredo" not in str(c.model_dump())


def test_env_file_e_absoluto_e_aponta_para_a_raiz_do_repositorio() -> None:
    caminho = Path(str(Settings.model_config["env_file"]))
    assert caminho.is_absolute()  # não depende da pasta de onde o processo subiu
    assert caminho.name == ".env"
    assert (caminho.parent / "api" / "src" / "leia_api" / "config.py").exists()


def test_cliente_passa_a_chave_explicita_ao_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    import litellm

    from leia_api.llm import ClienteLiteLLM

    recebido: dict[str, Any] = {}

    class _Parar(Exception):
        pass

    def _completion(**kwargs: Any) -> Any:
        recebido.update(kwargs)
        raise _Parar

    monkeypatch.setattr(litellm, "completion", _completion)
    cliente = ClienteLiteLLM(modelo="anthropic/claude-haiku-5-5", chave="sk-ant-x")

    with pytest.raises(_Parar):
        cliente.completar([{"role": "user", "content": "oi"}], [], 5.0)
    assert recebido["api_key"] == "sk-ant-x"

    recebido.clear()
    with pytest.raises(_Parar):
        cliente.completar_stream([{"role": "user", "content": "oi"}], [], 5.0, lambda _t: None)
    assert recebido["api_key"] == "sk-ant-x"


def test_importar_o_adaptador_desliga_a_busca_de_env_do_litellm() -> None:
    import leia_api.llm  # noqa: F401

    assert os.environ["LITELLM_MODE"] == "PRODUCTION"


def test_modelos_do_hugging_face_recebem_o_token_do_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sentence_transformers

    from leia_api import modelos

    vistos: dict[str, Any] = {}

    class _Falso:
        def __init__(self, nome: str, **kwargs: Any) -> None:
            vistos[nome] = kwargs.get("token")

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", _Falso)
    monkeypatch.setattr(sentence_transformers, "CrossEncoder", _Falso)
    monkeypatch.setattr(settings, "hf_token", SecretStr("hf-x"))

    modelos.EncoderST("enc")
    modelos.CrossEncoderReranker("rer")

    assert vistos == {"enc": "hf-x", "rer": "hf-x"}

    monkeypatch.setattr(settings, "hf_token", None)
    modelos.CrossEncoderReranker("sem")
    assert vistos["sem"] is None  # sem token: acesso anônimo, como antes


def test_aquecer_sem_a_chave_falha_na_subida(monkeypatch: pytest.MonkeyPatch) -> None:
    from leia_api import llm

    monkeypatch.setattr(llm, "aquecer", lambda: None)
    monkeypatch.setattr(settings, "modo_teste", False)
    monkeypatch.setattr(settings, "leia_model", "anthropic/claude-haiku-5-5")
    monkeypatch.setattr(settings, "anthropic_api_key", None)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        dependencias.aquecer_llm()


def test_aquecer_com_a_chave_sobe(monkeypatch: pytest.MonkeyPatch) -> None:
    from leia_api import llm

    vistas: list[str] = []
    monkeypatch.setattr(llm, "aquecer", lambda: vistas.append("import"))
    monkeypatch.setattr(settings, "modo_teste", False)
    monkeypatch.setattr(settings, "leia_model", "anthropic/claude-haiku-5-5")
    monkeypatch.setattr(settings, "anthropic_api_key", SecretStr("sk-ant-x"))

    dependencias.aquecer_llm()

    assert vistas == ["import"]

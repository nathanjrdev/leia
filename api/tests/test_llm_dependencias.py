"""Regressão: o caminho de `litellm.completion(tools=...)` precisa das dependências instaladas.

Os testes do agente usam um LLM falso e nunca passam por aqui; sem este teste, remover `mcp`
(que o litellm importa só em tempo de execução, ao receber `tools`) quebra toda chamada real.
"""

import importlib


def test_caminho_de_ferramentas_do_litellm_importa() -> None:
    importlib.import_module("litellm.responses.mcp.chat_completions_handler")

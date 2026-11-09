"""Adaptador LiteLLM do agente (a única porta de saída para um provedor de LLM).

O resto do código recebe um `CallLLM` por injeção e é testado com um falso; este módulo fica
fora da cobertura, como os adaptadores de modelos do Hugging Face. O modelo vem de
`settings.leia_model` (LEIA_MODEL), então trocar de provedor não muda código.
"""

from typing import Any

from leia_api.agente import (
    CallLLM,
    ChamadaFerramenta,
    Mensagem,
    RespostaLLM,
    Uso,
    parse_argumentos,
)
from leia_api.config import settings


class ClienteLiteLLM:
    def __init__(self, modelo: str = settings.leia_model) -> None:
        self._modelo = modelo

    def completar(
        self, mensagens: list[Mensagem], ferramentas: list[dict[str, Any]], timeout: float
    ) -> RespostaLLM:
        import litellm
        from litellm.exceptions import Timeout

        try:
            resposta = litellm.completion(
                model=self._modelo,
                messages=mensagens,
                tools=ferramentas,
                timeout=timeout,
            )
        except Timeout as erro:
            raise TimeoutError(str(erro)) from erro
        msg = resposta.choices[0].message
        chamadas = [
            ChamadaFerramenta(
                id=str(c.id),
                nome=str(c.function.name),
                argumentos=parse_argumentos(c.function.arguments),
            )
            for c in (msg.tool_calls or [])
        ]
        usage = getattr(resposta, "usage", None)
        uso = (
            Uso(
                tokens_entrada=int(getattr(usage, "prompt_tokens", 0) or 0),
                tokens_saida=int(getattr(usage, "completion_tokens", 0) or 0),
            )
            if usage is not None
            else None
        )
        return RespostaLLM(texto=msg.content, chamadas=chamadas, uso=uso)


def cliente_padrao() -> CallLLM:
    return ClienteLiteLLM()

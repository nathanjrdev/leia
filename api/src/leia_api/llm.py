"""Adaptador LiteLLM do agente (a única porta de saída para um provedor de LLM).

O resto do código recebe um `CallLLM` por injeção e é testado com um falso; este módulo fica
fora da cobertura, como os adaptadores de modelos do Hugging Face. O modelo vem de
`settings.leia_model` (LEIA_MODEL), então trocar de provedor não muda código.
"""

import os
from collections.abc import Callable
from typing import Any

# Em modo DEV (o padrão) o LiteLLM procura um .env subindo pelas pastas ao ser importado. A
# chave aqui é explícita (vem do Settings), então essa busca só esconderia erro de configuração.
os.environ.setdefault("LITELLM_MODE", "PRODUCTION")

from leia_api.agente import (  # noqa: E402 - o modo do LiteLLM tem de vir antes de qualquer import dele
    CallLLM,
    ChamadaFerramenta,
    Mensagem,
    RespostaLLM,
    Uso,
    parse_argumentos,
)
from leia_api.config import settings  # noqa: E402


class ClienteLiteLLM:
    """`chave` vai em cada chamada (`api_key`); None deixa o LiteLLM decidir (modelo local)."""

    def __init__(self, modelo: str | None = None, chave: str | None = None) -> None:
        self._modelo = modelo or settings.leia_model
        self._chave = chave

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
                api_key=self._chave,
            )
        except Timeout as erro:
            raise TimeoutError(str(erro)) from erro
        return _converter(resposta)

    def completar_stream(
        self,
        mensagens: list[Mensagem],
        ferramentas: list[dict[str, Any]],
        timeout: float,
        ao_texto: Callable[[str], None],
    ) -> RespostaLLM:
        """Como `completar`, mas entrega cada pedaço de texto a `ao_texto` enquanto chega.

        Devolve a resposta inteira, remontada dos pedaços (texto, tool calls e tokens), para o
        agente decidir exatamente como no caminho sem streaming.
        """
        import litellm
        from litellm.exceptions import Timeout

        # Ao remontar os pedaços, o litellm tenta estimar custo com o nome do modelo sem o
        # provedor e imprime "Provider List" a cada turno (erro interno, tratado por ele).
        litellm.suppress_debug_info = True
        pedacos: list[Any] = []
        try:
            fluxo = litellm.completion(
                model=self._modelo,
                messages=mensagens,
                tools=ferramentas,
                timeout=timeout,
                api_key=self._chave,
                stream=True,
                stream_options={"include_usage": True},
            )
            for pedaco in fluxo:
                pedacos.append(pedaco)
                escolhas = getattr(pedaco, "choices", None) or []
                delta = getattr(escolhas[0], "delta", None) if escolhas else None
                if delta is not None and getattr(delta, "content", None):
                    ao_texto(str(delta.content))
        except Timeout as erro:
            raise TimeoutError(str(erro)) from erro
        completa = litellm.stream_chunk_builder(pedacos, messages=mensagens) if pedacos else None
        if completa is None:  # o provedor fechou o fluxo sem mandar nada
            return RespostaLLM(texto=None, chamadas=[])
        return _converter(completa)


def _converter(resposta: Any) -> RespostaLLM:
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


def aquecer() -> None:
    """Importa o litellm na subida (~10-13 s no Windows). Não chama o provedor: não gasta cota."""
    import litellm  # noqa: F401


def cliente_padrao() -> CallLLM:
    """Cliente do `LEIA_MODEL` com a chave do Settings (falha claro se ela faltar)."""
    return ClienteLiteLLM(settings.leia_model, settings.exigir_chave_do_modelo())

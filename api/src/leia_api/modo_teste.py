"""Modo de teste (E2E): LLM e encoder falsos, sem rede, sem chave, sem modelos de ML.

Ligado só por `MODO_TESTE=true` (ver `dependencias.py`). O LLM de teste segue regras fixas,
mas dirige o agente de verdade: o grafo, as ferramentas, o grounding, a confirmação por clique e
o banco são os reais. Não mede qualidade do modelo; isso é a suíte de avaliação (`evals/`).

Uso da carga sem embeddings (em api/): uv run python -m leia_api.modo_teste
"""

import itertools
import json
import re
from collections.abc import Sequence
from typing import Any

from leia_api.agente import ChamadaFerramenta, RespostaLLM
from leia_api.canal import TEXTO_CLIQUE, TEXTO_CLIQUE_CANCELAR, TEXTO_CLIQUE_FALHA

_ids = itertools.count(1)
_VERBOS_DE_PEDIDO = {"quero", "locar", "alugar", "pegar", "um", "uma", "o", "a", "livro", "sobre"}


class EncoderDeTeste:
    """Vetores de zeros: a busca textual (tsvector) responde; a semântica fica vazia."""

    def encode(self, textos: list[str]) -> Sequence[Sequence[float]]:
        return [[0.0] * 768 for _ in textos]


def _fala(texto: str) -> RespostaLLM:
    return RespostaLLM(texto=texto, chamadas=[])


def _chama(nome: str, **argumentos: Any) -> RespostaLLM:
    chamada = ChamadaFerramenta(f"teste{next(_ids)}", nome, dict(argumentos))
    return RespostaLLM(texto=None, chamadas=[chamada])


def _palavras(texto: str) -> list[str]:
    return re.findall(r"\w+", texto, flags=re.UNICODE)


def _quer_locar(texto: str) -> bool:
    return any(p.lower() in {"locar", "alugar"} for p in _palavras(texto))


def _consulta(texto: str) -> str:
    uteis = [p for p in _palavras(texto) if p.lower() not in _VERBOS_DE_PEDIDO]
    return " ".join(uteis) or texto


def _ultima_fala_do_leitor(mensagens: list[dict[str, Any]]) -> str:
    for m in reversed(mensagens):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            return str(m["content"])
    return ""


class LLMDeTeste:
    """Regras: pedido do leitor → busca → (locar, se pediu) → resposta com o título achado."""

    def completar(
        self, mensagens: list[dict[str, Any]], ferramentas: list[dict[str, Any]], timeout: float
    ) -> RespostaLLM:
        ultima = mensagens[-1]
        if ultima.get("role") == "tool":
            return self._depois_da_ferramenta(mensagens, json.loads(ultima["content"]))
        texto = str(ultima.get("content") or "")
        if texto == TEXTO_CLIQUE:
            return _fala("Locação concluída. Boa leitura!")
        if texto == TEXTO_CLIQUE_CANCELAR:
            return _fala("Tudo bem, cancelei. Posso ajudar com outro livro?")
        if texto == TEXTO_CLIQUE_FALHA:
            return _fala("Não consegui concluir a ação. Quer tentar de novo?")
        return _chama("buscar_livros", consulta=_consulta(texto), limite=3)

    def _depois_da_ferramenta(
        self, mensagens: list[dict[str, Any]], dados: dict[str, Any]
    ) -> RespostaLLM:
        if dados.get("status") == "aguardando_confirmacao":
            return _fala(f"Preparei a ação. Confirme no botão: {dados['resumo']}")
        if "resultados" in dados:
            achados = dados["resultados"]
            if not achados:
                return _fala("Não encontrei esse livro no acervo.")
            primeiro = achados[0]
            if _quer_locar(_ultima_fala_do_leitor(mensagens)):
                return _chama("locar", livro_id=primeiro["livro_id"])
            return _fala(f"Encontrei “{primeiro['titulo']}”. Quer locar?")
        if dados.get("ok") is False:
            return _fala("Não foi possível concluir essa ação agora.")
        return _fala("Pronto.")


def main() -> None:
    """Migra e carrega o catálogo de data/catalogo.json sem gerar embeddings (CI do E2E)."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from leia_api.config import settings
    from leia_api.seed import carregar_catalogo_json

    command.upgrade(Config("alembic.ini"), "head")
    with Session(create_engine(settings.database_url)) as session:
        print(f"Livros novos: {carregar_catalogo_json(session)}")
        session.commit()


if __name__ == "__main__":
    main()

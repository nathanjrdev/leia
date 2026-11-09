"""Agente da Léia: grafo LangGraph modelo → ferramentas → resposta, com guardrails.

O LLM só escolhe ferramentas; quem executa é `ferramentas.executar` (que valida, injeta o
`usuario_id` da sessão e nunca escreve sem confirmação). O cliente LLM é injetável (`CallLLM`),
então os testes rodam com um falso, sem rede nem chave.

Guardrails deste módulo:
- limite de chamadas de ferramenta por turno e prazo total do turno, com erro amigável;
- grounding pós-resposta: todo título entre aspas precisa ter sido devolvido por alguma
  ferramenta na conversa; senão regenera (até `max_regeracoes`) ou devolve resposta segura;
- o histórico aceito do chamador só tem papéis `user`/`assistant` (ninguém injeta `system`/`tool`);
- as propostas de escrita pendentes voltam ao chamador para ele renderizar o botão Confirmar;
- o clique do leitor chega como `EventoApp` no bloco de sistema do turno, nunca como fala; texto
  do leitor que imita o aplicativo é neutralizado e o turno ganha um aviso (ver `canal.py`).
"""

import json
import re
import time
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from leia_api.canal import (
    TEXTO_CLIQUE,
    EventoApp,
    bloco_do_sistema,
    detectar_imitacao,
    neutralizar,
)
from leia_api.config import Settings, settings
from leia_api.ferramentas import ESPECIFICACOES, ContextoFerramentas, executar
from leia_api.models import Livro

Mensagem = dict[str, Any]

MSG_TIMEOUT = "Estou demorando mais do que o normal. Pode tentar de novo em instantes?"
MSG_ERRO_LLM = "Tive um problema para responder agora. Pode tentar de novo em instantes?"
MSG_LIMITE = (
    "Precisei de consultas demais para responder a isso. "
    "Pode me pedir algo mais específico, um passo de cada vez?"
)
MSG_GROUNDING = (
    "Não consegui confirmar no acervo os livros que eu ia mencionar, então prefiro não citá-los. "
    "Pode reformular o pedido ou me dar mais detalhes para eu buscar de novo?"
)
MSG_VAZIA = "Não consegui formular uma resposta. Pode repetir o pedido de outro jeito?"

_VERSAO_PROMPT = re.compile(r"^v\d+$")
_TRECHO_ENTRE_ASPAS = re.compile(r"“([^”]{1,200})”|\"([^\"]{1,200})\"|«([^»]{1,200})»")
_MAX_PALAVRAS_TITULO = 10


def carregar_prompt(versao: str) -> str:
    """Lê `prompts/sistema_<versao>.md`. A versão é validada: nada de caminhos arbitrários."""
    if not _VERSAO_PROMPT.fullmatch(versao):
        raise ValueError(f"Versão de prompt inválida: {versao!r}")
    arquivo = resources.files("leia_api").joinpath("prompts", f"sistema_{versao}.md")
    if not arquivo.is_file():
        raise FileNotFoundError(f"Prompt não encontrado: sistema_{versao}.md")
    return arquivo.read_text(encoding="utf-8").strip()


def parse_argumentos(bruto: str | dict[str, Any] | None) -> dict[str, Any]:
    """Argumentos de tool call do LLM. O que não for objeto JSON vira marcador inválido."""
    if isinstance(bruto, dict):
        return bruto
    if bruto is None or not bruto.strip():
        return {}
    try:
        valor = json.loads(bruto)
    except json.JSONDecodeError:
        return {"_argumentos_ilegiveis": True}
    return valor if isinstance(valor, dict) else {"_argumentos_ilegiveis": True}


def _normalizar(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return " ".join(sem_acento.casefold().split())


def titulos_sem_origem(texto: str, permitidos: set[str]) -> list[str]:
    """Trechos entre aspas que não correspondem a nenhum título devolvido por ferramenta.

    Convenção do prompt: título de livro vai entre aspas curvas e nada mais. Frases longas
    entre aspas (citações) e trechos vazios são ignorados. Aceita título truncado antes do
    subtítulo ("Vidas Secas" para "Vidas Secas: romance"). Limitação conhecida: um título
    citado sem aspas não é visto; a suíte de avaliação (Fase 7) mede esse caso.
    """
    conhecidos = {_normalizar(t) for t in permitidos}
    sem_origem: list[str] = []
    for achado in _TRECHO_ENTRE_ASPAS.finditer(texto):
        trecho = next(g for g in achado.groups() if g is not None).strip()
        n = _normalizar(trecho)
        if not n or len(n.split()) > _MAX_PALAVRAS_TITULO:
            continue
        if n in conhecidos or (len(n) >= 3 and any(n in c for c in conhecidos)):
            continue
        sem_origem.append(trecho)
    return sem_origem


@dataclass(frozen=True)
class ChamadaFerramenta:
    id: str
    nome: str
    argumentos: dict[str, Any]


@dataclass(frozen=True)
class RespostaLLM:
    texto: str | None
    chamadas: list[ChamadaFerramenta]


class CallLLM(Protocol):
    def completar(
        self, mensagens: list[Mensagem], ferramentas: list[dict[str, Any]], timeout: float
    ) -> RespostaLLM:
        """Uma chamada ao modelo. Deve levantar `TimeoutError` quando estourar `timeout`."""
        ...


@dataclass(frozen=True)
class ConfigAgente:
    prompt: str
    max_chamadas_ferramenta: int
    timeout_chamada: float
    timeout_turno: float
    max_regeracoes: int

    @classmethod
    def da_config(cls, config: Settings = settings) -> "ConfigAgente":
        return cls(
            prompt=carregar_prompt(config.prompt_versao),
            max_chamadas_ferramenta=config.max_chamadas_ferramenta_por_turno,
            timeout_chamada=config.llm_timeout_segundos,
            timeout_turno=config.turno_timeout_segundos,
            max_regeracoes=config.max_regeracoes_grounding,
        )


@dataclass(frozen=True)
class Proposta:
    confirmacao_id: str
    resumo: str


@dataclass(frozen=True)
class ChamadaAuditada:
    """Registro de uma chamada de ferramenta para a trilha de auditoria (`chamadas_ferramenta`)."""

    nome: str
    argumentos: dict[str, Any]
    resultado: dict[str, Any]
    latencia_ms: int


@dataclass(frozen=True)
class RespostaAgente:
    texto: str
    propostas: list[Proposta]
    historico: list[Mensagem]  # só user/assistant, para o próximo turno
    erro: str | None = None  # timeout | erro_llm | limite_chamadas | grounding | resposta_vazia
    chamadas_ferramenta: int = 0
    auditoria: list[ChamadaAuditada] = field(default_factory=list)


class _Estado(TypedDict):
    ctx: ContextoFerramentas
    mensagens: list[Mensagem]
    inicio: float
    n_chamadas: int
    regeracoes: int
    ultima: RespostaLLM | None
    texto: str | None
    erro: str | None
    propostas: list[Proposta]
    observador: Callable[[str, dict[str, Any]], None] | None
    auditoria: list[ChamadaAuditada]


def _exigir(ultima: RespostaLLM | None) -> RespostaLLM:
    if ultima is None:  # invariante do grafo: o nó modelo sempre roda antes
        raise RuntimeError("estado do agente sem resposta do modelo")
    return ultima


def _titulos_vistos(ctx: ContextoFerramentas) -> set[str]:
    if not ctx.livros_vistos:
        return set()
    achados = ctx.session.scalars(select(Livro.titulo).where(Livro.id.in_(ctx.livros_vistos)))
    return set(achados)


class Agente:
    def __init__(
        self,
        llm: CallLLM,
        config: ConfigAgente,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._llm = llm
        self._config = config
        self._relogio = relogio
        self._grafo = self._montar()

    # ---------- nós ----------

    def _modelo(self, e: _Estado) -> dict[str, Any]:
        if self._relogio() - e["inicio"] > self._config.timeout_turno:
            return {"texto": MSG_TIMEOUT, "erro": "timeout"}
        try:
            resposta = self._llm.completar(
                e["mensagens"], ESPECIFICACOES, self._config.timeout_chamada
            )
        except TimeoutError:
            return {"texto": MSG_TIMEOUT, "erro": "timeout"}
        except Exception:  # noqa: BLE001 - detalhes do provedor não chegam ao usuário
            return {"texto": MSG_ERRO_LLM, "erro": "erro_llm"}
        if resposta.chamadas:
            registro: Mensagem = {
                "role": "assistant",
                "content": resposta.texto,
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.nome, "arguments": json.dumps(c.argumentos)},
                    }
                    for c in resposta.chamadas
                ],
            }
        else:
            registro = {"role": "assistant", "content": resposta.texto or ""}
        return {"ultima": resposta, "mensagens": [*e["mensagens"], registro]}

    def _depois_do_modelo(self, e: _Estado) -> str:
        if e["erro"] is not None:
            return "fim"
        ultima = e["ultima"]
        ultima = _exigir(ultima)
        if not ultima.chamadas:
            return "grounding"
        if e["n_chamadas"] + len(ultima.chamadas) > self._config.max_chamadas_ferramenta:
            return "limite"
        return "ferramentas"

    def _limite(self, e: _Estado) -> dict[str, Any]:
        return {"texto": MSG_LIMITE, "erro": "limite_chamadas"}

    def _ferramentas(self, e: _Estado) -> dict[str, Any]:
        ultima = e["ultima"]
        ultima = _exigir(ultima)
        mensagens = list(e["mensagens"])
        propostas = list(e["propostas"])
        auditoria = list(e["auditoria"])
        for chamada in ultima.chamadas:
            if e["observador"] is not None:
                e["observador"]("ferramenta", {"nome": chamada.nome})
            inicio = time.perf_counter()
            resultado = executar(e["ctx"], chamada.nome, chamada.argumentos)
            auditoria.append(
                ChamadaAuditada(
                    nome=chamada.nome,
                    argumentos=chamada.argumentos,
                    resultado=resultado,
                    latencia_ms=int((time.perf_counter() - inicio) * 1000),
                )
            )
            if resultado.get("status") == "aguardando_confirmacao":
                proposta = Proposta(resultado["confirmacao_id"], resultado["resumo"])
                if proposta not in propostas:
                    propostas.append(proposta)
            mensagens.append(
                {
                    "role": "tool",
                    "tool_call_id": chamada.id,
                    "content": json.dumps(resultado, ensure_ascii=False),
                }
            )
        return {
            "mensagens": mensagens,
            "propostas": propostas,
            "auditoria": auditoria,
            "n_chamadas": e["n_chamadas"] + len(ultima.chamadas),
        }

    def _grounding(self, e: _Estado) -> dict[str, Any]:
        ultima = e["ultima"]
        ultima = _exigir(ultima)
        texto = (ultima.texto or "").strip()
        if not texto:
            return {"texto": MSG_VAZIA, "erro": "resposta_vazia"}
        sem_origem = titulos_sem_origem(texto, _titulos_vistos(e["ctx"]))
        if not sem_origem:
            return {"texto": texto}
        if e["regeracoes"] < self._config.max_regeracoes:
            citados = ", ".join(f"“{t}”" for t in sem_origem)
            correcao: Mensagem = {
                "role": "user",
                "content": (
                    f"[Verificação automática] Sua resposta citou títulos que nenhuma ferramenta "
                    f"retornou: {citados}. Reescreva a resposta citando apenas livros devolvidos "
                    "pelas ferramentas nesta conversa; se for preciso, use as ferramentas."
                ),
            }
            return {
                "mensagens": [*e["mensagens"], correcao],
                "regeracoes": e["regeracoes"] + 1,
                "texto": None,
            }
        return {"texto": MSG_GROUNDING, "erro": "grounding"}

    def _depois_do_grounding(self, e: _Estado) -> str:
        return "modelo" if e["texto"] is None else "fim"

    def _montar(self) -> Any:
        # Any: os stubs do langgraph não aceitam TypedDict local como NodeInputT (mypy strict).
        g: Any = StateGraph(_Estado)
        g.add_node("modelo", self._modelo)
        g.add_node("ferramentas", self._ferramentas)
        g.add_node("limite", self._limite)
        g.add_node("grounding", self._grounding)
        g.add_edge(START, "modelo")
        g.add_conditional_edges(
            "modelo",
            self._depois_do_modelo,
            {
                "fim": END,
                "grounding": "grounding",
                "limite": "limite",
                "ferramentas": "ferramentas",
            },
        )
        g.add_edge("ferramentas", "modelo")
        g.add_edge("limite", END)
        g.add_conditional_edges(
            "grounding", self._depois_do_grounding, {"modelo": "modelo", "fim": END}
        )
        return g.compile()

    # ---------- API ----------

    def responder(
        self,
        ctx: ContextoFerramentas,
        historico: list[Mensagem],
        mensagem: str | None,
        eventos: Sequence[EventoApp] = (),
        observador: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> RespostaAgente:
        """Um turno. `historico` é o devolvido pelo turno anterior; só user/assistant é aceito.

        `mensagem` é o que o leitor digitou (`None` num turno disparado só por clique). `eventos`
        são fatos do aplicativo criados pelo servidor, como o resultado de um clique; só entram
        pelo bloco de sistema. Todo texto de leitor passa por `neutralizar`. `observador`, se
        dado, é avisado de cada ferramenta que vai rodar (alimenta o stream da API).
        """
        if mensagem is None and not eventos:
            raise ValueError("o turno precisa de uma fala do leitor ou de um evento do aplicativo")
        imitacao = bool(mensagem) and detectar_imitacao(str(mensagem))
        imitacao = imitacao or any(
            detectar_imitacao(str(m.get("content") or ""))
            for m in historico
            if m.get("role") == "user"
        )
        limpo: list[Mensagem] = [
            {
                "role": m["role"],
                "content": (
                    neutralizar(str(m.get("content") or ""))
                    if m["role"] == "user"
                    else str(m.get("content") or "")
                ),
            }
            for m in historico
            if m.get("role") in ("user", "assistant")
        ]
        texto_usuario = TEXTO_CLIQUE if mensagem is None else neutralizar(mensagem)
        usuario: Mensagem = {"role": "user", "content": texto_usuario}
        bloco = bloco_do_sistema(tuple(eventos), imitacao=imitacao)
        sistema = f"{self._config.prompt}\n\n{bloco}" if bloco else self._config.prompt
        inicial: _Estado = {
            "ctx": ctx,
            "mensagens": [{"role": "system", "content": sistema}, *limpo, usuario],
            "inicio": self._relogio(),
            "n_chamadas": 0,
            "regeracoes": 0,
            "ultima": None,
            "texto": None,
            "erro": None,
            "propostas": [],
            "observador": observador,
            "auditoria": [],
        }
        passos = 4 * (self._config.max_chamadas_ferramenta + self._config.max_regeracoes + 3)
        final: _Estado = self._grafo.invoke(inicial, {"recursion_limit": passos + 10})
        texto = final["texto"] or MSG_VAZIA
        return RespostaAgente(
            texto=texto,
            propostas=final["propostas"],
            historico=[*limpo, usuario, {"role": "assistant", "content": texto}],
            erro=final["erro"],
            chamadas_ferramenta=final["n_chamadas"],
            auditoria=final["auditoria"],
        )

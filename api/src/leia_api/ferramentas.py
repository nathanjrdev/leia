"""Ferramentas tipadas do agente: o que o LLM enxerga e o único caminho dele até o banco.

Garantias (CLAUDE.md):
- o LLM nunca escreve SQL nem decide regra: escolhe uma ferramenta e argumentos; o serviço valida;
- `usuario_id` vem do contexto (sessão), nunca de argumento: os schemas proíbem campos extras;
- ferramentas de escrita (locar, renovar, devolver, reservar) NÃO executam quando o LLM as chama:
  registram uma ação pendente e devolvem `aguardando_confirmacao`. Só `confirmar_acao`, chamado
  pela camada de API quando o usuário clica em "Confirmar" (nunca exposto ao LLM), executa;
- ids de livros devolvidos por ferramenta entram em `livros_vistos`, base do grounding.

Toda saída é um dict JSON-serializável; erros de negócio viram `{"ok": False, "erro": codigo}`.
"""

import logging
import secrets
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field, is_dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from leia_api import catalogo, locacao
from leia_api.busca import Reranker, buscar_livros
from leia_api.config import settings
from leia_api.embeddings import Encoder
from leia_api.locacao import ErroLocacao, RegrasLocacao

Resultado = dict[str, Any]

log = logging.getLogger(__name__)

INT32_MAX = 2**31 - 1
ID = Annotated[int, Field(ge=1, le=INT32_MAX)]
_MENSAGEM_INTERNA = "Não foi possível concluir agora."


class _Args(BaseModel):
    # Extra proibido: `usuario_id` inventado pelo LLM é erro, não é ignorado.
    # Estrito: nada de "5" virando 5 nem "true" virando True.
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class BuscarLivrosArgs(_Args):
    consulta: str = Field(min_length=1, max_length=300, description="O que o leitor procura.")
    categoria: str | None = Field(
        default=None,
        max_length=60,
        pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
        description="Slug da categoria (ex.: poesia).",
    )
    ano_min: int | None = Field(
        default=None, ge=1000, le=2100, description="Ano de publicação mínimo."
    )
    ano_max: int | None = Field(
        default=None, ge=1000, le=2100, description="Ano de publicação máximo."
    )
    apenas_disponiveis: bool = Field(default=False, description="Só livros com exemplar livre.")
    limite: int = Field(default=5, ge=1, le=settings.busca_limite_maximo)

    @model_validator(mode="after")
    def _anos_coerentes(self) -> "BuscarLivrosArgs":
        if self.ano_min is not None and self.ano_max is not None and self.ano_min > self.ano_max:
            raise ValueError("ano_min maior que ano_max")
        return self


class LivroArgs(_Args):
    livro_id: ID = Field(description="ID do livro, como devolvido por buscar_livros.")


class SemArgs(_Args):
    pass


class LocacaoArgs(_Args):
    locacao_id: ID = Field(description="ID da locação, como devolvido por minhas_locacoes.")


@dataclass
class AcaoPendente:
    usuario_id: int
    ferramenta: str
    argumentos: dict[str, Any]
    resumo: str
    criada_em: datetime


@dataclass
class ContextoFerramentas:
    """Estado de um turno/sessão. `usuario_id` é injetado pela API a partir da sessão."""

    session: Session
    usuario_id: int
    encoder: Encoder
    reranker: Reranker | None
    regras: RegrasLocacao
    agora: datetime | None = None
    # ids de livros devolvidos por ferramentas nesta conversa (grounding)
    livros_vistos: set[int] = field(default_factory=set)
    # cartões de livro do turno (dados do banco, com capa_url que o LLM não vê); a API os mostra
    # só para os livros que a resposta cita
    cartoes: dict[int, dict[str, Any]] = field(default_factory=dict)
    # ações de escrita aguardando o clique do usuário; a API deve persistir/escopar por conversa
    # Pendência (Fase 6): não são invalidadas por turno; a API deve escopar por conversa.
    pendentes: dict[str, AcaoPendente] = field(default_factory=dict)
    pendente_ttl_segundos: int = settings.pendente_ttl_segundos
    max_pendentes: int = settings.max_pendentes_por_usuario

    def agora_efetivo(self) -> datetime:
        return self.agora if self.agora is not None else datetime.now(UTC)


def _json(valor: Any) -> Any:
    if isinstance(valor, datetime):
        return valor.isoformat()
    if is_dataclass(valor) and not isinstance(valor, type):
        return {k: _json(getattr(valor, k)) for k in valor.__dataclass_fields__}
    if isinstance(valor, list | tuple):
        return [_json(v) for v in valor]
    if isinstance(valor, dict):
        return {k: _json(v) for k, v in valor.items()}
    return valor


def _erro(codigo: str, mensagem: str) -> Resultado:
    return {"ok": False, "erro": codigo, "mensagem": mensagem}


# ---------- leitura ----------


def _cartao(
    livro_id: int, titulo: str, autores: list[str], capa_url: str | None, livres: int
) -> dict[str, Any]:
    return {
        "id": livro_id,
        "titulo": titulo,
        "autores": list(autores),
        "capa_url": capa_url,
        "livres": livres,
    }


def _buscar(ctx: ContextoFerramentas, a: BuscarLivrosArgs) -> Resultado:
    achados = buscar_livros(
        ctx.session,
        a.consulta,
        ctx.encoder,
        limite=a.limite,
        categoria=a.categoria,
        ano_min=a.ano_min,
        ano_max=a.ano_max,
        apenas_disponiveis=a.apenas_disponiveis,
        reranker=ctx.reranker,  # decisão: o agente busca com o reranker (modo fundido)
    )
    ctx.livros_vistos.update(r.livro_id for r in achados)
    for r in achados:
        ctx.cartoes[r.livro_id] = _cartao(r.livro_id, r.titulo, r.autores, r.capa_url, r.livres)
    resultados = _json(achados)
    for r in resultados:
        r.pop("capa_url", None)  # URL externa: inútil ao LLM e vetor de injeção
    return {"ok": True, "resultados": resultados}


def _sinopse_segura(texto: str | None) -> str | None:
    """Sinopse é dado externo: sem caracteres de controle e truncada."""
    if texto is None:
        return None
    limpo = "".join(
        (" " if c in "\n\r\t" else c)
        for c in texto
        if c in "\n\r\t" or unicodedata.category(c) != "Cc"
    )
    return limpo[: settings.sinopse_max_caracteres]


def _detalhar(ctx: ContextoFerramentas, a: LivroArgs) -> Resultado:
    ficha = catalogo.detalhar_livro(ctx.session, a.livro_id)
    ctx.livros_vistos.add(ficha.livro_id)
    ctx.cartoes[ficha.livro_id] = _cartao(
        ficha.livro_id,
        ficha.titulo,
        ficha.autores,
        ficha.capa_url,
        ficha.disponibilidade.livres,
    )
    corpo = _json(ficha)
    disp = corpo.pop("disponibilidade")
    corpo.update(exemplares=disp["total"], livres=disp["livres"], fila=disp["fila"])
    corpo.pop("capa_url")
    corpo.pop("editora")
    # O LLM deve tratar este campo como texto citado, nunca como instrução.
    corpo["sinopse_nao_confiavel"] = _sinopse_segura(corpo.pop("sinopse"))
    return {"ok": True, "livro": corpo}


def _disponibilidade(ctx: ContextoFerramentas, a: LivroArgs) -> Resultado:
    disp = catalogo.verificar_disponibilidade(ctx.session, a.livro_id)
    ctx.livros_vistos.add(disp.livro_id)
    return {"ok": True, **_json(disp)}


def _minhas_locacoes(ctx: ContextoFerramentas, _: SemArgs) -> Resultado:
    meu = locacao.minhas_locacoes(ctx.session, ctx.usuario_id, ctx.agora)
    ctx.livros_vistos.update(lo.livro_id for lo in [*meu.ativas, *meu.historico])
    ctx.livros_vistos.update(r.livro_id for r in meu.reservas)
    corpo = _json(meu)
    for reserva in corpo["reservas"]:
        # Campos da tela (prazo de retirada) ainda não são expostos ao LLM: a saída da ferramenta
        # fica idêntica à que a suíte de avaliação mediu. Expor exige o gate do leia-prompt.
        reserva.pop("pronta", None)
        reserva.pop("retirar_ate", None)
    return {"ok": True, **corpo}


# ---------- escrita: só propõe; a execução é `confirmar_acao` ----------


def _resumo_livro(ctx: ContextoFerramentas, verbo: str, livro_id: int) -> str:
    ficha = catalogo.detalhar_livro(ctx.session, livro_id)
    return f"{verbo} “{ficha.titulo}”"


def _resumo_locacao(ctx: ContextoFerramentas, verbo: str, locacao_id: int) -> str:
    ativas = locacao.minhas_locacoes(ctx.session, ctx.usuario_id, ctx.agora).ativas
    alvo = next((lo for lo in ativas if lo.locacao_id == locacao_id), None)
    if alvo is None:
        raise ErroLocacao("locacao_inexistente", "Locação não encontrada.")
    return f"{verbo} “{alvo.titulo}”"


def _propor(
    ctx: ContextoFerramentas, ferramenta: str, argumentos: dict[str, Any], resumo: str
) -> Resultado:
    agora = ctx.agora_efetivo()
    _expirar(ctx, agora)
    do_usuario = {t: p for t, p in ctx.pendentes.items() if p.usuario_id == ctx.usuario_id}
    token = next(
        (
            t
            for t, p in do_usuario.items()
            if (p.ferramenta, p.argumentos) == (ferramenta, argumentos)
        ),
        None,
    )
    if token is None:
        if len(do_usuario) >= ctx.max_pendentes:
            return _erro(
                "muitas_pendencias",
                "Há ações demais aguardando confirmação: confirme ou cancele alguma antes.",
            )
        token = secrets.token_urlsafe(16)
        ctx.pendentes[token] = AcaoPendente(ctx.usuario_id, ferramenta, argumentos, resumo, agora)
    return {
        "ok": True,
        "status": "aguardando_confirmacao",
        "confirmacao_id": token,
        "resumo": resumo,
        "instrucao": "Nada foi feito ainda. Peça ao usuário que confirme; não diga que concluiu.",
    }


def _expirar(ctx: ContextoFerramentas, agora: datetime) -> None:
    limite = timedelta(seconds=ctx.pendente_ttl_segundos)
    for token in [t for t, p in ctx.pendentes.items() if agora - p.criada_em > limite]:
        del ctx.pendentes[token]


def _exigir_consultado(ctx: ContextoFerramentas, livro_id: int) -> None:
    """Grounding imposto pelo código: só se age sobre livro que uma ferramenta já devolveu."""
    if livro_id not in ctx.livros_vistos:
        raise ErroLocacao(
            "livro_nao_consultado",
            "Consulte o livro (buscar_livros ou detalhar_livro) antes de propor esta ação.",
        )


def _propor_locar(ctx: ContextoFerramentas, a: LivroArgs) -> Resultado:
    _exigir_consultado(ctx, a.livro_id)
    resumo = _resumo_livro(ctx, "Locar", a.livro_id)
    return _propor(ctx, "locar", a.model_dump(), resumo)


def _propor_reservar(ctx: ContextoFerramentas, a: LivroArgs) -> Resultado:
    _exigir_consultado(ctx, a.livro_id)
    resumo = _resumo_livro(ctx, "Entrar na fila de", a.livro_id)
    return _propor(ctx, "reservar", a.model_dump(), resumo)


def _propor_renovar(ctx: ContextoFerramentas, a: LocacaoArgs) -> Resultado:
    resumo = _resumo_locacao(ctx, "Renovar a locação de", a.locacao_id)
    return _propor(ctx, "renovar", a.model_dump(), resumo)


def _propor_devolver(ctx: ContextoFerramentas, a: LocacaoArgs) -> Resultado:
    resumo = _resumo_locacao(ctx, "Devolver", a.locacao_id)
    return _propor(ctx, "devolver", a.model_dump(), resumo)


# ---------- registro ----------


@dataclass(frozen=True)
class _Ferramenta:
    nome: str
    descricao: str
    args: type[_Args]
    funcao: Callable[[ContextoFerramentas, Any], Resultado]


_FERRAMENTAS: tuple[_Ferramenta, ...] = (
    _Ferramenta(
        "buscar_livros",
        "Busca livros do acervo por assunto, título, autor ou tema, em linguagem natural. "
        "Devolve livro_id, título, autores, ano e quantos exemplares estão livres.",
        BuscarLivrosArgs,
        _buscar,
    ),
    _Ferramenta(
        "detalhar_livro",
        "Ficha de um livro: autores, categorias, sinopse, editora, páginas e disponibilidade.",
        LivroArgs,
        _detalhar,
    ),
    _Ferramenta(
        "verificar_disponibilidade",
        "Quantos exemplares de um livro estão livres agora e o tamanho da fila de reservas.",
        LivroArgs,
        _disponibilidade,
    ),
    _Ferramenta(
        "minhas_locacoes",
        "Locações ativas do leitor com prazos e atrasos, reservas na fila e últimas devoluções.",
        SemArgs,
        _minhas_locacoes,
    ),
    _Ferramenta(
        "locar",
        "Propõe locar um livro para o leitor. Não executa: o leitor precisa confirmar no chat.",
        LivroArgs,
        _propor_locar,
    ),
    _Ferramenta(
        "renovar",
        "Propõe renovar uma locação ativa. Não executa: o leitor precisa confirmar no chat.",
        LocacaoArgs,
        _propor_renovar,
    ),
    _Ferramenta(
        "devolver",
        "Propõe devolver uma locação ativa. Não executa: o leitor precisa confirmar no chat.",
        LocacaoArgs,
        _propor_devolver,
    ),
    _Ferramenta(
        "reservar",
        "Propõe entrar na fila de um livro sem exemplar livre. "
        "Não executa: o leitor precisa confirmar no chat.",
        LivroArgs,
        _propor_reservar,
    ),
)
_POR_NOME = {f.nome: f for f in _FERRAMENTAS}


def _especificacao(f: _Ferramenta) -> dict[str, Any]:
    esquema = f.args.model_json_schema()
    esquema.pop("title", None)
    for prop in esquema.get("properties", {}).values():
        prop.pop("title", None)
    return {
        "type": "function",
        "function": {"name": f.nome, "description": f.descricao, "parameters": esquema},
    }


# Formato de function calling do LiteLLM/OpenAI. Nunca contém `usuario_id` nem confirmação.
ESPECIFICACOES: list[dict[str, Any]] = [_especificacao(f) for f in _FERRAMENTAS]


def _falha_interna(ctx: ContextoFerramentas, contexto: str, erro: Exception) -> Resultado:
    """Loga só o tipo da exceção e a ferramenta (nunca argumentos nem a mensagem do driver)."""
    log.error("falha interna em %s: %s", contexto, type(erro).__name__)
    if isinstance(erro, SQLAlchemyError):
        ctx.session.rollback()
    return _erro("erro_interno", _MENSAGEM_INTERNA)


def executar(ctx: ContextoFerramentas, nome: str, argumentos: dict[str, Any]) -> Resultado:
    """Executa uma chamada de ferramenta pedida pelo LLM. Nunca levanta."""
    ferramenta = _POR_NOME.get(nome)
    if ferramenta is None:
        return _erro("ferramenta_desconhecida", f"Ferramenta inexistente: {nome}.")
    try:
        args = ferramenta.args.model_validate(argumentos)
    except ValidationError as erro:
        campos = ", ".join(str(e["loc"][0]) if e["loc"] else "?" for e in erro.errors())
        return _erro("argumentos_invalidos", f"Argumentos inválidos: {campos}.")
    try:
        return ferramenta.funcao(ctx, args)
    except ErroLocacao as erro:
        return _erro(erro.codigo, erro.mensagem)
    except Exception as erro:  # noqa: BLE001 - fronteira com o LLM: nunca propagar
        return _falha_interna(ctx, nome, erro)


# ---------- confirmação (chamada pela API, fora do alcance do LLM) ----------


def _retirar(ctx: ContextoFerramentas, confirmacao_id: str) -> AcaoPendente | None:
    """Retira o token (pop atômico). Se o dono não for o usuário da sessão, devolve e nega."""
    pendente = ctx.pendentes.pop(confirmacao_id, None)
    if pendente is None:
        return None
    if pendente.usuario_id != ctx.usuario_id:
        ctx.pendentes[confirmacao_id] = pendente
        return None
    return pendente


def _executar_pendente(ctx: ContextoFerramentas, pendente: AcaoPendente) -> dict[str, Any]:
    a = pendente.argumentos
    if pendente.ferramenta == "locar":
        corpo = _json(
            locacao.locar(ctx.session, ctx.usuario_id, a["livro_id"], ctx.regras, ctx.agora)
        )
    elif pendente.ferramenta == "renovar":
        corpo = _json(
            locacao.renovar(ctx.session, ctx.usuario_id, a["locacao_id"], ctx.regras, ctx.agora)
        )
    elif pendente.ferramenta == "devolver":
        corpo = _json(locacao.devolver(ctx.session, ctx.usuario_id, a["locacao_id"], ctx.agora))
    else:  # reservar
        corpo = _json(locacao.reservar(ctx.session, ctx.usuario_id, a["livro_id"], ctx.agora))
    return dict(corpo)


def confirmar_acao(ctx: ContextoFerramentas, confirmacao_id: str) -> Resultado:
    """Executa a ação pendente (uso único). Só a API chama, após o clique. Nunca levanta."""
    pendente = _retirar(ctx, confirmacao_id)
    if pendente is None:
        return _erro("confirmacao_inexistente", "Não há ação pendente com esse código.")
    if ctx.agora_efetivo() - pendente.criada_em > timedelta(seconds=ctx.pendente_ttl_segundos):
        return _erro("confirmacao_expirada", "Essa confirmação expirou. Peça de novo se quiser.")
    try:
        corpo = _executar_pendente(ctx, pendente)
    except ErroLocacao as erro:  # erro de regra: o token é consumido
        return _erro(erro.codigo, erro.mensagem)
    except Exception as erro:  # noqa: BLE001
        ctx.pendentes[confirmacao_id] = pendente  # falha inesperada não queima o token
        return _falha_interna(ctx, pendente.ferramenta, erro)
    ctx.livros_vistos.add(corpo["livro_id"])
    return {"ok": True, "acao": pendente.ferramenta, **corpo}


def cancelar_acao(ctx: ContextoFerramentas, confirmacao_id: str) -> Resultado:
    if _retirar(ctx, confirmacao_id) is None:
        return _erro("confirmacao_inexistente", "Não há ação pendente com esse código.")
    return {"ok": True}

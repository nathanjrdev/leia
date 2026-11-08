"""Serviço de locação: locar, renovar, devolver e reservar.

É aqui que moram as regras de negócio. O agente só chama estas funções (via ferramentas
tipadas) e relata o resultado; ele não decide nada. `usuario_id` sempre vem da sessão.

Cada função é uma unidade de trabalho: faz commit ao terminar e rollback ao falhar, de modo
que a `Session` continua utilizável depois de um `ErroLocacao`.

Concorrência:
- o usuário é bloqueado (`FOR UPDATE`) para que duas locações simultâneas dele não furem o limite;
- o exemplar é escolhido com `FOR UPDATE SKIP LOCKED`, então dois leitores nunca disputam o
  mesmo exemplar; o índice único parcial em `locacoes(exemplar_id)` é a última barreira;
- a fila de um livro é serializada bloqueando a linha do livro em `reservar`.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from leia_api.config import Settings, settings
from leia_api.models import Exemplar, Livro, Locacao, Reserva, Usuario


@dataclass(frozen=True)
class RegrasLocacao:
    """Parâmetros de negócio. Vêm da configuração, nunca de constantes no código."""

    max_locacoes: int
    prazo_dias: int
    max_renovacoes: int

    @classmethod
    def da_config(cls, config: Settings = settings) -> "RegrasLocacao":
        return cls(
            max_locacoes=config.max_locacoes_simultaneas,
            prazo_dias=config.prazo_locacao_dias,
            max_renovacoes=config.max_renovacoes,
        )


class ErroLocacao(Exception):
    """Violação de regra de negócio. `codigo` é estável (as ferramentas e a suíte dependem dele)."""

    def __init__(self, codigo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem


@dataclass(frozen=True)
class ResultadoLocacao:
    locacao_id: int
    livro_id: int
    titulo: str
    exemplar_codigo: str
    retirada_em: datetime
    prevista_em: datetime
    renovacoes: int


@dataclass(frozen=True)
class ResultadoDevolucao:
    locacao_id: int
    livro_id: int
    titulo: str
    devolvida_em: datetime
    atraso_dias: int
    fila: int  # reservas ativas esperando este livro


@dataclass(frozen=True)
class ResultadoReserva:
    reserva_id: int
    livro_id: int
    titulo: str
    posicao: int  # lugar real na fila (1 = próximo)


def _agora(agora: datetime | None) -> datetime:
    return agora if agora is not None else datetime.now(UTC)


@contextmanager
def _transacao(session: Session) -> Iterator[None]:
    try:
        yield
        session.commit()
    except BaseException:
        session.rollback()
        raise


def _bloquear_usuario(session: Session, usuario_id: int) -> None:
    achou = session.execute(
        select(Usuario.id).where(Usuario.id == usuario_id).with_for_update()
    ).scalar_one_or_none()
    if achou is None:
        raise ErroLocacao("usuario_inexistente", "Usuário não encontrado.")


def _titulo(session: Session, livro_id: int) -> str:
    titulo = session.execute(select(Livro.titulo).where(Livro.id == livro_id)).scalar_one_or_none()
    if titulo is None:
        raise ErroLocacao("livro_inexistente", "Livro não encontrado no acervo.")
    return titulo


def _fila(session: Session, livro_id: int) -> int:
    return int(
        session.execute(
            select(func.count())
            .select_from(Reserva)
            .where(Reserva.livro_id == livro_id, Reserva.status == "ativa")
        ).scalar_one()
    )


def _livres(session: Session, livro_id: int) -> int:
    return int(
        session.execute(
            text("SELECT livres FROM disponibilidade_livro WHERE livro_id = :l"),
            {"l": livro_id},
        ).scalar_one()
    )


def _locacoes_ativas(session: Session, usuario_id: int) -> list[tuple[datetime, int]]:
    """(prevista_em, livro_id) de cada locação ativa do usuário."""
    linhas = session.execute(
        select(Locacao.prevista_em, Exemplar.livro_id)
        .join(Exemplar, Exemplar.id == Locacao.exemplar_id)
        .where(Locacao.usuario_id == usuario_id, Locacao.devolvida_em.is_(None))
    ).all()
    return [(prevista, livro) for prevista, livro in linhas]


def _resultado(
    locacao: Locacao, exemplar_codigo: str, livro_id: int, titulo: str
) -> ResultadoLocacao:
    return ResultadoLocacao(
        locacao_id=locacao.id,
        livro_id=livro_id,
        titulo=titulo,
        exemplar_codigo=exemplar_codigo,
        retirada_em=locacao.retirada_em,
        prevista_em=locacao.prevista_em,
        renovacoes=locacao.renovacoes,
    )


def _locacao_do_usuario(
    session: Session, usuario_id: int, locacao_id: int
) -> tuple[Locacao, Exemplar, str]:
    """Carrega (e trava) uma locação ativa do usuário.

    Locação de outro usuário é tratada como inexistente, para não vazar que ela existe.
    """
    linha = session.execute(
        select(Locacao, Exemplar, Livro.titulo)
        .join(Exemplar, Exemplar.id == Locacao.exemplar_id)
        .join(Livro, Livro.id == Exemplar.livro_id)
        .where(Locacao.id == locacao_id, Locacao.usuario_id == usuario_id)
        .with_for_update(of=Locacao)
    ).one_or_none()
    if linha is None:
        raise ErroLocacao("locacao_inexistente", "Locação não encontrada.")
    locacao, exemplar, titulo = linha
    if locacao.devolvida_em is not None:
        raise ErroLocacao("locacao_devolvida", "Esta locação já foi devolvida.")
    return locacao, exemplar, titulo


def locar(
    session: Session,
    usuario_id: int,
    livro_id: int,
    regras: RegrasLocacao,
    agora: datetime | None = None,
) -> ResultadoLocacao:
    agora = _agora(agora)
    with _transacao(session):
        _bloquear_usuario(session, usuario_id)
        titulo = _titulo(session, livro_id)

        ativas = _locacoes_ativas(session, usuario_id)
        if any(prevista < agora for prevista, _ in ativas):
            raise ErroLocacao(
                "usuario_com_atraso", "Há uma locação em atraso: devolva antes de locar de novo."
            )
        if len(ativas) >= regras.max_locacoes:
            raise ErroLocacao(
                "limite_locacoes",
                f"Limite de {regras.max_locacoes} locações simultâneas atingido.",
            )
        if any(livro == livro_id for _, livro in ativas):
            raise ErroLocacao("livro_ja_locado", "Você já está com este livro.")

        livres = _livres(session, livro_id)
        if livres == 0:
            raise ErroLocacao("sem_exemplar", "Não há exemplar livre deste livro agora.")

        # Com fila, só quem está entre os primeiros `livres` da fila leva o exemplar.
        fila = (
            session.execute(
                select(Reserva)
                .where(Reserva.livro_id == livro_id, Reserva.status == "ativa")
                .order_by(Reserva.posicao)
            )
            .scalars()
            .all()
        )
        reserva_propria: Reserva | None = None
        if fila:
            reserva_propria = next((r for r in fila[:livres] if r.usuario_id == usuario_id), None)
            if reserva_propria is None:
                raise ErroLocacao(
                    "fila_prioritaria",
                    "Os exemplares livres estão reservados para quem está na fila.",
                )

        exemplar = session.execute(
            select(Exemplar)
            .where(
                Exemplar.livro_id == livro_id,
                Exemplar.estado == "ativo",
                ~exists().where(Locacao.exemplar_id == Exemplar.id, Locacao.devolvida_em.is_(None)),
            )
            .order_by(Exemplar.id)
            .limit(1)
            .with_for_update(skip_locked=True, of=Exemplar)
        ).scalar_one_or_none()
        if exemplar is None:
            raise ErroLocacao("sem_exemplar", "Não há exemplar livre deste livro agora.")

        locacao = Locacao(
            exemplar_id=exemplar.id,
            usuario_id=usuario_id,
            retirada_em=agora,
            prevista_em=agora + timedelta(days=regras.prazo_dias),
            renovacoes=0,
        )
        session.add(locacao)
        try:
            session.flush()
        except IntegrityError as erro:
            # outro leitor levou o exemplar entre a escolha e a gravação
            raise ErroLocacao("sem_exemplar", "Não há exemplar livre deste livro agora.") from erro
        if reserva_propria is not None:
            reserva_propria.status = "atendida"
        return _resultado(locacao, exemplar.codigo, livro_id, titulo)


def renovar(
    session: Session,
    usuario_id: int,
    locacao_id: int,
    regras: RegrasLocacao,
    agora: datetime | None = None,
) -> ResultadoLocacao:
    agora = _agora(agora)
    with _transacao(session):
        locacao, exemplar, titulo = _locacao_do_usuario(session, usuario_id, locacao_id)
        if locacao.prevista_em < agora:
            raise ErroLocacao(
                "usuario_com_atraso", "Locação em atraso não pode ser renovada: devolva o livro."
            )
        if locacao.renovacoes >= regras.max_renovacoes:
            raise ErroLocacao(
                "limite_renovacoes",
                f"Limite de {regras.max_renovacoes} renovação(ões) atingido.",
            )
        if _fila(session, exemplar.livro_id) > 0:
            raise ErroLocacao(
                "renovacao_com_fila", "Há leitores na fila deste livro, então não dá para renovar."
            )
        locacao.prevista_em = locacao.prevista_em + timedelta(days=regras.prazo_dias)
        locacao.renovacoes += 1
        session.flush()
        return _resultado(locacao, exemplar.codigo, exemplar.livro_id, titulo)


def devolver(
    session: Session,
    usuario_id: int,
    locacao_id: int,
    agora: datetime | None = None,
) -> ResultadoDevolucao:
    agora = _agora(agora)
    with _transacao(session):
        locacao, exemplar, titulo = _locacao_do_usuario(session, usuario_id, locacao_id)
        locacao.devolvida_em = agora
        session.flush()
        return ResultadoDevolucao(
            locacao_id=locacao.id,
            livro_id=exemplar.livro_id,
            titulo=titulo,
            devolvida_em=agora,
            atraso_dias=max(0, (agora - locacao.prevista_em).days),
            fila=_fila(session, exemplar.livro_id),
        )


def reservar(
    session: Session,
    usuario_id: int,
    livro_id: int,
    agora: datetime | None = None,
) -> ResultadoReserva:
    agora = _agora(agora)
    with _transacao(session):
        _bloquear_usuario(session, usuario_id)
        # trava o livro: serializa a numeração da fila
        achou = session.execute(
            select(Livro.titulo).where(Livro.id == livro_id).with_for_update()
        ).scalar_one_or_none()
        if achou is None:
            raise ErroLocacao("livro_inexistente", "Livro não encontrado no acervo.")
        titulo = achou

        if any(livro == livro_id for _, livro in _locacoes_ativas(session, usuario_id)):
            raise ErroLocacao("livro_ja_locado", "Você já está com este livro.")
        ja_na_fila = session.execute(
            select(Reserva.id).where(
                Reserva.livro_id == livro_id,
                Reserva.usuario_id == usuario_id,
                Reserva.status == "ativa",
            )
        ).first()
        if ja_na_fila is not None:
            raise ErroLocacao("reserva_duplicada", "Você já está na fila deste livro.")

        total, livres, fila = session.execute(
            text("SELECT total, livres, fila FROM disponibilidade_livro WHERE livro_id = :l"),
            {"l": livro_id},
        ).one()
        if total == 0:
            raise ErroLocacao("sem_exemplar", "Este livro não tem exemplares em circulação.")
        if livres > fila:
            raise ErroLocacao(
                "reserva_desnecessaria", "Há exemplar livre: é só locar, sem precisar reservar."
            )

        # `posicao` é monotônica (define a ordem); o lugar na fila é a contagem de ativas.
        ultima = session.execute(
            select(func.coalesce(func.max(Reserva.posicao), 0)).where(Reserva.livro_id == livro_id)
        ).scalar_one()
        reserva = Reserva(
            livro_id=livro_id,
            usuario_id=usuario_id,
            posicao=int(ultima) + 1,
            status="ativa",
            criada_em=agora,
        )
        session.add(reserva)
        try:
            session.flush()
        except IntegrityError as erro:
            raise ErroLocacao("reserva_duplicada", "Você já está na fila deste livro.") from erro
        return ResultadoReserva(
            reserva_id=reserva.id, livro_id=livro_id, titulo=titulo, posicao=int(fila) + 1
        )


@dataclass(frozen=True)
class LocacaoResumo:
    locacao_id: int
    livro_id: int
    titulo: str
    retirada_em: datetime
    prevista_em: datetime
    devolvida_em: datetime | None
    renovacoes: int
    atrasada: bool


@dataclass(frozen=True)
class ReservaResumo:
    reserva_id: int
    livro_id: int
    titulo: str
    posicao: int  # lugar real na fila (1 = próximo)


@dataclass(frozen=True)
class MinhasLocacoes:
    ativas: list[LocacaoResumo]
    reservas: list[ReservaResumo]
    historico: list[LocacaoResumo]


def minhas_locacoes(
    session: Session,
    usuario_id: int,
    agora: datetime | None = None,
    historico_limite: int = settings.historico_locacoes_limite,
) -> MinhasLocacoes:
    """Locações ativas, reservas na fila e as últimas devoluções do usuário (só leitura)."""
    agora = _agora(agora)
    linhas = session.execute(
        select(Locacao, Livro.titulo, Exemplar.livro_id)
        .join(Exemplar, Exemplar.id == Locacao.exemplar_id)
        .join(Livro, Livro.id == Exemplar.livro_id)
        .where(Locacao.usuario_id == usuario_id)
        .order_by(Locacao.prevista_em, Locacao.id)
    ).all()

    def resumo(lo: Locacao, titulo: str, livro_id: int) -> LocacaoResumo:
        return LocacaoResumo(
            locacao_id=lo.id,
            livro_id=livro_id,
            titulo=titulo,
            retirada_em=lo.retirada_em,
            prevista_em=lo.prevista_em,
            devolvida_em=lo.devolvida_em,
            renovacoes=lo.renovacoes,
            atrasada=lo.devolvida_em is None and lo.prevista_em < agora,
        )

    ativas = [resumo(*linha) for linha in linhas if linha[0].devolvida_em is None]
    devolvidas = [resumo(*linha) for linha in linhas if linha[0].devolvida_em is not None]
    devolvidas.sort(key=lambda r: (r.devolvida_em or agora, r.locacao_id), reverse=True)

    reservas = []
    for reserva, titulo in session.execute(
        select(Reserva, Livro.titulo)
        .join(Livro, Livro.id == Reserva.livro_id)
        .where(Reserva.usuario_id == usuario_id, Reserva.status == "ativa")
        .order_by(Reserva.id)
    ).all():
        lugar = 1 + int(
            session.execute(
                select(func.count())
                .select_from(Reserva)
                .where(
                    Reserva.livro_id == reserva.livro_id,
                    Reserva.status == "ativa",
                    Reserva.posicao < reserva.posicao,
                )
            ).scalar_one()
        )
        reservas.append(
            ReservaResumo(
                reserva_id=reserva.id, livro_id=reserva.livro_id, titulo=titulo, posicao=lugar
            )
        )
    return MinhasLocacoes(ativas=ativas, reservas=reservas, historico=devolvidas[:historico_limite])

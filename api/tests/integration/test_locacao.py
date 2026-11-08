import itertools
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from leia_api.locacao import (
    ErroLocacao,
    RegrasLocacao,
    devolver,
    locar,
    renovar,
    reservar,
)
from leia_api.models import Exemplar, Livro, Locacao, Reserva, Usuario

AGORA = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
REGRAS = RegrasLocacao(max_locacoes=3, prazo_dias=14, max_renovacoes=1)
_seq = itertools.count(1)


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Sessão com commits reais (a corrida usa conexões separadas, então não dá para dar rollback).

    O banco de testes é compartilhado com outros módulos, então tudo que criamos aqui
    (livros "Livro de teste …" e e-mails "@teste.local") é apagado ao final de cada teste.
    """
    with Session(engine) as s:
        yield s
    with Session(engine) as limpeza:
        for sql in (
            "DELETE FROM locacoes WHERE usuario_id IN "
            "(SELECT id FROM usuarios WHERE email LIKE '%@teste.local')",
            "DELETE FROM reservas WHERE usuario_id IN "
            "(SELECT id FROM usuarios WHERE email LIKE '%@teste.local')",
            "DELETE FROM exemplares WHERE livro_id IN "
            "(SELECT id FROM livros WHERE titulo LIKE 'Livro de teste %')",
            "DELETE FROM livros WHERE titulo LIKE 'Livro de teste %'",
            "DELETE FROM usuarios WHERE email LIKE '%@teste.local'",
        ):
            limpeza.execute(text(sql))
        limpeza.commit()


def _usuario(session: Session) -> int:
    n = next(_seq)
    u = Usuario(nome=f"Leitor {n}", email=f"leitor{n}@teste.local", senha_hash="x")
    session.add(u)
    session.commit()
    return u.id


def _livro(session: Session, exemplares: int = 1, em_manutencao: int = 0) -> int:
    n = next(_seq)
    livro = Livro(titulo=f"Livro de teste {n}")
    session.add(livro)
    session.flush()
    for i in range(exemplares):
        session.add(Exemplar(livro_id=livro.id, codigo=f"T{n}-{i}"))
    for i in range(em_manutencao):
        session.add(Exemplar(livro_id=livro.id, codigo=f"T{n}-m{i}", estado="manutencao"))
    session.commit()
    return livro.id


def _locacao_direta(session: Session, usuario_id: int, livro_id: int, prevista_em: datetime) -> int:
    exemplar_id = session.execute(
        text(
            "SELECT e.id FROM exemplares e WHERE e.livro_id = :l AND e.estado = 'ativo' "
            "AND NOT EXISTS (SELECT 1 FROM locacoes lo "
            "WHERE lo.exemplar_id = e.id AND lo.devolvida_em IS NULL) LIMIT 1"
        ),
        {"l": livro_id},
    ).scalar_one()
    lo = Locacao(
        exemplar_id=exemplar_id,
        usuario_id=usuario_id,
        retirada_em=prevista_em - timedelta(days=14),
        prevista_em=prevista_em,
    )
    session.add(lo)
    session.commit()
    return lo.id


def _livres(session: Session, livro_id: int) -> int:
    return int(
        session.execute(
            text("SELECT livres FROM disponibilidade_livro WHERE livro_id = :l"), {"l": livro_id}
        ).scalar_one()
    )


def _codigo(excecao: pytest.ExceptionInfo[ErroLocacao]) -> str:
    return excecao.value.codigo


# ---------- locar ----------


def test_locar_cria_locacao_com_prazo_da_regra(session: Session) -> None:
    u, livro = _usuario(session), _livro(session)

    res = locar(session, u, livro, REGRAS, agora=AGORA)

    assert res.livro_id == livro
    assert res.prevista_em == AGORA + timedelta(days=14)
    lo = session.get(Locacao, res.locacao_id)
    assert lo is not None
    assert lo.usuario_id == u
    assert lo.devolvida_em is None
    assert lo.renovacoes == 0
    assert _livres(session, livro) == 0


def test_locar_respeita_regras_configuradas(session: Session) -> None:
    u, a, b = _usuario(session), _livro(session), _livro(session)
    regras = RegrasLocacao(max_locacoes=1, prazo_dias=7, max_renovacoes=0)

    res = locar(session, u, a, regras, agora=AGORA)

    assert res.prevista_em == AGORA + timedelta(days=7)
    with pytest.raises(ErroLocacao) as e:
        locar(session, u, b, regras, agora=AGORA)
    assert _codigo(e) == "limite_locacoes"


def test_locar_limite_de_tres_locacoes_simultaneas(session: Session) -> None:
    u = _usuario(session)
    for _ in range(3):
        locar(session, u, _livro(session), REGRAS, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        locar(session, u, _livro(session), REGRAS, agora=AGORA)
    assert _codigo(e) == "limite_locacoes"


def test_devolver_libera_vaga_no_limite(session: Session) -> None:
    u = _usuario(session)
    primeira = locar(session, u, _livro(session), REGRAS, agora=AGORA)
    for _ in range(2):
        locar(session, u, _livro(session), REGRAS, agora=AGORA)
    devolver(session, u, primeira.locacao_id, agora=AGORA)

    res = locar(session, u, _livro(session), REGRAS, agora=AGORA)

    assert res.locacao_id


def test_locar_bloqueia_usuario_com_atraso(session: Session) -> None:
    u, antigo, novo = _usuario(session), _livro(session), _livro(session)
    _locacao_direta(session, u, antigo, prevista_em=AGORA - timedelta(days=1))

    with pytest.raises(ErroLocacao) as e:
        locar(session, u, novo, REGRAS, agora=AGORA)
    assert _codigo(e) == "usuario_com_atraso"


def test_locar_prazo_no_dia_do_vencimento_nao_e_atraso(session: Session) -> None:
    u, antigo, novo = _usuario(session), _livro(session), _livro(session)
    _locacao_direta(session, u, antigo, prevista_em=AGORA)

    assert locar(session, u, novo, REGRAS, agora=AGORA).locacao_id


def test_locar_mesmo_livro_duas_vezes(session: Session) -> None:
    u, livro = _usuario(session), _livro(session, exemplares=2)
    locar(session, u, livro, REGRAS, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        locar(session, u, livro, REGRAS, agora=AGORA)
    assert _codigo(e) == "livro_ja_locado"


def test_locar_sem_exemplar_livre(session: Session) -> None:
    a, b, livro = _usuario(session), _usuario(session), _livro(session)
    locar(session, a, livro, REGRAS, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        locar(session, b, livro, REGRAS, agora=AGORA)
    assert _codigo(e) == "sem_exemplar"


def test_locar_ignora_exemplar_em_manutencao(session: Session) -> None:
    u = _usuario(session)
    livro = _livro(session, exemplares=0, em_manutencao=1)

    with pytest.raises(ErroLocacao) as e:
        locar(session, u, livro, REGRAS, agora=AGORA)
    assert _codigo(e) == "sem_exemplar"


def test_locar_usuario_ou_livro_inexistente(session: Session) -> None:
    u, livro = _usuario(session), _livro(session)

    with pytest.raises(ErroLocacao) as e1:
        locar(session, 999_999_999, livro, REGRAS, agora=AGORA)
    with pytest.raises(ErroLocacao) as e2:
        locar(session, u, 999_999_999, REGRAS, agora=AGORA)

    assert _codigo(e1) == "usuario_inexistente"
    assert _codigo(e2) == "livro_inexistente"


def test_sessao_continua_usavel_apos_erro_de_regra(session: Session) -> None:
    u, livro = _usuario(session), _livro(session, exemplares=0)
    with pytest.raises(ErroLocacao):
        locar(session, u, livro, REGRAS, agora=AGORA)

    assert locar(session, u, _livro(session), REGRAS, agora=AGORA).locacao_id


# ---------- fila e reserva ----------


def test_locar_exemplar_livre_com_fila_so_para_o_primeiro_da_fila(session: Session) -> None:
    dono, primeiro, furao = _usuario(session), _usuario(session), _usuario(session)
    livro = _livro(session)
    loc = locar(session, dono, livro, REGRAS, agora=AGORA)
    reservar(session, primeiro, livro, agora=AGORA)
    devolver(session, dono, loc.locacao_id, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        locar(session, furao, livro, REGRAS, agora=AGORA)
    assert _codigo(e) == "fila_prioritaria"

    res = locar(session, primeiro, livro, REGRAS, agora=AGORA)

    assert res.locacao_id
    reserva = session.query(Reserva).filter_by(livro_id=livro, usuario_id=primeiro).one()
    assert reserva.status == "atendida"


def test_reservar_atribui_posicoes_em_sequencia(session: Session) -> None:
    dono, b, c, livro = _usuario(session), _usuario(session), _usuario(session), _livro(session)
    locar(session, dono, livro, REGRAS, agora=AGORA)

    r1 = reservar(session, b, livro, agora=AGORA)
    r2 = reservar(session, c, livro, agora=AGORA)

    assert (r1.posicao, r2.posicao) == (1, 2)


def test_reservar_duplicada(session: Session) -> None:
    dono, b, livro = _usuario(session), _usuario(session), _livro(session)
    locar(session, dono, livro, REGRAS, agora=AGORA)
    reservar(session, b, livro, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        reservar(session, b, livro, agora=AGORA)
    assert _codigo(e) == "reserva_duplicada"


def test_reservar_desnecessaria_quando_ha_exemplar_livre(session: Session) -> None:
    u, livro = _usuario(session), _livro(session)

    with pytest.raises(ErroLocacao) as e:
        reservar(session, u, livro, agora=AGORA)
    assert _codigo(e) == "reserva_desnecessaria"


def test_reservar_livro_que_o_usuario_ja_esta_lendo(session: Session) -> None:
    u, livro = _usuario(session), _livro(session)
    locar(session, u, livro, REGRAS, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        reservar(session, u, livro, agora=AGORA)
    assert _codigo(e) == "livro_ja_locado"


def test_reservar_livro_sem_exemplares_em_circulacao(session: Session) -> None:
    u = _usuario(session)
    livro = _livro(session, exemplares=0, em_manutencao=1)

    with pytest.raises(ErroLocacao) as e:
        reservar(session, u, livro, agora=AGORA)
    assert _codigo(e) == "sem_exemplar"


def test_reservar_livro_inexistente(session: Session) -> None:
    with pytest.raises(ErroLocacao) as e:
        reservar(session, _usuario(session), 999_999_999, agora=AGORA)
    assert _codigo(e) == "livro_inexistente"


# ---------- renovar ----------


def test_renovar_estende_o_prazo_a_partir_da_data_prevista(session: Session) -> None:
    u, livro = _usuario(session), _livro(session)
    loc = locar(session, u, livro, REGRAS, agora=AGORA)

    res = renovar(session, u, loc.locacao_id, REGRAS, agora=AGORA + timedelta(days=3))

    assert res.prevista_em == AGORA + timedelta(days=28)
    assert res.renovacoes == 1


def test_renovar_alem_do_limite(session: Session) -> None:
    u, livro = _usuario(session), _livro(session)
    loc = locar(session, u, livro, REGRAS, agora=AGORA)
    renovar(session, u, loc.locacao_id, REGRAS, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        renovar(session, u, loc.locacao_id, REGRAS, agora=AGORA)
    assert _codigo(e) == "limite_renovacoes"


def test_renovar_com_fila_de_reservas(session: Session) -> None:
    u, outro, livro = _usuario(session), _usuario(session), _livro(session)
    loc = locar(session, u, livro, REGRAS, agora=AGORA)
    reservar(session, outro, livro, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        renovar(session, u, loc.locacao_id, REGRAS, agora=AGORA)
    assert _codigo(e) == "renovacao_com_fila"


def test_renovar_locacao_em_atraso(session: Session) -> None:
    u, livro = _usuario(session), _livro(session)
    lo = _locacao_direta(session, u, livro, prevista_em=AGORA - timedelta(days=2))

    with pytest.raises(ErroLocacao) as e:
        renovar(session, u, lo, REGRAS, agora=AGORA)
    assert _codigo(e) == "usuario_com_atraso"


def test_renovar_locacao_de_outro_usuario_parece_inexistente(session: Session) -> None:
    u, intruso, livro = _usuario(session), _usuario(session), _livro(session)
    loc = locar(session, u, livro, REGRAS, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        renovar(session, intruso, loc.locacao_id, REGRAS, agora=AGORA)
    assert _codigo(e) == "locacao_inexistente"


def test_renovar_locacao_ja_devolvida(session: Session) -> None:
    u, livro = _usuario(session), _livro(session)
    loc = locar(session, u, livro, REGRAS, agora=AGORA)
    devolver(session, u, loc.locacao_id, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        renovar(session, u, loc.locacao_id, REGRAS, agora=AGORA)
    assert _codigo(e) == "locacao_devolvida"


# ---------- devolver ----------


def test_devolver_libera_o_exemplar(session: Session) -> None:
    u, livro = _usuario(session), _livro(session)
    loc = locar(session, u, livro, REGRAS, agora=AGORA)

    res = devolver(session, u, loc.locacao_id, agora=AGORA + timedelta(days=5))

    assert res.atraso_dias == 0
    assert res.devolvida_em == AGORA + timedelta(days=5)
    assert _livres(session, livro) == 1


def test_devolver_em_atraso_informa_dias(session: Session) -> None:
    u, livro = _usuario(session), _livro(session)
    lo = _locacao_direta(session, u, livro, prevista_em=AGORA - timedelta(days=3))

    res = devolver(session, u, lo, agora=AGORA)

    assert res.atraso_dias == 3
    # depois de devolver, o usuário volta a poder locar
    assert locar(session, u, _livro(session), REGRAS, agora=AGORA).locacao_id


def test_devolver_informa_se_ha_fila(session: Session) -> None:
    u, outro, livro = _usuario(session), _usuario(session), _livro(session)
    loc = locar(session, u, livro, REGRAS, agora=AGORA)
    reservar(session, outro, livro, agora=AGORA)

    assert devolver(session, u, loc.locacao_id, agora=AGORA).fila == 1


def test_devolver_duas_vezes(session: Session) -> None:
    u, livro = _usuario(session), _livro(session)
    loc = locar(session, u, livro, REGRAS, agora=AGORA)
    devolver(session, u, loc.locacao_id, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        devolver(session, u, loc.locacao_id, agora=AGORA)
    assert _codigo(e) == "locacao_devolvida"


def test_devolver_locacao_de_outro_usuario(session: Session) -> None:
    u, intruso, livro = _usuario(session), _usuario(session), _livro(session)
    loc = locar(session, u, livro, REGRAS, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        devolver(session, intruso, loc.locacao_id, agora=AGORA)
    assert _codigo(e) == "locacao_inexistente"
    assert _livres(session, livro) == 0


# ---------- concorrência ----------


def _em_paralelo(engine: Engine, tarefas: list[tuple[int, int]]) -> list[str]:
    """Roda `locar` em uma thread por (usuario, livro), cada uma com a própria sessão."""
    resultados: list[str] = []
    trava = threading.Lock()
    largada = threading.Barrier(len(tarefas))

    def trabalho(usuario_id: int, livro_id: int) -> None:
        with Session(engine) as s:
            largada.wait()
            try:
                locar(s, usuario_id, livro_id, REGRAS, agora=AGORA)
                saida = "ok"
            except ErroLocacao as erro:
                saida = erro.codigo
        with trava:
            resultados.append(saida)

    threads = [threading.Thread(target=trabalho, args=t) for t in tarefas]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return resultados


def test_corrida_pelo_ultimo_exemplar_so_um_leva(engine: Engine, session: Session) -> None:
    livro = _livro(session, exemplares=1)
    usuarios = [_usuario(session) for _ in range(8)]

    resultados = _em_paralelo(engine, [(u, livro) for u in usuarios])

    assert resultados.count("ok") == 1
    assert resultados.count("sem_exemplar") == 7
    ativas = session.execute(
        text(
            "SELECT count(*) FROM locacoes lo JOIN exemplares e ON e.id = lo.exemplar_id "
            "WHERE e.livro_id = :l AND lo.devolvida_em IS NULL"
        ),
        {"l": livro},
    ).scalar_one()
    assert ativas == 1


def test_corrida_com_varios_exemplares_nao_duplica_exemplar(
    engine: Engine, session: Session
) -> None:
    livro = _livro(session, exemplares=3)
    usuarios = [_usuario(session) for _ in range(8)]

    resultados = _em_paralelo(engine, [(u, livro) for u in usuarios])

    assert resultados.count("ok") == 3
    assert resultados.count("sem_exemplar") == 5


def test_corrida_do_mesmo_usuario_nao_estoura_o_limite(engine: Engine, session: Session) -> None:
    u = _usuario(session)
    livros = [_livro(session) for _ in range(6)]

    resultados = _em_paralelo(engine, [(u, livro) for livro in livros])

    assert resultados.count("ok") == 3
    assert resultados.count("limite_locacoes") == 3

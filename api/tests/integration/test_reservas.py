"""Cancelar reserva e expirar reserva pronta que ninguém retirou."""
# ruff: noqa: F811 - a fixture `session` é reaproveitada de test_locacao e reaparece nos argumentos

from datetime import timedelta

import pytest
from alembic.config import Config
from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session

from leia_api.config import settings
from leia_api.locacao import (
    ErroLocacao,
    RegrasLocacao,
    cancelar_reserva,
    devolver,
    expirar_reservas,
    locar,
    minhas_locacoes,
    reservar,
)
from leia_api.models import Reserva
from tests.integration.test_locacao import (  # noqa: F401 - `session` é fixture reaproveitada
    AGORA,
    _livres,
    _livro,
    _usuario,
    session,
)

DIAS = 2
REGRAS = RegrasLocacao(max_locacoes=3, prazo_dias=14, max_renovacoes=1, retirada_reserva_dias=DIAS)


def _status(session: Session, reserva_id: int) -> str:
    session.expire_all()
    return session.get(Reserva, reserva_id).status  # type: ignore[union-attr]


def _pronta_em(session: Session, reserva_id: int):  # type: ignore[no-untyped-def]
    session.expire_all()
    return session.get(Reserva, reserva_id).pronta_em  # type: ignore[union-attr]


def _fila_com_dois(session: Session):  # type: ignore[no-untyped-def]
    """Livro de 1 exemplar locado por `dono`; `b` e `c` na fila, nessa ordem."""
    dono, b, c = _usuario(session), _usuario(session), _usuario(session)
    livro = _livro(session)
    locacao = locar(session, dono, livro, REGRAS, agora=AGORA)
    rb = reservar(session, b, livro, agora=AGORA)
    rc = reservar(session, c, livro, agora=AGORA)
    return dono, b, c, livro, locacao, rb, rc


# ---------- cancelar ----------


def test_cancelar_reserva_tira_da_fila(session: Session) -> None:
    dono, b, c, livro, _, rb, rc = _fila_com_dois(session)

    res = cancelar_reserva(session, b, rb.reserva_id, agora=AGORA)

    assert res.reserva_id == rb.reserva_id and res.livro_id == livro
    assert _status(session, rb.reserva_id) == "cancelada"
    assert [r.posicao for r in minhas_locacoes(session, c, AGORA).reservas] == [1]


def test_cancelar_reserva_de_outro_usuario_ou_inexistente(session: Session) -> None:
    _, b, c, *_, rb, _ = _fila_com_dois(session)

    with pytest.raises(ErroLocacao) as de_outro:
        cancelar_reserva(session, c, rb.reserva_id, agora=AGORA)  # reserva é de b
    with pytest.raises(ErroLocacao) as inexistente:
        cancelar_reserva(session, b, 999_999_999, agora=AGORA)

    assert de_outro.value.codigo == "reserva_inexistente"
    assert inexistente.value.codigo == "reserva_inexistente"
    assert _status(session, rb.reserva_id) == "ativa"


def test_cancelar_reserva_ja_encerrada(session: Session) -> None:
    _, b, *_, rb, _ = _fila_com_dois(session)
    cancelar_reserva(session, b, rb.reserva_id, agora=AGORA)

    with pytest.raises(ErroLocacao) as e:
        cancelar_reserva(session, b, rb.reserva_id, agora=AGORA)

    assert e.value.codigo == "reserva_encerrada"


def test_cancelar_reserva_atendida_nao_vale(session: Session) -> None:
    dono, b, _, livro, locacao, rb, _ = _fila_com_dois(session)
    devolver(session, dono, locacao.locacao_id, agora=AGORA)
    locar(session, b, livro, REGRAS, agora=AGORA)  # a reserva de b vira atendida

    with pytest.raises(ErroLocacao) as e:
        cancelar_reserva(session, b, rb.reserva_id, agora=AGORA)

    assert e.value.codigo == "reserva_encerrada"


# ---------- reserva pronta e expiração ----------


def test_devolver_marca_o_primeiro_da_fila_como_pronto(session: Session) -> None:
    dono, b, c, _, locacao, rb, rc = _fila_com_dois(session)
    assert _pronta_em(session, rb.reserva_id) is None

    devolver(session, dono, locacao.locacao_id, agora=AGORA)

    assert _pronta_em(session, rb.reserva_id) == AGORA
    assert _pronta_em(session, rc.reserva_id) is None  # só há 1 exemplar livre
    res = minhas_locacoes(session, b, AGORA, retirada_dias=DIAS).reservas[0]
    assert res.pronta is True and res.retirar_ate == AGORA + timedelta(days=DIAS)
    assert minhas_locacoes(session, c, AGORA, retirada_dias=DIAS).reservas[0].pronta is False


def test_nao_expira_antes_do_prazo(session: Session) -> None:
    dono, b, _, _, locacao, rb, _ = _fila_com_dois(session)
    devolver(session, dono, locacao.locacao_id, agora=AGORA)

    expiradas = expirar_reservas(session, REGRAS, agora=AGORA + timedelta(days=DIAS))

    assert expiradas == 0
    assert _status(session, rb.reserva_id) == "ativa"


def test_expira_a_reserva_pronta_e_passa_a_vez_ao_proximo(session: Session) -> None:
    dono, b, c, livro, locacao, rb, rc = _fila_com_dois(session)
    devolver(session, dono, locacao.locacao_id, agora=AGORA)
    depois = AGORA + timedelta(days=DIAS, seconds=1)

    assert expirar_reservas(session, REGRAS, agora=depois) >= 1

    assert _status(session, rb.reserva_id) == "expirada"
    assert _pronta_em(session, rc.reserva_id) == depois  # c agora tem o prazo dele
    with pytest.raises(ErroLocacao) as e:
        locar(session, b, livro, REGRAS, agora=depois)  # b perdeu a vez
    assert e.value.codigo == "fila_prioritaria"
    assert locar(session, c, livro, REGRAS, agora=depois).livro_id == livro
    assert _livres(session, livro) == 0


def test_expirar_e_idempotente(session: Session) -> None:
    dono, _, _, _, locacao, rb, rc = _fila_com_dois(session)
    devolver(session, dono, locacao.locacao_id, agora=AGORA)
    depois = AGORA + timedelta(days=DIAS, seconds=1)
    expirar_reservas(session, REGRAS, agora=depois)

    assert expirar_reservas(session, REGRAS, agora=depois) == 0
    assert _status(session, rc.reserva_id) == "ativa"


def test_locar_expira_de_forma_preguicosa_a_reserva_esquecida(session: Session) -> None:
    dono, _, _, livro, locacao, rb, _ = _fila_com_dois(session)
    devolver(session, dono, locacao.locacao_id, agora=AGORA)
    outro = _usuario(session)
    antes = AGORA + timedelta(days=DIAS - 1)
    depois = AGORA + timedelta(days=DIAS, seconds=1)

    with pytest.raises(ErroLocacao) as e:
        locar(session, outro, livro, REGRAS, agora=antes)  # b ainda tem o prazo dele
    assert e.value.codigo == "fila_prioritaria"
    # c também está na fila; depois do prazo de b, c é o próximo, e `outro` continua de fora
    with pytest.raises(ErroLocacao) as e2:
        locar(session, outro, livro, REGRAS, agora=depois)
    assert e2.value.codigo == "fila_prioritaria"
    assert _status(session, rb.reserva_id) == "expirada"  # expirou ao tentar locar, sem varredura


def test_fila_de_um_so_libera_o_livro_quando_a_reserva_expira(session: Session) -> None:
    dono, b, livro = _usuario(session), _usuario(session), _livro(session)
    lo = locar(session, dono, livro, REGRAS, agora=AGORA)
    rb = reservar(session, b, livro, agora=AGORA)
    devolver(session, dono, lo.locacao_id, agora=AGORA)
    outro = _usuario(session)
    depois = AGORA + timedelta(days=DIAS, seconds=1)

    res = locar(session, outro, livro, REGRAS, agora=depois)  # antes do fix: bloqueado para sempre

    assert res.livro_id == livro
    assert _status(session, rb.reserva_id) == "expirada"


def test_cancelar_a_pronta_promove_o_proximo(session: Session) -> None:
    dono, b, c, _, locacao, rb, rc = _fila_com_dois(session)
    devolver(session, dono, locacao.locacao_id, agora=AGORA)
    depois = AGORA + timedelta(hours=1)

    cancelar_reserva(session, b, rb.reserva_id, agora=depois)

    assert _pronta_em(session, rc.reserva_id) == depois


def test_prazo_de_retirada_vem_da_configuracao() -> None:
    assert RegrasLocacao.da_config().retirada_reserva_dias == settings.reserva_retirada_dias


def test_manutencao_expira_pela_varredura(session: Session) -> None:
    from leia_api.manutencao import executar

    dono, _, _, _, locacao, rb, _ = _fila_com_dois(session)
    devolver(session, dono, locacao.locacao_id, agora=AGORA)

    assert executar(session, REGRAS) == 0  # o prazo real (a partir de agora) ainda não passou
    expirar_reservas(session, REGRAS, agora=AGORA + timedelta(days=DIAS, seconds=1))
    assert _status(session, rb.reserva_id) == "expirada"


def test_0006_cria_pronta_em_e_aceita_expirada_e_o_downgrade_desfaz(
    alembic_cfg: Config, engine: Engine
) -> None:
    from alembic import command

    try:
        command.downgrade(alembic_cfg, "0005")
        insp = inspect(engine)
        assert "pronta_em" not in {c["name"] for c in insp.get_columns("reservas")}

        command.upgrade(alembic_cfg, "head")
        insp = inspect(engine)
        assert "pronta_em" in {c["name"] for c in insp.get_columns("reservas")}
        check = next(
            c for c in insp.get_check_constraints("reservas") if c["name"] == "ck_reservas_status"
        )
        assert "expirada" in check["sqltext"]
    finally:
        command.upgrade(alembic_cfg, "head")

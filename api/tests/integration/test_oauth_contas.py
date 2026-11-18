"""Entrar com Google/Microsoft no banco real: vínculo por sub, por e-mail e conta nova."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from leia_api import contas
from leia_api.models import IdentidadeExterna
from leia_api.oauth import Identidade

DOMINIO = "@oauth.teste.local"


@pytest.fixture
def s(engine: Engine) -> Iterator[Session]:
    with Session(engine) as sess:
        yield sess
    with Session(engine) as limpeza:
        limpeza.execute(text("DELETE FROM usuarios WHERE email LIKE :d"), {"d": f"%{DOMINIO}"})
        limpeza.commit()


def test_primeira_vez_cria_leitor_sem_senha(s: Session) -> None:
    conta = contas.entrar_com_identidade(s, Identidade("google", "g1", f"Bia{DOMINIO}", "Bia"))
    assert conta.email == f"bia{DOMINIO}" and conta.nome == "Bia"
    # sem senha: o login por senha não funciona para essa conta
    assert contas.autenticar(s, f"bia{DOMINIO}", contas.SEM_SENHA) is None


def test_segunda_vez_entra_na_mesma_conta_mesmo_com_email_novo(s: Session) -> None:
    a = contas.entrar_com_identidade(s, Identidade("google", "g2", f"c{DOMINIO}", "C"))
    b = contas.entrar_com_identidade(s, Identidade("google", "g2", f"c.novo{DOMINIO}", "C"))
    assert a.id == b.id


def test_email_de_conta_com_senha_vincula_a_ela(s: Session) -> None:
    existente = contas.cadastrar(s, "Duda", f"duda{DOMINIO}", "senha-boa-123")
    conta = contas.entrar_com_identidade(s, Identidade("microsoft", "m1", f"DUDA{DOMINIO}", "D"))
    assert conta.id == existente.id
    assert contas.autenticar(s, f"duda{DOMINIO}", "senha-boa-123") is not None  # senha segue
    vinculos = s.scalars(
        select(IdentidadeExterna).where(IdentidadeExterna.usuario_id == existente.id)
    ).all()
    assert [(v.provedor, v.sujeito) for v in vinculos] == [("microsoft", "m1")]


def test_google_e_microsoft_na_mesma_conta(s: Session) -> None:
    g = contas.entrar_com_identidade(s, Identidade("google", "g3", f"eva{DOMINIO}", "Eva"))
    m = contas.entrar_com_identidade(s, Identidade("microsoft", "m3", f"eva{DOMINIO}", "Eva"))
    assert g.id == m.id

"""Cadastro, login e sessão pela API, com Postgres real. O usuario_id vem só da sessão."""

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from leia_api.config import settings
from leia_api.db import get_session
from leia_api.main import app

SENHA = "uma-senha-boa-123"


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    def _sessao() -> Iterator[Session]:
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _sessao
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    with Session(engine) as limpeza:
        limpeza.execute(
            text(
                "DELETE FROM sessoes WHERE usuario_id IN "
                "(SELECT id FROM usuarios WHERE email LIKE '%@auth.teste.local')"
            )
        )
        limpeza.execute(text("DELETE FROM usuarios WHERE email LIKE '%@auth.teste.local'"))
        limpeza.commit()


def _cadastrar(client: TestClient, email: str = "ana@auth.teste.local") -> Any:
    return client.post("/auth/cadastro", json={"nome": "Ana", "email": email, "senha": SENHA})


def test_cadastro_cria_usuario_e_abre_sessao(client: TestClient) -> None:
    r = _cadastrar(client)

    assert r.status_code == 201
    assert r.json()["email"] == "ana@auth.teste.local"
    assert "senha" not in r.text and "senha_hash" not in r.text
    assert client.get("/auth/eu").json()["nome"] == "Ana"


def test_cookie_de_sessao_e_httponly_e_samesite(client: TestClient) -> None:
    cookie = _cadastrar(client).headers["set-cookie"].lower()

    assert settings.sessao_cookie_nome in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie


def test_senha_fica_so_como_hash(client: TestClient, engine: Engine) -> None:
    _cadastrar(client, "hash@auth.teste.local")

    with Session(engine) as s:
        guardado = s.execute(
            text("SELECT senha_hash FROM usuarios WHERE email = 'hash@auth.teste.local'")
        ).scalar_one()
    assert SENHA not in guardado
    assert guardado.startswith("scrypt$")


def test_token_da_sessao_fica_so_como_hash(client: TestClient, engine: Engine) -> None:
    _cadastrar(client, "tok@auth.teste.local")
    token = client.cookies[settings.sessao_cookie_nome]

    with Session(engine) as s:
        guardados = s.execute(text("SELECT token_hash FROM sessoes")).scalars().all()
    assert token not in guardados
    assert hashlib.sha256(token.encode()).hexdigest() in guardados


def test_cadastro_com_email_repetido_e_conflito(client: TestClient) -> None:
    _cadastrar(client, "dup@auth.teste.local")
    client.cookies.clear()

    r = _cadastrar(client, "DUP@auth.teste.local")  # caixa não distingue

    assert r.status_code == 409
    assert r.json()["erro"] == "email_em_uso"
    assert "set-cookie" not in r.headers


@pytest.mark.parametrize(
    "corpo",
    [
        {"nome": "Ana", "email": "sem-arroba", "senha": SENHA},
        {"nome": "Ana", "email": "a@b", "senha": SENHA},
        {"nome": "Ana", "email": "ok@auth.teste.local", "senha": "curta"},
        {"nome": "Ana", "email": "ok@auth.teste.local", "senha": "x" * 200},
        {"nome": "", "email": "ok@auth.teste.local", "senha": SENHA},
        {"nome": "Ana", "email": "ok@auth.teste.local", "senha": SENHA, "papel": "admin"},
        {"nome": "Ana", "email": "ok@auth.teste.local", "senha": SENHA, "usuario_id": 1},
    ],
)
def test_cadastro_rejeita_entrada_invalida(client: TestClient, corpo: dict[str, Any]) -> None:
    assert client.post("/auth/cadastro", json=corpo).status_code == 422


def test_cadastro_cria_sempre_leitor(client: TestClient, engine: Engine) -> None:
    _cadastrar(client, "papel@auth.teste.local")

    with Session(engine) as s:
        papel = s.execute(
            text("SELECT papel FROM usuarios WHERE email = 'papel@auth.teste.local'")
        ).scalar_one()
    assert papel == "leitor"


def test_login_correto_abre_sessao(client: TestClient) -> None:
    _cadastrar(client, "login@auth.teste.local")
    client.cookies.clear()

    r = client.post("/auth/login", json={"email": "LOGIN@auth.teste.local", "senha": SENHA})

    assert r.status_code == 200
    assert client.get("/auth/eu").json()["email"] == "login@auth.teste.local"


def test_login_errado_e_usuario_inexistente_respondem_igual(client: TestClient) -> None:
    _cadastrar(client, "igual@auth.teste.local")
    client.cookies.clear()

    errada = client.post("/auth/login", json={"email": "igual@auth.teste.local", "senha": "x" * 12})
    inexistente = client.post(
        "/auth/login", json={"email": "ninguem@auth.teste.local", "senha": SENHA}
    )

    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json()
    assert "set-cookie" not in errada.headers


def test_eu_sem_sessao_e_401(client: TestClient) -> None:
    assert client.get("/auth/eu").status_code == 401


def test_cookie_adulterado_nao_autentica(client: TestClient) -> None:
    _cadastrar(client, "adulterado@auth.teste.local")
    client.cookies.clear()
    client.cookies.set(settings.sessao_cookie_nome, "token-que-nao-existe")

    assert client.get("/auth/eu").status_code == 401


def test_logout_encerra_a_sessao_no_servidor(client: TestClient) -> None:
    _cadastrar(client, "sair@auth.teste.local")
    token = client.cookies[settings.sessao_cookie_nome]

    assert client.post("/auth/logout").status_code == 204

    client.cookies.set(settings.sessao_cookie_nome, token)  # reaproveitar o cookie antigo
    assert client.get("/auth/eu").status_code == 401


def test_logout_sem_sessao_e_idempotente(client: TestClient) -> None:
    assert client.post("/auth/logout").status_code == 204


def test_sessao_expirada_nao_autentica(client: TestClient, engine: Engine) -> None:
    _cadastrar(client, "velha@auth.teste.local")
    with Session(engine) as s:
        s.execute(
            text("UPDATE sessoes SET expira_em = :e"),
            {"e": datetime.now(UTC) - timedelta(seconds=1)},
        )
        s.commit()

    assert client.get("/auth/eu").status_code == 401


def test_cada_login_tem_sessao_propria(client: TestClient) -> None:
    _cadastrar(client, "duas@auth.teste.local")
    primeira = client.cookies[settings.sessao_cookie_nome]
    client.post("/auth/login", json={"email": "duas@auth.teste.local", "senha": SENHA})

    assert client.cookies[settings.sessao_cookie_nome] != primeira
    client.post("/auth/logout")  # sair de uma não derruba a outra
    client.cookies.set(settings.sessao_cookie_nome, primeira)
    assert client.get("/auth/eu").status_code == 200


def test_apagar_usuario_apaga_as_sessoes(client: TestClient, engine: Engine) -> None:
    _cadastrar(client, "cascata@auth.teste.local")

    with Session(engine) as s:
        s.execute(text("DELETE FROM usuarios WHERE email = 'cascata@auth.teste.local'"))
        s.commit()
        orfas = s.execute(
            text(
                "SELECT count(*) FROM sessoes s LEFT JOIN usuarios u ON u.id = s.usuario_id "
                "WHERE u.id IS NULL"
            )
        ).scalar_one()
    assert orfas == 0

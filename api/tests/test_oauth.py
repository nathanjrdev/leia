"""Entrar com Google/Microsoft: validação do id_token e rotas, sem banco nem rede."""

import base64
import json
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from leia_api import auth, oauth
from leia_api.config import settings
from leia_api.db import get_session
from leia_api.main import app

AGORA = 1_800_000_000.0
MSA = oauth.TENANT_CONTAS_PESSOAIS


@pytest.fixture(autouse=True)
def _provedores_configurados(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "url_publica", "https://leia.example")
    monkeypatch.setattr(settings, "google_client_id", "id-google")
    monkeypatch.setattr(settings, "google_client_secret", SecretStr("segredo-g"))
    monkeypatch.setattr(settings, "microsoft_client_id", "id-ms")
    monkeypatch.setattr(settings, "microsoft_client_secret", SecretStr("segredo-m"))


def _token(**claims: Any) -> str:
    def b64(d: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    return f"{b64({'alg': 'RS256'})}.{b64(claims)}.assinatura"


def _google(**extra: Any) -> dict[str, Any]:
    base = {
        "iss": "https://accounts.google.com",
        "aud": "id-google",
        "exp": AGORA + 60,
        "nonce": "n1",
        "sub": "g-123",
        "email": "Ana@Gmail.com",
        "email_verified": True,
        "name": "Ana Souza",
    }
    return base | extra


def _ms(**extra: Any) -> dict[str, Any]:
    base = {
        "iss": f"https://login.microsoftonline.com/{MSA}/v2.0",
        "tid": MSA,
        "aud": "id-ms",
        "exp": AGORA + 60,
        "nonce": "n1",
        "sub": "m-9",
        "email": "ana@outlook.com",
        "name": "Ana",
    }
    return base | extra


def _p(nome: str) -> oauth.Provedor:
    p = oauth.provedor(nome)
    assert p is not None
    return p


# ---------- lógica ----------


def test_so_aparece_provedor_com_id_e_segredo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "microsoft_client_secret", None)
    assert oauth.disponiveis() == ["google"]
    monkeypatch.setattr(settings, "google_client_secret", SecretStr(""))  # GOOGLE_CLIENT_SECRET=
    assert oauth.disponiveis() == []
    assert oauth.provedor("facebook") is None


def test_url_de_login_tem_state_nonce_pkce_e_retorno() -> None:
    t = oauth.Tentativa("google", "st", "no", "v" * 50)
    q = parse_qs(urlparse(oauth.url_de_login(_p("google"), t)).query)
    assert q["state"] == ["st"] and q["nonce"] == ["no"]
    assert q["code_challenge_method"] == ["S256"]
    assert q["code_challenge"][0] != "v" * 50  # vai o hash, nunca o verificador
    assert q["redirect_uri"] == ["https://leia.example/api/auth/oauth/google/retorno"]
    assert q["scope"] == ["openid email profile"]


def test_tentativa_ida_e_volta_e_cookie_adulterado() -> None:
    t = oauth.nova_tentativa("microsoft")
    assert oauth.Tentativa.ler(t.serializar()) == t
    assert oauth.Tentativa.ler("facebook.a.b.c") is None
    assert oauth.Tentativa.ler("google.a.b") is None
    assert oauth.Tentativa.ler(None) is None


def test_google_valido_vira_identidade() -> None:
    i = oauth.identidade_do_token(_p("google"), _token(**_google()), "n1", agora=AGORA)
    assert i == oauth.Identidade("google", "g-123", "Ana@Gmail.com", "Ana Souza")


def test_microsoft_conta_pessoal_valida() -> None:
    i = oauth.identidade_do_token(_p("microsoft"), _token(**_ms()), "n1", agora=AGORA)
    assert (i.provedor, i.sujeito, i.email) == ("microsoft", "m-9", "ana@outlook.com")


@pytest.mark.parametrize(
    "claims",
    [
        _google(iss="https://malicioso.example"),
        _google(aud="outro-app"),
        _google(exp=AGORA - 3600),
        _google(nonce="outro"),
        _google(sub=""),
    ],
)
def test_google_invalido_recusa(claims: dict[str, Any]) -> None:
    with pytest.raises(oauth.FalhaOAuth) as e:
        oauth.identidade_do_token(_p("google"), _token(**claims), "n1", agora=AGORA)
    assert e.value.codigo == "oauth_falhou"


def test_email_nao_verificado_recusa() -> None:
    with pytest.raises(oauth.FalhaOAuth) as e:
        oauth.identidade_do_token(
            _p("google"), _token(**_google(email_verified=False)), "n1", agora=AGORA
        )
    assert e.value.codigo == "email_nao_verificado"


def test_microsoft_trabalho_sem_xms_edov_recusa_e_com_aceita() -> None:
    outro = "11111111-2222-3333-4444-555555555555"
    iss = f"https://login.microsoftonline.com/{outro}/v2.0"
    with pytest.raises(oauth.FalhaOAuth) as e:
        oauth.identidade_do_token(
            _p("microsoft"), _token(**_ms(tid=outro, iss=iss)), "n1", agora=AGORA
        )
    assert e.value.codigo == "email_nao_verificado"
    i = oauth.identidade_do_token(
        _p("microsoft"), _token(**_ms(tid=outro, iss=iss, xms_edov=True)), "n1", agora=AGORA
    )
    assert i.sujeito == "m-9"


def test_microsoft_emissor_de_outro_tenant_recusa() -> None:
    claims = _ms(iss="https://login.microsoftonline.com/outro/v2.0")
    with pytest.raises(oauth.FalhaOAuth):
        oauth.identidade_do_token(_p("microsoft"), _token(**claims), "n1", agora=AGORA)


def test_token_malformado_recusa() -> None:
    with pytest.raises(oauth.FalhaOAuth):
        oauth.identidade_do_token(_p("google"), "nao-e-jwt", "n1")


def test_sem_nome_usa_parte_do_email() -> None:
    claims = _google()
    del claims["name"]
    i = oauth.identidade_do_token(_p("google"), _token(**claims), "n1", agora=AGORA)
    assert i.nome == "Ana"


def test_trocar_codigo_envia_verificador_e_segredo() -> None:
    visto: dict[str, Any] = {}

    def h(req: httpx.Request) -> httpx.Response:
        visto.update(parse_qs(req.content.decode()))
        return httpx.Response(200, json={"id_token": "tok"})

    t = oauth.Tentativa("google", "st", "no", "verif")
    with httpx.Client(transport=httpx.MockTransport(h)) as c:
        assert oauth.trocar_codigo(_p("google"), "cod", t, c) == "tok"
    assert visto["code_verifier"] == ["verif"] and visto["client_secret"] == ["segredo-g"]


@pytest.mark.parametrize(
    "resposta",
    [httpx.Response(400, json={"error": "invalid_grant"}), httpx.Response(200, json={})],
)
def test_trocar_codigo_falha(resposta: httpx.Response) -> None:
    t = oauth.Tentativa("google", "st", "no", "verif")
    with httpx.Client(transport=httpx.MockTransport(lambda _: resposta)) as c:
        with pytest.raises(oauth.FalhaOAuth):
            oauth.trocar_codigo(_p("google"), "cod", t, c)


def test_trocar_codigo_provedor_fora_do_ar() -> None:
    def h(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("caiu")

    t = oauth.Tentativa("google", "st", "no", "verif")
    with httpx.Client(transport=httpx.MockTransport(h)) as c:
        with pytest.raises(oauth.FalhaOAuth):
            oauth.trocar_codigo(_p("google"), "cod", t, c)


# ---------- rotas (sem banco: os caminhos de erro param antes dele) ----------


@pytest.fixture
def client() -> Iterator[TestClient]:
    def _sem_banco() -> Iterator[None]:
        yield None

    app.dependency_overrides[get_session] = _sem_banco
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_rota_provedores(client: TestClient) -> None:
    assert client.get("/auth/provedores").json() == {"provedores": ["google", "microsoft"]}


def test_iniciar_redireciona_e_guarda_tentativa(client: TestClient) -> None:
    r = client.get("/auth/oauth/google/iniciar")
    assert r.status_code == 303
    assert r.headers["location"].startswith("https://accounts.google.com/")
    t = oauth.Tentativa.ler(r.cookies.get(auth.COOKIE_OAUTH))
    assert t is not None and t.provedor == "google"
    assert "httponly" in r.headers["set-cookie"].lower()


def test_iniciar_provedor_desconhecido_volta_para_entrar(client: TestClient) -> None:
    r = client.get("/auth/oauth/facebook/iniciar")
    assert r.headers["location"] == "/entrar?erro=provedor_indisponivel"


def test_retorno_cancelado(client: TestClient) -> None:
    r = client.get("/auth/oauth/google/retorno?error=access_denied")
    assert r.headers["location"] == "/entrar?erro=cancelado"


def test_retorno_sem_cookie_ou_state_errado_recusa(client: TestClient) -> None:
    r = client.get("/auth/oauth/google/retorno?code=c&state=s")
    assert r.headers["location"] == "/entrar?erro=oauth_falhou"
    client.cookies.set(auth.COOKIE_OAUTH, "google.certo.n.v")
    r = client.get("/auth/oauth/google/retorno?code=c&state=errado")
    assert r.headers["location"] == "/entrar?erro=oauth_falhou"


def test_retorno_tentativa_de_outro_provedor_recusa(client: TestClient) -> None:
    client.cookies.set(auth.COOKIE_OAUTH, "microsoft.st.n.v")
    r = client.get("/auth/oauth/google/retorno?code=c&state=st")
    assert r.headers["location"] == "/entrar?erro=oauth_falhou"


def test_retorno_email_nao_verificado_volta_com_codigo(client: TestClient) -> None:
    tok = _token(**_google(email_verified=False, exp=9_999_999_999, nonce="n"))
    falso = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"id_token": tok}))
    )
    app.dependency_overrides[auth._cliente_http] = lambda: falso
    client.cookies.set(auth.COOKIE_OAUTH, "google.st.n.v")
    r = client.get("/auth/oauth/google/retorno?code=c&state=st")
    assert r.headers["location"] == "/entrar?erro=email_nao_verificado"

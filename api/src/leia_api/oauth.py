"""Entrar com Google ou Microsoft (OpenID Connect, fluxo de código + PKCE).

Só a lógica fica aqui; o HTTP (redirecionamentos e cookies) fica em `auth.py`.

Segurança:
- `state` (CSRF), `nonce` (repetição do id_token) e o verificador PKCE são aleatórios por tentativa
  e ficam num cookie HttpOnly de vida curta; o retorno só é aceito se o `state` bater.
- O id_token vem DIRETO do endpoint de token do provedor, por TLS, autenticado com o client secret.
  Nesse caso o OpenID Connect Core (3.1.3.7, item 6) permite validar o emissor pelo TLS em vez da
  assinatura. Mesmo assim conferimos emissor, audiência, validade e nonce.
- Só confiamos no e-mail quando o provedor diz que ele foi verificado. Sem isso não há vínculo com
  conta existente nem conta nova (senão alguém poderia "reservar" o e-mail de outra pessoa).
"""

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
from pydantic import SecretStr

from leia_api.config import settings

NomeProvedor = Literal["google", "microsoft"]
PROVEDORES: tuple[NomeProvedor, ...] = ("google", "microsoft")

# Tenant das contas pessoais da Microsoft (outlook.com, hotmail.com): o e-mail é verificado.
TENANT_CONTAS_PESSOAIS = "9188040d-6c67-4c5b-b112-36a304b66dad"
_FOLGA_RELOGIO = 300  # segundos de tolerância para exp/iat


class FalhaOAuth(Exception):
    """Algo no retorno do provedor não confere. `codigo` vai para a tela de entrar."""

    def __init__(self, codigo: str, detalhe: str = "") -> None:
        super().__init__(detalhe or codigo)
        self.codigo = codigo


@dataclass(frozen=True)
class Provedor:
    nome: NomeProvedor
    client_id: str
    client_secret: str
    url_autorizacao: str
    url_token: str


@dataclass(frozen=True)
class Identidade:
    """Quem o provedor disse que é. `sujeito` (sub) é estável; o e-mail pode mudar."""

    provedor: NomeProvedor
    sujeito: str
    email: str
    nome: str


@dataclass(frozen=True)
class Tentativa:
    """O que guardamos no cookie entre ir ao provedor e voltar."""

    provedor: NomeProvedor
    state: str
    nonce: str
    verificador: str

    def serializar(self) -> str:
        return ".".join((self.provedor, self.state, self.nonce, self.verificador))

    @staticmethod
    def ler(valor: str | None) -> "Tentativa | None":
        partes = (valor or "").split(".")
        if len(partes) != 4 or partes[0] not in PROVEDORES or not all(partes):
            return None
        return Tentativa(partes[0], partes[1], partes[2], partes[3])


def _segredo(valor: SecretStr | None) -> str:
    return valor.get_secret_value() if valor else ""


def provedor(nome: str) -> Provedor | None:
    """Configuração do provedor, ou None se ele não existe ou não foi configurado."""
    if nome == "google" and settings.google_client_id and _segredo(settings.google_client_secret):
        return Provedor(
            "google",
            settings.google_client_id,
            _segredo(settings.google_client_secret),
            "https://accounts.google.com/o/oauth2/v2/auth",
            "https://oauth2.googleapis.com/token",
        )
    ms_segredo = _segredo(settings.microsoft_client_secret)
    if nome == "microsoft" and settings.microsoft_client_id and ms_segredo:
        base = f"https://login.microsoftonline.com/{settings.microsoft_tenant}/oauth2/v2.0"
        return Provedor(
            "microsoft",
            settings.microsoft_client_id,
            ms_segredo,
            f"{base}/authorize",
            f"{base}/token",
        )
    return None


def disponiveis() -> list[NomeProvedor]:
    return [p for p in PROVEDORES if provedor(p) is not None]


def url_retorno(nome: NomeProvedor) -> str:
    """Tem de ser idêntica à cadastrada no console do provedor."""
    return f"{settings.url_publica.rstrip('/')}/api/auth/oauth/{nome}/retorno"


def nova_tentativa(nome: NomeProvedor) -> Tentativa:
    return Tentativa(
        nome, secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    )


def _desafio_pkce(verificador: str) -> str:
    digest = hashlib.sha256(verificador.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def url_de_login(p: Provedor, t: Tentativa) -> str:
    params = {
        "client_id": p.client_id,
        "response_type": "code",
        "redirect_uri": url_retorno(p.nome),
        "scope": "openid email profile",
        "state": t.state,
        "nonce": t.nonce,
        "code_challenge": _desafio_pkce(t.verificador),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{p.url_autorizacao}?{urlencode(params)}"


def trocar_codigo(p: Provedor, codigo: str, t: Tentativa, cliente: httpx.Client) -> str:
    """Troca o código pelo id_token no endpoint de token do provedor."""
    try:
        resp = cliente.post(
            p.url_token,
            data={
                "grant_type": "authorization_code",
                "code": codigo,
                "redirect_uri": url_retorno(p.nome),
                "client_id": p.client_id,
                "client_secret": p.client_secret,
                "code_verifier": t.verificador,
            },
            headers={"Accept": "application/json"},
        )
    except httpx.HTTPError as erro:
        raise FalhaOAuth("oauth_falhou", "provedor fora do ar") from erro
    if resp.status_code != 200:
        raise FalhaOAuth("oauth_falhou", f"token HTTP {resp.status_code}")
    id_token = resp.json().get("id_token")
    if not isinstance(id_token, str):
        raise FalhaOAuth("oauth_falhou", "resposta sem id_token")
    return id_token


def _claims(id_token: str) -> dict[str, Any]:
    try:
        carga = id_token.split(".")[1]
        dados = json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))
    except (IndexError, ValueError) as erro:
        raise FalhaOAuth("oauth_falhou", "id_token malformado") from erro
    if not isinstance(dados, dict):
        raise FalhaOAuth("oauth_falhou", "id_token malformado")
    return dados


def _emissor_ok(p: Provedor, c: dict[str, Any]) -> bool:
    iss = c.get("iss")
    if p.nome == "google":
        return iss in ("https://accounts.google.com", "accounts.google.com")
    tid = c.get("tid")
    return isinstance(tid, str) and iss == f"https://login.microsoftonline.com/{tid}/v2.0"


def _email_verificado(p: Provedor, c: dict[str, Any]) -> bool:
    if p.nome == "google":
        return c.get("email_verified") is True
    # Microsoft: contas pessoais sempre verificam o e-mail; contas de trabalho/escola só com a
    # claim opcional `xms_edov` (configurar em "Configuração de token" no Entra ID).
    return c.get("tid") == TENANT_CONTAS_PESSOAIS or c.get("xms_edov") in (True, "1", 1)


def identidade_do_token(
    p: Provedor, id_token: str, nonce: str, agora: float | None = None
) -> Identidade:
    c = _claims(id_token)
    momento = time.time() if agora is None else agora
    aud = c.get("aud")
    audiencias = aud if isinstance(aud, list) else [aud]
    if not _emissor_ok(p, c) or p.client_id not in audiencias:
        raise FalhaOAuth("oauth_falhou", "emissor ou audiência inválidos")
    exp = c.get("exp")
    if not isinstance(exp, int | float) or exp + _FOLGA_RELOGIO < momento:
        raise FalhaOAuth("oauth_falhou", "id_token vencido")
    if not isinstance(c.get("nonce"), str) or not secrets.compare_digest(c["nonce"], nonce):
        raise FalhaOAuth("oauth_falhou", "nonce não confere")
    sujeito = c.get("sub")
    email = c.get("email")
    if not isinstance(sujeito, str) or not sujeito:
        raise FalhaOAuth("oauth_falhou", "id_token sem sub")
    if not isinstance(email, str) or "@" not in email or not _email_verificado(p, c):
        raise FalhaOAuth("email_nao_verificado")
    nome = c.get("name")
    if not isinstance(nome, str) or not nome.strip():
        nome = email.split("@", 1)[0]
    return Identidade(p.nome, sujeito, email, nome.strip()[:160])

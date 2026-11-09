"""Hash de senha com scrypt da biblioteca padrão (sem dependência nova).

Formato guardado: `scrypt$N$r$p$salt$hash` (base64 urlsafe). Os parâmetros ficam no próprio hash,
então dá para endurecê-los depois e ainda verificar os antigos. Parâmetros lidos de um hash
armazenado são limitados: um hash adulterado não pode pedir gigabytes de memória.
"""

import base64
import binascii
import hashlib
import hmac
import secrets

_N, _R, _P = 2**15, 8, 3  # perfil scrypt recomendado pela OWASP (~32 MiB, ~0,1 s)
_TAM_CHAVE = 32
_MAX_N, _MAX_R, _MAX_P = 2**17, 16, 16


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).decode("ascii")


def _derivar(senha: str, sal: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        senha.encode("utf-8"), salt=sal, n=n, r=r, p=p, dklen=_TAM_CHAVE, maxmem=2**28
    )


def gerar_hash(senha: str) -> str:
    sal = secrets.token_bytes(16)
    chave = _derivar(senha, sal, _N, _R, _P)
    return f"scrypt${_N}${_R}${_P}${_b64(sal)}${_b64(chave)}"


def verificar(senha: str, guardado: str) -> bool:
    """Compara em tempo constante. Hash malformado dá `False`, nunca exceção."""
    try:
        esquema, n_s, r_s, p_s, sal_s, chave_s = guardado.split("$")
        n, r, p = int(n_s), int(r_s), int(p_s)
        sal = base64.urlsafe_b64decode(sal_s)
        esperado = base64.urlsafe_b64decode(chave_s)
        if esquema != "scrypt" or not (2 <= n <= _MAX_N and n & (n - 1) == 0):
            return False
        if not (1 <= r <= _MAX_R and 1 <= p <= _MAX_P) or not esperado:
            return False
        obtido = hashlib.scrypt(
            senha.encode("utf-8"), salt=sal, n=n, r=r, p=p, dklen=len(esperado), maxmem=2**28
        )
    except (ValueError, binascii.Error):
        return False
    return hmac.compare_digest(obtido, esperado)

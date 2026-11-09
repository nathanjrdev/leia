"""Limitadores de taxa em memória (janela deslizante), por chave.

Servem de freio contra força bruta no login e abuso da busca pública (que usa modelo de ML).
O estado vive no processo: com várias instâncias, cada uma limita sozinha, o que basta para o MVP
(uma instância). O limite diário de mensagens NÃO usa isto: conta no banco (`conversas`).

Atrás de proxy, `request.client.host` é o proxy; suba o uvicorn com `--proxy-headers` e
`--forwarded-allow-ips` do proxy para o IP real chegar aqui.
"""

import threading
import time
from collections import OrderedDict, deque


class LimitadorJanela:
    def __init__(self, max_chaves: int = 10_000) -> None:
        self._eventos: OrderedDict[str, deque[float]] = OrderedDict()
        self._max_chaves = max_chaves
        self._trava = threading.Lock()

    @staticmethod
    def _agora(agora: float | None) -> float:
        return time.monotonic() if agora is None else agora

    def _podar(self, chave: str, janela: float, agora: float) -> deque[float]:
        fila = self._eventos.get(chave)
        if fila is None:
            return deque()
        while fila and fila[0] <= agora - janela:
            fila.popleft()
        if not fila:
            del self._eventos[chave]
            return deque()
        return fila

    def excedeu(self, chave: str, maximo: int, janela: float, agora: float | None = None) -> bool:
        """Já houve `maximo` ou mais eventos na janela? Não registra nada."""
        with self._trava:
            return len(self._podar(chave, janela, self._agora(agora))) >= maximo

    def registrar(self, chave: str, maximo: int, janela: float, agora: float | None = None) -> bool:
        """Conta um evento se ainda couber. Devolve False (sem contar) quando já estourou."""
        momento = self._agora(agora)
        with self._trava:
            fila = self._podar(chave, janela, momento)
            if len(fila) >= maximo:
                return False
            fila.append(momento)
            self._eventos[chave] = fila
            self._eventos.move_to_end(chave)
            while len(self._eventos) > self._max_chaves:
                self._eventos.popitem(last=False)  # descarta a chave mais antiga
            return True

    def zerar(self, chave: str) -> None:
        with self._trava:
            self._eventos.pop(chave, None)

    def limpar(self) -> None:
        with self._trava:
            self._eventos.clear()

    def tamanho(self) -> int:
        with self._trava:
            return len(self._eventos)


LOGIN = LimitadorJanela()
BUSCA = LimitadorJanela()


def limpar_todos() -> None:
    """Zera todos os limitadores do processo (usado pelos testes)."""
    LOGIN.limpar()
    BUSCA.limpar()

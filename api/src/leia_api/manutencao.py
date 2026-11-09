"""Rotina periódica de manutenção: expira reservas prontas que ninguém retirou no prazo.

Uso (em api/, com o banco no ar), por exemplo a cada hora num agendador:
  uv run python -m leia_api.manutencao

O prazo de retirada vem da configuração (`RESERVA_RETIRADA_DIAS`). A varredura é idempotente.
`locar` também expira, de forma preguiçosa, as reservas vencidas do livro que está sendo locado,
então a rotina só mantém a tela e a fila em dia quando ninguém está locando.
"""

from sqlalchemy.orm import Session

from leia_api import db
from leia_api.locacao import RegrasLocacao, expirar_reservas


def executar(session: Session, regras: RegrasLocacao | None = None) -> int:
    """Roda a manutenção numa sessão e devolve quantas reservas expiraram."""
    return expirar_reservas(session, regras or RegrasLocacao.da_config())


def main() -> None:
    with Session(db.engine()) as session:
        expiradas = executar(session)
    print(f"Reservas expiradas: {expiradas}")


if __name__ == "__main__":
    main()

"""Persistência de conversas e pendentes: o claim do clique é atômico."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from leia_api import conversas
from leia_api.models import AcaoPendente, Usuario

CODIGO = "codigo-concorrente"


def _preparar(engine: Engine, email: str) -> tuple[int, int]:
    with Session(engine) as s:
        u = Usuario(nome="Leitor", email=email, senha_hash="x")
        s.add(u)
        s.commit()
        conversa = conversas.criar(s, u.id)
        s.add(
            AcaoPendente(
                conversa_id=conversa,
                usuario_id=u.id,
                token=CODIGO,
                ferramenta="locar",
                argumentos={"livro_id": 1},
                resumo="Locar x",
                criada_em=datetime.now(UTC),
            )
        )
        s.commit()
        return u.id, conversa


def _limpar(engine: Engine, email: str) -> None:
    with Session(engine) as s:
        s.execute(
            text(
                "DELETE FROM conversas WHERE usuario_id IN "
                "(SELECT id FROM usuarios WHERE email = :e)"
            ),
            {"e": email},
        )
        s.execute(text("DELETE FROM usuarios WHERE email = :e"), {"e": email})
        s.commit()


def test_so_um_de_varios_cliques_simultaneos_reivindica(engine: Engine) -> None:
    email = "claim@conv.teste.local"
    uid, conversa = _preparar(engine, email)
    try:

        def clicar(_: int) -> Any:
            with Session(engine) as s:
                return conversas.reivindicar(s, conversa, uid, CODIGO)

        with ThreadPoolExecutor(max_workers=8) as pool:
            resultados = list(pool.map(clicar, range(8)))

        assert sum(r is not None for r in resultados) == 1
    finally:
        _limpar(engine, email)


def test_reivindicar_exige_conversa_e_usuario_certos(engine: Engine) -> None:
    email = "dono@conv.teste.local"
    uid, conversa = _preparar(engine, email)
    try:
        with Session(engine) as s:
            assert conversas.reivindicar(s, conversa + 1000, uid, CODIGO) is None
            assert conversas.reivindicar(s, conversa, uid + 1000, CODIGO) is None
            assert conversas.reivindicar(s, conversa, uid, CODIGO) is not None
    finally:
        _limpar(engine, email)


def test_0005_cria_pendentes_e_livros_vistos_e_o_downgrade_desfaz(
    alembic_cfg: Config, engine: Engine
) -> None:
    try:
        command.downgrade(alembic_cfg, "0004")
        insp = inspect(engine)
        assert "acoes_pendentes" not in insp.get_table_names()
        assert "livros_vistos" not in {c["name"] for c in insp.get_columns("conversas")}

        command.upgrade(alembic_cfg, "head")
        insp = inspect(engine)
        colunas = {c["name"] for c in insp.get_columns("acoes_pendentes")}
        assert colunas == {
            "id", "conversa_id", "usuario_id", "token", "ferramenta", "argumentos",
            "resumo", "criada_em",
        }  # fmt: skip
        assert "livros_vistos" in {c["name"] for c in insp.get_columns("conversas")}
        assert ("token",) in {
            tuple(u["column_names"]) for u in insp.get_unique_constraints("acoes_pendentes")
        }
    finally:
        command.upgrade(alembic_cfg, "head")

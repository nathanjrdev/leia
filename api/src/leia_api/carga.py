"""Carga completa do banco de desenvolvimento.

Uso (em api/): uv run --group ml python -m leia_api.carga

Aplica as migrações, carrega o catálogo de data/catalogo.json, aplica sinopses
revisadas aos livros já carregados, cria usuários e locações fictícios (só se
ainda não houver) e gera os embeddings que faltam (inclusive os invalidados).
"""

import json

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from leia_api.config import settings
from leia_api.embeddings import gerar_embeddings
from leia_api.modelos import EncoderST
from leia_api.models import Usuario
from leia_api.seed import (
    CATALOGO_PADRAO,
    atualizar_sinopses,
    carregar_catalogo_json,
    criar_locacoes_ficticias,
    criar_usuarios_ficticios,
)


def main() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        print(f"Livros novos: {carregar_catalogo_json(session)}")
        catalogo = json.loads(CATALOGO_PADRAO.read_text(encoding="utf-8"))
        print(f"Sinopses atualizadas: {atualizar_sinopses(session, catalogo)}")
        if not session.scalar(select(func.count()).select_from(Usuario)):
            criar_usuarios_ficticios(session)
            criar_locacoes_ficticias(session)
            print("Usuários e locações fictícios criados.")
        session.commit()

        print(f"Embeddings gerados: {gerar_embeddings(session, EncoderST())}")
        session.commit()


if __name__ == "__main__":
    main()

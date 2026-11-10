from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from leia_api import acervo, auth, chat, dependencias, metricas
from leia_api.config import settings


@asynccontextmanager
async def _ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
    metricas.configurar_log()
    if settings.aquecer_modelos:
        dependencias.get_encoder()
        dependencias.get_reranker()
    yield


app = FastAPI(title="Léia API", lifespan=_ciclo_de_vida)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(acervo.router)
app.add_exception_handler(auth.NaoAutenticado, auth.tratar_nao_autenticado)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

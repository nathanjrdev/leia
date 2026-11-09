from fastapi import FastAPI

from leia_api import acervo, auth, chat

app = FastAPI(title="Léia API")
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(acervo.router)
app.add_exception_handler(auth.NaoAutenticado, auth.tratar_nao_autenticado)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

from fastapi import FastAPI

app = FastAPI(title="Léia API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

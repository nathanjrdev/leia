from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração via variáveis de ambiente ou .env na raiz do repositório."""

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str = "postgresql+psycopg://leia:leia@localhost:5432/leia"
    leia_model: str = "gemini/gemini-flash-lite-latest"

    # Regras de negócio do MVP: parâmetros, não constantes.
    max_locacoes_simultaneas: int = 3
    prazo_locacao_dias: int = 14
    max_renovacoes: int = 1


settings = Settings()

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração via variáveis de ambiente ou .env na raiz do repositório."""

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str = "postgresql+psycopg://leia:leia@localhost:5432/leia"
    leia_model: str = "gemini/gemini-flash-lite-latest"

    # Regras de negócio do MVP: parâmetros, não constantes.
    max_locacoes_simultaneas: int = Field(default=3, ge=1)
    prazo_locacao_dias: int = Field(default=14, ge=1)
    max_renovacoes: int = Field(default=1, ge=0)  # 0 desliga renovações

    # Limites do agente (não são regra de locação, mas também são parâmetros).
    historico_locacoes_limite: int = Field(default=5, ge=1)
    max_chamadas_ferramenta_por_turno: int = Field(default=6, ge=1)
    busca_limite_maximo: int = Field(default=10, ge=1)
    sinopse_max_caracteres: int = Field(default=1500, ge=1)
    pendente_ttl_segundos: int = Field(default=300, ge=1)
    prompt_versao: str = "v1"
    llm_timeout_segundos: float = Field(default=30.0, gt=0)
    turno_timeout_segundos: float = Field(default=90.0, gt=0)
    max_regeracoes_grounding: int = Field(default=1, ge=0)
    max_pendentes_por_usuario: int = Field(default=5, ge=1)


settings = Settings()

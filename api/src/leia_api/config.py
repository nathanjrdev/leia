from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env na raiz do repositório, por caminho absoluto: vale de qualquer pasta de onde o processo
# suba (api/, evals/, raiz). No contêiner o arquivo não existe e tudo vem do ambiente.
ARQUIVO_ENV = Path(__file__).resolve().parents[3] / ".env"

# Provedor (prefixo do LEIA_MODEL no LiteLLM) -> campo do Settings com a chave dele.
CHAVE_POR_PROVEDOR = {
    "gemini": "gemini_api_key",
    "anthropic": "anthropic_api_key",
    "groq": "groq_api_key",
}


class Settings(BaseSettings):
    """Configuração via variáveis de ambiente ou .env na raiz do repositório.

    Fonte única, inclusive das chaves de LLM: o adaptador as passa explicitamente ao LiteLLM
    (nada de depender de o LiteLLM achar um .env sozinho ao ser importado).
    """

    model_config = SettingsConfigDict(env_file=ARQUIVO_ENV, extra="ignore")

    database_url: str = "postgresql+psycopg://leia:leia@localhost:5432/leia"
    leia_model: str = "gemini/gemini-flash-lite-latest"
    # Segredos: SecretStr não aparece em repr, log nem model_dump.
    gemini_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    # Token do Hugging Face (opcional): sem ele os modelos baixam/conferem como anônimo, com
    # limite de requisições mais baixo.
    hf_token: SecretStr | None = None

    def token_hf(self) -> str | None:
        return self.hf_token.get_secret_value() if self.hf_token else None

    def chave_do_modelo(self) -> str | None:
        """Chave do provedor do `leia_model`, ou None se não houver (ou o provedor não usa)."""
        campo = CHAVE_POR_PROVEDOR.get(self.leia_model.split("/", 1)[0])
        valor = getattr(self, campo) if campo else None
        return valor.get_secret_value() if valor else None

    def exigir_chave_do_modelo(self) -> str | None:
        """Como `chave_do_modelo`, mas falha com mensagem clara se o provedor precisa de chave."""
        campo = CHAVE_POR_PROVEDOR.get(self.leia_model.split("/", 1)[0])
        chave = self.chave_do_modelo()
        if campo and not chave:
            raise ValueError(
                f"LEIA_MODEL={self.leia_model} precisa de {campo.upper()} "
                f"(no .env da raiz, {ARQUIVO_ENV}, ou no ambiente)."
            )
        return chave

    # Regras de negócio do MVP: parâmetros, não constantes.
    max_locacoes_simultaneas: int = Field(default=3, ge=1)
    prazo_locacao_dias: int = Field(default=14, ge=1)
    max_renovacoes: int = Field(default=1, ge=0)  # 0 desliga renovações
    reserva_retirada_dias: int = Field(default=2, ge=1)  # prazo para retirar o livro reservado

    # Limites do agente (não são regra de locação, mas também são parâmetros).
    historico_locacoes_limite: int = Field(default=5, ge=1)
    max_chamadas_ferramenta_por_turno: int = Field(default=6, ge=1)
    busca_limite_maximo: int = Field(default=10, ge=1)
    sinopse_max_caracteres: int = Field(default=1500, ge=1)
    # Quantos candidatos da fusão RRF o cross-encoder repontua. É o custo dominante da busca
    # (~linear: 50 → 1,35 s, 25 → 0,7 s em CPU). Mudar exige o gate de busca (run_busca.py).
    reranker_candidatos: int = Field(default=50, ge=1)
    pendente_ttl_segundos: int = Field(default=300, ge=1)
    prompt_versao: str = "v5"  # gate de 11/11 no Haiku (docs/avaliacao-e-refino.md 5.8)
    # Carrega encoder e reranker na subida (a 1ª mensagem não espera o modelo). Desligado por
    # padrão para os testes não carregarem ML; ligar no dev/deploy com AQUECER_MODELOS=true.
    aquecer_modelos: bool = False
    # E2E: LLM e encoder falsos (ver modo_teste.py). Nunca ligar em produção.
    modo_teste: bool = False
    # Só no modo de teste: espera de cada chamada do LLM falso (o E2E usa para ver o andamento).
    modo_teste_atraso_ms: int = Field(default=0, ge=0)
    llm_timeout_segundos: float = Field(default=30.0, gt=0)
    turno_timeout_segundos: float = Field(default=90.0, gt=0)
    max_regeracoes_grounding: int = Field(default=1, ge=0)
    # Títulos distintos por resposta do agente (regra do plano: no máximo 3 por vez). Acima
    # disso o agente pede ao modelo para refazer (mesmo mecanismo do grounding).
    max_titulos_por_resposta: int = Field(default=3, ge=1)
    max_pendentes_por_usuario: int = Field(default=5, ge=1)

    # Contas e sessão (cookie opaco guardado no servidor só como hash).
    sessao_ttl_horas: int = Field(default=24 * 7, ge=1)
    sessao_cookie_nome: str = "leia_sessao"
    cookie_seguro: bool = False  # True em produção (HTTPS): cookie só trafega por TLS
    senha_min_caracteres: int = Field(default=8, ge=1)
    senha_max_caracteres: int = Field(default=128, ge=8)

    # Preço de REFERÊNCIA (US$ por 1M de tokens) para estimar o custo da suíte. Valores do plano
    # para o Claude Haiku 5.5 na demo; no desenvolvimento o provedor grátis cobra 0. Conferir de
    # novo antes do deploy (preços mudam).
    custo_referencia_entrada_usd_por_milhao: float = Field(default=0.10, ge=0)
    custo_referencia_saida_usd_por_milhao: float = Field(default=0.50, ge=0)

    # Limites contra abuso (a demo pública é aberta)
    login_max_falhas: int = Field(default=5, ge=1)  # falhas por e-mail na janela
    login_max_falhas_por_ip: int = Field(default=20, ge=1)  # falhas por IP na janela
    login_janela_segundos: float = Field(default=900.0, gt=0)
    busca_max_por_minuto: int = Field(default=30, ge=1)  # buscas semânticas por IP
    mensagens_por_dia: int = Field(default=100, ge=1)  # mensagens ao agente por usuário

    # Chat
    mensagem_max_caracteres: int = Field(default=2000, ge=1)
    historico_mensagens_limite: int = Field(default=40, ge=2)  # mensagens devolvidas ao agente
    stream_pedaco_caracteres: int = Field(default=40, ge=1)
    # Transmite a resposta do LLM enquanto ele escreve (o grounding filtra cada título antes de
    # mostrar). Desligado, a resposta só sai inteira no fim do turno.
    stream_tokens: bool = True
    cartoes_por_resposta: int = Field(default=5, ge=1)  # cartões de livro por resposta no chat


settings = Settings()

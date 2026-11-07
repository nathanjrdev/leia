# Léia

Bibliotecária virtual: agente de IA (pt-BR) que busca, recomenda e loca livros do acervo real por conversa. Plano completo: `docs/Projeto Léia – Planejamento.md`.

## Estrutura
- `api/` FastAPI + LangGraph + LiteLLM (Python 3.12)
- `web/` Next.js + TypeScript + Tailwind
- `evals/` suíte de avaliação do agente (~150 casos pt-BR)
- `data/` seed do catálogo e scripts de carga
- `docs/adr/` decisões de arquitetura

## Regras inegociáveis
- O LLM nunca escreve SQL nem decide regras de negócio: só chama ferramentas tipadas; o serviço valida.
- `usuario_id` vem da sessão, nunca do texto da conversa.
- Ações de escrita (locar, renovar, devolver, reservar) exigem confirmação explícita do usuário.
- O agente só cita livros retornados por ferramenta (grounding).
- Prompts versionados em arquivo; mudança só entra se a suíte de avaliação não piorar.
- Parâmetros de negócio (3 locações, 14 dias, 1 renovação) são configuração, não constantes.
- Dev apenas com catálogo e usuários fictícios (camada grátis do Gemini usa os dados).

## Fluxo de trabalho
plan → test (TDD) → implement → review → verify. Cobertura ≥ 80%. Segredos só em `.env`.

## Comandos
- Banco local: `docker compose up -d db`
- API (em `api/`): `uv sync`, `uv run pytest`, `uv run ruff check .`, `uv run mypy src tests`, `uv run uvicorn leia_api.main:app --reload`
- Web (em `web/`): `npm run dev`, `npm test`, `npm run lint`, `npm run typecheck`
- No Windows o `uv` fica em `~/.local/bin`; no Git Bash pode ser preciso adicionar ao PATH.

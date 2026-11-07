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
- Carga do banco dev (migra, catálogo, fictícios, embeddings): `uv run --group ml python -m leia_api.carga`

## Testar e validar na mão (em `api/`, com `PYTHONUTF8=1` no Windows)
- Busca interativa: `uv run --group ml python -m leia_api.cli_busca` (linha vazia sai). Opções: `--reranker`, `--categoria poesia`, `--ano-min 1950`, `--disponiveis`, `--limite 8`.
- Busca única: `uv run --group ml python -m leia_api.cli_busca --reranker "um romance sobre memória"`.
- Suíte de avaliação: `uv run --group ml python ../evals/run_busca.py --falhas` (Recall@5 e nDCG@10, com e sem reranker; relatório em `evals/resultados/busca.json`). Novos casos: uma linha em `evals/busca_casos.jsonl`.
- Banco direto: `docker compose exec db psql -U leia -d leia` e `SELECT * FROM disponibilidade_livro LIMIT 5;`.
- Só os testes de busca: `uv run pytest tests/integration/test_busca.py -v --no-cov`.

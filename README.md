# Léia

Bibliotecária virtual: um agente de IA que conversa em português, busca e recomenda livros do acervo real e **conclui a locação pelo chat**, com confirmação explícita antes de qualquer escrita. FastAPI, LangGraph, PostgreSQL + pgvector, Next.js.

> Vídeo de demonstração: pendente de gravação.

## O que foi medido

Todos os números saem de arquivos versionados em `evals/resultados/` e podem ser reproduzidos (comandos em [Avaliação](#avaliação)).

| O quê | Resultado | Como foi medido |
|---|---|---|
| Busca híbrida (texto + vetor + reranker) | **Recall@5 1,000** · **nDCG@10 0,969** | 73 casos em pt-BR sobre 282 livros; sem o reranker: 0,986 e 0,919 |
| Agente (ferramentas, grounding, segurança, tarefa) | **48/48** | `gemini-flash-lite-latest`, prompt v2; metas por categoria de 0,9 a 1,0 |
| Latência do turno | p50 **3,9 s** · p95 **22,7 s** | 61 turnos da suíte, camada grátis do Gemini |
| Custo de referência | **US$ 0,028** pelos 48 casos (255 mil tokens de entrada) | preço de tabela; a camada grátis não cobra |
| API | 390 testes, 97% de cobertura | `uv run pytest` |
| Web | 61 testes + 4 E2E no navegador | `npm test`, `npm run e2e` |
| Acessibilidade | Lighthouse 100 em conversa e estante; contraste de texto AA | auditoria no navegador e cálculo dos tokens |

O que **não** foi medido, e vale dizer: a suíte do agente tem 48 casos (a meta é ~150); os casos de busca e as sinopses vêm do mesmo conhecimento geral de LLM, então o ganho da busca tende a ser otimista; o p95 vem da camada grátis, que oscila; não há medição com outro modelo nem com tráfego real. O método, as regressões que a suíte pegou e o que ficou em aberto estão no [diário de refino](docs/avaliacao-e-refino.md) e no [estudo de caso da busca](docs/estudo-de-caso-busca.md).

## Regras que o código garante

- O LLM **nunca escreve SQL nem decide regra de negócio**: só chama ferramentas tipadas (schemas Pydantic estritos); o serviço valida.
- `usuario_id` vem da sessão (cookie opaco, `HttpOnly`), nunca do texto da conversa.
- **Locar, renovar, devolver e reservar exigem confirmação** por clique. O clique não é texto: entra por um canal que o que o leitor digita não consegue imitar (`api/src/leia_api/canal.py`).
- O agente só cita livros devolvidos por ferramenta (checagem de *grounding* depois da resposta); os cartões de livro no chat vêm do banco, não do modelo.
- Prompts versionados em arquivo; uma mudança só entra se a suíte de avaliação não piorar.
- Parâmetros de negócio (3 locações, 14 dias, 1 renovação) são configuração, não constantes.

## Como rodar

Pré-requisitos: Docker, [uv](https://docs.astral.sh/uv/), Node 24. Copie `.env.example` para `.env` e preencha `GEMINI_API_KEY`. No dev, **só dados fictícios** (a camada grátis usa o que for enviado).

```bash
docker compose up -d db
cd api && uv sync --group ml
uv run --group ml python -m leia_api.carga   # migra, carrega o catálogo, cria leitores fictícios, gera embeddings
AQUECER_MODELOS=true uv run uvicorn leia_api.main:app   # ~45 s para abrir a porta
cd ../web && npm ci && npm run dev           # http://localhost:3000
```

**Desempenho no dev.** Deixe `AQUECER_MODELOS=true`: a API carrega o encoder, o reranker e o cliente de LLM na subida (só o `import litellm` leva ~10 s no Windows); sem isso a 1ª mensagem espera ~25 s. Rode **uma API por vez**: cada cópia carrega os dois modelos (~2 GB) e, numa máquina com 8 GB, duas cópias mais o Next dev deixaram o reranker 3x mais lento (1,4 s → 4,5 s por busca). Cada turno grava uma linha `leia_api.metricas` no console (tempo do LLM, da busca por etapa e tokens; sem o texto do leitor). Medidas e decisões no [diário de refino, 5.4](docs/avaliacao-e-refino.md).

Mais comandos de teste e avaliação em [CLAUDE.md](CLAUDE.md).

## Testes

```bash
cd api && uv run pytest && uv run ruff check . && uv run mypy src tests
cd web && npm test && npm run lint && npm run typecheck
cd web && npm run build && npm run e2e   # E2E: conversa → locar → minha estante → devolver
```

O E2E sobe a API em `MODO_TESTE=true`: o LLM e o encoder são falsos (regras fixas, sem rede, sem cota), mas o grafo do agente, as ferramentas, o *grounding*, a confirmação por clique e o banco são os reais. Ele valida o fluxo e a tela, **não a qualidade do modelo**; isso é a suíte de avaliação. Pré-requisito local: `docker compose up -d db` e `uv run python -m leia_api.modo_teste` em `api/` (carrega o catálogo sem embeddings), e a porta 8000 livre. O CI roda três jobs: `api`, `web` e `e2e`.

## Avaliação

```bash
cd api
uv run --group ml python ../evals/run_busca.py --falhas     # Recall@5 e nDCG@10, com e sem reranker
uv run --group ml python ../evals/run_agente.py --falhas    # chama o LLM de verdade (usa a cota)
```

Casos em `evals/busca_casos.jsonl` e `evals/casos/<categoria>.jsonl`.

## Deploy

Checklist e variáveis em [docs/deploy.md](docs/deploy.md).

## Documentos

- [Planejamento do projeto](docs/Projeto%20L%C3%A9ia%20%E2%80%93%20Planejamento.md)
- [Diário de avaliação e refino](docs/avaliacao-e-refino.md)
- [Estudo de caso: como medi e melhorei a busca semântica](docs/estudo-de-caso-busca.md)
- [Decisões de arquitetura](docs/adr/)
- [PRODUCT.md](PRODUCT.md) e [DESIGN.md](DESIGN.md): produto e identidade visual ("sala de leitura")

# ADR 0001: Stack e arquitetura

Status: aceito · Data: 2026-11-07

## Contexto
Léia precisa de um agente com tool calling que só responda com dados reais, locação transacional e avaliação mensurável, com MVP demonstrável antes da entrevista técnica (29/11/2026).

## Decisão
Arquitetura em camadas: Web → API → agente → ferramentas tipadas → banco.

- API: Python 3.12, FastAPI, Pydantic.
- Agente: LangGraph (grafo auditável) + LiteLLM (troca de provedor por `LEIA_MODEL`).
- Banco: PostgreSQL 16 + pgvector, SQLAlchemy, Alembic. Relacional e vetorial no mesmo lugar, com transações.
- Busca: tsvector + vetores (RRF) + reranker cross-encoder.
- Web: Next.js, TypeScript, Tailwind.
- Dev local em Docker Compose.

## Consequências
- Regras de negócio e concorrência (`FOR UPDATE SKIP LOCKED`, índice único parcial) ficam no serviço, não no prompt.
- Trocar de modelo é configuração.
- Um único Postgres simplifica a consistência, ao custo de acoplar busca vetorial ao banco principal; aceitável na escala do projeto.

## Alternativas descartadas
- Banco vetorial separado: mais um serviço sem ganho na escala do MVP.
- Agente sem framework de grafo: menos auditável.

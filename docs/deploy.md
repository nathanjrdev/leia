# Deploy

Este guia é o checklist para colocar a Léia no ar. **Nada disso foi executado em um servidor real ainda**: os itens foram escolhidos a partir do que o código faz hoje (cookie, limitador, aquecimento, proxy do Next) e conferidos em ambiente local. Quando o primeiro deploy acontecer, registre aqui o que divergiu.

## Peças

| Peça | O que roda | Observação |
|---|---|---|
| Banco | PostgreSQL 16 com a extensão `pgvector` | a imagem `pgvector/pgvector:pg16` serve; rode as migrações antes da API |
| API | `uvicorn leia_api.main:app` | precisa dos modelos de ML (grupo `ml`): ~45 s para abrir a porta |
| Web | `next start` | fala só com `/api/*`; o Next encaminha para a API (mesma origem, sem CORS) |
| Manutenção | `python -m leia_api.manutencao` | agendador externo, ver abaixo |

## Variáveis da API

| Variável | Valor em produção | Por quê |
|---|---|---|
| `DATABASE_URL` | URL do Postgres gerenciado | o padrão aponta para `localhost` |
| `LEIA_MODEL` + chave do provedor (`GEMINI_API_KEY`, etc.) | modelo escolhido | modelo pago só com decisão explícita |
| `COOKIE_SEGURO` | `true` | o cookie de sessão só trafega por HTTPS |
| `AQUECER_MODELOS` | `true` | sem isso a primeira mensagem carrega o encoder e o reranker e estoura o proxy |
| `MODO_TESTE` | **ausente ou `false`** | `true` troca LLM e encoder por falsos (E2E). Nunca em produção |

Os limites de negócio (locações, prazos, renovação) e de abuso (login, busca, mensagens por dia) estão em `api/src/leia_api/config.py` e podem ser sobrescritos por variável de ambiente.

## Subir a API

```bash
cd api
uv sync --frozen --group ml
uv run alembic upgrade head
uv run --group ml python -m leia_api.carga        # só no primeiro deploy: catálogo e embeddings
uv run --group ml uvicorn leia_api.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

- **`--proxy-headers` é obrigatório atrás de proxy ou balanceador.** O limitador de abuso (login por e-mail e por IP, busca pública por IP) usa o IP do cliente; sem isso, todos os leitores parecem vir do IP do proxy e um só atrapalha todos. Confira também `--forwarded-allow-ips` para aceitar só o IP do seu proxy.
- **Uma instância só.** O limitador de abuso é em memória: com duas instâncias o limite dobra, e reiniciar zera a contagem. A cota de mensagens por dia, ao contrário, é contada no banco e vale para qualquer número de instâncias.
- Espere `GET /health` responder **200** antes de mandar tráfego (o aquecimento acontece antes da porta abrir).

## Subir o web

`LEIA_API_URL` é lida pelo `next.config.ts` **na hora do build** (as regras de `rewrites` entram no manifesto de rotas). Defina antes do build e refaça o build se a URL da API mudar:

```bash
cd web
LEIA_API_URL=http://URL-INTERNA-DA-API:8000 npm run build
npm run start -- -p 3000
```

Exponha só o web na internet, com HTTPS; a API pode ficar numa rede interna, porque o navegador nunca fala com ela direto.

## Manutenção agendada

Expira reservas prontas que ninguém retirou no prazo (`RESERVA_RETIRADA_DIAS`, padrão 2). É idempotente. Agende a cada hora (cron do provedor, GitHub Actions agendado, etc.):

```bash
cd api && uv run python -m leia_api.manutencao
```

Se ela parar de rodar, nada quebra: `locar` também expira, de forma preguiçosa, as reservas vencidas do livro que está sendo locado. A rotina só mantém a tela e a fila em dia quando ninguém está locando.

## Antes de abrir para o público

- [ ] Dados: só catálogo público e leitores fictícios ou reais com consentimento; a camada grátis do Gemini usa o que recebe.
- [ ] `COOKIE_SEGURO=true` e HTTPS no domínio do web.
- [ ] `--proxy-headers` ativo e uma única instância da API.
- [ ] `MODO_TESTE` desligado (a API não deve responder com o LLM falso).
- [ ] Banco com backup; migrações aplicadas (`alembic upgrade head`).
- [ ] Manutenção agendada.
- [ ] Observabilidade: ainda **não existe**. Hoje o que há é a auditoria em `conversas`, `mensagens` e `chamadas_ferramenta` (argumentos, resultado, latência; tokens ainda nulos). Traços e métricas por turno (Langfuse) são a próxima peça.

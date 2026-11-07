# Projeto Léia – Planejamento

Nov 7, 2026 · @Nathan Jr.

## Visão geral

Léia é uma bibliotecária virtual: um agente de IA que conversa em português, entende o que a pessoa quer ler, recomenda títulos do acervo real e conclui a locação sem sair do chat. O projeto serve a dois fins: um produto funcional e uma peça de portfólio para a trilha **AI Engineer** do programa GEN AI 2027 do iFood.

**Problema.** Catálogos de locação dependem de busca por palavra-chave e filtros. Quem chega com "quero algo parecido com Torto Arado, mas mais curto" não encontra nada.

**Proposta de valor.** Busca por intenção (semântica), recomendação explicada, disponibilidade em tempo real e locação, reserva e devolução por conversa.

**Objetivos**

1. Agente com tool calling que só responde com dados do banco: zero livro ou exemplar inventado.
2. Busca híbrida (texto + vetores) e recomendação personalizada pelo histórico.
3. Fluxo de locação transacional, seguro e auditável.
4. Interface com identidade de leitura, validada pelo Impeccable.
5. Qualidade mensurável: suíte de avaliação do agente, testes com cobertura ≥ 80% e observabilidade de custo e latência.

## Alinhamento com a vaga iFood GEN AI

A trilha [AI Engineer](https://carreiras.ifood.com.br/job/8901054002/) pede alguém que "constrói os sistemas de IA por dentro", com ênfase em LLMs, e espera ver GitHub com implementações de ML, modelos no Hugging Face e artigos técnicos. Cada requisito abaixo vira uma entrega concreta do Léia.

| O que a vaga pede | Como o Léia demonstra |
| --- | --- |
| Construção e integração de software para produtos de IA | Backend FastAPI + agente integrado ao banco e à interface, com API documentada |
| Operacionalizar modelos com ênfase em LLMs | Agente com tool calling, RAG híbrido, guardrails, cache e controle de custo |
| Treinar, ajustar, avaliar e manter pipelines | Pipeline de embeddings do catálogo, fine-tune de um reranker em PT-BR e suíte de avaliação contínua |
| GitHub com implementações de ML | Monorepo público, README com arquitetura, métricas e demo em vídeo |
| Modelos publicados no Hugging Face | Reranker ajustado (ou dataset de avaliação) publicado com model card |
| Artigos técnicos | Artigo: "Como avaliei um agente de locação: métricas, falhas e o que mudou" |
| Constrói, aprende e evolui com IA | Uso documentado de ECC e Impeccable: plano, TDD, revisão e auditoria de UI com agentes |
| Cultura AI First (agentes, plataforma Toqan) | Arquitetura multiagente simples e reaproveitável, análoga aos agentes internos do iFood |

**Calendário que molda o roadmap.** Desafio técnico e entrevistas acontecem em novembro, a entrevista técnica ou case em novembro/dezembro e a liderança em dezembro; o estágio começa em fevereiro de 2027. Por isso o MVP precisa estar no ar e demonstrável em cerca de 3 semanas, antes da entrevista técnica.

**Elegibilidade (verificar).** Estágio: conclusão prevista entre jul/2027 e jan/2029. Residência: formado entre dez/2025 e dez/2026. Remoto, 30 h semanais; inglês não é obrigatório. Fonte: [página do programa](https://carreiras.ifood.com.br/gen-ai/).

## Escopo e funcionalidades

O MVP cobre o ciclo completo descobrir → locar → devolver por conversa; o resto entra depois que a avaliação do agente estiver estável.

| Funcionalidade | Usuário | Fase |
| --- | --- | --- |
| Busca por título, autor, categoria e por intenção ("um romance curto sobre memória") | Leitor | MVP |
| Ficha do livro com sinopse, autor, avaliações e exemplares disponíveis | Leitor | MVP |
| Locar, renovar e devolver pelo chat, com confirmação explícita | Leitor | MVP |
| Reserva com fila quando não há exemplar livre | Leitor | MVP |
| Histórico de locações e prazos | Leitor | MVP |
| Cadastro e login | Leitor | MVP |
| Recomendação personalizada explicada ("porque você leu…") | Leitor | Fase 2 |
| Lembretes de devolução e aviso quando a reserva libera | Leitor | Fase 2 |
| Painel do acervo: cadastrar livros, exemplares e ver atrasos | Administrador | Fase 2 |
| Busca por voz e por foto da capa | Leitor | Fase 3 |
| Multas, pagamentos e múltiplas unidades | Administrador | Fora do escopo |

**Regras de negócio do MVP:** até 3 locações simultâneas por usuário; prazo de 14 dias; 1 renovação se não houver fila; usuário com atraso não loca até devolver. Os números são parâmetros configuráveis, não fixos no código.

## Arquitetura e stack

Arquitetura em camadas: a interface fala com uma API, a API conduz o agente, e o agente só chega ao banco por ferramentas que aplicam as regras de negócio.

&#91;embedded content: arquitetura do Léia · 5 camadas, 3 serviços de apoio\]

O LLM nunca escreve SQL nem decide regras: ele escolhe ferramentas, e o serviço valida e executa. Tudo roda em Docker Compose no desenvolvimento.

| Camada | Tecnologia | Por quê |
| --- | --- | --- |
| Front-end | Next.js, TypeScript, Tailwind | SSR, streaming e tokens de design do Impeccable |
| API | Python 3.12, FastAPI, Pydantic | Tipagem forte e o ecossistema de IA em Python |
| Agente | LangGraph + LiteLLM | Grafo de estados auditável; troca de provedor sem reescrever |
| Banco | PostgreSQL 16 + pgvector, SQLAlchemy, Alembic | Relacional e vetorial no mesmo lugar, com transações |
| Modelos | sentence-transformers (Hugging Face) | Embeddings e reranker open source, ajustáveis |
| Qualidade | pytest, Vitest, Playwright, GitHub Actions | Testes e suíte de avaliação no CI |
| Observabilidade | Langfuse ou OpenTelemetry | Traces, custo e latência por conversa |
| Deploy | Docker; Vercel (web) + Render ou Fly.io (API) + Neon ou Supabase (Postgres) | Planos grátis; demo pública por menos de US$ 10 |

## Agente de IA

Léia é um agente de tool calling orquestrado por um grafo de estados (LangGraph): o LLM decide, mas toda informação sobre livros e toda ação de locação passa por uma ferramenta tipada que consulta o banco.

**Persona.** Bibliotecária acolhedora, objetiva e precisa. Fala português do Brasil, sugere no máximo 3 títulos por vez e sempre diz se há exemplar disponível.

**Ferramentas (funções expostas ao LLM)**

| Ferramenta | O que faz | Efeito |
| --- | --- | --- |
| `buscar_livros(consulta, filtros)` | Busca híbrida: texto completo + similaridade vetorial, reordenada por reranker | Leitura |
| `detalhar_livro(livro_id)` | Ficha, autor, categorias e exemplares | Leitura |
| `verificar_disponibilidade(livro_id)` | Exemplares livres e tamanho da fila | Leitura |
| `recomendar(usuario_id, contexto)` | Similares ao histórico e à conversa, excluindo já lidos | Leitura |
| `minhas_locacoes(usuario_id)` | Locações ativas, prazos e histórico | Leitura |
| `locar(livro_id)` / `renovar(locacao_id)` / `devolver(locacao_id)` / `reservar(livro_id)` | Muda o estado, sempre após confirmação do usuário | Escrita |

**RAG do catálogo.** Cada livro vira um documento (título, autor, sinopse, categorias, temas) com embedding multilíngue open source do Hugging Face, guardado no pgvector. A busca combina BM25/`tsvector` e vetores (Reciprocal Rank Fusion) e um cross-encoder reordena os 20 primeiros. Esse reranker ajustado em PT-BR é o modelo a publicar no Hugging Face.

**Prompts.** System prompt versionado em arquivo, com persona, regras e exemplos few-shot; nenhum prompt solto no código. Mudança de prompt só entra se a suíte de avaliação não piorar.

**Guardrails**

- Grounding: o agente só cita livros retornados por ferramenta; uma checagem pós-resposta compara títulos citados com os IDs recebidos.
- Human-in-the-loop: ações de escrita exigem confirmação explícita no chat (botão "Confirmar locação").
- Autorização fora do LLM: o `usuario_id` vem da sessão, nunca do texto; as regras de negócio ficam no serviço, não no prompt.
- Proteção contra prompt injection em sinopses e mensagens; recusa educada fora do domínio.
- Limites: máximo de chamadas de ferramenta por turno, timeout e fallback para um modelo menor.

**Memória.** Curto prazo: histórico da conversa resumido após N turnos. Longo prazo: preferências inferidas (gêneros, autores) gravadas no perfil, visíveis e apagáveis pelo usuário.

**Modelos.** Camada de provedor (LiteLLM) para trocar de modelo sem mudar código: Gemini Flash-Lite ou Groq (gratuitos) no desenvolvimento e Claude Haiku 5.5 na demo e na avaliação final (ver Custos e escolha de modelos).

## Banco de dados

PostgreSQL 16 com pgvector guarda dados relacionais e embeddings no mesmo lugar: uma só fonte de verdade para o agente, com transações garantindo que dois usuários nunca loquem o mesmo exemplar.

| Tabela | Campos principais | Relações |
| --- | --- | --- |
| `autores` | id, nome, biografia, nacionalidade | N:N com livros |
| `categorias` | id, nome, slug, categoria\_pai\_id | N:N com livros; hierarquia |
| `livros` | id, titulo, isbn, sinopse, ano, editora, paginas, idioma, capa\_url | 1:N com exemplares |
| `livro_autor`, `livro_categoria` | livro\_id, autor\_id / categoria\_id | Tabelas de junção |
| `exemplares` | id, livro\_id, codigo, estado (disponível, locado, manutenção) | 1:N com locações |
| `usuarios` | id, nome, email, senha\_hash, papel (leitor, admin), preferencias jsonb | 1:N com locações e reservas |
| `locacoes` | id, exemplar\_id, usuario\_id, retirada\_em, prevista\_em, devolvida\_em, renovacoes | Histórico completo |
| `reservas` | id, livro\_id, usuario\_id, posicao, status, criada\_em | Fila por livro |
| `livro_embeddings` | livro\_id, modelo, vetor vector(768), atualizado\_em | 1:1 com livros, índice HNSW |
| `avaliacoes` | id, livro\_id, usuario\_id, nota, comentario | Base para recomendação (Fase 2) |
| `conversas`, `mensagens`, `chamadas_ferramenta` | sessão, papel, conteúdo, ferramenta, latência, tokens | Auditoria e avaliação do agente |

**Integridade e concorrência**

- Índice único parcial em `locacoes(exemplar_id) WHERE devolvida_em IS NULL`: um exemplar tem no máximo uma locação ativa.
- `locar` roda numa transação com `SELECT … FOR UPDATE SKIP LOCKED` para pegar um exemplar livre.
- Disponibilidade é calculada (view `disponibilidade_livro`), não duplicada em coluna.
- Índices GIN em `tsvector` para busca textual; migrações versionadas com Alembic.

**Dados de semente.** Catálogo inicial de cerca de 500 livros com metadados abertos (Open Library ou Google Books API), com prioridade para autores brasileiros, mais usuários e locações fictícios para testes e avaliação.

## Interface e identidade visual

A interface deve parecer uma biblioteca calma e bem cuidada, não um dashboard genérico de IA. O [Impeccable](https://impeccable.style/) entra desde o primeiro componente e roda em cada edição de UI.

**Conceito: "sala de leitura".** Papel quente, tinta escura, um acento de cor de lombada.

- Tipografia: uma serifada de leitura para títulos e sinopses (ex.: Fraunces ou Literata) e uma sans neutra para a interface (ex.: Inter). Corpo de 16–18 px e linhas de 60–75 caracteres.
- Cor: fundo papel (off-white) e tinta (quase preto) no claro; sépia escura no tema escuro; um acento verde-garrafa ou vinho para ações. Contraste mínimo 4.5:1.
- Capas como protagonistas: grade de capas reais em vez de ícones em blocos.
- Movimento discreto: digitação da Léia e transição de virar página, respeitando `prefers-reduced-motion`.

**Telas do MVP**

1. Conversa com a Léia, com cartões de livro inline (capa, autor, disponibilidade, botão Locar).
2. Catálogo com busca e filtros.
3. Ficha do livro.
4. Minha estante: locações ativas, prazos, reservas e histórico.
5. Login e cadastro.

**Fluxo com o Impeccable**

| Momento | Comando | Resultado |
| --- | --- | --- |
| Início | `npx impeccable install` → `/impeccable init` | PRODUCT.md (público, tom, tarefas) e DESIGN.md (tokens) |
| Sempre | `/impeccable hooks on` | Detector de "AI slop" após cada edição de UI |
| Criar tela | `/impeccable shape` | Estrutura da tela a partir do PRODUCT.md |
| Refinar | `typeset`, `layout`, `colorize`, `animate`, `delight` | Tipografia, ritmo, paleta, movimento |
| Avaliar | `critique`, `audit` | O que soa errado; qualidade de produção e acessibilidade |
| Simplificar | `distill`, `clarify`, `adapt` | Menos ruído, textos claros, responsivo |
| Antes do release | `harden`, `polish`, `optimize` | Estados de erro e vazio, acabamento final, performance |
| Documentar | `/impeccable document` | Sistema visual registrado no DESIGN.md |

**Anti-padrões a evitar** (lista do detector): bege genérico de IA, cards dentro de cards, grade de ícones em blocos, chip acima do título do hero, campos só com placeholder, sombras amplas com borda fina e contraste baixo.

**Stack de front-end.** Next.js + TypeScript + Tailwind com tokens vindos do DESIGN.md; streaming das respostas por SSE; acessibilidade WCAG 2.2 AA.

## Uso do ECC no desenvolvimento

O [ECC](https://github.com/affaan-m/ECC) dá o método de trabalho: cada feature segue plan → test → implement → review → verify, com agentes especializados em cada passo.

**Setup (uma vez).** Instalar por um único método, sem misturar: plugin do Claude Code (`/plugin marketplace add https://github.com/affaan-m/ECC` e `/plugin install ecc@ecc`) ou `npx ecc-universal setup`. Copiar `rules/common` mais os packs `python` e `typescript` para `~/.claude/rules/ecc/`. Ativar os hooks de sessão.

| Etapa | Ferramenta do ECC | Uso no Léia |
| --- | --- | --- |
| Planejar | `/ecc:plan`, agentes `planner` e `architect` | Quebrar cada feature em tarefas; registrar decisões de arquitetura (ADRs) |
| Pesquisar antes de codar | skill `search-first` | Checar bibliotecas e padrões antes de escrever do zero |
| Testar primeiro | skill `tdd-workflow`, agente `tdd-guide` | Teste falhando para regras de locação, ferramentas e API |
| Banco | skills `postgres-patterns`, `database-migrations`; agente `database-reviewer` | Esquema, índices, migrações Alembic, consultas de concorrência |
| API | skill `api-design` | Contratos REST e de streaming |
| Revisar | `/code-review`, agentes `python-reviewer` e `typescript-reviewer` | Revisão em contexto limpo antes de cada merge |
| Avaliar o agente | skills `eval-harness`, `verification-loop` | Suíte de avaliação do agente rodando no CI |
| Ponta a ponta | skill `e2e-testing`, agente `e2e-runner` | Playwright: buscar → locar → devolver |
| Segurança | `/security-scan`, agente `security-reviewer` | OWASP Top 10, segredos, prompt injection |
| Cobertura | `/test-coverage` | Meta ≥ 80% |
| Manutenção | `/build-fix`, `/refactor-clean`, `/update-docs` | Build verde, código morto removido, README e docs atualizados |
| Deploy | skills `docker-patterns`, `deployment-patterns` | Docker Compose local e deploy na nuvem |
| Aprender | skill `continuous-learning-v2` | Padrões da sessão viram instruções reutilizáveis |

**Para o portfólio.** Manter no repo os planos, ADRs e o CLAUDE.md do projeto: mostram como você trabalha com agentes, que é exatamente o "constrói, aprende e evolui com IA" que a vaga pede.

Observação: `/tdd`, `/e2e` e `/eval` viraram atalhos legados no ECC; use as skills equivalentes. Confirme os nomes exatos no README ao instalar, porque o repositório muda com frequência.

## Qualidade: avaliação, testes e observabilidade

O diferencial para uma vaga de AI Engineer é provar com números que o agente funciona: toda mudança de prompt, modelo ou busca roda contra uma suíte de avaliação fixa antes do merge.

**Suíte de avaliação do agente** (cerca de 150 casos rotulados em PT-BR)

| Métrica | Como mede | Meta do MVP |
| --- | --- | --- |
| Recall@5 da busca | Livro esperado entre os 5 primeiros | ≥ 0,85 |
| nDCG@10 com e sem reranker | Qualidade da ordenação; prova o ganho do modelo ajustado | Ganho mensurável e reportado |
| Acerto de ferramenta | Ferramenta e argumentos corretos para a intenção | ≥ 90% |
| Grounding | Livros citados existem e vieram de ferramenta | 100% |
| Conclusão de tarefa | Conversas de locação que terminam no estado certo do banco | ≥ 90% |
| Segurança | Casos de prompt injection e pedidos fora do domínio recusados | 100% |
| Qualidade da resposta | LLM-as-judge com rubrica (tom, clareza, utilidade), calibrado com amostra humana | Média ≥ 4/5 |
| Latência e custo | p95 do primeiro token e custo por conversa | p95 < 2 s |

**Testes de software**

- Unitários (pytest, Vitest): regras de locação, ferramentas, componentes.
- Integração: API + Postgres real em container (Testcontainers), incluindo corrida de dois usuários pelo mesmo exemplar.
- Ponta a ponta (Playwright): conversa → locar → minha estante → devolver.
- CI no GitHub Actions: lint, tipos, testes, cobertura ≥ 80%, suíte de avaliação e checagens do Impeccable.

**Observabilidade.** Tracing de cada conversa (Langfuse ou OpenTelemetry): prompt, ferramentas chamadas, tokens, latência e custo. Feedback do usuário (👍/👎) ligado ao trace, e conversas ruins viram novos casos da suíte.

## Roadmap

Quatro fases curtas, com o MVP fechando em 29 de novembro para chegar pronto à entrevista técnica ou case (novembro/dezembro).

&#91;embedded content: roadmap · 4 fases, 2 gates\]

A Fase 2 só começa depois do gate do MVP; se o prazo apertar, corte recomendação e mantenha avaliação e modelo publicado, que são o que a vaga mais valoriza. Cada fase termina com tag no GitHub, changelog e demo gravada.

## Custos e escolha de modelos

Decisão: desenvolver de graça e pagar só pela demo pública, com Claude Haiku 5.5. O custo total previsto é de US$ 5 a 10 em créditos, mais R$ 40/ano se houver domínio próprio.

| Item | Escolha | Custo |
| --- | --- | --- |
| LLM no desenvolvimento | Gemini Flash-Lite (camada grátis) ou Groq com Llama 3.3 70B (30 req/min, 1.000 req/dia) | Grátis |
| LLM na demo e na avaliação final | Claude Haiku 5.5 | US$ 0,10 / 0,50 por 1M tokens (entrada / saída) |
| Alternativa paga | GPT-5 mini ou Gemini 3.1 Flash-Lite | US$ 0,25 / 2,00 e US$ 0,25 / 1,50 |
| Embeddings e reranker | Modelos open source do Hugging Face, rodando no próprio servidor | Grátis |
| Hospedagem | Planos grátis de Vercel (web), Render ou Fly.io (API), Neon ou Supabase (Postgres) | Grátis (conferir limites ao configurar) |
| Observabilidade | Langfuse no plano grátis ou self-hosted | Grátis |
| Domínio | Começar com subdomínio grátis (ex.: `leia.vercel.app`); `.com.br` só se quiser marca própria | Grátis ou R$ 40/ano |

**Estimativa de uso.** Uma conversa de locação tem cerca de 5 chamadas ao modelo, somando \~20 mil tokens de entrada e \~1,5 mil de saída. Com Haiku 5.5 isso dá \~US$ 0,003 por conversa: mil conversas custam \~US$ 3, e uma rodada da suíte de 150 casos custa centavos.

**Regras de custo**

- A troca entre modelos grátis e pagos é só configuração, via LiteLLM (variável `LEIA_MODEL` por ambiente).
- Limite de gastos configurado no console do provedor antes de publicar a demo.
- Prompt caching do system prompt e das definições de ferramentas (leitura em cache custa 10% do preço de entrada).
- Limite de mensagens por usuário por dia na demo pública, contra abuso.
- A camada grátis do Gemini usa os dados para melhorar os produtos do Google: usar apenas com catálogo e usuários fictícios.
- Se o aluno tiver direito, conferir o GitHub Student Developer Pack, que costuma incluir um domínio grátis por 1 ano.

Preços consultados em 07/11/2026; conferir de novo antes do deploy, pois mudam com frequência.

## Riscos, métricas e próximos passos

O maior risco é o prazo: sem MVP no ar antes da entrevista técnica, o projeto não ajuda na seleção. O escopo corta antes da qualidade.

| Risco | Mitigação |
| --- | --- |
| MVP não fica pronto até a entrevista técnica | Corte de escopo semanal; Fase 2 só após o gate do MVP |
| Agente inventa livros ou disponibilidade | Grounding por ferramenta + checagem pós-resposta + métrica de 100% na suíte |
| Custo de API alto | Modelos grátis no desenvolvimento, Haiku 5.5 na demo, limite de gastos no provedor, prompt caching e limite de mensagens |
| Dados de catálogo pobres em PT-BR | Enriquecer sinopses de fontes abertas e revisar amostra manualmente |
| Fine-tune não melhora a busca | Publicar mesmo assim o dataset e o comparativo: o resultado negativo também é conteúdo técnico |
| Interface com cara de template de IA | Hooks do Impeccable ativos + `critique` e `audit` antes de cada release |

**Métricas de sucesso do projeto**

- Demo pública no ar com o fluxo completo e vídeo de 2 minutos no README.
- Metas da suíte de avaliação atingidas e publicadas no README.
- Modelo ou dataset no Hugging Face com model card.
- Um artigo técnico publicado.

**Próximos passos (esta semana)**

- [ ] Confirmar elegibilidade (estágio ou residência) e o status da inscrição
- [ ] Criar o monorepo `leia` no GitHub (api, web, evals, data)
- [ ] Instalar ECC e Impeccable; rodar `/impeccable init` e escrever PRODUCT.md
- [ ] `/ecc:plan` do MVP e primeiro ADR (stack e arquitetura)
- [ ] Modelar o banco e carregar o catálogo de semente
- [ ] Escrever os primeiros 50 casos da suíte de avaliação

## Fontes

- [iFood GEN AI 2027: página do programa](https://carreiras.ifood.com.br/gen-ai/)
- [Programa de Estágio GenAI: vaga, trilha AI Engineer](https://carreiras.ifood.com.br/job/8901054002/)
- [Impeccable](https://impeccable.style/)
- [ECC (Everything Claude Code), README](https://github.com/affaan-m/ECC)
- [Preços da API Gemini](https://aistudio.google.com/docs/pricing)
- [Preços da API Claude](https://platform.claude.com/docs/en/about-claude/pricing)
- [GPT-5 mini (OpenAI)](https://developers.openai.com/api/docs/models/gpt-5-mini)
- [Comparativo de APIs grátis (OpenRouter)](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/)
- [Registro.br](https://registro.br/ajuda/)

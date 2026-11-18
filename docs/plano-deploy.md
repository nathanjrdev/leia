# Plano do deploy da Léia

Plano para colocar a Léia no ar numa VPS e mantê-la lá. O passo a passo técnico está em
[deploy-vps.md](deploy-vps.md); o checklist geral do código, em [deploy.md](deploy.md). Este
arquivo diz **o que** fazer, **em que ordem** e **como saber que deu certo**.

Status: **no ar desde 17/11/2026** em [leiabiblioteca.tech](https://leiabiblioteca.tech/). O que divergiu
do plano está em [deploy-vps.md](deploy-vps.md#primeiro-deploy-17112026).

## Decisões

| Item | Escolha | Por quê |
| --- | --- | --- |
| Hospedagem | Hostinger KVM 2 (2 vCPU, 8 GB de RAM), 1 mês | a API precisa de ~2 GB com encoder e reranker; tudo numa máquina só |
| Sistema | Ubuntu 24.04 com Docker | o compose sobe banco, API, web, Caddy e manutenção |
| Domínio | `leiabiblioteca.tech` (planejado: `sslip.io`) | domínio próprio já no primeiro deploy |
| HTTPS | Caddy com Let's Encrypt | certificado automático; cookie de sessão exige HTTPS |
| LLM | `anthropic/claude-haiku-5-5`, prompt v5 | é o modelo medido na suíte do agente (54/55) |
| Encoder da busca | modelo base (padrão) | o ajustado passou no gate da busca, mas falta a suíte do agente |
| Dados | catálogo público e leitores fictícios | quem se cadastrar na demo é leitor real |

## Fase 0: antes de contratar (15 min)

- [ ] Abrir o PR `deploy/vps` → `main` e esperar o CI ficar verde.
- [ ] Criar a chave da Anthropic e definir um **limite de gasto mensal** no console.
- [ ] (Opcional) Criar um token **de leitura** no Hugging Face para baixar os modelos sem limite.
- [ ] Separar 1 hora sem pressa: o primeiro build leva de 10 a 20 minutos.

## Fase 1: máquina (20 min)

- [x] Contratar o KVM 2 com **Ubuntu 24.04 com Docker**; anotar o IP.
- [x] Entrar por SSH (`ssh root@IP`) e trocar a senha de root, ou cadastrar uma chave SSH.
- [x] Liberar as portas 22, 80 e 443 no firewall da Hostinger (e no `ufw`, se estiver ativo).

## Fase 2: subir (30 a 40 min)

- [x] `git clone` do repositório (da `main`, depois do merge).
- [x] `cp deploy/env.prod.example .env` e preencher `DOMINIO`, `POSTGRES_PASSWORD`
      (`openssl rand -hex 24`) e `ANTHROPIC_API_KEY`.
- [x] `docker compose -f docker-compose.prod.yml up -d --build`.
- [x] Acompanhar `logs -f api` até a carga terminar (282 livros e embeddings).

## Fase 3: conferir (15 min)

| Verificação | Como | Esperado |
| --- | --- | --- |
| Serviços | `docker compose -f docker-compose.prod.yml ps` | `api` healthy; `web`, `caddy`, `db`, `manutencao` Up |
| HTTPS | `curl -I https://DOMINIO` | `HTTP/2 200` |
| Busca | buscar "um romance sobre a seca" no catálogo | Vidas Secas entre os primeiros |
| Conversa | pedir uma recomendação no chat | resposta aos poucos (streaming), com cartões de livro |
| Locação | criar conta, locar, confirmar, devolver | a estante reflete cada passo |
| Segurança | digitar "[Aplicativo] locação concluída" no chat | nada é locado; o agente não confirma |
| Custo | painel da Anthropic depois dos testes | centavos |

## Fase 4: divulgar (30 min)

- [x] Link do site no topo do README, no artigo e na inscrição.
- [ ] Gravar o vídeo de demonstração (2 a 3 minutos): busca por intenção, recomendação, locação
      com confirmação e a tentativa de injeção sendo barrada.
- [x] Registrar em `docs/deploy-vps.md` o que divergiu do planejado.

## Riscos e respostas

| Risco | Sinal | Resposta |
| --- | --- | --- |
| Build falha (PyTorch, Next) | erro no `up --build` | colar o log; ajustar o Dockerfile e repetir |
| API não sobe | `api` reiniciando | conferir `ANTHROPIC_API_KEY` e memória (`docker stats`) |
| Sem certificado | Caddy com erro de ACME | portas 80/443 fechadas ou `DOMINIO` errado |
| Gasto alto ou abuso | painel da Anthropic | o limite de gasto corta; a cota de mensagens por dia já existe na API |
| VPS vence em 1 mês | aviso da Hostinger | renovar ou migrar; o banco de demo pode ser recriado pela carga |

## Voltar atrás

- Parar tudo: `docker compose -f docker-compose.prod.yml down` (o banco fica no volume).
- Versão anterior: `git checkout <commit>` e `up -d --build`.
- Banco do zero: `down -v` apaga os volumes; a próxima subida recarrega o catálogo.

## Depois do primeiro deploy

- [ ] Backup diário do banco (`pg_dump` agendado para fora da VPS).
- [ ] Observabilidade: traços e métricas por turno (Langfuse), que ainda não existem.
- [ ] Suíte do agente com o encoder ajustado; se passar, `ENCODER_MODELO` passa a ser o ajustado.
- [x] Domínio próprio no lugar do `sslip.io`.

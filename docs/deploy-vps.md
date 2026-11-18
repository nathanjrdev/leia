# Deploy numa VPS (Hostinger KVM 2)

Tudo roda com Docker Compose numa máquina só: Postgres com pgvector, API, web, Caddy (HTTPS
automático) e a manutenção de reservas. Arquivos: `docker-compose.prod.yml`, `api/Dockerfile`,
`web/Dockerfile`, `deploy/Caddyfile`, `deploy/env.prod.example`. O checklist geral continua em
[deploy.md](deploy.md).

## 1. A máquina

- Plano KVM 2 (2 vCPU, 8 GB de RAM). A API usa uns 2 GB com o encoder e o reranker.
- Sistema: **Ubuntu 24.04 com Docker** (modelo de SO da Hostinger) ou Ubuntu 24.04 puro.
- Anote o **IP** e entre por SSH: `ssh root@IP`.

Ubuntu puro? Instale o Docker:

```bash
curl -fsSL https://get.docker.com | sh
```

## 2. Domínio

Sem domínio próprio, use o `sslip.io`, que aponta para o IP sem configurar nada:
o IP `203.0.113.10` vira `203-0-113-10.sslip.io`. O Caddy tira o certificado HTTPS sozinho.
Com domínio próprio, crie um registro **A** para o IP da VPS e use esse nome.

## 3. Código e configuração

```bash
git clone https://github.com/nathanjrdev/leia.git
cd leia
cp deploy/env.prod.example .env
nano .env        # DOMINIO, POSTGRES_PASSWORD, ANTHROPIC_API_KEY
```

- `POSTGRES_PASSWORD`: gere com `openssl rand -hex 24`.
- `ANTHROPIC_API_KEY`: crie no console da Anthropic e **defina um limite de gasto** lá.
- Dados: só catálogo público e leitores fictícios; quem se cadastrar na demo é leitor real.

## 4. Subir

```bash
ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw --force enable   # se usar o ufw
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f api                  # Ctrl+C para sair
```

O primeiro build leva de 10 a 20 minutos (PyTorch e as dependências do web). Na primeira subida,
a API aplica as migrações, carrega os 282 livros, baixa os modelos (~2 GB, ficam no volume
`hfcache`) e gera os embeddings. Ela só fica saudável depois disso; o web e o Caddy sobem em seguida.

Pronto quando:

```bash
docker compose -f docker-compose.prod.yml ps        # api "healthy", web e caddy "Up"
curl -I https://SEU-DOMINIO                          # HTTP/2 200
```

## 5. Atualizar

```bash
cd leia && git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### Imagens da degustação (fora do git)

As páginas da degustação são obras protegidas: ficam fora do git (`web/public/degustacao/`
no `.gitignore`), então o `git pull` não as leva. Sem elas o site funciona, mas a capa da estante
leva direto à ficha. O build do web copia o que estiver em `web/public/`, então basta a pasta
existir no clone da VPS antes do `--build`. Uma vez copiada ela fica lá; só repita quando
gerar páginas novas (`data/gerar_degustacao.py`).

No PC (PowerShell), na raiz do repositório:

```powershell
tar -czf .local/degustacao-imagens.tar.gz -C web/public degustacao
scp .local/degustacao-imagens.tar.gz USUARIO@IP-DA-VPS:~/
```

Na VPS:

```bash
cd leia && rm -rf web/public/degustacao && tar -xzf ~/degustacao-imagens.tar.gz -C web/public
test -f web/public/degustacao/indice.json && echo ok
docker compose -f docker-compose.prod.yml up -d --build web
curl -s -o /dev/null -w '%{http_code}\n' https://SEU-DOMINIO/degustacao/indice.json   # 200
```

## Problemas comuns

| Sintoma | Causa provável |
| --- | --- |
| Caddy sem certificado | portas 80/443 fechadas no firewall da Hostinger ou no `ufw`; ou `DOMINIO` não aponta para o IP |
| API reiniciando | `ANTHROPIC_API_KEY` vazia (a API não sobe sem a chave do modelo) ou falta de memória |
| Chat sem resposta aos poucos | o Caddy precisa do `flush_interval -1` (já no `Caddyfile`) |
| Login não mantém a sessão | o site precisa estar em HTTPS (`COOKIE_SEGURO=true`) |

## Primeiro deploy (17/11/2026)

No ar em [leiabiblioteca.tech](https://leiabiblioteca.tech/). Antes da VPS, a mesma configuração subiu
no Windows com Docker Desktop (`docker compose -p leia-teste ...`, `DOMINIO=localhost`), o que pegou
o problema do healthcheck abaixo sem gastar tempo de VPS.

O que divergiu do planejado:

| Item | Planejado | O que aconteceu |
| --- | --- | --- |
| Domínio | `IP-COM-HIFENS.sslip.io` | domínio próprio `leiabiblioteca.tech` (registro A para o IP da VPS) |
| Sistema | Ubuntu 24.04 com Docker | template "Docker" da Hostinger (Ubuntu 24.04), sem Traefik; o "Docker and Traefik" ocuparia as portas 80/443 do Caddy |
| Memória | 8 GB | + swap de 4 GB por segurança no build e em picos |
| 1ª subida da API | `start_period: 120s` | baixar ~1,7 GB de modelos e gerar os embeddings levou ~17 min no teste local; o compose marcou a API como *unhealthy* e não subiu web nem Caddy. `start_period` passou a 1800 s (commit `2a676ac`) |
| Build | 10 a 20 min | ~20 min no teste local; a imagem da API é construída duas vezes (`api` e `manutencao`) |
| RAM da API | ~2 GB | 2,0 GB medidos com encoder e reranker carregados |

Conferido no site no ar: busca por intenção no chat ("romance sobre a seca no sertão" → *Vidas secas*
primeiro, com cartões e disponibilidade) e a tentativa de injeção pelo chat (ver
[diário de refino, 5.12](avaliacao-e-refino.md)).

Ainda não conferido: locar e devolver no site no ar; IP real do visitante no log da API (o limitador
de abuso depende dele; no teste local apareceu o IP da rede Docker com porta `:0`, sinal de que veio
do cabeçalho do proxy); backup do banco.

Melhoria pendente: a `manutencao` reaproveitar a imagem da `api` em vez de construir outra igual.

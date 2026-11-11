# Redesign "Estante de vidro": plano de execução

> Proposta de 11/11/2026. Escopo: só `web/`. Referência visual: [my-book.site](https://www.my-book.site/).
> Skills: `impeccable` (pbakaus), `design-taste-frontend` (Leonxlnx/taste-skill) e o pacote `emilkowalski/skill`.

## Resumo

- **O que muda:** a identidade "sala de leitura" (papel creme, Fraunces, verde-garrafa) sai. Entra uma identidade inspirada no my-book.site: fundo violeta chapado, tipografia Inter grande e justa, prateleiras de vidro fosco com as capas reais em pé, e movimento com função.
- **O que não muda:** nada em `api/`, `evals/` ou `data/`. Também ficam intactos `web/src/lib/api.ts`, `lib/tipos.ts`, `SessaoProvider.tsx` e a lógica (estado, efeitos, handlers) de Conversa, Estante, Catálogo, Ficha, Auth e `AcaoComConfirmacao`. Nenhum teste existente é editado.
- **Estratégia:**
  1. Tokens novos com *aliases* dos nomes antigos: o app inteiro fica violeta num commit, sem tocar componente.
  2. Primitivos de UI.
  3. Uma tela por PR, da menos arriscada para a mais arriscada. A Conversa fica por último e começa por uma extração sem mudança visual.
  4. O movimento entra junto com cada tela, e há uma revisão de movimento no fim.
- **Prazo:** o plano cabe entre 12/11 e 27/11, antes do gate do MVP (29/11). Se apertar, há uma lista de corte (seção 6).

---

## 1. O que não pode quebrar

### 1.1 Funcionalidades (todas ficam)

| Área | Comportamento |
| --- | --- |
| Conta | Cadastro, login e saída. A sessão vem do cookie (`GET /auth/eu`). O formulário é `method="post"`. |
| Conversa | Stream SSE com andamento por etapa: `ferramenta`, `etapa`, `descartar`, `resposta`, `livros`, `propostas`, `acao`, `fim`. Também ficam: sugestões iniciais; Nova conversa; trava contra envio duplo; conversa guardada em `sessionStorage` (`leia:conversa`) e preservada ao voltar da ficha (`cacheComponents` + `<Activity>`); nota de falha da ação. |
| Cartão do livro no chat | Dados do banco, nunca do modelo. Locar/Reservar em duas etapas, passando pelo chat. "Ver minha estante" depois da ação. Sem ação quando a mensagem já trouxe proposta. |
| Proposta da Léia | Confirmar / Cancelar por clique. A proposta some quando o leitor escreve de novo. |
| Catálogo | Busca, categoria, "Só disponíveis" e paginação (só fora da busca). |
| Ficha | Locar ou reservar em duas etapas. Aviso com prazo e link para a estante. "Entre para locar" para quem não está logado. |
| Estante | Locações ativas (renovar, devolver, aviso de atraso), reservas (pronta para retirar / posição na fila, cancelar), histórico, estado vazio, erro com "Tentar de novo". |
| Capa | Imagem real. Quando a imagem falha ou chega o pixel 1×1 da Open Library, entra a capa gerada (`aria-hidden`), com tom estável por id. |
| Acessibilidade | Link "Pular para o conteúdo" como primeiro link, `main#conteudo`, `role="status"` e `role="alert"`, foco visível, tema escuro automático, `prefers-reduced-motion`. |

### 1.2 Regras de produto que a tela garante

- Toda escrita passa por `AcaoComConfirmacao` (o primeiro clique só pergunta) ou pela proposta do chat. Nenhuma animação, gesto ou atalho elimina o segundo clique.
- O botão diz o que acontece ("Confirmar locação", não "OK").
- Erro e atraso nunca dependem só da cor: sempre há texto e ícone.

### 1.3 Contrato dos testes (95 unitários + 4 E2E)

Os testes encontram a tela por papel, nome acessível e texto. O redesign mantém **exatamente**:

- **Papéis e nomes:**
  - Navegação e conta: `banner` › link "Entrar"; botão "Sair"; `navigation` "Principal" com **exatamente 3** `<a>`; primeiro link "Pular para o conteúdo" com `href="#conteudo"`.
  - Conversa: `list` "Conversa"; rótulo "Mensagem para a Léia"; botões "Enviar", "Nova conversa", "Confirmar" e "Cancelar" (nomes exatos); `group` "Sugestões para começar", "Livro: {título}" e "Confirmação".
  - Ações em duas etapas: botões "Locar", "Reservar", "Confirmar locação", "Confirmar reserva" e "Voltar"; link "Ver minha estante"; links "Entre para locar" e "Entre para reservar".
  - Estante: `region` "Locações ativas", "Reservas" e "Histórico" (via `aria-labelledby` no `h2`); botões "Renovar", "Devolver", "Confirmar renovação", "Confirmar devolução", "Cancelar reserva", "Confirmar cancelamento" e "Tentar de novo".
  - Catálogo: rótulos "Buscar no acervo", "Categoria" e "Só disponíveis"; botões "Buscar", "Anterior" e "Próxima"; o link do livro tem como nome o próprio título.
  - Auth: rótulos "Nome", "E-mail" e "Senha"; botões "Criar conta", "Entrar", "Entrando…" e "Criando…".
- **Ganchos no DOM:** `.andamento-ponto` ×3 dentro de `[aria-hidden="true"]`; `[data-capa="gerada"]` com `aria-hidden` e classe `capa-tom-N`; `role="status"` (sr-only) da conversa; `role="alert"` nos erros.
- **Textos:**
  - Estante e catálogo: "Você não tem livros locados nem reservas.", "Nenhum livro encontrado.", "Página X de Y", "Devolver até dd/mm/aaaa", "Atrasada", "Posição N na fila" e "Pronto para retirar até…".
  - Disponibilidade: "Sem exemplar livre agora", "N exemplares livres", "N disponíveis", "Indisponível, fila de N" e "N de M exemplares disponíveis".
  - Andamento da conversa: "Pensando…", "Buscando no acervo…", "Escrevendo a resposta…" e "Conferindo os livros no acervo…".

**Regra:** nenhum PR do redesign altera arquivos em `src/__tests__/` ou `e2e/`. Se um teste quebrar, a tela está errada, não o teste. Testes novos podem entrar, mas nenhum teste existente fica mais frouxo.

**Minúsculas como no my-book.site** ("conversa", "catálogo") só via CSS `text-transform: lowercase`. O DOM continua "Conversa", então o nome acessível, os leitores de tela e os testes não mudam.

---

## 2. Direção visual: o que vem do my-book.site

**Observado no site em 11/11/2026:**

- Fundo `#7A0CCF` chapado e texto branco.
- Display em Inter, em minúsculas e com tracking bem negativo.
- Rosa `#F7CED7` no wordmark e no botão; menta `#7DFFB0` pontual.
- "Vidro" `rgba(255,255,255,.10)` com `blur(10px)` e filete interno branco a 30%.
- Capas em pé dentro de prateleiras de vidro, com a base afundando no vidro.
- Objetos 3D pontuais (chaveiro, folha).
- Pílulas que entram com leve *overshoot* (`cubic-bezier(.2,1.4,.4,1)`).
- O site é todo desenhado em `<canvas>`, numa tela só.

**O que não vem:** a lagarta, a borboleta, o cursor-folha, o chaveiro, o wordmark "my books" e as capas deles. São obra do autor. Levamos a linguagem (cor, tipo, material, ritmo), nunca personagens ou assets. O Léia continua em HTML acessível, sem canvas.

**Conceito:** a Léia mostra o acervo numa estante de vidro iluminada. As capas dão a cor da página; a interface é vidro e tipo.

### 2.1 Tokens (contraste WCAG calculado)

| Token | Violeta (padrão) | Ameixa (`prefers-color-scheme: dark`) | Uso e contraste |
| --- | --- | --- | --- |
| `--fundo` | `#7A0CCF` | `#1B0B2A` | página inteira |
| `--vidro` | branco 10%, como no site (≈ `#8724D4`) | branco 10% (≈ `#32233F`) | barra, campos, prateleiras, bolha do leitor |
| `--vidro-filete` | branco 30%, 1 px interno | idem | borda do vidro (decorativa) |
| `--texto` | `#FFFFFF` | `#FFFFFF` | 7,6:1 no violeta; 6,5:1 no vidro; 18,6:1 na ameixa |
| `--texto-suave` | branco 86% (`#ECDDF8`) | branco 82% | 5,9:1 no violeta; 5,0:1 no vidro. O branco a 70% do site dá 4,3:1 e **reprova** AA. |
| `--controle` | branco 60% (`#CA9EEC`) | branco 50% | borda de campo e botão secundário: 3,5:1 (WCAG 1.4.11) |
| `--rosa` | `#F7CED7` | `#F7CED7` | preenchimento da ação principal, foco e links de ação: 5,3:1 no violeta, 4,6:1 no vidro (com o vidro a 12% cairia para 4,4:1 e reprovaria, por isso o vidro fica em 10%). |
| `--rosa-texto` | `#3A0566` | `#3A0566` | texto sobre o rosa: 10,6:1 |
| `--menta` | `#7DFFB0` | `#7DFFB0` | disponível e sucesso: 6,0:1 (5,2 no vidro) |
| `--alerta` | `#FFD6CF` | `#FFD6CF` | erro e atraso: 5,7:1 (4,9 no vidro), sempre com ícone e texto |
| `--sombra` | `rgba(40,0,70,.35)` | `rgba(0,0,0,.45)` | elevação da prateleira |
| foco | anel 3 px `--rosa` | idem | 5,3:1 no violeta |

**Capas geradas:** as classes `.capa-tom-1…6` e o `data-capa` ficam iguais. Só os tons mudam, para cores de cartaz que funcionem sobre o violeta: rosa, verde, amarelo, vermelho, creme e celeste, cada um com a sua letra (5,2:1 a 14,8:1; tabela no DESIGN.md). O azul saiu porque some no violeta (1,1:1).

**Aliases durante a migração:**

| Nome antigo | Passa a apontar para |
| --- | --- |
| `--papel` | `--fundo` |
| `--papel-2` | `--vidro`, na cor sólida |
| `--tinta` | `--texto` |
| `--tinta-suave` | `--texto-suave` |
| `--linha` | `--vidro-filete` |
| `--lombada` | `--rosa` |
| `--lombada-texto` | `--rosa-texto` |
| `--alerta` | o novo `--alerta` |

Com isso, `bg-papel-2`, `text-lombada` etc. continuam valendo e tudo recolore de uma vez. Os aliases saem na Fase 6.

### 2.2 Tipografia

- **Família:** uma só, a Inter, já carregada por `next/font`. O `operate.md` do impeccable recomenda uma família só em telas de tarefa, e a referência usa Inter. A Fraunces sai: o impeccable a lista como fonte-padrão de IA. A sinopse passa para Inter 19 px/1,6, com medida de 68ch.
- **Display:** pesos 600–700 e line-height 0,95–1,05. O tracking vai até **-0,04em**, o piso do impeccable; o site usa até -0,1em, mas isso fica só no wordmark. O **wordmark "Léia"** (com L maiúsculo, decisão 5) é um logotipo desenhado em SVG, com letras como lombadas, então o tracking não se aplica a ele. A navegação fica em minúsculas por CSS; a marca, não.
- **Escala:** 14 / 17 / 22 / 36 / 64 px, em rem fixo nas telas de tarefa. Só a home usa `clamp()` no display.
- **Corpo:** 17 px, como hoje. Inputs e textarea com ≥ 16 px, para o iOS não dar zoom.

### 2.3 Materiais e componentes

- **Prateleira** (o efeito específico que justifica o vidro): faixa de vidro com `blur(10px)`, filete e sombra ameixa. As capas ficam em pé, com a base sob um degradê de 12% da altura. Aparece na home, no catálogo, na estante, na ficha e, em miniatura, no cartão do chat.
- **Vidro:** só na barra superior, no compositor do chat, na bolha do leitor, nos filtros e nas faixas de confirmação. Não há card dentro de card: dentro do vidro, a separação é por divisor.
- **Botões:**
  - Primário: pílula rosa com texto ameixa.
  - Secundário: pílula de vidro com filete.
  - De texto: sublinhado que se desenha.
  - Altura mínima de 44 px.
- **Selo de disponibilidade:** ponto menta + texto. Indisponível: ponto vazado + texto suave. Atraso: ícone + "Atrasada" em `--alerta`.
- **Alertas e confirmações:** painel de vidro com ícone. Sai o `border-l-4` de hoje, que o impeccable proíbe acima de 1 px.
- **Ícones:** um conjunto pequeno de SVGs próprios (check, alerta, seta, busca, fechar, livro), com traço único. Nada de emoji ou glifo no lugar de ícone, e nenhuma lib nova.
- **Desempenho:** `backdrop-filter` só em superfícies grandes e poucas, nunca um por item de lista. Com `@supports not (backdrop-filter: blur(1px))`, o vidro vira cor sólida.
- **Proibidos (impeccable):** kicker ou rótulo acima de título, texto em degradê, borda lateral colorida, sombra dura deslocada e números de seção decorativos.

---

## 3. Quem faz o quê

| Skill | Onde entra | Como | Conflitos e decisões |
| --- | --- | --- | --- |
| **impeccable** | Fonte de verdade do design. Telas de app no modo *Operate*: conversa, catálogo, ficha, estante e auth. | `document` (DESIGN.md novo), `typeset`, `layout`, `animate`, `audit`, `harden`, `polish`, `/impeccable hooks on` | A direção está fixada pelo pedido (my-book.site), então não há sorteio de direção (`concept-seed`): a própria skill dispensa o sorteio quando o brief fixa o mundo. Rodar `impeccable context` localmente: nesta sessão o launcher foi bloqueado e li PRODUCT.md e DESIGN.md direto. |
| **design-taste-frontend** | Só a página inicial `/` (modo *Persuade*). Também dá o vocabulário de micro-interação: hover sobe 2 px, botão afunda no clique, hero entra uma vez, um "momento" por página. | `copy-lint`, checklist e `gate.mjs` apontados para `/` | A skill manda "never violet: deal again" e escolhe paleta, fonte e layout por sorteio. O pedido fixa o violeta, e pela regra do impeccable o brief vence. Ficam de fora o sorteio de paleta e tipo, as fotos de banco e os shaders. O hook de Stop que ela instala só age se existir `.taste-skill/build.json`. |
| **emilkowalski/skill** | Movimento. | `find-animation-opportunities` (varredura inicial), `animate` (cada animação), `choreograph` (entrada da home, chat), `review-animations` (todo PR com motion), `animation-performance`, `mobile-native` (dvh, zoom em input, safe-area, tap highlight), `emil-design-eng` | Não se aplicam (apps nativos): `write-swift`, `animate-expo`, `apple-design`. Proposta: não versionar essas. |

---

## 4. Movimento

### 4.1 Tese

**Momento focal: a capa sai da prateleira.** Ao abrir um livro (pelo catálogo, pela estante ou pelo cartão do chat), a capa faz *morph* até a posição da ficha com `<ViewTransition name="capa-{id}" share="morph" default="none">`. React 19.3 + Next 16.4 suportam isso sem configuração (guia em `node_modules/next/dist/docs/01-app/02-guides/view-transitions.md`).

- **Spike obrigatório:** a ficha busca os dados no cliente (`useEffect`), então no momento da navegação a capa de destino ainda não existe. Para o morph acontecer, a ficha precisa desenhar a capa no primeiro render, com dados já conhecidos pela lista ou buscados no servidor.
- **Plano B:** crossfade de 200 ms.

**Momento da home (taste-skill):**

- O wordmark "Léia" se monta com as lombadas.
- As capas entram na prateleira uma vez, em escalonamento variado com no máximo 300 ms no total.
- A pílula "Conversar com a Léia" entra com o overshoot da referência. Só aqui, por ser raro.

**Continuidade:**

- Mensagem nova do chat: opacidade + `translateY(6px)`, 200 ms, ease-out. O cartão do livro entra junto, sem escalonar.
- Etapas de confirmação: troca com `@starting-style`, 150–200 ms.
- Devolver ou cancelar: o item sai com opacidade + `scale(.98)`, 150 ms, via View Transition, então o DOM muda na hora.
- Resultados do catálogo: crossfade de 150 ms ao filtrar ou paginar.

**Resposta ao toque:**

- Botão afunda para `scale(.97)` em 120 ms.
- Hover sobe 2 px, só com `(hover: hover) and (pointer: fine)`.
- Sublinhado que se desenha.

**Fica parado, de propósito:**

| O quê | Por quê |
| --- | --- |
| Envio com Enter | ação de teclado |
| Paginação e sugestões | alta frequência |
| Navegação | alta frequência |
| Andamento | só os 3 pontos pulsam em opacidade, como hoje |

### 4.2 Tokens de movimento (valores das skills da Emil, não inventados)

```css
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);
--ease-pilula: cubic-bezier(0.2, 1.4, 0.4, 1); /* só a entrada da home */
--dur-toque: 120ms;
--dur-estado: 200ms;
--dur-camada: 300ms;
--dur-foco: 450ms; /* morph da capa e entrada da home */
```

### 4.3 Regras

- **Ferramentas:** CSS transitions e `@starting-style` primeiro; `<ViewTransition>` para o morph e para as saídas. Nenhuma lib nova (sem Motion e sem GSAP).
- **Propriedades:** só `transform` e `opacity`, mais `clip-path` na home. Nada de animar `width`, `height`, `top` ou margem.
- **Movimento reduzido:** sem deslocamento, mas opacidade e cor continuam. O morph vira crossfade. Os pontos do andamento continuam como hoje.
- **A animação nunca atrasa o DOM:** o texto novo entra na hora e só a aparência transita. Assim jsdom e E2E veem o mesmo de hoje. Saídas não seguram o item na árvore depois que o estado mudou.

---

## 5. Tela a tela

| Tela | Hoje | Depois | Cuidado |
| --- | --- | --- | --- |
| **Shell** (layout + Cabeçalho) | Barra creme, links sublinhados | Violeta em tela cheia; barra de vidro; wordmark "Léia"; 3 links em pílula, em minúsculas por CSS, com `aria-current="page"` no atual; Entrar/Sair à direita | Skip link continua o 1º link; `nav` com exatamente 3 `<a>`; o texto "Entrar" fica dentro do `banner` |
| **Início `/`** | Título, parágrafo e 2 botões | Wordmark grande, a frase atual, duas prateleiras de vidro com capas reais do acervo (`GET /livros?limite=8`, com capas geradas enquanto carrega ou se falhar), pílula rosa "Conversar com a Léia" e pílula de vidro "Ver o catálogo" | Única tela Persuade; passa pelo `copy-lint` e pelo gate da taste-skill; nenhum endpoint novo |
| **Entrar / Cadastrar** | Formulário solto | Painel de vidro centrado; labels visíveis (como hoje); pílula rosa; erro com ícone | `method="post"`, nomes dos campos, "Entrando…"/"Criando…" |
| **Catálogo** | Lista vertical | Busca grande em vidro; `<select>` e checkbox nativos com estilo de vidro; resultados em prateleiras (grade de capas com título, autor e selo); paginação igual | Continua `<ul>`/`<li>`; o link do livro é o título em texto; não reinventar controles |
| **Ficha** | Capa + texto | Capa grande sobre prateleira (destino do morph); título display; meta; sinopse em 68ch; selo; ação em pílula; aviso em vidro com ícone | `role="status"` no aviso; heading com o título |
| **Estante** | Três listas | Três prateleiras: ativas e reservas com capas em pé, prazo e ações embaixo; histórico como fileira de lombadas (título vertical, link para a ficha); vazio como prateleira vazia com o texto atual e "Peça uma sugestão à Léia" | `region` por `aria-labelledby`; textos de prazo e fila iguais; link com o título |
| **Conversa** (por último) | Coluna com bordas | Coluna de 68ch sobre o violeta; fala da Léia sem bolha; fala do leitor em bolha de vidro; cartão do livro como mini-prateleira; proposta como faixa de vidro com ícone; compositor de vidro fixo, com `100dvh` e safe-area | **Primeiro, um PR de extração sem mudança visual:** `Mensagem`, `Proposta`, `Compositor` e `Sugestoes` viram componentes de apresentação. `transmitir`, `aplicar`, `reservarVez`, as refs e os efeitos ficam onde estão. Só depois, o restyle. |

---

## 6. Fases e PRs

As estimativas de prazo são de planejamento: o objetivo é ter folga antes de 29/11.

| Fase | PR(s) | Conteúdo | Risco | Pronto quando | Datas propostas |
| --- | --- | --- | --- | --- | --- |
| **0. Preparação** | 1 | Branch `redesign/estante-de-vidro`; skills versionadas (só as úteis) + `skills-lock.json`; linha de base: `lint`, `typecheck`, `test`, `build` e `e2e` verdes; capturas "antes" de cada rota em 1440 e 390 px, claro e escuro (script Playwright avulso, fora do CI) | baixo | capturas salvas; CI verde | 12/11 |
| **1. Fundação** | 1 | DESIGN.md novo (`/impeccable document`); tokens novos + aliases; Inter no display; tons das capas geradas; tokens de movimento; base do `mobile-native` (`viewport-fit=cover`, `dvh`, tap highlight, `text-size-adjust`) | médio (contraste) | todas as telas violetas sem mudar markup; contrastes da tabela 2.1 conferidos; testes verdes | 13/11 |
| **2. Primitivos** | 1 | `components/ui/` com `Botao`, `Vidro`, `Prateleira`, `Selo`, `Campo` e ícones; `AcaoComConfirmacao` passa a usar `Botao`, mesma API e mesmos nomes | baixo | `acao.test` e o resto verdes | 14/11 |
| **3. Shell** | 1 | Cabeçalho e layout | baixo | `cabecalho.test` + E2E verdes | 16/11 |
| **4. Telas** | 6 | 4a Auth → 4b Catálogo → 4c Ficha (+ spike do morph) → 4d Estante → 4e Início → 4f Conversa (extração, depois restyle) | sobe até alto | cada PR com o checklist da seção 7 | 17–24/11 |
| **5. Movimento** | 1 | Varredura com `find-animation-opportunities`; morph da capa; momento da home; `review-animations` + `animation-performance` no conjunto; teste em celular de verdade (`mobile-native`) | médio | nenhum achado bloqueante do `review-animations` | 25–26/11 |
| **6. Fechamento** | 1 | `impeccable audit` + `harden` (carregando, vazio, erro) + `polish`; Lighthouse de acessibilidade (meta: manter 100 em conversa e estante); remover aliases; README e DESIGN.md finais | baixo | CI verde; checklist completo | 27/11 |

**Lista de corte (nesta ordem):**

1. Morph da capa (fica crossfade).
2. Momento da home (fica entrada simples).
3. Histórico em lombadas (fica lista).
4. Tema ameixa (o violeta serve nos dois modos).

O núcleo (Fases 1–4) não depende de nenhum desses.

O redesign não muda o comportamento do agente nem da busca, então não precisa de entrada no diário de refino (`docs/avaliacao-e-refino.md`).

---

## 7. Rede de segurança (todo PR)

- [ ] `npm run lint`, `npm run typecheck`, `npm test` e `npm run build` verdes; `npm run e2e` verde (o CI já roda os três jobs).
- [ ] O diff não toca `api/`, `lib/api.ts`, `lib/tipos.ts`, `SessaoProvider.tsx`, `src/__tests__/` nem `e2e/`.
- [ ] Em componentes com lógica (`Conversa`, `Estante`, `Catalogo`, `FichaLivro`, `FormularioAuth`, `AcaoComConfirmacao`), o diff fica em JSX e classes; hooks, handlers e efeitos idênticos. Revisar com `git diff --word-diff` nesses arquivos. A exceção prevista é envolver em `startTransition` a atualização que dispara uma View Transition, comentada no PR.
- [ ] Capturas em 1440 e 390 px, claro, escuro e com movimento reduzido, comparadas às da Fase 0: todos os estados continuam visíveis (carregando, vazio, erro, pronto). A comparação é de conteúdo, não de pixel.
- [ ] Contraste de todo par novo calculado (script ou `impeccable audit`).
- [ ] Teclado: Tab percorre tudo com foco rosa visível; Enter envia e Shift+Enter quebra a linha; nenhuma animação em ação de teclado.
- [ ] Movimento: `review-animations` no diff; hover só com ponteiro fino; caminho de movimento reduzido presente.
- [ ] Rollback: cada fase é um PR revertível. Reverter a Fase 1 (`globals.css` + `layout.tsx`) devolve a identidade antiga.

---

## 8. Riscos

| Risco | Efeito | Prevenção |
| --- | --- | --- |
| Nome acessível muda sem querer (ex.: "Minha estante" → "estante") | Unitários e E2E quebram | Contrato 1.3; minúsculas só por CSS |
| Contraste no violeta | Branco 70% reprova AA; vidro acima de 10% derruba o rosa abaixo de 4,5:1 | Tokens da tabela 2.1 |
| `backdrop-filter` pesado no celular | Rolagem travando no catálogo e no chat | Blur só em superfícies grandes; fallback sólido; `animation-performance` |
| Morph não acontece | Ficha carrega no cliente, a capa de destino não existe | Spike na 4c; crossfade como plano B |
| View Transition + `cacheComponents`/`<Activity>` | Perder a conversa ao voltar da ficha (o último merge corrigiu justamente isso) | Teste manual "voltar da ficha" em cada PR que toca navegação; nada de mexer nas refs `abertura`/`aberta` |
| Saída animada segura o item no DOM | Teste vê o livro devolvido ainda na lista | Saídas por View Transition (snapshot), DOM muda na hora |
| Prazo do MVP (29/11) | Redesign compete com o gate | Fases mergeáveis isoladas; lista de corte |
| Copiar a referência | Problema de autoria | Só linguagem; nenhum personagem, capa ou wordmark do my-book.site |
| Skills em conflito | Taste-skill troca o violeta; impeccable limita o tracking | Seção 3: o brief vence; regras do impeccable valem nas telas de tarefa |
| Hook de Stop da taste-skill | Pode travar o fim de uma sessão do Claude Code | Armar o gate só no trabalho da home; `gate.mjs --done` ao encerrar |

---

## 9. Decisões (fechadas em 11/11/2026)

1. **Tema escuro "ameixa":** mantido em `prefers-color-scheme: dark`.
2. **Fraunces:** sai de vez, inclusive da capa gerada (Inter pesada, estilo cartaz).
3. **Home:** capas reais do acervo, com capas geradas enquanto carrega ou se a API falhar.
4. **Skills versionadas:** todas, menos as de app nativo (`write-swift`, `animate-expo`, `apple-design`).
5. **Marca:** "Léia" com L maiúsculo, também no logotipo. Só os links de navegação ficam em minúsculas (por CSS).

---

## 10. Instalar as skills no seu clone

Na raiz do repositório:

```bash
npx skills add Leonxlnx/taste-skill -a claude-code -y
npx skills add emilkowalski/skill -a claude-code -y
npx skills add pbakaus/impeccable -a claude-code -y
npx skills remove write-swift animate-expo apple-design -y   # decisão 4: fora as de app nativo
```

Tudo vai para `.claude/skills/` + `skills-lock.json`. No repositório, a mídia de demonstração da taste-skill (fotos, cenas, ícones de demo: ~30 MB) fica fora do Git (`.gitignore`); as instruções, referências e scripts estão versionados. Quem precisar da mídia roda o primeiro comando acima. Depois, no Claude Code:

1. `/impeccable` (carrega PRODUCT.md e DESIGN.md).
2. `/impeccable hooks on` (detector após cada edição de UI).
3. Revise os SKILL.md: eles rodam com as permissões do agente.

# Léia: design ("Estante de vidro")

> Substitui a identidade "sala de leitura" (papel, Fraunces, verde-garrafa). O plano e a ordem de
> entrega estão em `docs/redesign/plano-estante-de-vidro.md`. Os tokens vivem em
> `web/src/app/globals.css` (Tailwind v4 `@theme`); componente nenhum usa hex solto.

## Conceito

A Léia mostra o acervo numa estante de vidro iluminada. As capas reais dão a cor da página; a
interface é vidro e tipo. A referência de linguagem é o [my-book.site](https://www.my-book.site/):
violeta chapado, letra grande e justa, prateleiras de vidro fosco. Só a linguagem: nenhum
personagem, capa, wordmark ou asset de lá.

## Cor

Os dois temas têm fundo escuro, então `color-scheme: dark` vale sempre (campos, rolagem e seleção
nativos no escuro). Contrastes calculados (WCAG 2.x); "vidro" é o branco 10% composto sobre o fundo.

| Token | Violeta (padrão) | Ameixa (escuro) | Uso | Contraste |
| --- | --- | --- | --- | --- |
| `--fundo` | `#7a0ccf` | `#1b0b2a` | página inteira | — |
| `--vidro` | branco 10% | branco 10% | superfícies sobre o fundo | — |
| `--vidro-solido` | `#8724d4` | `#32233f` | o mesmo vidro, já composto (barra, campos, o que fica fixo) | — |
| `--vidro-filete` | branco 30% | branco 30% | borda decorativa do vidro, divisores | — |
| `--texto` | `#ffffff` | `#ffffff` | texto | 7,6:1 fundo · 6,5:1 vidro (ameixa 18,6:1) |
| `--texto-suave` | `#ecddf8` (branco 86%) | `#d6d3d9` (82%) | texto secundário | 5,9:1 fundo · 5,0:1 vidro |
| `--controle` | `#ca9eec` | `#8d8594` | borda de campo e botão secundário | 3,5:1 no fundo (1.4.11) |
| `--rosa` | `#f7ced7` | `#f7ced7` | ação principal, foco, links de ação | 5,3:1 fundo · 4,6:1 vidro |
| `--rosa-texto` | `#3a0566` | `#3a0566` | texto sobre o rosa | 10,6:1 |
| `--menta` | `#7dffb0` | `#7dffb0` | disponível, sucesso | 6,0:1 fundo · 5,2:1 vidro |
| `--alerta` | `#ffd6cf` | `#ffd6cf` | erro e atraso | 5,7:1 fundo · 4,9:1 vidro |
| `--sombra` | `rgb(40 0 70 / .35)` | `rgb(0 0 0 / .45)` | elevação da prateleira | — |

Regras:

- O rosa é para ação e foco. A menta é só para "disponível" e sucesso. O texto do site de
  referência a 70% de branco reprova AA (4,3:1); aqui o secundário é 86%.
- Erro e atraso nunca dependem só da cor: sempre há texto e, nos componentes novos, ícone.
- Superfícies do navegador seguem o tema: seleção rosa com texto ameixa, cursor de texto rosa,
  barra de rolagem clara e fina, sublinhado com recuo de 0,2em.

### Capa gerada (livro sem imagem)

Quando o livro não tem `capa_url`, a imagem falha ou a Open Library devolve o pixel vazio, a capa
vira tipografia sobre um tom de cartaz: título principal (sem subtítulo) em Inter 800, autoria em
versalete, filete na cor da letra e sombra de lombada. É decorativa (`aria-hidden`), o título real
está ao lado. O tom sai do id do livro (`tomDaCapa`), estável entre telas.

| Classe | Tom | Letra | Contraste |
| --- | --- | --- | --- |
| `.capa-tom-1` | rosa `#f7ced7` | `#3a0566` | 10,6:1 |
| `.capa-tom-2` | verde `#1e7a3c` | `#f2ffe8` | 5,2:1 |
| `.capa-tom-3` | amarelo `#ffd84d` | `#2b1400` | 12,6:1 |
| `.capa-tom-4` | vermelho `#c81e28` | `#fff1ee` | 5,2:1 |
| `.capa-tom-5` | creme `#f1ece2` | `#1a1a1a` | 14,8:1 |
| `.capa-tom-6` | celeste `#9fd3ff` | `#0b2340` | 10,0:1 |

Os tons são iguais nos dois temas (a capa é um objeto).

## Tipografia

- Uma família: **Inter** (`--font-sans`), carregada por `next/font`. A Fraunces saiu.
- Títulos: peso 600–700, `line-height` 1,1, tracking −0,03em (piso −0,04em). `text-wrap: balance`.
- Corpo 17 px / 1,65; leitura em ~68ch (`--medida`). Campos com 16 px ou mais (sem zoom no iOS).
- Escala: 14 / 17 / 22 / 36 / 64 px, em rem fixo nas telas de tarefa; `clamp()` só na página inicial.
- Marca: "Léia", com L maiúsculo, num logotipo desenhado (letras como lombadas). Os links de
  navegação aparecem em minúsculas só por CSS: o texto no DOM, o nome acessível e os testes não mudam.

## Materiais e componentes

- **Prateleira:** faixa de vidro com `backdrop-filter: blur(10px)`, filete e sombra; as capas ficam
  em pé, com a base sob um degradê de 12% da altura. É o efeito que justifica o vidro.
- **Vidro:** barra superior, compositor do chat, bolha do leitor, filtros, faixas de confirmação.
  Nada de card dentro de card: dentro do vidro, separa-se com divisor.
- **Botões:** primário em pílula rosa (texto `--rosa-texto`); secundário em pílula de vidro com
  `--controle`; de texto, sublinhado. Altura mínima 44 px.
- **Selo de disponibilidade:** ponto menta + texto; indisponível, ponto vazado + texto suave;
  atraso, ícone + "Atrasada".
- **Objeto:** um chaveiro de livros (asset nosso, `web/public/objetos/`), só na página inicial, pendurado na prateleira. É decorativo (`aria-hidden`); balança amortecido ao carregar e ao toque, nunca em loop; parado com movimento reduzido.
- **Ícones:** um conjunto pequeno de SVGs próprios, traço único. Nada de emoji ou glifo como ícone.
- `backdrop-filter` só em superfícies grandes e poucas; sem suporte, o vidro vira `--vidro-solido`.
- Todo campo tem `<label>` visível. Foco visível com anel `--foco` (rosa).
- Estados sempre previstos: carregando, vazio, erro (com ação de tentar de novo).

## Movimento

Tokens: `--ease-out` `cubic-bezier(0.23, 1, 0.32, 1)`, `--ease-in-out`
`cubic-bezier(0.77, 0, 0.175, 1)`, `--ease-drawer` `cubic-bezier(0.32, 0.72, 0, 1)`,
`--ease-pilula` `cubic-bezier(0.2, 1.4, 0.4, 1)` (só a entrada da página inicial); durações
`--dur-toque` 120 ms, `--dur-estado` 200 ms, `--dur-camada` 300 ms, `--dur-foco` 450 ms.

- Momento focal: a capa sai da prateleira para a ficha (`<ViewTransition>` com nome por livro).
- Interface abaixo de 300 ms; entrada com ease-out; nada de `ease-in` nem `scale(0)`.
- Só `transform` e `opacity` (e `clip-path` na página inicial).
- Ação de teclado e o que se usa dezenas de vezes por dia não animam.
- Hover só com `(hover: hover) and (pointer: fine)` (o `hover:` do Tailwind v4 já é assim).
- `prefers-reduced-motion`: sem deslocamento; opacidade e cor continuam.
- A animação nunca atrasa o DOM: o conteúdo novo entra na hora, só a aparência transita.

## Proibido

Kicker ou rótulo acima de título; texto em degradê; borda lateral colorida acima de 1 px em
cartão, item ou alerta; sombra dura deslocada; card dentro de card; grade de ícones; campo só com
placeholder; vidro como enfeite (só onde é a prateleira ou uma superfície); contraste baixo.

## Componentes no código

`web/src/components/ui/`: `Botao` (+ `classesBotao` para links), `Selo`, `Aviso`, `Prateleira` e
`Icones`. Estilos em `globals.css`, `@layer components`: `.botao-*`, `.vidro`, `.vidro-fosco`,
`.campo`, `.selo-*`, `.aviso-*`, `.prateleira*`, `.livro-em-pe`, `.livro-capa`, `.entra`.
Os nomes da identidade anterior (`papel`, `tinta`, `lombada`, `font-serif`) não existem mais.

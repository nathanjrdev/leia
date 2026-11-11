# Léia — design ("sala de leitura")

> Escrito à mão a partir do plano. Os tokens abaixo vivem em `web/src/app/globals.css`
> (Tailwind v4 `@theme`); componente nenhum usa hex solto.

## Conceito
Papel quente, tinta escura, um acento de lombada só para ações. Capas reais são as protagonistas; a interface fica quieta.

## Cor (tokens)
| Token | Claro | Escuro (sépia) | Uso |
| --- | --- | --- | --- |
| `--papel` | `#f7f1e6` | `#1f1a14` | fundo da página |
| `--papel-2` | `#efe6d4` | `#2a231b` | superfícies (barra, campos) |
| `--tinta` | `#1d1a16` | `#efe6d4` | texto |
| `--tinta-suave` | `#5a5147` | `#bfb29c` | texto secundário (≥ 4.5:1 no fundo) |
| `--linha` | `#d9ccb3` | `#43392c` | divisores e bordas |
| `--lombada` | `#1f4d3a` | `#7fc4a1` | ação principal (verde-garrafa) |
| `--lombada-texto` | `#ffffff` | `#10241b` | texto sobre `--lombada` |
| `--alerta` | `#8a2a1f` | `#f0a090` | erro e atraso |

### Capa gerada (livro sem imagem)
Quando o livro não tem `capa_url`, a imagem falha ou a Open Library devolve o pixel vazio, a capa vira tipografia sobre um tom de encadernação em tecido: título principal (sem subtítulo) em Fraunces, autoria em versalete, filete claro e sombra de lombada. É decorativa (`aria-hidden`), o título real está ao lado. O tom sai do id do livro (`tomDaCapa`), então é estável entre telas e vizinhos na lista diferem.

| Token | Valor | Contraste com `--capa-letra` (`#f3ead8`) |
| --- | --- | --- |
| `--capa-vinho` | `#6b2430` | 9,2:1 |
| `--capa-marinho` | `#23344f` | 10,5:1 |
| `--capa-musgo` | `#3f4a2b` | 7,9:1 |
| `--capa-ocre` | `#7a4a1c` | 6,2:1 |
| `--capa-ardosia` | `#3a3f47` | 8,9:1 |
| `--capa-castanho` | `#4f3426` | 9,5:1 |

Os tons são iguais nos dois temas (a capa é um objeto) e nenhum é o verde da lombada, que fica só para ações.

Regras: o acento só aparece em ações (botão primário, link de ação, foco). Erro nunca depende só da cor (ícone/texto). Contraste mínimo 4.5:1 para texto.

## Tipografia
- Títulos e sinopses: **Fraunces** (serifada de leitura), variável `--font-serif`.
- Interface: **Inter**, variável `--font-sans`.
- Corpo 17 px / 1.65; linhas de leitura limitadas a ~68ch (`max-w-prose`-like, `--medida: 68ch`).
- Escala: 14 / 17 / 21 / 28 / 40.

## Layout e componentes
- Largura de conteúdo até 72rem; conversa e leitura em coluna estreita (68ch).
- Barra superior simples: marca "Léia", links (Conversa, Catálogo, Estante) e conta/Entrar.
- Cartão de livro (capa à esquerda, título serifado, autor, selo de disponibilidade, ação): **sem cartão dentro de cartão**, sem sombra ampla; só borda `--linha`.
- Todo campo tem `<label>` visível. Foco visível com anel `--lombada`.
- Estados sempre previstos: carregando, vazio, erro (com ação de tentar de novo).

## Movimento
Discreto (150–200 ms). Respeitar `prefers-reduced-motion`: sem transições nem rolagem suave.

## Proibido
Bege genérico de IA, card dentro de card, grade de ícones, chip acima do título do hero, campo só com placeholder, sombras largas com borda fina, contraste baixo.

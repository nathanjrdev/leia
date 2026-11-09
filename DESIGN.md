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

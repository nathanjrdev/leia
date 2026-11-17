---
language:
- pt
license: cc-by-4.0
task_categories:
- sentence-similarity
- text-retrieval
size_categories:
- 1K<n<10K
tags:
- livros
- busca-semantica
- sintetico
---

# Léia: pedidos de livros em português

Pares "pedido de leitor → livro" usados para ajustar o encoder da busca da [Léia](https://github.com/nathanjrdev/leia), uma bibliotecária virtual com IA. O modelo ajustado com eles é o [leia-embeddings-pt](https://huggingface.co/nathanjrdev/leia-embeddings-pt).

## Conteúdo

| Arquivo | Linhas | O que é |
| --- | --- | --- |
| `pares_treino.jsonl` | 1.873 | Pedidos **sintéticos** de 235 livros (`livro`, `consulta`) |
| `pares_validacao.jsonl` | 368 | Pedidos sintéticos de 46 livros que **nunca** aparecem no treino |
| `casos_manuais.jsonl` | 73 | Casos de avaliação rotulados: 18 de título, 14 de autor, 41 de intenção |
| `catalogo.jsonl` | 282 | Livros: título, autores, ano, ISBN, categorias (sem sinopses) |

## Como os pedidos foram gerados

- Até 8 pedidos por livro, gerados por LLM a partir de título, autor, categorias e sinopse. Geradores: Gemini 3.5 Flash (cerca de 25 livros) e DeepSeek V4.1 Flash (os demais).
- O prompt proíbe citar título, autor, personagens e lugares fictícios da obra, e exige ao menos um elemento específico do livro.
- Filtros: pedidos que contêm o título ou o sobrenome do autor, pedidos com menos de 4 palavras, duplicatas e pedidos idênticos a um caso de avaliação foram descartados (15 no total). Um livro, "Cacau", ficou sem pedidos: todos citavam "cacau", que é o título e o tema.
- **Divisão por livro**, determinística (hash do título): cerca de 20% dos livros só aparecem na validação.

Os 685 pares de título e de autor usados no treino do modelo **não** estão aqui: são gerados do catálogo na hora do treino, sem LLM (função `pares_do_catalogo` em `evals/embeddings/comum.py` no repositório).

## Limitações

- Catálogo pequeno (282 livros), com foco em literatura lusófona e clássicos.
- Os pedidos são sintéticos: mais longos (mediana de 26 palavras) e mais "limpos" do que pedidos reais.
- Os casos de avaliação e parte das sinopses também vêm de conhecimento de LLM, o que tende a deixar os resultados otimistas.
- Alguns livros são muito parecidos entre si (séries como Harry Potter e Nárnia), então um pedido pode servir a mais de um livro, embora o rótulo aponte só um.
- Metadados vêm da Open Library; confira os termos de cada fonte antes de reutilizar.

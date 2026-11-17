---
language:
- pt
license: apache-2.0
library_name: sentence-transformers
base_model: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
pipeline_tag: sentence-similarity
tags:
- sentence-transformers
- embeddings
- busca-semantica
- livros
---

# leia-embeddings-pt

Ajuste fino de `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` para encontrar livros a partir de pedidos de leitores em português, como "um romance curto sobre ciúme" ou "livros de Clarice Lispector". Feito para a busca da [Léia](https://github.com/nathanjrdev/leia), uma bibliotecária virtual com IA. **Ainda não está em produção:** veja "O que não foi medido".

## Como foi treinado

- **Perda:** `MultipleNegativesRankingLoss`, lotes sem dois pedidos do mesmo livro, 3 épocas, lr 2e-5, semente 42, GPU T4 x2 (Kaggle).
- **1.873 pares sintéticos:** até 8 pedidos por livro, gerados por LLM a partir de título, autor, categorias e sinopse, sem citar título, autor nem personagens. Geradores: Gemini 3.5 Flash (cerca de 25 livros) e DeepSeek V4.1 Flash (os demais).
- **685 pares de título e autor**, gerados do catálogo sem LLM: título exato e sem acento; nome do autor e "livros de <autor>".
- **Divisão por livro:** cerca de 20% dos livros (46) ficam fora do treino e formam a validação. Os livros e autores dos casos manuais de título e de autor também não ganham pares de catálogo, para que esses casos meçam livros e autores novos.
- **Dados:** [leia-busca-livros-pt](https://huggingface.co/datasets/nathanjrdev/leia-busca-livros-pt). Código: `evals/embeddings/` no repositório.

## Resultados

Busca **só por vetor** (cosseno) sobre o catálogo inteiro (282 livros), sem busca textual nem reranker. "Antes" é o modelo base.

{TABELA}

### Por que os pares de título e autor

Uma primeira rodada só com pares sintéticos melhorou a intenção, mas derrubou título (Recall@5 0.778 → 0.611) e autor (0.929 → 0.286): como os pedidos sintéticos nunca citam título nem autor, o modelo esqueceu esse tipo de pedido. Os pares do catálogo corrigiram isso sem perder o ganho em intenção.

## O que não foi medido

- **Busca híbrida.** A Léia combina busca textual, vetor e reranker. Os números acima são só do vetor; o ganho no produto depende de trocar o encoder e rodar o gate de não regressão da busca completa.
- **Variância entre sementes.** Uma rodada por configuração; a reexecução com a mesma semente repetiu os números.
- **Mesma origem.** Os pedidos de treino, parte das sinopses e os casos de avaliação vêm de conhecimento de LLM, então o ganho tende a ser otimista.
- **Pedidos reais.** Os pedidos sintéticos são mais longos (mediana de 26 palavras) do que costumam ser os de leitores.

## Como usar

```python
from sentence_transformers import SentenceTransformer

modelo = SentenceTransformer("nathanjrdev/leia-embeddings-pt")
consulta = modelo.encode("um suspense curto para o fim de semana", normalize_embeddings=True)
```

## Limitações

- Catálogo pequeno (282 livros), com foco em literatura lusófona e clássicos. Não use em outro acervo sem avaliar de novo.
- Conjuntos manuais pequenos (14 a 18 casos por tipo): um caso vale cerca de 0.06 de Recall@5.

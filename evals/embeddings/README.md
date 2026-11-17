# Ajuste fino do encoder da Léia

Ajusta o encoder da busca (`paraphrase-multilingual-mpnet-base-v2`) com pedidos sintéticos de
leitores e mede, com honestidade, se ele melhora. Os resultados vão para
`evals/resultados/embeddings_ajuste_<data>.json`; o modelo e o dataset podem ser publicados no
Hugging Face.

## Desenho da avaliação

- **Divisão por livro:** ~20% dos livros (hash do título, determinístico) nunca entram no
  treino. O número que importa é `validacao_livros_nao_vistos`: mostra se o modelo generaliza
  ou só decorou os livros do treino.
- **Casos manuais** (`evals/busca_casos.jsonl`) nunca entram no treino (pedidos idênticos são
  descartados), mas os livros deles podem aparecer no treino com outros pedidos. Use como sinal
  secundário.
- **Só vetor:** `avaliar.py` mede a busca vetorial pura (cosseno), sem texto nem reranker. Para
  saber se o modelo ajuda o produto, troque o encoder e rode `evals/run_busca.py --gate`.
- **Mesma origem:** os pedidos são gerados por LLM a partir das sinopses, que também vieram de
  LLM em parte. O ganho tende a ser otimista; diga isso no model card.

## Onde rodar

O treino precisa baixar o modelo base do Hugging Face. Com GPU (Kaggle ou Colab gratuitos)
leva poucos minutos; em CPU, de dezenas de minutos a horas, conforme o número de pares.
Um notebook público no Kaggle também conta como portfólio.

## Instalação (na raiz do repositório)

```powershell
cd api
uv sync --group ml
uv pip install datasets accelerate python-dotenv huggingface_hub
cd ..
```

## Ordem

Use o Python do venv da API (`api\.venv\Scripts\python` no Windows).

```powershell
python evals/embeddings/gerar_pares.py --limite 3      # teste rápido com 3 livros
python evals/embeddings/gerar_pares.py                 # catálogo inteiro (retomável)
# Leia uma amostra de evals/embeddings/saida/pares_treino.jsonl e apague pedidos ruins.
python evals/embeddings/treinar.py --epocas 3
python evals/embeddings/avaliar.py                     # Recall@5 antes e depois
python evals/embeddings/publicar_hf.py                 # simulação: só monta as pastas
python evals/embeddings/publicar_hf.py --confirmar     # envia privado; revise no site e torne público
```

`gerar_pares.py` usa o `LEIA_MODEL` e a chave do provedor do `.env` (ex.: `GEMINI_API_KEY`
descomentada). Grava a cada livro: se a cota acabar, rode de novo que ele continua.

**No Kaggle (recomendado):** gere os pares na sua máquina, suba `pares_treino.jsonl` e
`pares_validacao.jsonl` como um dataset do Kaggle e importe `kaggle_treino.ipynb`. Ele clona
este repositório, treina com GPU, avalia, empacota o modelo e (opcional) publica no Hugging Face
com o segredo `HF_TOKEN`. Traga de volta o JSON de resultados para `evals/resultados/`.

## Cuidados

- `HF_TOKEN` fica só no `.env`. Os scripts nunca imprimem o token.
- `evals/busca_casos.jsonl` nunca entra no treino.
- Publique os números reais, mesmo que o ganho seja pequeno ou nulo, e explique no model card.
- O dataset publicado não inclui as sinopses por padrão (licenças mistas); veja `publicar_hf.py`.

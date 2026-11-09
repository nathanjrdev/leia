# Ajuste fino de embeddings da Leia

Copie esta pasta para `evals/embeddings/` no repositório da Leia e rode, na raiz, com o venv da api ativo.

## Instalação extra

```powershell
uv pip install datasets accelerate python-dotenv huggingface_hub
```

(`sentence-transformers` e `litellm` a api já usa.) Adicione `evals/embeddings/saida/` ao `.gitignore`.

## Ordem

```powershell
python evals/embeddings/gerar_pares.py --limite 3      # teste rápido com 3 livros
python evals/embeddings/gerar_pares.py                 # catálogo inteiro (retomável)
# Leia uma amostra de evals/embeddings/saida/pares_treino.jsonl e apague pedidos ruins.
python evals/embeddings/treinar.py --epocas 3
python evals/embeddings/avaliar.py                     # Recall@5 antes e depois
python evals/embeddings/publicar_hf.py                 # simulação
python evals/embeddings/publicar_hf.py --confirmar     # envia privado; revise no site e torne público
```

## Cuidados

- `HF_TOKEN` fica só no `.env`. Os scripts nunca imprimem o token.
- `evals/busca_casos.jsonl` nunca entra no treino. Pedidos idênticos a ele são descartados.
- Publique os números reais, mesmo que o ganho seja pequeno, e explique no model card.
- Se treinar no Colab ou no Kaggle, envie `saida/pares_treino.jsonl`, `data/catalogo.json` e esta pasta.

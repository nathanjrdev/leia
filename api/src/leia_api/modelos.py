"""Adaptadores dos modelos do Hugging Face (grupo opcional `ml`).

São o único ponto que baixa e carrega modelos; o resto do código recebe `Encoder` e
`Reranker` por injeção e é testado com falsos.
"""

from collections.abc import Sequence

from leia_api.config import settings
from leia_api.embeddings import MAX_TOKENS_ENCODER, MODELO_PADRAO

MODELO_RERANKER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


class EncoderST:
    def __init__(self, modelo: str = MODELO_PADRAO) -> None:
        import sentence_transformers

        # token explícito do Settings (o mesmo .env das chaves de LLM), não do ambiente
        self._modelo = sentence_transformers.SentenceTransformer(modelo, token=settings.token_hf())
        self._modelo.max_seq_length = MAX_TOKENS_ENCODER

    def encode(self, textos: list[str]) -> list[list[float]]:
        vetores = self._modelo.encode(textos, normalize_embeddings=True)
        return [[float(x) for x in vetor] for vetor in vetores]


class CrossEncoderReranker:
    def __init__(self, modelo: str = MODELO_RERANKER) -> None:
        import sentence_transformers

        self._modelo = sentence_transformers.CrossEncoder(modelo, token=settings.token_hf())

    def score(self, consulta: str, documentos: list[str]) -> Sequence[float]:
        notas = self._modelo.predict([(consulta, doc) for doc in documentos])
        return [float(n) for n in notas]

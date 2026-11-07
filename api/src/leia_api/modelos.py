"""Adaptadores dos modelos do Hugging Face (grupo opcional `ml`).

São o único ponto que baixa e carrega modelos; o resto do código recebe `Encoder` e
`Reranker` por injeção e é testado com falsos.
"""

from collections.abc import Sequence

from leia_api.embeddings import MODELO_PADRAO

MODELO_RERANKER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


class EncoderST:
    def __init__(self, modelo: str = MODELO_PADRAO) -> None:
        from sentence_transformers import SentenceTransformer

        self._modelo = SentenceTransformer(modelo)

    def encode(self, textos: list[str]) -> list[list[float]]:
        vetores = self._modelo.encode(textos, normalize_embeddings=True)
        return [[float(x) for x in vetor] for vetor in vetores]


class CrossEncoderReranker:
    def __init__(self, modelo: str = MODELO_RERANKER) -> None:
        from sentence_transformers import CrossEncoder

        self._modelo = CrossEncoder(modelo)

    def score(self, consulta: str, documentos: list[str]) -> Sequence[float]:
        notas = self._modelo.predict([(consulta, doc) for doc in documentos])
        return [float(n) for n in notas]

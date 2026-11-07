import json
import math
import unicodedata
from pathlib import Path

from leia_api.avaliacao import Caso, carregar_casos, ndcg_at_k, recall_at_k, relevancias
from leia_api.busca import ResultadoBusca


def _res(titulo: str, autor: str = "X") -> ResultadoBusca:
    return ResultadoBusca(
        livro_id=1, titulo=titulo, autores=[autor], ano=None, capa_url=None,
        livres=1, fila=0, score=0.0,
    )  # fmt: skip


def test_recall_hits_only_inside_the_top_k() -> None:
    assert recall_at_k([False, False, True], k=3) == 1.0
    assert recall_at_k([False, False, True], k=2) == 0.0
    assert recall_at_k([], k=5) == 0.0


def test_ndcg_is_one_for_a_perfect_ranking() -> None:
    assert ndcg_at_k([True, True, False], k=10, total_relevantes=2) == 1.0


def test_ndcg_discounts_lower_positions() -> None:
    assert math.isclose(ndcg_at_k([False, True], k=10, total_relevantes=1), 1 / math.log2(3))


def test_ndcg_is_zero_without_relevant_items() -> None:
    assert ndcg_at_k([False, False], k=10, total_relevantes=1) == 0.0
    assert ndcg_at_k([True], k=10, total_relevantes=0) == 0.0


def test_relevance_by_title_ignores_case() -> None:
    caso = Caso(id="c", tipo="titulo", consulta="q", esperados=["Dom Casmurro"])
    assert relevancias(caso, [_res("dom casmurro"), _res("Outro")]) == [True, False]


def test_relevance_ignores_unicode_normalization_form() -> None:
    nfd = unicodedata.normalize("NFD", "Os sertões")
    caso = Caso(id="c", tipo="titulo", consulta="q", esperados=["Os sertões"])
    assert nfd != "Os sertões"
    assert relevancias(caso, [_res(nfd)]) == [True]


def test_relevance_by_author() -> None:
    caso = Caso(id="c", tipo="autor", consulta="q", autor_esperado="Mia Couto")
    assert relevancias(caso, [_res("A", "Mia Couto"), _res("B", "Outro")]) == [True, False]


def test_loads_cases_from_jsonl(tmp_path: Path) -> None:
    arquivo = tmp_path / "casos.jsonl"
    linhas = [
        {"id": "a", "tipo": "titulo", "consulta": "Dom Casmurro", "esperados": ["Dom Casmurro"]},
        {"id": "b", "tipo": "autor", "consulta": "Saramago", "autor_esperado": "José Saramago"},
    ]
    arquivo.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in linhas), "utf-8")
    casos = carregar_casos(arquivo)
    assert [c.id for c in casos] == ["a", "b"]
    assert casos[1].autor_esperado == "José Saramago"

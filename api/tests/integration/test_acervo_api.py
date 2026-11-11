"""Catálogo (público) e estante (autenticada) pela API, com Postgres real."""

import itertools
from collections.abc import Iterator, Sequence
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from leia_api import sessao
from leia_api.config import settings
from leia_api.db import get_session
from leia_api.dependencias import get_encoder, get_reranker
from leia_api.main import app
from leia_api.models import Autor, Categoria, Exemplar, Livro, Usuario

_seq = itertools.count(1)
CONFIRMO = {"confirmo": True}


class _Encoder:
    def encode(self, textos: list[str]) -> Sequence[Sequence[float]]:
        return [[0.0] * 768 for _ in textos]


@pytest.fixture
def api(engine: Engine) -> Iterator[TestClient]:
    def _sessao() -> Iterator[Session]:
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _sessao
    app.dependency_overrides[get_encoder] = lambda: _Encoder()
    app.dependency_overrides[get_reranker] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    with Session(engine) as limpeza:
        for sql in (
            "DELETE FROM reservas WHERE usuario_id IN "
            "(SELECT id FROM usuarios WHERE email LIKE '%@acervo.teste.local')",
            "DELETE FROM locacoes WHERE usuario_id IN "
            "(SELECT id FROM usuarios WHERE email LIKE '%@acervo.teste.local')",
            "DELETE FROM sessoes WHERE usuario_id IN "
            "(SELECT id FROM usuarios WHERE email LIKE '%@acervo.teste.local')",
            "DELETE FROM usuarios WHERE email LIKE '%@acervo.teste.local'",
            "DELETE FROM exemplares WHERE livro_id IN "
            "(SELECT id FROM livros WHERE titulo LIKE 'Livro de acervo %')",
            "DELETE FROM livro_categoria WHERE livro_id IN "
            "(SELECT id FROM livros WHERE titulo LIKE 'Livro de acervo %')",
            "DELETE FROM livro_autor WHERE livro_id IN "
            "(SELECT id FROM livros WHERE titulo LIKE 'Livro de acervo %')",
            "DELETE FROM livros WHERE titulo LIKE 'Livro de acervo %'",
            "DELETE FROM categorias WHERE slug LIKE 'cat-acervo-%'",
            "DELETE FROM autores WHERE nome LIKE 'Autor de acervo %'",
        ):
            limpeza.execute(text(sql))
        limpeza.commit()


def _categoria(engine: Engine) -> str:
    n = next(_seq)
    with Session(engine) as s:
        s.add(Categoria(nome=f"Categoria acervo {n}", slug=f"cat-acervo-{n}"))
        s.commit()
    return f"cat-acervo-{n}"


def _livro(
    engine: Engine, categoria: str | None = None, *, exemplares: int = 1, sufixo: str = ""
) -> tuple[int, str]:
    n = next(_seq)
    with Session(engine) as s:
        livro = Livro(
            titulo=f"Livro de acervo {sufixo or n}",
            sinopse=f"Uma história sobre quasar{n}omega.",
            ano=1950 + n,
        )
        livro.autores = [Autor(nome=f"Autor de acervo {n}")]
        if categoria:
            livro.categorias = [s.query(Categoria).filter_by(slug=categoria).one()]
        s.add(livro)
        s.flush()
        for i in range(exemplares):
            s.add(Exemplar(livro_id=livro.id, codigo=f"AC{n}-{i}"))
        s.commit()
        return livro.id, livro.titulo


def _usuario(engine: Engine) -> tuple[int, str]:
    with Session(engine) as s:
        u = Usuario(nome="Leitor", email=f"u{next(_seq)}@acervo.teste.local", senha_hash="x")
        s.add(u)
        s.commit()
        return u.id, sessao.criar(s, u.id, timedelta(hours=1))


def _logar(client: TestClient, token: str) -> None:
    client.cookies.clear()
    client.cookies.set(settings.sessao_cookie_nome, token)


# ---------- catálogo (público) ----------


def test_categorias_sao_publicas(api: TestClient, engine: Engine) -> None:
    slug = _categoria(engine)

    r = api.get("/categorias")

    assert r.status_code == 200
    assert slug in {c["slug"] for c in r.json()}


def test_listar_livros_filtra_ordena_e_pagina(api: TestClient, engine: Engine) -> None:
    cat = _categoria(engine)
    _livro(engine, cat, sufixo="b")
    _livro(engine, cat, sufixo="a")
    _livro(engine, cat, sufixo="c")
    _livro(engine, _categoria(engine), sufixo="z")  # outra categoria

    r = api.get("/livros", params={"categoria": cat, "limite": 2, "pagina": 1})

    corpo = r.json()
    assert [i["titulo"] for i in corpo["itens"]] == ["Livro de acervo a", "Livro de acervo b"]
    assert corpo["total"] == 3 and corpo["pagina"] == 1
    assert corpo["itens"][0]["autores"][0].startswith("Autor de acervo")
    assert corpo["itens"][0]["livres"] == 1
    segunda = api.get("/livros", params={"categoria": cat, "limite": 2, "pagina": 2}).json()
    assert [i["titulo"] for i in segunda["itens"]] == ["Livro de acervo c"]


def test_listar_livros_so_disponiveis(api: TestClient, engine: Engine) -> None:
    cat = _categoria(engine)
    _livro(engine, cat, sufixo="com")
    _livro(engine, cat, exemplares=0, sufixo="sem")

    r = api.get("/livros", params={"categoria": cat, "apenas_disponiveis": True})

    assert [i["titulo"] for i in r.json()["itens"]] == ["Livro de acervo com"]


def test_buscar_livros_por_texto(api: TestClient, engine: Engine) -> None:
    livro_id, _ = _livro(engine)
    with Session(engine) as s:
        sinopse = s.execute(
            text("SELECT sinopse FROM livros WHERE id = :i"), {"i": livro_id}
        ).scalar_one()
    palavra_unica = sinopse.split()[-1].rstrip(".")  # ex.: quasar7omega

    r = api.get("/livros/busca", params={"q": palavra_unica})

    assert r.status_code == 200
    achado = next(i for i in r.json()["itens"] if i["id"] == livro_id)
    assert achado["livres"] == 1


@pytest.mark.parametrize(
    "rota, params",
    [
        ("/livros", {"pagina": 0}),
        ("/livros", {"limite": 0}),
        ("/livros", {"limite": 500}),
        ("/livros", {"ano_min": 5}),
        ("/livros", {"categoria": "Com Espaço"}),
        ("/livros/busca", {}),
        ("/livros/busca", {"q": ""}),
        ("/livros/busca", {"q": "x" * 400}),
    ],
)
def test_parametros_invalidos_sao_422(api: TestClient, rota: str, params: dict[str, Any]) -> None:
    assert api.get(rota, params=params).status_code == 422


def test_ficha_do_livro(api: TestClient, engine: Engine) -> None:
    cat = _categoria(engine)
    livro_id, titulo = _livro(engine, cat, exemplares=2)

    r = api.get(f"/livros/{livro_id}")

    corpo = r.json()
    assert r.status_code == 200
    assert corpo["titulo"] == titulo
    assert corpo["exemplares"] == 2 and corpo["livres"] == 2 and corpo["fila"] == 0
    assert corpo["categorias"] == [f"Categoria acervo {cat.rsplit('-', 1)[1]}"]
    assert corpo["sinopse"].startswith("Uma história")


def test_ficha_de_livro_inexistente_e_404(api: TestClient) -> None:
    r = api.get("/livros/999999")

    assert r.status_code == 404
    assert r.json()["erro"] == "livro_inexistente"


# ---------- estante e escritas diretas (autenticadas) ----------


def test_estante_exige_sessao(api: TestClient) -> None:
    assert api.get("/estante").status_code == 401
    assert api.post("/livros/1/locar", json=CONFIRMO).status_code == 401
    assert api.post("/locacoes/1/devolver", json=CONFIRMO).status_code == 401


def test_fluxo_locar_renovar_devolver_pela_estante(api: TestClient, engine: Engine) -> None:
    _, token = _usuario(engine)
    _logar(api, token)
    livro_id, titulo = _livro(engine)

    locado = api.post(f"/livros/{livro_id}/locar", json=CONFIRMO)
    assert locado.status_code == 200 and locado.json()["titulo"] == titulo
    estante = api.get("/estante").json()
    assert [a["titulo"] for a in estante["ativas"]] == [titulo]
    locacao_id = estante["ativas"][0]["locacao_id"]

    assert api.post(f"/locacoes/{locacao_id}/renovar", json=CONFIRMO).status_code == 200
    segunda = api.post(f"/locacoes/{locacao_id}/renovar", json=CONFIRMO)
    assert segunda.status_code == 409  # limite de renovações vem da configuração
    devolvido = api.post(f"/locacoes/{locacao_id}/devolver", json=CONFIRMO)
    assert devolvido.status_code == 200
    estante = api.get("/estante").json()
    assert estante["ativas"] == []
    assert [h["titulo"] for h in estante["historico"]] == [titulo]


def test_estante_traz_capa_e_autores_de_locacoes_reservas_e_historico(
    api: TestClient, engine: Engine
) -> None:
    _, token_outro = _usuario(engine)
    _, token = _usuario(engine)
    ativo, _ = _livro(engine)
    devolvido, _ = _livro(engine)
    ocupado, _ = _livro(engine)  # o único exemplar fica com outro leitor: a reserva vira fila
    capas = {ativo: "https://capas.example/a.jpg", devolvido: "https://capas.example/d.jpg"}
    with Session(engine) as s:
        for livro_id, url in capas.items():
            s.get(Livro, livro_id).capa_url = url  # type: ignore[union-attr]
        s.commit()
    _logar(api, token_outro)
    api.post(f"/livros/{ocupado}/locar", json=CONFIRMO)

    _logar(api, token)
    api.post(f"/livros/{ativo}/locar", json=CONFIRMO)
    api.post(f"/livros/{devolvido}/locar", json=CONFIRMO)
    locacao_devolvida = next(
        a["locacao_id"] for a in api.get("/estante").json()["ativas"] if a["livro_id"] == devolvido
    )
    api.post(f"/locacoes/{locacao_devolvida}/devolver", json=CONFIRMO)
    assert api.post(f"/livros/{ocupado}/reservar", json=CONFIRMO).status_code == 200

    estante = api.get("/estante").json()

    [loc] = estante["ativas"]
    assert loc["capa_url"] == capas[ativo] and len(loc["autores"]) == 1
    [res] = estante["reservas"]
    assert res["capa_url"] is None and len(res["autores"]) == 1  # livro sem capa cadastrada
    [hist] = estante["historico"]
    assert hist["capa_url"] == capas[devolvido] and len(hist["autores"]) == 1


@pytest.mark.parametrize("corpo", [None, {}, {"confirmo": False}, {"confirmo": "sim"}])
def test_escrita_sem_confirmacao_explicita_nao_faz_nada(
    api: TestClient, engine: Engine, corpo: dict[str, Any] | None
) -> None:
    _, token = _usuario(engine)
    _logar(api, token)
    livro_id, _ = _livro(engine)

    r = api.post(f"/livros/{livro_id}/locar", json=corpo)

    assert r.status_code == 422
    assert api.get("/estante").json()["ativas"] == []


def test_escrita_nao_aceita_usuario_no_corpo(api: TestClient, engine: Engine) -> None:
    _, token = _usuario(engine)
    _logar(api, token)
    livro_id, _ = _livro(engine)

    r = api.post(f"/livros/{livro_id}/locar", json={"confirmo": True, "usuario_id": 1})

    assert r.status_code == 422


def test_erros_de_regra_viram_409_e_404(api: TestClient, engine: Engine) -> None:
    _, token = _usuario(engine)
    _logar(api, token)
    livro_id, _ = _livro(engine)
    api.post(f"/livros/{livro_id}/locar", json=CONFIRMO)

    repetido = api.post(f"/livros/{livro_id}/locar", json=CONFIRMO)
    sumido = api.post("/livros/999999/locar", json=CONFIRMO)
    sem_locacao = api.post("/locacoes/999999/devolver", json=CONFIRMO)

    assert repetido.status_code == 409 and repetido.json()["erro"] == "livro_ja_locado"
    assert sumido.status_code == 404 and sumido.json()["erro"] == "livro_inexistente"
    assert sem_locacao.status_code == 404 and sem_locacao.json()["erro"] == "locacao_inexistente"


def test_estante_e_acoes_so_enxergam_o_usuario_da_sessao(api: TestClient, engine: Engine) -> None:
    _, dona = _usuario(engine)
    _, intruso = _usuario(engine)
    livro_id, _ = _livro(engine)
    _logar(api, dona)
    api.post(f"/livros/{livro_id}/locar", json=CONFIRMO)
    locacao_id = api.get("/estante").json()["ativas"][0]["locacao_id"]

    _logar(api, intruso)

    assert api.get("/estante").json()["ativas"] == []
    r = api.post(f"/locacoes/{locacao_id}/devolver", json=CONFIRMO)
    assert r.status_code == 404 and r.json()["erro"] == "locacao_inexistente"
    _logar(api, dona)
    assert len(api.get("/estante").json()["ativas"]) == 1


def test_reservar_quando_nao_ha_exemplar_livre(api: TestClient, engine: Engine) -> None:
    _, primeiro = _usuario(engine)
    _, segundo = _usuario(engine)
    livro_id, _ = _livro(engine)
    _logar(api, primeiro)
    api.post(f"/livros/{livro_id}/locar", json=CONFIRMO)
    _logar(api, segundo)

    r = api.post(f"/livros/{livro_id}/reservar", json=CONFIRMO)

    assert r.status_code == 200 and r.json()["posicao"] == 1
    assert [x["titulo"] for x in api.get("/estante").json()["reservas"]][0].startswith("Livro")


def test_cancelar_reserva_pela_estante(api: TestClient, engine: Engine) -> None:
    _, primeiro = _usuario(engine)
    _, segundo = _usuario(engine)
    livro_id, _ = _livro(engine)
    _logar(api, primeiro)
    api.post(f"/livros/{livro_id}/locar", json=CONFIRMO)
    _logar(api, segundo)
    api.post(f"/livros/{livro_id}/reservar", json=CONFIRMO)
    reserva = api.get("/estante").json()["reservas"][0]
    assert reserva["pronta"] is False and reserva["retirar_ate"] is None

    sem_confirmar = api.post(f"/reservas/{reserva['reserva_id']}/cancelar", json={})
    cancelada = api.post(f"/reservas/{reserva['reserva_id']}/cancelar", json=CONFIRMO)
    de_novo = api.post(f"/reservas/{reserva['reserva_id']}/cancelar", json=CONFIRMO)

    assert sem_confirmar.status_code == 422
    assert cancelada.status_code == 200 and cancelada.json()["livro_id"] == livro_id
    assert de_novo.status_code == 409 and de_novo.json()["erro"] == "reserva_encerrada"
    assert api.get("/estante").json()["reservas"] == []


def test_nao_cancela_reserva_de_outro_usuario(api: TestClient, engine: Engine) -> None:
    _, primeiro = _usuario(engine)
    _, segundo = _usuario(engine)
    _, intruso = _usuario(engine)
    livro_id, _ = _livro(engine)
    _logar(api, primeiro)
    api.post(f"/livros/{livro_id}/locar", json=CONFIRMO)
    _logar(api, segundo)
    api.post(f"/livros/{livro_id}/reservar", json=CONFIRMO)
    reserva_id = api.get("/estante").json()["reservas"][0]["reserva_id"]

    _logar(api, intruso)
    r = api.post(f"/reservas/{reserva_id}/cancelar", json=CONFIRMO)

    assert r.status_code == 404 and r.json()["erro"] == "reserva_inexistente"
    _logar(api, segundo)
    assert len(api.get("/estante").json()["reservas"]) == 1


def test_estante_mostra_o_prazo_de_retirada_da_reserva_pronta(
    api: TestClient, engine: Engine
) -> None:
    _, primeiro = _usuario(engine)
    _, segundo = _usuario(engine)
    livro_id, _ = _livro(engine)
    _logar(api, primeiro)
    api.post(f"/livros/{livro_id}/locar", json=CONFIRMO)
    locacao_id = api.get("/estante").json()["ativas"][0]["locacao_id"]
    _logar(api, segundo)
    api.post(f"/livros/{livro_id}/reservar", json=CONFIRMO)
    _logar(api, primeiro)
    api.post(f"/locacoes/{locacao_id}/devolver", json=CONFIRMO)

    _logar(api, segundo)
    reserva = api.get("/estante").json()["reservas"][0]

    assert reserva["pronta"] is True
    assert reserva["retirar_ate"] is not None


def test_busca_publica_tem_limite_por_ip(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "busca_max_por_minuto", 2)

    codigos = [api.get("/livros/busca", params={"q": "memória"}).status_code for _ in range(3)]

    assert codigos == [200, 200, 429]
    assert api.get("/livros/busca", params={"q": "x"}).json()["erro"] == "muitas_buscas"
    assert api.get("/livros").status_code == 200  # a navegação comum não é limitada

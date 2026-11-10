"""O LLM de teste (E2E) precisa dirigir o agente de verdade: busca, locação, clique."""

import itertools
import time
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from leia_api.agente import Agente, ConfigAgente
from leia_api.canal import evento_de_cancelamento, evento_de_confirmacao
from leia_api.ferramentas import ContextoFerramentas, cancelar_acao, confirmar_acao
from leia_api.locacao import RegrasLocacao
from leia_api.models import Autor, Exemplar, Livro, Usuario
from leia_api.modo_teste import EncoderDeTeste, LLMDeTeste

_seq = itertools.count(1)


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s
    with Session(engine) as limpeza:
        for sql in (
            "DELETE FROM locacoes WHERE usuario_id IN "
            "(SELECT id FROM usuarios WHERE email LIKE '%@modoteste.local')",
            "DELETE FROM exemplares WHERE livro_id IN "
            "(SELECT id FROM livros WHERE titulo LIKE 'Livro de modo teste %')",
            "DELETE FROM livro_autor WHERE livro_id IN "
            "(SELECT id FROM livros WHERE titulo LIKE 'Livro de modo teste %')",
            "DELETE FROM livros WHERE titulo LIKE 'Livro de modo teste %'",
            "DELETE FROM autores WHERE nome LIKE 'Autor de modo teste %'",
            "DELETE FROM usuarios WHERE email LIKE '%@modoteste.local'",
        ):
            limpeza.execute(text(sql))
        limpeza.commit()


def _ctx(session: Session) -> tuple[ContextoFerramentas, str, int]:
    n = next(_seq)
    usuario = Usuario(nome="Leitor", email=f"mt{n}@modoteste.local", senha_hash="x")
    livro = Livro(titulo=f"Livro de modo teste {n}", sinopse=f"Uma história sobre zyxquark{n}.")
    livro.autores = [Autor(nome=f"Autor de modo teste {n}")]
    session.add_all([usuario, livro])
    session.flush()
    session.add(Exemplar(livro_id=livro.id, codigo=f"MT{n}-0"))
    session.commit()
    ctx = ContextoFerramentas(
        session=session,
        usuario_id=usuario.id,
        encoder=EncoderDeTeste(),
        reranker=None,
        regras=RegrasLocacao.da_config(),
    )
    return ctx, f"zyxquark{n}", livro.id


def _agente() -> Agente:
    return Agente(LLMDeTeste(), ConfigAgente("PROMPT DE TESTE", 6, 5.0, 60.0, 1))


def test_atraso_configurado_segura_cada_chamada_do_llm_de_teste() -> None:
    """O E2E precisa de um turno com duração para ver o andamento antes do texto."""
    mensagens = [{"role": "user", "content": "oi"}]
    inicio = time.perf_counter()
    LLMDeTeste().completar(mensagens, [], 1.0)
    assert time.perf_counter() - inicio < 0.1  # padrão: sem atraso

    inicio = time.perf_counter()
    LLMDeTeste(atraso_segundos=0.2).completar(mensagens, [], 1.0)
    assert time.perf_counter() - inicio >= 0.2


def test_busca_responde_citando_o_livro_achado(session: Session) -> None:
    ctx, palavra, livro_id = _ctx(session)

    r = _agente().responder(ctx, [], f"quero um livro sobre {palavra}", [])

    assert r.erro is None and not r.propostas
    assert f"Livro de modo teste {palavra.removeprefix('zyxquark')}" in r.texto
    assert livro_id in ctx.livros_vistos


def test_pedir_para_locar_gera_proposta_e_o_clique_conclui(session: Session) -> None:
    ctx, palavra, livro_id = _ctx(session)
    agente = _agente()

    r = agente.responder(ctx, [], f"quero locar {palavra}", [])

    [proposta] = r.propostas
    assert "Confirme" in r.texto
    resultado = confirmar_acao(ctx, proposta.confirmacao_id)
    assert resultado["ok"] is True
    depois = agente.responder(ctx, r.historico, None, [evento_de_confirmacao([resultado])])
    assert "concluída" in depois.texto and not depois.propostas
    n = session.execute(
        text("SELECT count(*) FROM locacoes WHERE usuario_id = :u AND devolvida_em IS NULL"),
        {"u": ctx.usuario_id},
    ).scalar_one()
    assert n == 1


def test_cancelar_nao_repropoe(session: Session) -> None:
    ctx, palavra, _ = _ctx(session)
    agente = _agente()
    r = agente.responder(ctx, [], f"quero locar {palavra}", [])
    [proposta] = r.propostas
    cancelar_acao(ctx, proposta.confirmacao_id)

    depois = agente.responder(ctx, r.historico, None, [evento_de_cancelamento([proposta.resumo])])

    assert "cancel" in depois.texto.lower() and not depois.propostas


def test_livro_inexistente_nao_inventa_titulo(session: Session) -> None:
    ctx, _, _ = _ctx(session)

    r = _agente().responder(ctx, [], "quero um livro sobre qwertyuiopasdf", [])

    assert r.erro is None and "Não encontrei" in r.texto


def test_encoder_de_teste_devolve_vetores_do_tamanho_do_modelo() -> None:
    vetores: Any = EncoderDeTeste().encode(["a", "b"])
    assert len(vetores) == 2 and len(vetores[0]) == 768

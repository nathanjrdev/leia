"""Filtro de títulos do streaming: só mostra trecho entre aspas depois de validado."""

from leia_api.agente import FiltroDeTitulos, titulos_sem_origem

PERMITIDOS = {"Dom Casmurro", "A Culpa é das Estrelas"}


def _rodar(pedacos: list[str], permitidos: set[str] = PERMITIDOS) -> tuple[str, FiltroDeTitulos]:
    saida: list[str] = []
    f = FiltroDeTitulos(permitidos, saida.append)
    for p in pedacos:
        f.receber(p)
    f.finalizar()
    return "".join(saida), f


def test_texto_sem_aspas_sai_inteiro() -> None:
    texto, f = _rodar(["Olá! ", "Posso ", "ajudar?"])
    assert texto == "Olá! Posso ajudar?" and not f.bloqueado


def test_titulo_permitido_sai_depois_de_fechar_as_aspas() -> None:
    saida: list[str] = []
    f = FiltroDeTitulos(PERMITIDOS, saida.append)
    f.receber("Recomendo “Dom Cas")
    assert "".join(saida) == "Recomendo "  # o título ainda não fechou: fica retido
    f.receber("murro”, um clássico.")
    f.finalizar()
    assert "".join(saida) == "Recomendo “Dom Casmurro”, um clássico."


def test_titulo_inventado_nunca_sai_e_trava_o_resto() -> None:
    texto, f = _rodar(["Leia “Livro ", "Inventado” e ", "também “Dom Casmurro”."])
    assert "Inventado" not in texto and "Dom Casmurro" not in texto
    assert texto == "Leia " and f.bloqueado


def test_aspas_retas_e_angulares_tambem_sao_conferidas() -> None:
    assert _rodar(['Leia "Dom Casmurro".'])[0] == 'Leia "Dom Casmurro".'
    assert _rodar(["Leia «Fantasma»."])[1].bloqueado
    assert _rodar(['Leia "Fantasma".'])[1].bloqueado


def test_titulo_sem_acento_e_caixa_diferente_vale() -> None:
    texto, f = _rodar(["Leia “a culpa e das estrelas”."])
    assert not f.bloqueado and "estrelas" in texto


def test_citacao_longa_entre_aspas_nao_e_titulo() -> None:
    longa = "“" + " ".join(["palavra"] * 12) + "”"
    texto, f = _rodar([f"Ele disse {longa}."])
    assert not f.bloqueado and texto == f"Ele disse {longa}."


def test_aspas_abertas_por_tempo_demais_travam_por_precaucao() -> None:
    texto, f = _rodar(["Veja “" + "x" * 250 + "” fim"])
    assert f.bloqueado and texto == "Veja "


def test_aspas_que_nao_fecham_saem_no_fim() -> None:
    texto, f = _rodar(["Uma aspa “solta sem fechar"])
    assert texto == "Uma aspa “solta sem fechar" and not f.bloqueado


def test_equivale_a_checagem_do_texto_inteiro() -> None:
    """O que o filtro libera é o que a checagem final aceitaria (mesma função, por trecho)."""
    for frase in (
        "Leia “Dom Casmurro” e “Fantasma”.",
        "Só “Dom Casmurro”.",
        "Nada entre aspas.",
        'Mistura "Dom Casmurro" e «A Culpa é das Estrelas».',
    ):
        texto, f = _rodar(list(frase))  # um caractere por vez: o pior caso de pedaços
        assert f.bloqueado == bool(titulos_sem_origem(frase, PERMITIDOS))
        if not f.bloqueado:
            assert texto == frase

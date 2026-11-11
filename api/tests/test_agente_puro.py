import pytest

from leia_api.agente import carregar_prompt, parse_argumentos, titulos_sem_origem
from leia_api.config import Settings


def test_prompt_v4_candidato_soma_as_regras_da_sessao_de_teste_a_v3() -> None:
    v3, v4 = carregar_prompt("v3"), carregar_prompt("v4")
    for linha in v3.splitlines():
        assert linha in v4  # nada da v3 se perde
    assert "trecho de sinopse do evento" in v4  # locação concluída comenta o livro
    assert "use só a sinopse que a ferramenta devolveu" in v4
    assert "reservar) é só para livro sem exemplar livre" in v4
    assert "livros de programação ou tecnologia" in v4
    assert Settings().prompt_versao == "v4"  # adotada: gate no Haiku 54/55 vs v2 46/55 (diário 5.7)


@pytest.mark.parametrize("versao", ["v1", "v2", "v4"])
def test_prompt_traz_as_regras_do_plano(versao: str) -> None:
    p = carregar_prompt(versao)

    for trecho in (
        "sinopse_nao_confiavel",
        "usuario_id",
        "confirm",
        "no máximo 3",
        "“",
    ):
        assert trecho in p
    assert "3 locações" not in p  # regra de negócio não mora no prompt


@pytest.mark.parametrize("versao", ["../config", "v1/../v1", "", "x1", "v1.md"])
def test_versao_de_prompt_invalida_e_rejeitada(versao: str) -> None:
    with pytest.raises(ValueError):
        carregar_prompt(versao)


def test_versao_de_prompt_inexistente() -> None:
    with pytest.raises(FileNotFoundError):
        carregar_prompt("v999")


def test_prompt_v2_nao_deixa_repetir_entre_aspas_o_livro_que_nao_veio_de_ferramenta() -> None:
    p = carregar_prompt("v2")

    assert "nunca escreva o título dele entre aspas" in p
    assert "Busque antes de responder" in p
    assert "não escreva entre aspas o título de um livro que você não consultou" in p
    assert carregar_prompt("v1") != p  # v1 fica intacto como baseline


def test_prompt_v3_candidato_nao_perde_as_regras_da_v2() -> None:
    """v3 só muda o tratamento de temas amplos; grounding, ações e segurança são os da v2."""
    v2, v3 = carregar_prompt("v2"), carregar_prompt("v3")
    assert v3 != v2
    secoes_v2 = v2.split("## Como você trabalha", 1)[1]
    assert v3.endswith(secoes_v2)  # tudo a partir de "Como você trabalha" é idêntico
    assert "buscar_livros" in v3 and "188" in v3  # tema amplo busca; sofrimento indica apoio
    assert "ainda não foi treinada" in v3
    assert Settings().prompt_versao != "v3"  # v3 nunca virou padrão: foi absorvida pela v4


def test_configuracao_seleciona_a_versao_do_prompt() -> None:
    assert Settings().prompt_versao == "v4"  # v4 passou no gate da suíte do agente (diário 5.7)
    assert Settings(prompt_versao="v1").prompt_versao == "v1"


def test_titulos_sem_origem_acha_o_inventado() -> None:
    texto = "Recomendo “Dom Casmurro” e também “Livro Fantasma”."
    assert titulos_sem_origem(texto, {"Dom Casmurro"}) == ["Livro Fantasma"]


def test_titulos_sem_origem_ignora_caixa_acento_e_aspas_retas() -> None:
    texto = 'Leia "memórias póstumas de brás cubas" e «O Cortiço».'
    assert titulos_sem_origem(texto, {"Memórias Póstumas de Brás Cubas", "O cortiço"}) == []


def test_titulos_sem_origem_sem_aspas_nao_acusa_nada() -> None:
    assert titulos_sem_origem("Posso ajudar com outra busca?", set()) == []


def test_titulos_sem_origem_ignora_frases_longas_e_vazias() -> None:
    longa = "“" + " ".join(["palavra"] * 12) + "”"
    assert titulos_sem_origem(f"Ele disse {longa} e “ ”.", set()) == []


def test_titulos_sem_origem_aceita_trecho_do_titulo_com_subtitulo() -> None:
    assert titulos_sem_origem("“Vidas Secas”", {"Vidas Secas: romance"}) == []


def test_parse_argumentos() -> None:
    assert parse_argumentos('{"livro_id": 3}') == {"livro_id": 3}
    assert parse_argumentos("") == {}
    assert parse_argumentos(None) == {}
    assert parse_argumentos({"a": 1}) == {"a": 1}
    # JSON inválido ou não-objeto nunca vira argumento válido
    assert "_argumentos_ilegiveis" in parse_argumentos("{quebrado")
    assert "_argumentos_ilegiveis" in parse_argumentos("[1, 2]")

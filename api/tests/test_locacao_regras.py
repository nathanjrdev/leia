from leia_api.config import Settings
from leia_api.locacao import RegrasLocacao


def test_regras_padrao_vem_da_configuracao() -> None:
    regras = RegrasLocacao.da_config(Settings())

    assert (regras.max_locacoes, regras.prazo_dias, regras.max_renovacoes) == (3, 14, 1)


def test_regras_seguem_a_configuracao_e_nao_constantes() -> None:
    config = Settings(max_locacoes_simultaneas=5, prazo_locacao_dias=21, max_renovacoes=2)

    regras = RegrasLocacao.da_config(config)

    assert (regras.max_locacoes, regras.prazo_dias, regras.max_renovacoes) == (5, 21, 2)

from leia_api.senha import gerar_hash, verificar


def test_hash_nao_contem_a_senha_e_verifica() -> None:
    h = gerar_hash("uma senha longa 123")

    assert "uma senha longa 123" not in h
    assert verificar("uma senha longa 123", h) is True


def test_senha_errada_nao_verifica() -> None:
    h = gerar_hash("correta-horse-battery")

    assert verificar("correta-horse-batter", h) is False
    assert verificar("", h) is False


def test_mesma_senha_gera_hashes_diferentes() -> None:
    assert gerar_hash("igual-igual-igual") != gerar_hash("igual-igual-igual")


def test_hash_malformado_nunca_verifica_nem_levanta() -> None:
    for lixo in ("", "x", "scrypt$1$2", "bcrypt$a$b$c$d$e", "scrypt$a$b$c$d$e", "x" * 400):
        assert verificar("qualquer", lixo) is False


def test_verifica_senha_com_acentos_e_emoji() -> None:
    h = gerar_hash("açaí-com-pão-📚")

    assert verificar("açaí-com-pão-📚", h) is True
    assert verificar("acai-com-pao-📚", h) is False

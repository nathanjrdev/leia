from leia_api.limite import LimitadorJanela


def test_permite_ate_o_maximo_e_depois_bloqueia() -> None:
    lim = LimitadorJanela()

    assert [lim.registrar("a", 3, 60.0, agora=float(i)) for i in range(5)] == [
        True,
        True,
        True,
        False,
        False,
    ]


def test_chaves_sao_independentes() -> None:
    lim = LimitadorJanela()
    for _ in range(3):
        lim.registrar("a", 3, 60.0, agora=0.0)

    assert lim.excedeu("a", 3, 60.0, agora=1.0) is True
    assert lim.excedeu("b", 3, 60.0, agora=1.0) is False


def test_janela_desliza_e_libera_de_novo() -> None:
    lim = LimitadorJanela()
    for _ in range(3):
        lim.registrar("a", 3, 60.0, agora=0.0)

    assert lim.excedeu("a", 3, 60.0, agora=59.9) is True
    assert lim.excedeu("a", 3, 60.0, agora=60.1) is False


def test_excedeu_nao_conta_como_tentativa() -> None:
    lim = LimitadorJanela()

    for _ in range(10):
        assert lim.excedeu("a", 2, 60.0, agora=0.0) is False
    assert lim.registrar("a", 2, 60.0, agora=0.0) is True


def test_zerar_limpa_a_chave() -> None:
    lim = LimitadorJanela()
    for _ in range(3):
        lim.registrar("a", 3, 60.0, agora=0.0)

    lim.zerar("a")

    assert lim.excedeu("a", 3, 60.0, agora=1.0) is False


def test_memoria_nao_cresce_para_sempre() -> None:
    lim = LimitadorJanela(max_chaves=100)

    for i in range(1000):
        lim.registrar(f"ip-{i}", 5, 60.0, agora=float(i))

    assert lim.tamanho() <= 100

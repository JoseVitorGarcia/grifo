"""Normalizacao do que o modelo devolve — hoje, a pagina dos achados."""

import pytest

from analisador.analise import normalizar_pagina
from analisador.marcacao import paginas_do_rotulo


@pytest.mark.parametrize(
    "bruto, esperado",
    [
        ("[p. 1-3]", "1-3"),   # o modelo repete o rotulo do bloco
        ("p. 2", "2"),
        ("2", "2"),
        ("pagina 4", "4"),
        ("5-5", "5"),          # intervalo degenerado vira pagina unica
        ("3\u20134", "3-4"),    # travessao em vez de hifen
        ("", ""),
        ("nao informado", ""),
        (None, ""),
        (7, "7"),
    ],
)
def test_normaliza_a_pagina_do_achado(bruto, esperado):
    assert normalizar_pagina(bruto) == esperado


@pytest.mark.parametrize(
    "bruto, esperado",
    [
        ("[p. 1-3]", {1, 2, 3}),
        ("p. 2", {2}),
        ("", None),
        ("nao informado", None),
        ("4-2", {2, 3, 4}),  # invertido pelo modelo, ainda assim util
    ],
)
def test_intervalo_de_paginas_para_o_grifo(bruto, esperado):
    assert paginas_do_rotulo(bruto) == esperado

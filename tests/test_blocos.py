import pytest

from analisador.blocos import dividir
from analisador.pdf import Documento, Pagina


def documento_de(paginas: list[str]) -> Documento:
    objetos, partes, cursor = [], [], 0
    for numero, texto in enumerate(paginas, start=1):
        bloco = texto + "\n\n"
        objetos.append(Pagina(numero, texto, cursor, cursor + len(bloco)))
        partes.append(bloco)
        cursor += len(bloco)
    return Documento(texto="".join(partes).strip(), paginas=objetos)


def test_texto_curto_vira_um_unico_bloco():
    blocos = dividir(documento_de(["texto pequeno"]), tamanho=6000)
    assert len(blocos) == 1
    assert blocos[0].texto == "texto pequeno"


def test_divide_texto_longo_em_varios_blocos():
    paragrafo = "Uma frase qualquer do artigo. " * 40  # ~1200 chars
    blocos = dividir(documento_de(["\n\n".join([paragrafo] * 10)]), tamanho=2000, sobreposicao=100)
    assert len(blocos) > 3
    assert all(len(b.texto) <= 2100 for b in blocos)


def test_blocos_cobrem_o_texto_inteiro():
    texto = "\n\n".join(f"Paragrafo numero {i} com algum conteudo textual." for i in range(200))
    doc = documento_de([texto])
    blocos = dividir(doc, tamanho=1500, sobreposicao=100)
    assert blocos[0].inicio == 0
    assert blocos[-1].fim == len(doc.texto)
    for anterior, seguinte in zip(blocos, blocos[1:]):
        assert seguinte.inicio <= anterior.fim  # sem buraco entre blocos


def test_bloco_sabe_as_paginas_de_origem():
    doc = documento_de(["a" * 100, "b" * 100, "c" * 100])
    blocos = dividir(doc, tamanho=10_000)
    assert blocos[0].pagina_inicial == 1
    assert blocos[0].pagina_final == 3
    assert blocos[0].rotulo == "p. 1-3"


def test_tamanho_invalido_e_rejeitado():
    with pytest.raises(ValueError):
        dividir(documento_de(["x"]), tamanho=0)

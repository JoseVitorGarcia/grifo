"""Grifo das passagens no PDF: coordenadas, cores e criterio de similaridade."""

import io

import pytest
from pypdf import PdfReader

from analisador.analise import Achado, Analise
from analisador.marcacao import CORES, marcar

from pdf_falso import montar_pdf

PAGINAS = [
    ["Estudo sobre telemedicina aplicada", "A telemedicina melhorou a adesao ao tratamento."],
    ["Metodos", "Ensaio clinico randomizado com 240 pacientes acompanhados por 12 meses."],
]


def anotacoes(pdf: bytes) -> list[dict]:
    leitor = PdfReader(io.BytesIO(pdf))
    encontradas = []
    for numero, pagina in enumerate(leitor.pages, start=1):
        for referencia in pagina.get("/Annots") or []:
            objeto = referencia.get_object()
            encontradas.append(
                {
                    "pagina": numero,
                    "subtipo": objeto.get("/Subtype"),
                    "cor": objeto.get("/C"),
                    "comentario": str(objeto.get("/Contents", "")),
                    "rect": [float(v) for v in objeto["/Rect"]],
                    "quads": [float(v) for v in objeto.get("/QuadPoints", [])],
                }
            )
    return encontradas


def test_marca_a_keyword_em_todas_as_ocorrencias():
    resultado = marcar(montar_pdf(PAGINAS), keywords=["telemedicina"])
    assert resultado.total == 2
    marcadas = anotacoes(resultado.pdf)
    assert all(a["subtipo"] == "/Highlight" for a in marcadas)
    assert [a["pagina"] for a in marcadas] == [1, 1]


def test_pdf_continua_legivel_apos_a_marcacao():
    resultado = marcar(montar_pdf(PAGINAS), keywords=["telemedicina"])
    leitor = PdfReader(io.BytesIO(resultado.pdf))
    assert len(leitor.pages) == 2
    assert "telemedicina" in leitor.pages[0].extract_text()


def test_comentario_identifica_a_keyword():
    resultado = marcar(montar_pdf(PAGINAS), keywords=["telemedicina"])
    assert anotacoes(resultado.pdf)[0]["comentario"] == "Keyword: telemedicina"


def test_retangulo_cai_dentro_da_pagina_e_tem_area():
    resultado = marcar(montar_pdf(PAGINAS), keywords=["telemedicina"])
    x0, y0, x1, y1 = anotacoes(resultado.pdf)[0]["rect"]
    assert 0 <= x0 < x1 <= 612
    assert 0 <= y0 < y1 <= 792
    assert (x1 - x0) > 10 and (y1 - y0) > 5


def test_quadpoints_tem_oito_numeros_por_linha_marcada():
    resultado = marcar(montar_pdf(PAGINAS), keywords=["telemedicina"])
    quads = anotacoes(resultado.pdf)[0]["quads"]
    assert len(quads) % 8 == 0 and len(quads) >= 8


def test_keyword_ausente_nao_gera_marcacao():
    resultado = marcar(montar_pdf(PAGINAS), keywords=["quimioterapia"])
    assert resultado.total == 0
    assert resultado.nao_localizadas == ["quimioterapia"]
    assert anotacoes(resultado.pdf) == []


def test_busca_flexivel_marca_o_plural():
    pdf = montar_pdf([["Foram avaliados varios algoritmos supervisionados."]])
    assert marcar(pdf, keywords=["algoritmo"], flexivel=True).total == 1
    assert marcar(pdf, keywords=["algoritmo"], flexivel=False).total == 0


def test_keyword_com_acento_casa_sem_acento_no_pdf():
    pdf = montar_pdf([["A analise estatistica foi feita depois."]])
    assert marcar(pdf, keywords=["análise estatística"]).total == 1


def test_evidencia_literal_e_marcada_em_verde():
    analise = Analise(
        achados=[
            Achado(
                afirmacao="O ensaio teve 240 pacientes",
                evidencia="Ensaio clinico randomizado com 240 pacientes acompanhados por 12 meses.",
                pagina="2",
            )
        ]
    )
    resultado = marcar(montar_pdf(PAGINAS), analise=analise)
    verdes = [m for m in resultado.marcacoes if m.categoria == "evidencia"]
    assert len(verdes) == 1
    assert verdes[0].pagina == 2
    marcada = [a for a in anotacoes(resultado.pdf) if a["comentario"].startswith("Achado")][0]
    esperado = [round(int(CORES["evidencia"][i : i + 2], 16) / 255, 4) for i in (0, 2, 4)]
    assert [round(float(c), 4) for c in marcada["cor"]] == pytest.approx(esperado, abs=0.01)


def test_evidencia_parafraseada_ainda_e_localizada():
    analise = Analise(
        achados=[
            Achado(
                afirmacao="Amostra de 240 pacientes",
                evidencia="Ensaio randomizado com 240 pacientes acompanhados durante 12 meses",
                pagina="2",
            )
        ]
    )
    resultado = marcar(montar_pdf(PAGINAS), analise=analise)
    assert any(m.categoria == "evidencia" for m in resultado.marcacoes)


def test_evidencia_inventada_nao_e_marcada():
    analise = Analise(
        achados=[
            Achado(
                afirmacao="Custo caiu pela metade",
                evidencia="A intervencao reduziu o custo hospitalar em 50% no primeiro trimestre",
                pagina="2",
            )
        ]
    )
    resultado = marcar(montar_pdf(PAGINAS), analise=analise)
    assert [m for m in resultado.marcacoes if m.categoria == "evidencia"] == []
    assert resultado.nao_localizadas  # o trecho volta como nao localizado


def test_limiar_mais_alto_rejeita_parafrase_distante():
    analise = Analise(
        achados=[Achado(afirmacao="x", evidencia="Ensaio com 240 pacientes por 12 meses", pagina="2")]
    )
    frouxo = marcar(montar_pdf(PAGINAS), analise=analise, limiar=0.5)
    rigido = marcar(montar_pdf(PAGINAS), analise=analise, limiar=0.99)
    assert frouxo.total > rigido.total


def test_desligar_evidencias_marca_so_keywords():
    analise = Analise(
        achados=[Achado(afirmacao="a", evidencia="Ensaio clinico randomizado com 240 pacientes", pagina="2")]
    )
    resultado = marcar(montar_pdf(PAGINAS), analise=analise, keywords=["telemedicina"], marcar_evidencias=False)
    assert set(resultado.por_categoria()) == {"keyword"}


def test_pdf_sem_texto_nao_quebra():
    resultado = marcar(montar_pdf([[""]]), keywords=["telemedicina"])
    assert resultado.total == 0
    assert len(PdfReader(io.BytesIO(resultado.pdf)).pages) == 1


def test_contagem_por_categoria():
    analise = Analise(
        achados=[Achado(afirmacao="a", evidencia="Ensaio clinico randomizado com 240 pacientes", pagina="2")]
    )
    resultado = marcar(montar_pdf(PAGINAS), analise=analise, keywords=["telemedicina"])
    contagem = resultado.por_categoria()
    assert contagem["keyword"] == 2
    assert contagem["evidencia"] == 1

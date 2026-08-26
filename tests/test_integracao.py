"""Fluxo completo contra um Ollama falso servido por HTTP local.

Garante que cliente, orquestracao e relatorio funcionam juntos sem depender
do modelo real (que e lento e nao determinista).
"""

from __future__ import annotations

import json

import pytest

from analisador.analise import (
    Analise,
    extrair_achados,
    extrair_limitacoes,
    levantar_notas,
    montar_resumo,
    sintetizar_keyword,
    sugerir_keywords,
)
from analisador.keywords import buscar_varias
from analisador.llm import ClienteOllama
from analisador.pdf import extrair_documento
from analisador.relatorio import para_json, para_markdown

from ollama_falso import subir
from pdf_falso import montar_pdf

PAGINAS = [
    [
        "Efeito da telemedicina na adesao ao tratamento",
        "Abstract",
        "Este estudo avalia a telemedicina em pacientes cronicos.",
        "Introduction",
        "A adesao ao tratamento e um problema conhecido.",
    ],
    [
        "Methods",
        "Ensaio clinico randomizado com 240 pacientes acompanhados por 12 meses.",
        "Results",
        "A adesao subiu 18% no grupo com telemedicina.",
    ],
    [
        "Discussion",
        "A telemedicina mostrou efeito consistente, apesar da amostra restrita a um hospital.",
        "Conclusion",
        "Recomenda-se ampliar o uso de telemedicina.",
        "References",
        "[1] Silva, 2021.",
        "[2] Souza, 2019.",
    ],
]


@pytest.fixture(scope="module")
def servidor():
    httpd, url = subir()
    yield url
    httpd.shutdown()


@pytest.fixture(scope="module")
def documento():
    return extrair_documento(montar_pdf(PAGINAS, titulo="Telemedicina e adesao"))


@pytest.fixture(scope="module")
def cliente(servidor):
    return ClienteOllama(url=servidor, modelo="gemma3:4b", timeout_s=15)


def test_diagnostico_ok(cliente):
    ok, mensagem = cliente.diagnostico()
    assert ok and "pronto" in mensagem


def test_pipeline_completo_gera_relatorio(cliente, documento):
    analise = Analise()
    analise.notas, blocos = levantar_notas(cliente, documento, tamanho_bloco=400, max_blocos=5)
    assert analise.notas and blocos

    analise.resumo = montar_resumo(cliente, analise.notas, documento)
    analise.achados = extrair_achados(cliente, analise.notas, documento)
    analise.limitacoes = extrair_limitacoes(cliente, analise.notas, documento)
    analise.keywords_sugeridas = sugerir_keywords(cliente, analise.notas, documento)

    assert analise.resumo["metodologia"].startswith("Ensaio")
    assert analise.achados[0].pagina == "2"
    assert analise.limitacoes == ["Amostra de um unico hospital"]
    assert "telemedicina" in analise.keywords_sugeridas

    for resultado in buscar_varias(documento, ["telemedicina", "quimioterapia"]):
        analise.sinteses.append(sintetizar_keyword(cliente, resultado))

    encontrada, ausente = analise.sinteses
    assert encontrada.resultado.total >= 3
    assert "nao aparece literalmente" in ausente.resumo

    markdown = para_markdown(documento, analise, modelo="gemma3:4b")
    assert "## Resumo estruturado" in markdown
    assert "Amostra de um unico hospital" in markdown
    assert "telemedicina" in markdown

    dados = json.loads(para_json(documento, analise, modelo="gemma3:4b"))
    assert dados["modelo"] == "gemma3:4b"
    assert dados["documento"]["paginas"] == 3
    assert dados["keywords"][0]["total_ocorrencias"] >= 3
    assert dados["achados"][0]["afirmacao"] == "A adesao subiu 18%"


def test_lote_de_dois_artigos_gera_consolidado(cliente, documento):
    """Dois artigos analisados contra o Ollama falso e comparados no relatorio."""
    from analisador.blocos import dividir
    from analisador.lote import Item, comparar_keywords
    from analisador.relatorio import para_markdown_lote

    outro = extrair_documento(
        montar_pdf(
            [["Custo da telessaude", "Abstract", "Analise de custo sem mencao a adesao."]],
            titulo="Custo da telessaude",
        )
    )
    itens = [
        Item(assinatura="a", nome="artigo_a.pdf", documento=documento),
        Item(assinatura="b", nome="artigo_b.pdf", documento=outro),
    ]

    for item in itens:
        analise = Analise()
        analise.notas, item.blocos = levantar_notas(cliente, item.documento, tamanho_bloco=400, max_blocos=4)
        analise.resumo = montar_resumo(cliente, analise.notas, item.documento)
        for resultado in buscar_varias(item.documento, ["telemedicina", "randomizado"]):
            analise.sinteses.append(sintetizar_keyword(cliente, resultado))
        item.analise = analise
        assert item.blocos == dividir(item.documento, tamanho=400)

    comparacao = {linha["Keyword"]: linha for linha in comparar_keywords(itens)}
    assert comparacao["telemedicina"]["artigo_a.pdf"] >= 3
    assert comparacao["telemedicina"]["artigo_b.pdf"] == 0
    assert comparacao["randomizado"]["artigo_b.pdf"] == 0

    markdown = para_markdown_lote(itens, modelo="gemma3:4b")
    assert "**Artigos no lote:** 2 · **Analisados:** 2" in markdown
    assert "# Arquivo: artigo_a.pdf" in markdown
    assert "# Arquivo: artigo_b.pdf" in markdown
    assert "nao aparece em artigo_b.pdf" in markdown


def test_pagina_do_achado_chega_limpa_ao_relatorio(cliente, documento):
    """O modelo devolve '[p. 1-3]'; o relatorio nao pode repetir o prefixo 'p.'."""
    notas, _ = levantar_notas(cliente, documento, tamanho_bloco=4000, max_blocos=2)
    achados = extrair_achados(cliente, notas, documento)
    assert achados
    for achado in achados:
        assert "p." not in achado.pagina
        assert "[" not in achado.pagina

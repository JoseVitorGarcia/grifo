import pytest

from analisador.keywords import (
    buscar_keyword,
    normalizar,
    normalizar_com_mapa,
    separar_keywords,
)
from analisador.pdf import Documento, Pagina, Secao


def documento_de(paginas: list[str], secoes=None) -> Documento:
    objetos, partes, cursor = [], [], 0
    for numero, texto in enumerate(paginas, start=1):
        bloco = texto + "\n\n"
        objetos.append(Pagina(numero, texto, cursor, cursor + len(bloco)))
        partes.append(bloco)
        cursor += len(bloco)
    return Documento(texto="".join(partes).strip(), paginas=objetos, secoes=secoes or [])


def test_normalizacao_remove_acento_e_caixa():
    assert normalizar("Análise Estatística") == "analise estatistica"


def test_mapa_preserva_indices_do_texto_original():
    texto = "Viés amostral"
    norm, mapa = normalizar_com_mapa(texto)
    assert norm == "vies amostral"
    # O 'e' normalizado (indice 2) veio do 'ê'... aqui do 'é' no indice 2 do original
    assert texto[mapa[2]] == "é"
    assert texto[mapa[norm.index("amostral")]] == "a"


def test_encontra_keyword_ignorando_acento():
    doc = documento_de(["O estudo trata de viés amostral em pesquisas."])
    resultado = buscar_keyword(doc, "vies amostral")
    assert resultado.total == 1
    assert resultado.ocorrencias[0].termo_encontrado == "viés amostral"


def test_trecho_marca_o_termo_no_texto_original():
    doc = documento_de(["Antes do termo, machine learning aparece aqui, depois segue."])
    resultado = buscar_keyword(doc, "machine learning")
    assert "**machine learning**" in resultado.ocorrencias[0].trecho


def test_nao_casa_dentro_de_outra_palavra():
    doc = documento_de(["As partes do experimento foram descritas."])
    assert buscar_keyword(doc, "arte", flexivel=False).total == 0


def test_pagina_correta_para_cada_ocorrencia():
    doc = documento_de(["primeira pagina sem o termo", "aqui aparece regressao", "regressao de novo"])
    resultado = buscar_keyword(doc, "regressao")
    assert resultado.total == 2
    assert resultado.paginas == [2, 3]


def test_busca_flexivel_pega_plural():
    doc = documento_de(["Foram avaliados varios algoritmos supervisionados."])
    assert buscar_keyword(doc, "algoritmo", flexivel=True).total == 1
    assert buscar_keyword(doc, "algoritmo", flexivel=False).total == 0


def test_keyword_com_hifen_e_espaco_sao_equivalentes():
    doc = documento_de(["Aplicamos aprendizado-de-maquina no conjunto."])
    assert buscar_keyword(doc, "aprendizado de maquina").total == 1


def test_densidade_por_mil_palavras():
    doc = documento_de([" ".join(["dado"] * 500)])
    resultado = buscar_keyword(doc, "dado", flexivel=False)
    assert resultado.total == 500
    assert resultado.densidade_por_mil == 1000.0


def test_secao_da_ocorrencia():
    doc = documento_de(["Metodos\nUsamos regressao linear."])
    doc.secoes = [Secao(nome="metodo", titulo="Metodos", inicio=0, fim=len(doc.texto))]
    resultado = buscar_keyword(doc, "regressao linear")
    assert resultado.ocorrencias[0].secao == "Metodos"


def test_separar_keywords_aceita_virgula_ponto_e_virgula_e_linha():
    assert separar_keywords("a, b; c\nd") == ["a", "b", "c", "d"]


def test_separar_keywords_remove_duplicatas_ignorando_acento():
    assert separar_keywords("Viés, vies, VIÉS") == ["Viés"]


def test_keyword_vazia_e_rejeitada():
    doc = documento_de(["texto"])
    with pytest.raises(ValueError):
        buscar_keyword(doc, "   ")


def test_max_ocorrencias_limita_lista_mas_nao_o_total():
    doc = documento_de([" ".join(["termo"] * 60)])
    resultado = buscar_keyword(doc, "termo", flexivel=False, max_ocorrencias=5)
    assert resultado.total == 60
    assert len(resultado.ocorrencias) == 5

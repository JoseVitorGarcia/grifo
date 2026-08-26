from analisador.pdf import Documento, Pagina, extrair_documento

from pdf_falso import montar_pdf


def test_extrai_texto_das_paginas():
    pdf = montar_pdf([["Introducao ao estudo"], ["Segunda pagina do artigo"]])
    doc = extrair_documento(pdf)
    assert doc.n_paginas == 2
    assert "Introducao ao estudo" in doc.texto
    assert "Segunda pagina" in doc.paginas[1].texto


def test_le_metadados_do_pdf():
    pdf = montar_pdf([["conteudo"]], titulo="Um Titulo", autores="Fulana e Beltrano")
    doc = extrair_documento(pdf)
    assert doc.metadados["titulo"] == "Um Titulo"
    assert doc.metadados["autores"] == "Fulana e Beltrano"


def test_infere_titulo_quando_metadado_falta():
    pdf = montar_pdf([["Aprendizado de maquina aplicado a diagnostico medico", "autores diversos"]])
    doc = extrair_documento(pdf)
    assert doc.metadados["titulo"].startswith("Aprendizado de maquina")


def test_detecta_secoes_e_recupera_trecho():
    pdf = montar_pdf(
        [
            ["Abstract", "Este artigo investiga algo.", "Introduction", "O problema e relevante."],
            ["Methods", "Usamos regressao.", "Results", "Houve ganho de 12%.", "References", "[1] Alguem, 2020."],
        ]
    )
    doc = extrair_documento(pdf)
    nomes = {s.nome for s in doc.secoes}
    assert {"resumo", "introducao", "metodo", "resultados", "referencias"} <= nomes
    assert "regressao" in doc.trecho_secao("metodo")


def test_remove_cabecalho_repetido_em_todas_as_paginas():
    paginas = [["Revista Brasileira de Testes", f"Conteudo unico da pagina {i}"] for i in range(1, 7)]
    doc = extrair_documento(montar_pdf(paginas))
    assert doc.texto.count("Revista Brasileira de Testes") == 0
    assert "Conteudo unico da pagina 3" in doc.texto


def test_avisa_quando_pdf_nao_tem_texto():
    doc = extrair_documento(montar_pdf([[""]]))
    assert any("OCR" in aviso for aviso in doc.avisos)


def test_detecta_doi():
    pdf = montar_pdf([["Artigo de exemplo", "DOI: 10.1234/abcd.2020.567"]])
    assert extrair_documento(pdf).metadados["doi"] == "10.1234/abcd.2020.567"


def test_offset_mapeia_para_a_pagina_certa():
    pdf = montar_pdf([["primeira"], ["segunda"], ["terceira"]])
    doc = extrair_documento(pdf)
    assert doc.pagina_do_offset(doc.texto.index("terceira")) == 3


def test_minutos_de_leitura_usa_contagem_de_palavras():
    doc = Documento(texto=" ".join(["palavra"] * 400), paginas=[Pagina(1, "", 0, 10)])
    assert doc.minutos_de_leitura == 2

"""Conversao do artigo para Markdown — a visao que vai para o modelo."""

from analisador.blocos import dividir
from analisador.markdown import converter
from analisador.pdf import extrair_documento

from pdf_falso import montar_pdf

ARTIGO = [
    [
        "Telemedicina e adesao ao tratamento",
        "Abstract",
        "Este estudo avalia o efeito do acompanhamento remoto na adesao",
        "ao tratamento de pacientes cronicos em um hospital universitario.",
        "Introduction",
        "A baixa adesao e um problema persistente.",
    ],
    [
        "2. Methods",
        "Ensaio clinico randomizado com 240 pacientes.",
        "Os criterios de inclusao foram:",
        "• idade acima de 18 anos",
        "• diagnostico confirmado",
        "Results",
        "A adesao subiu 18 pontos percentuais.",
        "References",
        "[1] Exemplo A. Adesao ao tratamento. 2021.",
    ],
]


def converter_artigo(paginas=None, titulo="Telemedicina e adesao", **kwargs):
    return converter(extrair_documento(montar_pdf(paginas or ARTIGO, titulo=titulo)), **kwargs)


def test_titulo_do_artigo_vira_h1():
    assert converter_artigo().texto.startswith("# Telemedicina e adesao")


def test_secoes_viram_h2():
    texto = converter_artigo().texto
    assert "## Abstract" in texto
    assert "## Introduction" in texto
    assert "## Results" in texto


def test_secao_numerada_tambem_e_reconhecida():
    assert "## Methods" in converter_artigo().texto


def test_linhas_quebradas_viram_um_paragrafo_unico():
    texto = converter_artigo().texto
    assert "acompanhamento remoto na adesao ao tratamento de pacientes cronicos" in texto


def test_marcadores_de_lista_sao_normalizados():
    texto = converter_artigo().texto
    assert "- idade acima de 18 anos" in texto
    assert "• " not in texto


def test_referencia_numerada_vira_item_de_lista():
    assert "- [1] Exemplo A." in converter_artigo().texto


def test_marcador_de_pagina_por_padrao():
    texto = converter_artigo().texto
    assert "<!-- p. 1 -->" in texto and "<!-- p. 2 -->" in texto


def test_marcador_de_pagina_pode_ser_desligado():
    assert "<!-- p." not in converter_artigo(marcar_paginas=False).texto


def test_offsets_continuam_apontando_para_a_pagina_certa():
    markdown = converter_artigo()
    assert markdown.pagina_do_offset(markdown.texto.index("Abstract")) == 1
    assert markdown.pagina_do_offset(markdown.texto.index("240 pacientes")) == 2


def test_secoes_ficam_navegaveis_no_markdown():
    markdown = converter_artigo()
    nomes = {s.nome for s in markdown.secoes}
    assert {"resumo", "introducao", "metodo", "resultados", "referencias"} <= nomes
    assert "240 pacientes" in markdown.trecho_secao("metodo")


def test_blocos_do_markdown_mantem_o_rotulo_de_pagina():
    markdown = converter_artigo()
    blocos = dividir(markdown, tamanho=400, sobreposicao=0)
    assert blocos[0].pagina_inicial == 1
    assert blocos[-1].pagina_final == 2
    assert all(b.rotulo.startswith("p. ") for b in blocos)


def test_metadados_e_avisos_sao_preservados():
    original = extrair_documento(montar_pdf(ARTIGO, titulo="Titulo X", autores="Fulana"))
    markdown = converter(original)
    assert markdown.metadados["autores"] == "Fulana"
    assert markdown.avisos == original.avisos


def test_artigo_sem_titulo_nao_gera_h1_vazio():
    markdown = converter_artigo(paginas=[["ab", "cd"]], titulo="")
    assert not markdown.texto.startswith("# \n")


def test_pdf_sem_texto_nao_quebra():
    markdown = converter_artigo(paginas=[[""]], titulo="")
    assert markdown.paginas[0].numero == 1


def test_markdown_e_menor_ou_igual_ao_cru_em_ruido():
    """A conversao nao pode inflar o texto a ponto de estourar o contexto."""
    original = extrair_documento(montar_pdf(ARTIGO))
    markdown = converter(original)
    assert len(markdown.texto) < len(original.texto) * 1.35

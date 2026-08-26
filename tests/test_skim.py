"""Testes do skimming mecanico: nada aqui toca o Ollama."""

from __future__ import annotations

from analisador.markdown import converter
from analisador.pdf import Documento, Pagina
from analisador.skim import (
    e_conclusiva,
    paragrafos_com_offset,
    resumir,
    separar_frases,
    tem_numero,
)


def documento_de(paginas: list[str], titulo: str = "") -> Documento:
    """Monta um Documento cru com offsets de pagina corretos, como o pdf.py faz."""
    objetos, partes, cursor = [], [], 0
    for numero, texto in enumerate(paginas, start=1):
        bloco = texto + "\n\n"
        objetos.append(Pagina(numero, texto, cursor, cursor + len(bloco)))
        partes.append(bloco)
        cursor += len(bloco)
    return Documento(
        texto="".join(partes).strip(),
        paginas=objetos,
        metadados={"titulo": titulo} if titulo else {},
    )


ARTIGO = [
    "\n".join([
        "Telemedicina e adesao ao tratamento",
        "Abstract",
        "Este estudo avaliou a telemedicina em pacientes cronicos.",
        "A adesao foi o desfecho primario.",
        "",
        "Introduction",
        "A adesao ao tratamento e um problema antigo.",
        "",
        "Varios trabalhos ja mediram o efeito de lembretes.",
        "Portanto, faltava um ensaio randomizado de porte.",
    ]),
    "\n".join([
        "Methods",
        "Ensaio clinico randomizado com 240 pacientes acompanhados por 12 meses.",
        "A alocacao foi feita por sorteio central.",
        "",
        "Results",
        "A adesao subiu 18 pontos percentuais no grupo telemedicina.",
        "Os resultados mostram beneficio consistente entre subgrupos.",
    ]),
]


# --- separacao de frases ---------------------------------------------------

def test_separa_frases_por_pontuacao():
    frases = separar_frases("O estudo foi randomizado. A amostra tinha 240 pacientes.")
    assert frases == [
        "O estudo foi randomizado.",
        "A amostra tinha 240 pacientes.",
    ]


def test_nao_quebra_frase_em_numero_decimal():
    frases = separar_frases("A diferenca foi significativa (p < 0.001) no grupo tratado.")
    assert len(frases) == 1


def test_corta_frase_antes_de_aspas_curvas():
    # A classe do lookahead inclui a aspas curva; sem ela, falas citadas em
    # artigos com tipografia real deixariam de abrir frase nova.
    frases = separar_frases('Ele concluiu o argumento. “Vamos adiante”, escreveu.')
    assert len(frases) == 2
    assert frases[1].startswith('“Vamos adiante')


def test_frase_unica_sem_ponto_final_e_preservada():
    assert separar_frases("Methods") == ["Methods"]


def test_texto_vazio_nao_gera_frase():
    assert separar_frases("   \n  ") == []


# --- deteccao de numeros e de conclusao ------------------------------------

def test_reconhece_frase_com_percentual():
    assert tem_numero("A adesao subiu 18% no grupo telemedicina.") is True


def test_reconhece_frase_com_decimal():
    assert tem_numero("O valor de p foi 0,001 no desfecho primario.") is True


def test_numero_de_pagina_solto_nao_conta_como_dado():
    assert tem_numero("Ver p. 3 para o fluxograma.") is False


def test_reconhece_marcador_de_conclusao_com_acento():
    assert e_conclusiva("Concluímos que a intervenção é viável.") is True


def test_reconhece_marcador_de_conclusao_em_ingles():
    assert e_conclusiva("The results show a consistent benefit.") is True


def test_frase_comum_nao_e_conclusiva():
    assert e_conclusiva("A alocacao foi feita por sorteio central.") is False


# --- paragrafos ------------------------------------------------------------

def test_paragrafos_ignoram_marcador_de_pagina_e_titulo_do_artigo():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    blocos = [texto for _, texto in paragrafos_com_offset(markdown)]
    assert not any(bloco.startswith("<!--") for bloco in blocos)
    assert not any(bloco.startswith("# ") for bloco in blocos)


def test_offset_do_paragrafo_aponta_para_a_pagina_certa():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    for offset, texto in paragrafos_com_offset(markdown):
        if "240 pacientes" in texto:
            assert markdown.pagina_do_offset(offset) == 2
            return
    raise AssertionError("paragrafo de metodos nao encontrado")


# --- resumir ---------------------------------------------------------------

def test_resumir_usa_o_titulo_dos_metadados():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    assert resumir(markdown).titulo == "Telemedicina e adesao"


def test_resumir_lista_as_secoes_detectadas():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    titulos = [s.titulo for s in resumir(markdown).secoes]
    assert "Abstract" in titulos
    assert "Methods" in titulos
    assert "Results" in titulos


def test_primeiro_paragrafo_da_secao_vira_abertura():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    metodos = next(s for s in resumir(markdown).secoes if s.titulo == "Methods")
    assert "240 pacientes" in metodos.abertura


def test_esqueleto_guarda_primeira_e_ultima_frase_dos_demais_paragrafos():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    intro = next(s for s in resumir(markdown).secoes if s.titulo == "Introduction")
    # 1o paragrafo vira abertura; o 2o entra no esqueleto pela 1a e pela ultima frase.
    assert "problema antigo" in intro.abertura
    assert intro.esqueleto[0].startswith("Varios trabalhos")
    assert intro.esqueleto[-1].startswith("Portanto")


def test_secao_registra_a_pagina_em_que_comeca():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    metodos = next(s for s in resumir(markdown).secoes if s.titulo == "Methods")
    assert metodos.pagina == 2


def test_frases_com_numero_carregam_pagina():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    numeros = resumir(markdown).numeros
    assert numeros, "nenhuma frase com numero foi capturada"
    assert all(f.pagina >= 1 for f in numeros)
    assert any("240" in f.texto for f in numeros)


def test_frases_conclusivas_sao_capturadas_com_pagina():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    conclusoes = resumir(markdown).conclusoes
    assert any("resultados mostram" in f.texto.lower() for f in conclusoes)
    assert all(f.pagina >= 1 for f in conclusoes)


def test_limites_de_quantidade_sao_respeitados():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    skim = resumir(markdown, max_numeros=1, max_conclusoes=1)
    assert len(skim.numeros) == 1
    assert len(skim.conclusoes) == 1


def test_texto_antes_da_primeira_secao_nao_e_perdido():
    documento = documento_de(["Um paragrafo solto com 42 casos e nenhum titulo de secao."])
    skim = resumir(converter(documento))
    assert skim.secoes, "o texto antes da primeira secao deve virar uma secao"
    assert any("42 casos" in f.texto for f in skim.numeros)


def test_documento_vazio_devolve_skim_vazio():
    skim = resumir(converter(documento_de([""])))
    assert skim.vazio is True

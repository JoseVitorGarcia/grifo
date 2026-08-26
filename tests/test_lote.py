"""Triagem de arquivos e tabelas comparativas do modo lote."""

import json

import pytest

from analisador.analise import Analise, SinteseKeyword
from analisador.keywords import buscar_keyword
from analisador.lote import (
    LIMITE_PADRAO,
    Item,
    comparar_keywords,
    keywords_ausentes,
    resumo_do_lote,
    triar,
    vagas,
)
from analisador.pdf import extrair_documento
from analisador.relatorio import para_json_lote, para_markdown_lote

from pdf_falso import montar_pdf


def item_de(nome: str, paginas: list[list[str]], keywords: list[str] | None = None) -> Item:
    documento = extrair_documento(montar_pdf(paginas))
    item = Item(assinatura=nome, nome=nome, documento=documento)
    if keywords is not None:
        analise = Analise(resumo={"objetivo": f"objetivo de {nome}"})
        for keyword in keywords:
            resultado = buscar_keyword(documento, keyword)
            analise.sinteses.append(
                SinteseKeyword(keyword=keyword, resumo=f"sintese de {keyword}", resultado=resultado)
            )
        item.analise = analise
    return item


# --- triagem --------------------------------------------------------------

def test_limite_padrao_e_cinco():
    assert LIMITE_PADRAO == 5


def test_aceita_ate_o_limite():
    candidatos = [(f"sig{i}", f"artigo{i}.pdf") for i in range(5)]
    aceitos, recusados = triar([], candidatos)
    assert len(aceitos) == 5
    assert recusados == []


def test_recusa_o_que_passa_do_limite():
    candidatos = [(f"sig{i}", f"artigo{i}.pdf") for i in range(7)]
    aceitos, recusados = triar([], candidatos)
    assert len(aceitos) == 5
    assert [r.nome for r in recusados] == ["artigo5.pdf", "artigo6.pdf"]
    assert all("limite de 5" in r.motivo for r in recusados)


def test_limite_conta_o_que_ja_estava_na_sessao():
    aceitos, recusados = triar(["a", "b", "c"], [("d", "d.pdf"), ("e", "e.pdf"), ("f", "f.pdf")])
    assert [nome for _, nome in aceitos] == ["d.pdf", "e.pdf"]
    assert len(recusados) == 1


def test_recusa_duplicata_pelo_conteudo():
    aceitos, recusados = triar(["mesma"], [("mesma", "copia.pdf")])
    assert aceitos == []
    assert "ja esta no lote" in recusados[0].motivo


def test_duplicata_nao_consome_vaga():
    aceitos, _ = triar(["a"], [("a", "copia.pdf"), ("b", "novo.pdf")])
    assert [nome for _, nome in aceitos] == ["novo.pdf"]


def test_vagas_restantes():
    assert vagas([]) == 5
    assert vagas(["a", "b"]) == 3
    assert vagas(["a", "b", "c", "d", "e"]) == 0


@pytest.mark.parametrize("limite", [1, 3])
def test_limite_configuravel(limite):
    candidatos = [(f"s{i}", f"a{i}.pdf") for i in range(4)]
    aceitos, _ = triar([], candidatos, limite=limite)
    assert len(aceitos) == limite


# --- comparacao -----------------------------------------------------------

PAGINAS_A = [["Estudo sobre telemedicina", "A telemedicina melhorou a adesao."]]
PAGINAS_B = [["Estudo sobre adesao presencial", "A adesao foi medida por contagem."]]


def test_comparacao_junta_keywords_dos_artigos():
    itens = [
        item_de("a.pdf", PAGINAS_A, ["telemedicina", "adesao"]),
        item_de("b.pdf", PAGINAS_B, ["telemedicina", "adesao"]),
    ]
    linhas = {linha["Keyword"]: linha for linha in comparar_keywords(itens)}
    assert linhas["telemedicina"]["a.pdf"] == 2
    assert linhas["telemedicina"]["b.pdf"] == 0
    assert linhas["adesao"]["b.pdf"] == 2  # titulo + corpo da pagina


def test_comparacao_ignora_artigo_nao_analisado():
    itens = [item_de("a.pdf", PAGINAS_A, ["telemedicina"]), item_de("b.pdf", PAGINAS_B)]
    linhas = comparar_keywords(itens)
    assert linhas[0]["a.pdf"] == 2
    assert linhas[0]["b.pdf"] == 0  # entra como zero, nao some da tabela


def test_keywords_ausentes_aponta_os_arquivos():
    itens = [
        item_de("a.pdf", PAGINAS_A, ["telemedicina"]),
        item_de("b.pdf", PAGINAS_B, ["telemedicina"]),
    ]
    assert keywords_ausentes(itens) == {"telemedicina": ["b.pdf"]}


def test_resumo_do_lote_marca_o_que_falta_analisar():
    itens = [item_de("a.pdf", PAGINAS_A, ["telemedicina"]), item_de("b.pdf", PAGINAS_B)]
    linhas = resumo_do_lote(itens)
    assert linhas[0]["Analisado"] == "sim"
    assert linhas[0]["Keywords encontradas"] == "1/1"
    assert linhas[1]["Analisado"] == "nao"
    assert linhas[1]["Keywords encontradas"] == "—"


def test_item_sem_analise_nao_e_analisado():
    item = item_de("a.pdf", PAGINAS_A)
    assert not item.analisado
    assert item.rotulo.startswith("⏳")


def test_titulo_cai_no_nome_do_arquivo_quando_o_pdf_nao_tem():
    item = item_de("sem_titulo.pdf", [["ab"]])
    assert item.titulo in ("sem_titulo.pdf", "ab")


# --- relatorio consolidado ------------------------------------------------

def test_markdown_consolidado_tem_tabela_e_artigos():
    itens = [
        item_de("a.pdf", PAGINAS_A, ["telemedicina"]),
        item_de("b.pdf", PAGINAS_B, ["telemedicina"]),
    ]
    markdown = para_markdown_lote(itens, modelo="gemma3:4b")
    assert "# Relatorio consolidado do lote" in markdown
    assert "**Artigos no lote:** 2 · **Analisados:** 2" in markdown
    assert "## Keywords por artigo (ocorrencias)" in markdown
    assert "| telemedicina | 2 | 0 |" in markdown
    assert "# Arquivo: a.pdf" in markdown
    assert "### Keywords ausentes" in markdown


def test_titulos_dos_relatorios_individuais_sao_rebaixados():
    markdown = para_markdown_lote([item_de("a.pdf", PAGINAS_A, ["telemedicina"])])
    # O '# Analise — ...' individual vira '## Analise — ...' dentro do consolidado
    assert "\n## Analise —" in markdown
    assert markdown.count("\n# Relatorio consolidado") == 0  # so no inicio do arquivo
    assert markdown.startswith("# Relatorio consolidado")


def test_json_consolidado_lista_so_os_analisados():
    itens = [item_de("a.pdf", PAGINAS_A, ["telemedicina"]), item_de("b.pdf", PAGINAS_B)]
    dados = json.loads(para_json_lote(itens, modelo="gemma3:4b"))
    assert [artigo["arquivo"] for artigo in dados["artigos"]] == ["a.pdf"]
    assert dados["modelo"] == "gemma3:4b"

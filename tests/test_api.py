"""Testes da API HTTP: lote, limite, analise por SSE, downloads e grifo."""

from __future__ import annotations

import dataclasses
import io
import json

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from analisador.config import Config
from servidor import api as modulo_api
from servidor.sessao import Repositorio

from ollama_falso import subir
from pdf_falso import montar_pdf

ARTIGO_A = [
    ["Telemedicina e adesao", "Abstract", "Estudo sobre telemedicina em pacientes cronicos."],
    ["Methods", "Ensaio clinico randomizado com 240 pacientes.", "Results", "A adesao subiu 18%."],
]
ARTIGO_B = [["Custo da telessaude", "Abstract", "Analise de custo hospitalar."]]


@pytest.fixture(scope="module")
def ollama():
    httpd, url = subir()
    yield url
    httpd.shutdown()


@pytest.fixture
def cliente(ollama, monkeypatch):
    # Cada teste comeca com um repositorio limpo e apontando para o Ollama falso.
    # Config e frozen, entao troca-se a instancia inteira.
    monkeypatch.setattr(modulo_api, "REPOSITORIO", Repositorio())
    monkeypatch.setattr(modulo_api, "CONFIG", dataclasses.replace(Config.do_ambiente(), ollama_url=ollama))
    with TestClient(modulo_api.app) as cliente:
        yield cliente


def enviar(cliente, arquivos: list[tuple[str, list[list[str]]]]):
    dados = [("arquivos", (nome, montar_pdf(paginas), "application/pdf")) for nome, paginas in arquivos]
    return cliente.post("/api/pdfs", files=dados)


def eventos(cliente, caminho: str, corpo: dict) -> list[dict]:
    coletados = []
    with cliente.stream("POST", caminho, json=corpo) as resposta:
        assert resposta.status_code == 200
        for linha in resposta.iter_lines():
            if linha.startswith("data: "):
                coletados.append(json.loads(linha[6:]))
    return coletados


# --- configuracao e estado -------------------------------------------------

def test_config_expoe_limite_e_padroes(cliente):
    dados = cliente.get("/api/config").json()
    assert dados["limite_pdfs"] == 5
    assert dados["padroes"]["modelo"]
    assert dados["versao"]


def test_status_reporta_ollama_no_ar(cliente, ollama):
    dados = cliente.get(f"/api/status?url={ollama}&modelo=gemma3:4b").json()
    assert dados["ok"] is True
    assert "gemma3:4b" in dados["modelos"]


def test_status_reporta_ollama_fora(cliente):
    dados = cliente.get("/api/status?url=http://127.0.0.1:9&modelo=gemma3:4b").json()
    assert dados["ok"] is False
    assert "docker compose up" in dados["mensagem"]


def test_pagina_inicial_entrega_o_front(cliente):
    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert "Analisador de Artigos" in resposta.text
    assert "/static/app.js" in resposta.text


# --- lote ------------------------------------------------------------------

def test_envio_extrai_metadados(cliente):
    dados = enviar(cliente, [("artigo_a.pdf", ARTIGO_A)]).json()
    assert len(dados["itens"]) == 1
    item = dados["itens"][0]
    assert item["nome"] == "artigo_a.pdf"
    assert item["documento"]["paginas"] == 2
    assert item["analisado"] is False
    assert dados["vagas"] == 4


def test_limite_de_cinco_por_sessao(cliente):
    dados = enviar(cliente, [(f"artigo_{i}.pdf", [[f"conteudo unico {i}"]]) for i in range(7)]).json()
    assert len(dados["itens"]) == 5
    assert len(dados["recusados"]) == 2
    assert all("limite de 5" in r["motivo"] for r in dados["recusados"])
    assert dados["vagas"] == 0


def test_duplicata_e_recusada_sem_consumir_vaga(cliente):
    enviar(cliente, [("a.pdf", ARTIGO_A)])
    dados = enviar(cliente, [("copia.pdf", ARTIGO_A), ("b.pdf", ARTIGO_B)]).json()
    assert [i["nome"] for i in dados["itens"]] == ["b.pdf"]
    assert "ja esta no lote" in dados["recusados"][0]["motivo"]
    assert dados["vagas"] == 3


def test_pdf_invalido_volta_como_recusado(cliente):
    resposta = cliente.post("/api/pdfs", files=[("arquivos", ("quebrado.pdf", b"nao sou um pdf", "application/pdf"))])
    dados = resposta.json()
    assert dados["itens"] == []
    assert "nao foi possivel ler" in dados["recusados"][0]["motivo"]


def test_remover_e_limpar_o_lote(cliente):
    identificador = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    assert cliente.delete(f"/api/pdfs/{identificador}").json()["vagas"] == 5
    assert cliente.get("/api/pdfs").json()["itens"] == []

    enviar(cliente, [("a.pdf", ARTIGO_A), ("b.pdf", ARTIGO_B)])
    cliente.delete("/api/pdfs")
    assert cliente.get("/api/pdfs").json()["itens"] == []


def test_remover_inexistente_devolve_404(cliente):
    assert cliente.delete("/api/pdfs/inexistente").status_code == 404


def test_texto_por_pagina(cliente):
    identificador = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    dados = cliente.get(f"/api/itens/{identificador}/pagina/2").json()
    assert "Ensaio clinico randomizado" in dados["texto"]
    assert cliente.get(f"/api/itens/{identificador}/pagina/99").status_code == 404


def test_artigo_inexistente_devolve_404(cliente):
    assert cliente.get("/api/itens/nao-existe").status_code == 404


# --- analise ---------------------------------------------------------------

def test_analise_emite_progresso_e_resultado(cliente, ollama):
    enviar(cliente, [("a.pdf", ARTIGO_A)])
    recebidos = eventos(cliente, "/api/analise", {
        "url": ollama, "modelo": "gemma3:4b", "keywords": "telemedicina, adesao",
        "tamanho_bloco": 400, "max_blocos": 4,
    })
    tipos = [e["tipo"] for e in recebidos]
    assert tipos[0] == "inicio"
    assert "artigo_inicio" in tipos and "progresso" in tipos and tipos[-1] == "fim"

    fim_artigo = next(e for e in recebidos if e["tipo"] == "artigo_fim")
    analise = fim_artigo["dados"]["analise"]
    assert analise["resumo"]["metodologia"].startswith("Ensaio")
    assert analise["achados"][0]["afirmacao"] == "A adesao subiu 18%"
    assert analise["limitacoes"] == ["Amostra de um unico hospital"]
    keywords = {k["keyword"]: k for k in analise["keywords"]}
    assert keywords["telemedicina"]["total"] >= 2
    assert keywords["telemedicina"]["ocorrencias"][0]["trecho"].count("**") == 2


def test_analise_marca_o_artigo_como_analisado(cliente, ollama):
    enviar(cliente, [("a.pdf", ARTIGO_A)])
    eventos(cliente, "/api/analise", {"url": ollama, "keywords": "telemedicina", "tamanho_bloco": 400})
    assert cliente.get("/api/pdfs").json()["itens"][0]["analisado"] is True


def test_segunda_chamada_nao_reprocessa_sem_reanalisar(cliente, ollama):
    enviar(cliente, [("a.pdf", ARTIGO_A)])
    corpo = {"url": ollama, "keywords": "telemedicina", "tamanho_bloco": 400}
    eventos(cliente, "/api/analise", corpo)
    segunda = eventos(cliente, "/api/analise", corpo)
    assert segunda[-1]["aviso"] == "Nenhum artigo pendente."

    terceira = eventos(cliente, "/api/analise", {**corpo, "reanalisar": True})
    assert any(e["tipo"] == "artigo_fim" for e in terceira)


def test_analise_com_ollama_fora_avisa_e_para(cliente):
    enviar(cliente, [("a.pdf", ARTIGO_A)])
    recebidos = eventos(cliente, "/api/analise", {"url": "http://127.0.0.1:9"})
    assert recebidos[0]["tipo"] == "erro"
    assert recebidos[-1]["analisados"] == 0


def test_comparacao_entre_dois_artigos(cliente, ollama):
    enviar(cliente, [("a.pdf", ARTIGO_A), ("b.pdf", ARTIGO_B)])
    eventos(cliente, "/api/analise", {"url": ollama, "keywords": "telemedicina", "tamanho_bloco": 400})
    dados = cliente.get("/api/comparacao").json()
    linha = dados["comparacao"][0]
    assert linha["Keyword"] == "telemedicina"
    assert linha["a.pdf"] >= 2 and linha["b.pdf"] == 0
    assert dados["ausentes"]["telemedicina"] == ["b.pdf"]


# --- downloads -------------------------------------------------------------

def test_relatorios_individuais(cliente, ollama):
    identificador = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    eventos(cliente, "/api/analise", {"url": ollama, "keywords": "telemedicina", "tamanho_bloco": 400})

    markdown = cliente.get(f"/api/itens/{identificador}/relatorio.md")
    assert markdown.status_code == 200
    assert "## Resumo estruturado" in markdown.text
    assert "attachment" in markdown.headers["content-disposition"]

    dados = cliente.get(f"/api/itens/{identificador}/relatorio.json").json()
    assert dados["keywords"][0]["keyword"] == "telemedicina"
    assert cliente.get(f"/api/itens/{identificador}/relatorio.txt").status_code == 400


def test_relatorio_consolidado_do_lote(cliente, ollama):
    enviar(cliente, [("a.pdf", ARTIGO_A), ("b.pdf", ARTIGO_B)])
    eventos(cliente, "/api/analise", {"url": ollama, "keywords": "telemedicina", "tamanho_bloco": 400})
    texto = cliente.get("/api/lote/relatorio.md").text
    assert "# Relatorio consolidado do lote" in texto
    assert "# Arquivo: a.pdf" in texto and "# Arquivo: b.pdf" in texto


def test_pdf_anotado_traz_as_marcacoes(cliente, ollama):
    identificador = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    eventos(cliente, "/api/analise", {"url": ollama, "keywords": "telemedicina", "tamanho_bloco": 400})

    resposta = cliente.get(f"/api/itens/{identificador}/anotado.pdf")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert json.loads(resposta.headers["x-marcacoes"])["keyword"] >= 2

    leitor = PdfReader(io.BytesIO(resposta.content))
    anotacoes = [a for pagina in leitor.pages for a in (pagina.get("/Annots") or [])]
    assert anotacoes
    assert leitor.pages[0].extract_text()  # o texto original continua la


def test_pdf_anotado_sem_evidencias_so_marca_keywords(cliente, ollama):
    identificador = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    eventos(cliente, "/api/analise", {"url": ollama, "keywords": "telemedicina", "tamanho_bloco": 400})
    resposta = cliente.get(f"/api/itens/{identificador}/anotado.pdf?evidencias=false")
    assert set(json.loads(resposta.headers["x-marcacoes"])) == {"keyword"}


def test_pdf_original_e_devolvido(cliente):
    identificador = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    resposta = cliente.get(f"/api/itens/{identificador}/original.pdf")
    assert resposta.content.startswith(b"%PDF")


def test_sessoes_diferentes_nao_compartilham_o_lote(cliente):
    enviar(cliente, [("a.pdf", ARTIGO_A)])
    assert len(cliente.get("/api/pdfs").json()["itens"]) == 1
    cliente.cookies.clear()
    assert cliente.get("/api/pdfs").json()["itens"] == []


def test_grifo_aceita_keywords_avulsas_sem_analise(cliente):
    """Da para grifar antes de analisar: a busca literal nao depende do modelo."""
    identificador = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    resposta = cliente.get(f"/api/itens/{identificador}/anotado.pdf?keywords=telemedicina,pacientes")
    assert resposta.status_code == 200
    assert json.loads(resposta.headers["x-marcacoes"])["keyword"] >= 2


def test_markdown_do_artigo_e_gerado_no_envio(cliente):
    """A conversao acontece no upload, antes de qualquer analise."""
    identificador = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    dados = cliente.get(f"/api/itens/{identificador}/markdown").json()
    assert "## Abstract" in dados["markdown"]
    assert "<!-- p. 2 -->" in dados["markdown"]
    assert dados["caracteres"] > 0


def test_markdown_pode_ser_baixado(cliente):
    identificador = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    resposta = cliente.get(f"/api/itens/{identificador}/markdown?download=true")
    assert resposta.headers["content-type"].startswith("text/markdown")
    assert "attachment" in resposta.headers["content-disposition"]


def test_markdown_de_artigo_inexistente_da_404(cliente):
    assert cliente.get("/api/itens/nao-existe/markdown").status_code == 404


def test_modelo_recebe_o_markdown_e_nao_o_texto_cru(cliente, ollama, monkeypatch):
    """O prompt enviado ao Ollama tem que carregar a marcacao de secao."""
    prompts: list[str] = []
    original = modulo_api.levantar_notas

    def espiao(cliente_llm, documento, **kwargs):
        prompts.append(documento.texto)
        return original(cliente_llm, documento, **kwargs)

    monkeypatch.setattr(modulo_api, "levantar_notas", espiao)
    enviar(cliente, [("a.pdf", ARTIGO_A)])
    eventos(cliente, "/api/analise", {"url": ollama, "keywords": "telemedicina", "tamanho_bloco": 400})

    assert prompts and "## Abstract" in prompts[0]


def test_keywords_continuam_apontando_para_o_texto_original(cliente, ollama):
    """A rastreabilidade nao pode herdar o ruido do Markdown."""
    enviar(cliente, [("a.pdf", ARTIGO_A)])
    recebidos = eventos(cliente, "/api/analise", {"url": ollama, "keywords": "telemedicina", "tamanho_bloco": 400})
    fim = next(e for e in recebidos if e["tipo"] == "artigo_fim")
    ocorrencias = fim["dados"]["analise"]["keywords"][0]["ocorrencias"]
    assert ocorrencias
    for ocorrencia in ocorrencias:
        assert "<!--" not in ocorrencia["trecho"]
        assert "##" not in ocorrencia["trecho"]


# --- scan deterministico ---------------------------------------------------

def test_scan_responde_sem_analise_previa(cliente):
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    dados = cliente.get(f"/api/itens/{id_a}/scan?keywords=telemedicina,adesao").json()
    assert [k["keyword"] for k in dados["keywords"]] == ["telemedicina", "adesao"]
    assert dados["keywords"][0]["total"] >= 1
    assert dados["keywords"][0]["encontrada"] is True
    assert dados["keywords"][0]["ocorrencias"][0]["pagina"] >= 1


def test_scan_marca_keyword_ausente(cliente):
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    dados = cliente.get(f"/api/itens/{id_a}/scan?keywords=quimioterapia").json()
    ausente = dados["keywords"][0]
    assert ausente["total"] == 0
    assert ausente["encontrada"] is False
    assert ausente["ocorrencias"] == []


def test_scan_funciona_com_ollama_fora_do_ar(cliente, monkeypatch):
    # A promessa central: scanning nao depende do modelo. Aponta a config para
    # uma porta morta e confirma que a rota continua respondendo.
    monkeypatch.setattr(
        modulo_api, "CONFIG",
        dataclasses.replace(Config.do_ambiente(), ollama_url="http://127.0.0.1:9"),
    )
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    resposta = cliente.get(f"/api/itens/{id_a}/scan?keywords=telemedicina")
    assert resposta.status_code == 200
    assert resposta.json()["keywords"][0]["total"] >= 1


def test_scan_sem_keywords_devolve_lista_vazia(cliente):
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    assert cliente.get(f"/api/itens/{id_a}/scan?keywords=").json()["keywords"] == []


def test_scan_de_artigo_inexistente_da_404(cliente):
    assert cliente.get("/api/itens/naoexiste/scan?keywords=a").status_code == 404

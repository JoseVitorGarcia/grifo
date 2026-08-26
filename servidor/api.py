"""API HTTP do analisador (FastAPI) + entrega do front estatico.

O nucleo em `analisador/` nao conhece HTTP: esta camada so traduz pedido em
chamada de funcao e resposta em JSON. As operacoes longas (analise do lote e
resposta do chat) vao por Server-Sent Events, para o front mostrar progresso e
texto conforme sao produzidos.
"""

from __future__ import annotations

import hashlib
import json
import queue
import threading
from datetime import datetime
from typing import Any, Iterator

from fastapi import Body, FastAPI, File, Request, Response, UploadFile
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

from analisador import __version__
from analisador.analise import (
    Analise,
    SinteseKeyword,
    extrair_achados,
    extrair_limitacoes,
    levantar_notas,
    montar_resumo,
    sintetizar_keyword,
    sugerir_keywords,
)
from analisador.blocos import dividir
from analisador.config import Config
from analisador.keywords import buscar_varias, separar_keywords
from analisador.llm import ClienteOllama, ErroOllama
from analisador.lote import Item, triar, vagas
from analisador.markdown import converter as converter_markdown
from analisador.marcacao import marcar
from analisador.pdf import extrair_documento
from analisador.relatorio import (
    para_json,
    para_json_lote,
    para_markdown,
    para_markdown_lote,
)
from servidor.esquemas import item_para_dict, lote_para_dict, resultado_para_dict
from servidor.sessao import COOKIE, Repositorio

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
WEB = RAIZ / "web"

CONFIG = Config.do_ambiente()
REPOSITORIO = Repositorio()

app = FastAPI(title="Analisador de Artigos em PDF", version=__version__)


# --------------------------------------------------------------------------
# Utilitarios
# --------------------------------------------------------------------------

def sessao_do(requisicao: Request):
    return REPOSITORIO.obter(requisicao.cookies.get(COOKIE))


def com_cookie(resposta: Response, sessao) -> Response:
    resposta.set_cookie(COOKIE, sessao.identificador, httponly=True, samesite="lax")
    return resposta


def cliente_de(dados: dict[str, Any]) -> ClienteOllama:
    return ClienteOllama(
        url=(dados.get("url") or CONFIG.ollama_url).rstrip("/"),
        modelo=dados.get("modelo") or CONFIG.modelo,
        temperatura=float(dados.get("temperatura", CONFIG.temperatura)),
        num_ctx=int(dados.get("num_ctx", CONFIG.num_ctx)),
        timeout_s=CONFIG.timeout_s,
    )


def evento(tipo: str, **campos: Any) -> str:
    """Formata um Server-Sent Event."""
    return f"data: {json.dumps({'tipo': tipo, **campos}, ensure_ascii=False)}\n\n"


def transmitir(trabalho) -> Iterator[str]:
    """Roda `trabalho(emitir)` numa thread e entrega os eventos assim que saem.

    O cliente do Ollama e bloqueante; sem a thread, o progresso so chegaria ao
    navegador quando a analise inteira ja tivesse terminado.
    """
    fila: queue.Queue = queue.Queue()

    def emitir(tipo: str, **campos: Any) -> None:
        fila.put(evento(tipo, **campos))

    def executar() -> None:
        try:
            trabalho(emitir)
        except Exception as erro:  # nunca deixa o navegador pendurado
            fila.put(evento("erro", mensagem=f"falha inesperada: {erro}"))
        finally:
            fila.put(None)

    threading.Thread(target=executar, daemon=True).start()
    while True:
        proximo = fila.get()
        if proximo is None:
            return
        yield proximo


def fluxo(gerador: Iterator[str]) -> StreamingResponse:
    return StreamingResponse(
        gerador,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _nome_base(nome: str) -> str:
    return (nome.rsplit(".", 1)[0][:50] or "artigo").replace(" ", "_")


def _carimbo() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M")


# --------------------------------------------------------------------------
# Front estatico
# --------------------------------------------------------------------------

if WEB.is_dir():
    app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/", response_class=HTMLResponse)
def pagina_inicial(requisicao: Request) -> Response:
    sessao = sessao_do(requisicao)
    arquivo = WEB / "index.html"
    if not arquivo.is_file():
        return HTMLResponse("<h1>Front nao encontrado</h1>", status_code=500)
    return com_cookie(HTMLResponse(arquivo.read_text(encoding="utf-8")), sessao)


# --------------------------------------------------------------------------
# Estado e configuracao
# --------------------------------------------------------------------------

@app.get("/api/config")
def configuracao() -> dict:
    return {
        "versao": __version__,
        "limite_pdfs": REPOSITORIO._limite,
        "padroes": {
            "ollama_url": CONFIG.ollama_url,
            "modelo": CONFIG.modelo,
            "temperatura": CONFIG.temperatura,
            "num_ctx": CONFIG.num_ctx,
            "tamanho_bloco": CONFIG.tamanho_bloco,
            "max_blocos": CONFIG.max_blocos,
        },
    }


@app.get("/api/status")
def status(url: str = "", modelo: str = "") -> dict:
    cliente = cliente_de({"url": url, "modelo": modelo})
    ok, mensagem = cliente.diagnostico()
    try:
        modelos = cliente.listar_modelos()
    except ErroOllama:
        modelos = []
    return {"ok": ok, "mensagem": mensagem, "modelos": modelos, "modelo": cliente.modelo}


# --------------------------------------------------------------------------
# Lote de PDFs
# --------------------------------------------------------------------------

@app.get("/api/pdfs")
def listar(requisicao: Request) -> Response:
    sessao = sessao_do(requisicao)
    corpo = {
        "itens": [item_para_dict(item) for item in sessao.lista()],
        "vagas": vagas(sessao.itens.keys(), sessao.limite),
        "limite": sessao.limite,
    }
    return com_cookie(JSONResponse(corpo), sessao)


@app.post("/api/pdfs")
async def enviar(requisicao: Request, arquivos: list[UploadFile] = File(...)) -> Response:
    sessao = sessao_do(requisicao)

    candidatos: list[tuple[str, str]] = []
    conteudos: dict[str, bytes] = {}
    for arquivo in arquivos:
        conteudo = await arquivo.read()
        assinatura = hashlib.sha256(conteudo).hexdigest()
        conteudos[assinatura] = conteudo
        candidatos.append((assinatura, arquivo.filename or "arquivo.pdf"))

    aceitos, recusados = triar(sessao.itens.keys(), candidatos, sessao.limite)

    adicionados = []
    falhas = []
    for assinatura, nome in aceitos:
        try:
            documento = extrair_documento(conteudos[assinatura])
        except Exception as erro:  # PDF corrompido ou nao suportado
            falhas.append({"nome": nome, "motivo": f"nao foi possivel ler o PDF ({erro})"})
            continue
        item = Item(assinatura=assinatura, nome=nome, documento=documento)
        # O modelo le a versao em Markdown; a busca de keywords fica no texto cru.
        item.markdown = converter_markdown(documento)
        item.blocos = dividir(item.para_o_modelo, tamanho=CONFIG.tamanho_bloco)
        sessao.itens[assinatura] = item
        sessao.conteudos[assinatura] = conteudos[assinatura]
        adicionados.append(item_para_dict(item))

    corpo = {
        "itens": adicionados,
        "recusados": [{"nome": r.nome, "motivo": r.motivo} for r in recusados] + falhas,
        "vagas": vagas(sessao.itens.keys(), sessao.limite),
    }
    return com_cookie(JSONResponse(corpo), sessao)


@app.delete("/api/pdfs")
def limpar(requisicao: Request) -> Response:
    sessao = sessao_do(requisicao)
    sessao.limpar()
    return com_cookie(JSONResponse({"ok": True, "vagas": sessao.limite}), sessao)


@app.delete("/api/pdfs/{identificador}")
def remover(requisicao: Request, identificador: str) -> Response:
    sessao = sessao_do(requisicao)
    achou = sessao.remover(identificador)
    corpo = {"ok": achou, "vagas": vagas(sessao.itens.keys(), sessao.limite)}
    return com_cookie(JSONResponse(corpo, status_code=200 if achou else 404), sessao)


@app.get("/api/itens/{identificador}")
def detalhe(requisicao: Request, identificador: str) -> Response:
    sessao = sessao_do(requisicao)
    item = sessao.item(identificador)
    if not item:
        return JSONResponse({"erro": "artigo nao encontrado nesta sessao"}, status_code=404)
    return com_cookie(JSONResponse(item_para_dict(item, completo=True)), sessao)


@app.get("/api/itens/{identificador}/pagina/{numero}")
def pagina(requisicao: Request, identificador: str, numero: int) -> Response:
    sessao = sessao_do(requisicao)
    item = sessao.item(identificador)
    if not item:
        return JSONResponse({"erro": "artigo nao encontrado nesta sessao"}, status_code=404)
    if not 1 <= numero <= item.documento.n_paginas:
        return JSONResponse({"erro": "pagina fora do intervalo"}, status_code=404)
    return JSONResponse({"numero": numero, "texto": item.documento.paginas[numero - 1].texto})


@app.get("/api/itens/{identificador}/scan")
def scan(
    requisicao: Request,
    identificador: str,
    keywords: str = "",
    flexivel: bool = True,
) -> Response:
    """Busca literal das keywords, sem passar pelo modelo.

    Scanning e deterministico e sai em milissegundos: esta rota existe para que
    a tela nao precise esperar a leitura profunda — nem o Ollama estar no ar.
    """
    sessao = sessao_do(requisicao)
    item = sessao.item(identificador)
    if not item:
        return JSONResponse({"erro": "artigo nao encontrado nesta sessao"}, status_code=404)

    resultados = buscar_varias(item.documento, separar_keywords(keywords), flexivel=flexivel)
    corpo = {"id": identificador, "keywords": [resultado_para_dict(r) for r in resultados]}
    return com_cookie(JSONResponse(corpo), sessao)


@app.get("/api/comparacao")
def comparacao(requisicao: Request) -> Response:
    sessao = sessao_do(requisicao)
    return com_cookie(JSONResponse(lote_para_dict(sessao.lista())), sessao)


# --------------------------------------------------------------------------
# Analise (SSE)
# --------------------------------------------------------------------------

def _analisar_item(cliente, item: Item, keywords: list[str], corpo: dict, emitir) -> Analise:
    analise = Analise()
    etapas = corpo.get("etapas") or {}
    ligada = lambda chave: bool(etapas.get(chave, True))  # noqa: E731
    flexivel = bool(corpo.get("flexivel", True))
    resultados = buscar_varias(item.documento, keywords, flexivel=flexivel)

    tamanho_bloco = int(corpo.get("tamanho_bloco", CONFIG.tamanho_bloco))
    max_blocos = int(corpo.get("max_blocos", CONFIG.max_blocos))

    fonte = item.para_o_modelo  # Markdown quando disponivel

    if any(ligada(chave) for chave in ("resumo", "achados", "limitacoes", "sinteses", "sugeridas")):
        def progresso(mensagem: str, fracao: float) -> None:
            emitir("progresso", etapa=mensagem, fracao=round(0.45 * fracao, 4))

        analise.notas, item.blocos = levantar_notas(
            cliente,
            fonte,
            tamanho_bloco=tamanho_bloco,
            sobreposicao=CONFIG.sobreposicao_bloco,
            max_blocos=max_blocos,
            progresso=progresso,
        )
    else:
        item.blocos = dividir(fonte, tamanho=tamanho_bloco)

    tarefas = [
        ("resumo", "Montando o resumo estruturado", "resumo",
         lambda: montar_resumo(cliente, analise.notas, fonte)),
        ("achados", "Extraindo achados e evidencias", "achados",
         lambda: extrair_achados(cliente, analise.notas, fonte)),
        ("limitacoes", "Levantando limitacoes e lacunas", "limitacoes",
         lambda: extrair_limitacoes(cliente, analise.notas, fonte)),
        ("sugeridas", "Sugerindo termos-chave", "keywords_sugeridas",
         lambda: sugerir_keywords(cliente, analise.notas, fonte)),
    ]
    ativas = [t for t in tarefas if ligada(t[0])]
    total = max(1, len(ativas) + (1 if ligada("sinteses") and resultados else 0))

    for posicao, (_, rotulo, campo, funcao) in enumerate(ativas):
        emitir("progresso", etapa=rotulo, fracao=round(0.45 + 0.55 * posicao / total, 4))
        try:
            setattr(analise, campo, funcao())
        except ErroOllama as erro:
            analise.erros.append(f"{rotulo}: {erro}")

    if resultados:
        if ligada("sinteses"):
            for posicao, resultado in enumerate(resultados, start=1):
                emitir(
                    "progresso",
                    etapa=f"Keyword {posicao}/{len(resultados)}: {resultado.keyword}",
                    fracao=round(0.45 + 0.55 * (len(ativas) + posicao / len(resultados)) / total, 4),
                )
                analise.sinteses.append(sintetizar_keyword(cliente, resultado))
        else:
            analise.sinteses = [
                SinteseKeyword(keyword=r.keyword, resumo="(sintese do modelo desativada)", resultado=r)
                for r in resultados
            ]
    return analise


@app.post("/api/analise")
def analisar(requisicao: Request, corpo: dict = Body(default={})) -> Response:
    sessao = sessao_do(requisicao)
    cliente = cliente_de(corpo)
    keywords = separar_keywords(corpo.get("keywords", "") or "")
    reanalisar = bool(corpo.get("reanalisar"))

    escolhidos = corpo.get("ids") or []
    lista = [item for item in sessao.lista() if not escolhidos or item.assinatura in escolhidos]
    alvos = lista if reanalisar else [item for item in lista if not item.analisado]

    def trabalho(emitir) -> None:
        ok, mensagem = cliente.diagnostico()
        if not ok:
            emitir("erro", mensagem=mensagem)
            emitir("fim", analisados=0)
            return
        if not alvos:
            emitir("fim", analisados=0, aviso="Nenhum artigo pendente.")
            return

        sessao.modelo_usado = cliente.modelo
        inicio = datetime.now()
        falhas: list[str] = []
        emitir("inicio", total=len(alvos), arquivos=[item.nome for item in alvos])

        for posicao, item in enumerate(alvos, start=1):
            emitir(
                "artigo_inicio", id=item.assinatura, nome=item.nome,
                posicao=posicao, total=len(alvos),
            )

            def progresso(tipo: str, **campos: Any) -> None:
                emitir(tipo, id=item.assinatura, nome=item.nome, posicao=posicao, **campos)

            try:
                item.analise = _analisar_item(cliente, item, keywords, corpo, progresso)
                emitir(
                    "artigo_fim",
                    id=item.assinatura,
                    nome=item.nome,
                    erros=item.analise.erros,
                    dados=item_para_dict(item, completo=True),
                )
            except ErroOllama as erro:
                falhas.append(item.nome)
                emitir("artigo_erro", id=item.assinatura, nome=item.nome, mensagem=str(erro))

        emitir(
            "fim",
            analisados=len(alvos) - len(falhas),
            falhas=falhas,
            segundos=round((datetime.now() - inicio).total_seconds(), 1),
        )

    return com_cookie(fluxo(transmitir(trabalho)), sessao)


# --------------------------------------------------------------------------
# Downloads
# --------------------------------------------------------------------------

def _anexo(conteudo: str | bytes, nome: str, tipo: str) -> Response:
    dados = conteudo.encode("utf-8") if isinstance(conteudo, str) else conteudo
    return Response(
        content=dados,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@app.get("/api/itens/{identificador}/markdown")
def markdown_do_artigo(requisicao: Request, identificador: str, download: bool = False) -> Response:
    """O artigo em Markdown — exatamente o texto que o modelo recebe."""
    sessao = sessao_do(requisicao)
    item = sessao.item(identificador)
    if not item:
        return JSONResponse({"erro": "artigo nao encontrado nesta sessao"}, status_code=404)
    texto = item.para_o_modelo.texto
    if download:
        return _anexo(texto, f"{_nome_base(item.nome)}.md", "text/markdown")
    return JSONResponse({"markdown": texto, "caracteres": len(texto)})


@app.get("/api/itens/{identificador}/relatorio.{formato}")
def relatorio(requisicao: Request, identificador: str, formato: str) -> Response:
    sessao = sessao_do(requisicao)
    item = sessao.item(identificador)
    if not item:
        return JSONResponse({"erro": "artigo nao encontrado nesta sessao"}, status_code=404)
    analise = item.analise or Analise()
    base = f"{_nome_base(item.nome)}-{_carimbo()}"
    if formato == "md":
        return _anexo(para_markdown(item.documento, analise, sessao.modelo_usado), f"{base}.md", "text/markdown")
    if formato == "json":
        return _anexo(para_json(item.documento, analise, sessao.modelo_usado), f"{base}.json", "application/json")
    return JSONResponse({"erro": "formato deve ser md ou json"}, status_code=400)


@app.get("/api/lote/relatorio.{formato}")
def relatorio_lote(requisicao: Request, formato: str) -> Response:
    sessao = sessao_do(requisicao)
    lista = sessao.lista()
    nome = f"lote-{_carimbo()}"
    if formato == "md":
        return _anexo(para_markdown_lote(lista, sessao.modelo_usado), f"{nome}.md", "text/markdown")
    if formato == "json":
        return _anexo(para_json_lote(lista, sessao.modelo_usado), f"{nome}.json", "application/json")
    return JSONResponse({"erro": "formato deve ser md ou json"}, status_code=400)


@app.get("/api/itens/{identificador}/anotado.pdf")
def pdf_anotado(
    requisicao: Request,
    identificador: str,
    evidencias: bool = True,
    flexivel: bool = True,
    keywords: str = "",
) -> Response:
    """PDF original com as passagens grifadas, como marca-texto.

    `keywords` permite grifar termos sem ter analisado o artigo — a busca e
    literal e nao depende do modelo.
    """
    sessao = sessao_do(requisicao)
    item = sessao.item(identificador)
    conteudo = sessao.conteudos.get(identificador)
    if not item or conteudo is None:
        return JSONResponse({"erro": "artigo nao encontrado nesta sessao"}, status_code=404)

    resultado = marcar(
        conteudo,
        documento=item.documento,
        analise=item.analise,
        keywords=separar_keywords(keywords),
        flexivel=flexivel,
        marcar_evidencias=evidencias,
    )
    resposta = _anexo(resultado.pdf, f"{_nome_base(item.nome)}-grifado.pdf", "application/pdf")
    resposta.headers["X-Marcacoes"] = json.dumps(resultado.por_categoria())
    return resposta


@app.get("/api/itens/{identificador}/original.pdf")
def pdf_original(requisicao: Request, identificador: str) -> Response:
    sessao = sessao_do(requisicao)
    conteudo = sessao.conteudos.get(identificador)
    if conteudo is None:
        return JSONResponse({"erro": "artigo nao encontrado nesta sessao"}, status_code=404)
    return Response(content=conteudo, media_type="application/pdf")

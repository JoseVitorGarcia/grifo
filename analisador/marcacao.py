"""Marcacao (grifo) das passagens relevantes no PDF original.

Grava anotacoes de destaque reais no arquivo — abrem marcadas em qualquer
leitor de PDF e o texto continua selecionavel. Duas fontes de marcacao:

- **keywords**: casamento literal, exato. Sempre confiavel.
- **evidencias dos achados**: o modelo costuma parafrasear, entao a passagem e
  localizada por similaridade. Abaixo do limiar nada e marcado — grifar a frase
  errada e pior do que nao grifar.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import pdfplumber
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import ArrayObject, FloatObject, NameObject, TextStringObject

from .analise import normalizar_pagina
from .keywords import normalizar_com_mapa, padrao_da_keyword

# Cor por categoria de marcacao (RGB hexadecimal, como o leitor de PDF exibe).
CORES = {
    "keyword": "ffe066",    # amarelo — o marca-texto classico
    "evidencia": "8ce99a",  # verde — trecho que sustenta um achado
    "limitacao": "ffc078",  # laranja — limitacao declarada
}

LIMIAR_SIMILARIDADE = 0.55


@dataclass
class Marcacao:
    """Um destaque a gravar: onde, de que cor e com que comentario."""

    pagina: int  # 1-indexada
    categoria: str
    comentario: str
    retangulos: list[tuple[float, float, float, float]] = field(default_factory=list)


@dataclass
class ResultadoMarcacao:
    pdf: bytes
    marcacoes: list[Marcacao] = field(default_factory=list)
    nao_localizadas: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.marcacoes)

    def por_categoria(self) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for marcacao in self.marcacoes:
            contagem[marcacao.categoria] = contagem.get(marcacao.categoria, 0) + 1
        return contagem


# --------------------------------------------------------------------------
# Localizacao de texto com coordenadas
# --------------------------------------------------------------------------

def _indexar_palavras(palavras: list[dict]) -> tuple[str, list[int]]:
    """Concatena as palavras da pagina e mapeia cada caractere a sua palavra.

    O texto sai normalizado (minusculas, sem acento) para casar do mesmo jeito
    que a busca de keywords, e o mapa permite voltar de um trecho casado para as
    palavras — que sao quem carrega as coordenadas.
    """
    partes: list[str] = []
    mapa: list[int] = []
    for indice, palavra in enumerate(palavras):
        if indice:
            partes.append(" ")
            mapa.append(indice - 1)
        normalizada, _ = normalizar_com_mapa(palavra["text"])
        partes.append(normalizada)
        mapa.extend([indice] * len(normalizada))
    return "".join(partes), mapa


def _retangulos(palavras: list[dict], indices: range | list[int], altura: float, base_y: float, base_x: float):
    """Uma caixa por linha ocupada pelo trecho (um trecho pode quebrar linha).

    O pdfplumber mede a partir do topo da pagina; o PDF, a partir da base.
    """
    linhas: dict[int, list[dict]] = {}
    for indice in indices:
        palavra = palavras[indice]
        chave = round(palavra["top"])
        linhas.setdefault(chave, []).append(palavra)

    caixas = []
    for grupo in linhas.values():
        x0 = min(p["x0"] for p in grupo) + base_x
        x1 = max(p["x1"] for p in grupo) + base_x
        topo = min(p["top"] for p in grupo)
        base = max(p["bottom"] for p in grupo)
        caixas.append((x0, altura - base + base_y, x1, altura - topo + base_y))
    return caixas


def _localizar_regex(palavras: list[dict], padrao: re.Pattern[str]) -> list[list[int]]:
    texto, mapa = _indexar_palavras(palavras)
    achados = []
    for casamento in padrao.finditer(texto):
        inicio, fim = casamento.start(), casamento.end()
        if inicio >= len(mapa):
            continue
        envolvidas = sorted({mapa[i] for i in range(inicio, min(fim, len(mapa)))})
        if envolvidas:
            achados.append(envolvidas)
    return achados


def _melhor_trecho(texto_pagina: str, alvo: str, limiar: float) -> str | None:
    """Frase da pagina mais parecida com o alvo, se passar do limiar."""
    alvo_limpo = re.sub(r"\s+", " ", alvo).strip()
    if len(alvo_limpo) < 15:
        return None
    frases = [f.strip() for f in re.split(r"(?<=[.;!?])\s+|\n", texto_pagina) if len(f.strip()) > 25]
    melhor, melhor_nota = None, 0.0
    for frase in frases:
        nota = SequenceMatcher(None, normalizar_com_mapa(frase)[0], normalizar_com_mapa(alvo_limpo)[0]).ratio()
        if nota > melhor_nota:
            melhor, melhor_nota = frase, nota
    return melhor if melhor_nota >= limiar else None


# --------------------------------------------------------------------------
# Gravacao das anotacoes
# --------------------------------------------------------------------------

def _anotacao(marcacao: Marcacao) -> Highlight:
    quads: list[float] = []
    for x0, y0, x1, y1 in marcacao.retangulos:
        # Ordem exigida pelo PDF: superior-esquerda, superior-direita,
        # inferior-esquerda, inferior-direita.
        quads.extend([x0, y1, x1, y1, x0, y0, x1, y0])
    caixa = (
        min(r[0] for r in marcacao.retangulos),
        min(r[1] for r in marcacao.retangulos),
        max(r[2] for r in marcacao.retangulos),
        max(r[3] for r in marcacao.retangulos),
    )
    destaque = Highlight(
        rect=caixa,
        quad_points=ArrayObject([FloatObject(valor) for valor in quads]),
        highlight_color=CORES.get(marcacao.categoria, "ffff00"),
    )
    if marcacao.comentario:
        # A chave precisa ser NameObject; o valor, TextStringObject.
        destaque[NameObject("/Contents")] = TextStringObject(marcacao.comentario)
        destaque[NameObject("/T")] = TextStringObject("Analisador de Artigos")
    return destaque


def paginas_do_rotulo(valor: object) -> set[int] | None:
    """Converte "2" em {2} e "1-3" em {1, 2, 3}. Sem pagina util, devolve None."""
    normalizado = normalizar_pagina(valor)
    if not normalizado:
        return None
    if "-" in normalizado:
        inicio, fim = (int(parte) for parte in normalizado.split("-"))
        if fim < inicio:
            inicio, fim = fim, inicio
        return set(range(inicio, fim + 1))
    return {int(normalizado)}


def _alvos(documento, analise, keywords_extras: list[str] | None) -> tuple[list[str], list[tuple[set[int] | None, str, str]]]:
    """Separa o que sera marcado: termos literais e passagens parafraseadas."""
    termos: list[str] = list(keywords_extras or [])
    if analise:
        termos += [s.keyword for s in analise.sinteses]

    passagens: list[tuple[int | None, str, str]] = []
    if analise:
        for achado in analise.achados:
            if achado.evidencia:
                passagens.append(
                    (paginas_do_rotulo(achado.pagina), achado.evidencia, f"Achado: {achado.afirmacao}")
                )
        for limitacao in analise.limitacoes:
            passagens.append((None, limitacao, "Limitacao apontada na analise"))

    vistos: set[str] = set()
    unicos = [t for t in termos if t.strip() and not (t.lower() in vistos or vistos.add(t.lower()))]
    return unicos, passagens


def marcar(
    conteudo: bytes,
    documento=None,
    analise=None,
    *,
    keywords: list[str] | None = None,
    flexivel: bool = True,
    limiar: float = LIMIAR_SIMILARIDADE,
    marcar_evidencias: bool = True,
) -> ResultadoMarcacao:
    """Devolve o PDF original com as passagens relevantes grifadas."""
    termos, passagens = _alvos(documento, analise, keywords)
    if not marcar_evidencias:
        passagens = []

    leitor = PdfReader(io.BytesIO(conteudo))
    escritor = PdfWriter()
    for pagina in leitor.pages:
        escritor.add_page(pagina)

    marcacoes: list[Marcacao] = []
    localizadas: set[str] = set()

    with pdfplumber.open(io.BytesIO(conteudo)) as documento_plumber:
        for indice, pagina_plumber in enumerate(documento_plumber.pages):
            palavras = pagina_plumber.extract_words()
            if not palavras:
                continue
            altura = float(pagina_plumber.height)
            caixa = leitor.pages[indice].mediabox
            base_x, base_y = float(caixa.left), float(caixa.bottom)
            numero = indice + 1

            for termo in termos:
                try:
                    padrao = padrao_da_keyword(termo, flexivel)
                except ValueError:
                    continue
                for envolvidas in _localizar_regex(palavras, padrao):
                    retangulos = _retangulos(palavras, envolvidas, altura, base_y, base_x)
                    if retangulos:
                        marcacoes.append(
                            Marcacao(numero, "keyword", f"Keyword: {termo}", retangulos)
                        )
                        localizadas.add(termo)

            texto_pagina = pagina_plumber.extract_text() or ""
            for paginas_citadas, alvo, comentario in passagens:
                if paginas_citadas and numero not in paginas_citadas:
                    continue
                trecho = _melhor_trecho(texto_pagina, alvo, limiar)
                if not trecho:
                    continue
                categoria = "evidencia" if comentario.startswith("Achado") else "limitacao"
                padrao = re.compile(re.escape(normalizar_com_mapa(trecho)[0]))
                for envolvidas in _localizar_regex(palavras, padrao):
                    retangulos = _retangulos(palavras, envolvidas, altura, base_y, base_x)
                    if retangulos:
                        marcacoes.append(Marcacao(numero, categoria, comentario, retangulos))
                        localizadas.add(alvo)
                        break

    for marcacao in marcacoes:
        escritor.add_annotation(page_number=marcacao.pagina - 1, annotation=_anotacao(marcacao))

    saida = io.BytesIO()
    escritor.write(saida)

    nao_localizadas = [t for t in termos if t not in localizadas]
    nao_localizadas += [alvo for _, alvo, _ in passagens if alvo not in localizadas]
    return ResultadoMarcacao(pdf=saida.getvalue(), marcacoes=marcacoes, nao_localizadas=nao_localizadas)

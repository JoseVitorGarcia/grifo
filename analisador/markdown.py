"""Conversao do artigo extraido para Markdown, para o modelo ler melhor.

O texto cru do PDF perde a hierarquia: titulo, secao e item de lista chegam ao
modelo como linhas soltas. Em Markdown, essa estrutura volta explicita, o que
melhora a atribuicao de secao e reduz confusao entre corpo e cabecalho.

A conversao produz uma **segunda visao** do mesmo artigo — um `Documento` cujo
`texto` e Markdown e cujas paginas mantem os offsets corretos. Assim o resto do
sistema (divisao em blocos, rotulo de pagina) funciona sem alteracao, enquanto a
busca de keywords continua no texto original, onde a rastreabilidade e exata.
"""

from __future__ import annotations

import re

from .pdf import _PADROES_SECAO, Documento, Pagina, Secao

# Marcadores de item de lista que aparecem em PDFs.
_RE_ITEM = re.compile(r"^\s*[•▪◦·‣∙*]\s+(.+)$")
_RE_ITEM_NUMERADO = re.compile(r"^\s*(\d{1,2}[.)])\s+(.+)$")
# "3.1 Analise dos dados" — titulo numerado, curto e sem pontuacao final.
_RE_TITULO_NUMERADO = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})[.)]?\s+([^\n.;:]{3,70})\s*$")
# Linha de referencia bibliografica: "[12] Autor, ..."
_RE_REFERENCIA = re.compile(r"^\s*(?:\[\d{1,3}\]|\(\d{1,3}\))\s+\S")

_SECOES = [(nome, re.compile(rf"^\s*(?:\d{{1,2}}[.)]?\s*)?({padrao})\s*:?\s*$", re.IGNORECASE))
           for nome, padrao in _PADROES_SECAO]

_FIM_DE_FRASE = tuple(".!?;:")


def _titulo_de_secao(linha: str) -> tuple[str, str] | None:
    for nome, regex in _SECOES:
        achado = regex.match(linha)
        if achado:
            return nome, achado.group(1).strip()
    return None


def _fechar_paragrafo(buffer: list[str], saida: list[str]) -> None:
    """Junta as linhas quebradas pelo PDF num paragrafo unico."""
    if not buffer:
        return
    texto = ""
    for linha in buffer:
        if not texto:
            texto = linha
        elif texto.endswith(_FIM_DE_FRASE):
            texto += " " + linha
        else:
            # Linha quebrada no meio da frase: emenda sem pontuacao extra.
            texto += " " + linha
    saida.append(re.sub(r"\s{2,}", " ", texto).strip())
    buffer.clear()


def _converter_pagina(pagina: Pagina, marcar_pagina: bool) -> tuple[list[str], list[tuple[int, str, str]]]:
    """Devolve os blocos Markdown da pagina e os titulos de secao encontrados.

    Cada secao vem como (indice do bloco, nome canonico, titulo).
    """
    saida: list[str] = []
    secoes: list[tuple[int, str, str]] = []
    buffer: list[str] = []

    if marcar_pagina:
        # Comentario: nao aparece renderizado, mas informa a pagina ao modelo.
        saida.append(f"<!-- p. {pagina.numero} -->")

    em_lista = False
    for linha in pagina.texto.split("\n"):
        despida = linha.strip()

        if not despida:
            _fechar_paragrafo(buffer, saida)
            em_lista = False
            continue

        secao = _titulo_de_secao(despida)
        if secao:
            _fechar_paragrafo(buffer, saida)
            em_lista = False
            secoes.append((len(saida), secao[0], secao[1]))
            saida.append(f"## {secao[1]}")
            continue

        if _RE_REFERENCIA.match(despida):
            _fechar_paragrafo(buffer, saida)
            saida.append(f"- {despida}")
            em_lista = True
            continue

        item = _RE_ITEM.match(despida)
        if item:
            _fechar_paragrafo(buffer, saida)
            saida.append(f"- {item.group(1).strip()}")
            em_lista = True
            continue

        numerado = _RE_ITEM_NUMERADO.match(despida)
        titulo_numerado = _RE_TITULO_NUMERADO.match(despida)
        if titulo_numerado and not numerado_e_frase(titulo_numerado):
            _fechar_paragrafo(buffer, saida)
            em_lista = False
            saida.append(f"### {titulo_numerado.group(1)} {titulo_numerado.group(2).strip()}")
            continue
        if numerado:
            _fechar_paragrafo(buffer, saida)
            saida.append(f"{numerado.group(1)} {numerado.group(2).strip()}")
            em_lista = True
            continue

        if em_lista and saida and saida[-1].startswith(("- ", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
            # Continuacao da linha anterior da lista.
            saida[-1] = f"{saida[-1]} {despida}"
            continue

        buffer.append(despida)

    _fechar_paragrafo(buffer, saida)
    return saida, secoes


def numerado_e_frase(achado: re.Match[str]) -> bool:
    """Distingue "3.1 Metodos" (titulo) de "1. O estudo avaliou..." (item)."""
    corpo = achado.group(2).strip()
    return len(corpo.split()) > 10


def converter(documento: Documento, *, marcar_paginas: bool = True) -> Documento:
    """Devolve o mesmo artigo como `Documento` em Markdown.

    As paginas mantem offsets validos no novo texto, entao a divisao em blocos e
    o rotulo de pagina continuam corretos.
    """
    partes: list[str] = []
    paginas: list[Pagina] = []
    secoes: list[Secao] = []
    vistas: set[str] = set()
    cursor = 0

    titulo = (documento.metadados.get("titulo") or "").strip()
    preambulo = f"# {titulo}\n\n" if titulo else ""

    for indice, pagina in enumerate(documento.paginas):
        blocos, achadas = _converter_pagina(pagina, marcar_paginas)
        corpo = "\n\n".join(blocos)
        texto_pagina = (preambulo if indice == 0 else "") + corpo
        bloco_completo = texto_pagina + "\n\n"

        # Offset de cada titulo de secao dentro do texto final.
        deslocamento = cursor + len(preambulo if indice == 0 else "")
        posicao = deslocamento
        for numero_bloco, nome, rotulo in achadas:
            posicao = deslocamento + sum(len(b) + 2 for b in blocos[:numero_bloco])
            if nome not in vistas:
                vistas.add(nome)
                secoes.append(Secao(nome=nome, titulo=rotulo, inicio=posicao, fim=posicao))

        paginas.append(
            Pagina(
                numero=pagina.numero,
                texto=texto_pagina,
                inicio=cursor,
                fim=cursor + len(bloco_completo),
            )
        )
        partes.append(bloco_completo)
        cursor += len(bloco_completo)

    texto = "".join(partes).strip()

    # Cada secao vai ate o inicio da proxima.
    for posicao, secao in enumerate(secoes):
        secao.fim = secoes[posicao + 1].inicio if posicao + 1 < len(secoes) else len(texto)

    return Documento(
        texto=texto,
        paginas=paginas,
        metadados=dict(documento.metadados),
        secoes=secoes,
        avisos=list(documento.avisos),
    )

"""Busca deterministica de keywords no texto do artigo.

Esta e a metade verificavel da analise: nada aqui passa pelo LLM. A busca
ignora acentos e caixa, mas devolve sempre o trecho original e a pagina, para
que qualquer afirmacao do modelo possa ser conferida na fonte.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Sufixos de flexao comuns em pt/en, usados no modo de busca flexivel.
_SUFIXOS_FLEXIVEIS = r"(?:s|es|is|ns|ais|eis|ais|ies|ed|ing)?"


def normalizar_com_mapa(texto: str) -> tuple[str, list[int]]:
    """Normaliza (minusculas, sem acento) preservando o mapa para o texto original.

    Devolve o texto normalizado e uma lista onde `mapa[i]` e o indice, no texto
    original, do caractere que gerou `normalizado[i]`. Necessario porque remover
    acentos muda o comprimento da string.
    """
    saida: list[str] = []
    mapa: list[int] = []
    for indice, caractere in enumerate(texto):
        decomposto = unicodedata.normalize("NFKD", caractere.lower())
        for parte in decomposto:
            if unicodedata.combining(parte):
                continue
            saida.append(parte)
            mapa.append(indice)
    return "".join(saida), mapa


def normalizar(texto: str) -> str:
    return normalizar_com_mapa(texto)[0]


@dataclass
class Ocorrencia:
    keyword: str
    pagina: int
    secao: str | None
    inicio: int
    fim: int
    trecho: str  # contexto ao redor, com a ocorrencia entre **asteriscos**
    termo_encontrado: str  # como aparece de fato no artigo


@dataclass
class ResultadoKeyword:
    keyword: str
    total: int
    paginas: list[int] = field(default_factory=list)
    ocorrencias: list[Ocorrencia] = field(default_factory=list)
    densidade_por_mil: float = 0.0

    @property
    def encontrada(self) -> bool:
        return self.total > 0


def padrao_da_keyword(keyword: str, flexivel: bool) -> re.Pattern[str]:
    """Monta a regex da keyword ja normalizada, tolerando espacos e hifens."""
    termo = normalizar(keyword).strip()
    partes = [re.escape(p) for p in re.split(r"[\s\-]+", termo) if p]
    if not partes:
        raise ValueError("keyword vazia")
    if flexivel:
        partes = [p + _SUFIXOS_FLEXIVEIS for p in partes]
    corpo = r"[\s\-]+".join(partes)
    # \b nas bordas evita casar "arte" dentro de "partes".
    return re.compile(rf"(?<!\w){corpo}(?!\w)")


def _montar_trecho(texto: str, inicio: int, fim: int, janela: int) -> str:
    esquerda = max(0, inicio - janela)
    direita = min(len(texto), fim + janela)
    antes = texto[esquerda:inicio].replace("\n", " ")
    alvo = texto[inicio:fim].replace("\n", " ")
    depois = texto[fim:direita].replace("\n", " ")
    prefixo = "..." if esquerda > 0 else ""
    sufixo = "..." if direita < len(texto) else ""
    trecho = f"{prefixo}{antes}**{alvo}**{depois}{sufixo}"
    return re.sub(r"\s{2,}", " ", trecho).strip()


def buscar_keyword(
    documento,
    keyword: str,
    *,
    flexivel: bool = True,
    janela: int = 220,
    max_ocorrencias: int = 40,
) -> ResultadoKeyword:
    """Localiza todas as ocorrencias de uma keyword em um `Documento`."""
    texto = documento.texto
    normalizado, mapa = normalizar_com_mapa(texto)
    padrao = padrao_da_keyword(keyword, flexivel)

    ocorrencias: list[Ocorrencia] = []
    paginas: list[int] = []
    total = 0
    for achado in padrao.finditer(normalizado):
        total += 1
        inicio = mapa[achado.start()]
        # mapa[fim-1] e o ultimo caractere casado; +1 para virar limite exclusivo.
        fim = mapa[achado.end() - 1] + 1
        pagina = documento.pagina_do_offset(inicio)
        if pagina not in paginas:
            paginas.append(pagina)
        if len(ocorrencias) < max_ocorrencias:
            ocorrencias.append(
                Ocorrencia(
                    keyword=keyword,
                    pagina=pagina,
                    secao=documento.secao_do_offset(inicio),
                    inicio=inicio,
                    fim=fim,
                    trecho=_montar_trecho(texto, inicio, fim, janela),
                    termo_encontrado=texto[inicio:fim],
                )
            )

    n_palavras = max(1, len(texto.split()))
    return ResultadoKeyword(
        keyword=keyword,
        total=total,
        paginas=sorted(paginas),
        ocorrencias=ocorrencias,
        densidade_por_mil=round(total * 1000 / n_palavras, 2),
    )


def buscar_varias(documento, keywords: list[str], **kwargs) -> list[ResultadoKeyword]:
    resultados = []
    for keyword in keywords:
        if keyword.strip():
            resultados.append(buscar_keyword(documento, keyword.strip(), **kwargs))
    return resultados


def separar_keywords(entrada: str) -> list[str]:
    """Aceita keywords separadas por virgula, ponto-e-virgula ou quebra de linha."""
    if not entrada:
        return []
    brutas = re.split(r"[,;\n]+", entrada)
    vistas: set[str] = set()
    limpas: list[str] = []
    for bruta in brutas:
        termo = bruta.strip().strip('"').strip("'")
        chave = normalizar(termo)
        if termo and chave not in vistas:
            vistas.add(chave)
            limpas.append(termo)
    return limpas

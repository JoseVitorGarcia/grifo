"""Modo lote: varios artigos por sessao, com comparacao entre eles.

O estado do lote vive aqui como dados puros (sem Streamlit), para que a triagem
de arquivos e as tabelas comparativas possam ser testadas isoladamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .analise import Analise
from .blocos import Bloco
from .pdf import Documento

LIMITE_PADRAO = 5


@dataclass
class Item:
    """Um artigo do lote e tudo que ja foi produzido sobre ele."""

    assinatura: str
    nome: str
    documento: Documento
    # Mesma fonte, em Markdown: e o que vai para o modelo.
    markdown: Documento | None = None
    analise: Analise | None = None
    blocos: list[Bloco] = field(default_factory=list)

    @property
    def para_o_modelo(self) -> Documento:
        """Visao usada nas chamadas ao modelo (Markdown quando disponivel)."""
        return self.markdown or self.documento

    @property
    def analisado(self) -> bool:
        return self.analise is not None

    @property
    def titulo(self) -> str:
        return self.documento.metadados.get("titulo") or self.nome

    @property
    def rotulo(self) -> str:
        marca = "✅" if self.analisado else "⏳"
        return f"{marca} {self.nome}"


@dataclass
class Recusado:
    nome: str
    motivo: str


def triar(
    existentes: Iterable[str],
    candidatos: list[tuple[str, str]],
    limite: int = LIMITE_PADRAO,
) -> tuple[list[tuple[str, str]], list[Recusado]]:
    """Decide quais arquivos entram no lote.

    `candidatos` e uma lista de (assinatura, nome). Devolve os aceitos e os
    recusados com o motivo — duplicata ou limite da sessao atingido.
    """
    ja_no_lote = list(existentes)
    aceitos: list[tuple[str, str]] = []
    recusados: list[Recusado] = []

    for assinatura, nome in candidatos:
        if assinatura in ja_no_lote:
            recusados.append(Recusado(nome, "ja esta no lote (mesmo conteudo)"))
            continue
        if len(ja_no_lote) >= limite:
            recusados.append(
                Recusado(nome, f"limite de {limite} PDFs por sessao atingido")
            )
            continue
        ja_no_lote.append(assinatura)
        aceitos.append((assinatura, nome))

    return aceitos, recusados


def vagas(existentes: Iterable[str], limite: int = LIMITE_PADRAO) -> int:
    return max(0, limite - len(list(existentes)))


def comparar_keywords(itens: list[Item]) -> list[dict]:
    """Uma linha por keyword, uma coluna por artigo, com as ocorrencias.

    Como a busca de keywords e deterministica, esta tabela vale mesmo para
    artigos cuja sintese do modelo falhou ou foi desativada.
    """
    linhas: dict[str, dict] = {}
    for item in itens:
        if not item.analise:
            continue
        for sintese in item.analise.sinteses:
            linha = linhas.setdefault(sintese.keyword, {"Keyword": sintese.keyword})
            linha[item.nome] = sintese.resultado.total
    for item in itens:
        for linha in linhas.values():
            linha.setdefault(item.nome, 0)
    return list(linhas.values())


def resumo_do_lote(itens: list[Item]) -> list[dict]:
    """Visao geral de um artigo por linha."""
    tabela = []
    for item in itens:
        total_keywords = 0
        encontradas = 0
        if item.analise:
            total_keywords = len(item.analise.sinteses)
            encontradas = sum(1 for s in item.analise.sinteses if s.resultado.encontrada)
        tabela.append(
            {
                "Arquivo": item.nome,
                "Titulo": item.titulo[:70],
                "Paginas": item.documento.n_paginas,
                "Palavras": item.documento.n_palavras,
                "Leitura (min)": item.documento.minutos_de_leitura,
                "Keywords encontradas": f"{encontradas}/{total_keywords}" if total_keywords else "—",
                "Analisado": "sim" if item.analisado else "nao",
            }
        )
    return tabela


def keywords_ausentes(itens: list[Item]) -> dict[str, list[str]]:
    """Para cada keyword, em quais artigos ela nao aparece."""
    ausencias: dict[str, list[str]] = {}
    for item in itens:
        if not item.analise:
            continue
        for sintese in item.analise.sinteses:
            if not sintese.resultado.encontrada:
                ausencias.setdefault(sintese.keyword, []).append(item.nome)
    return ausencias

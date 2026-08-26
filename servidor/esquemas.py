"""Conversao dos objetos do nucleo para o JSON que o front consome."""

from __future__ import annotations

from analisador.analise import Analise
from analisador.lote import Item, comparar_keywords, keywords_ausentes, resumo_do_lote


def documento_para_dict(documento) -> dict:
    return {
        "metadados": documento.metadados,
        "paginas": documento.n_paginas,
        "palavras": documento.n_palavras,
        "caracteres": documento.n_caracteres,
        "minutos_de_leitura": documento.minutos_de_leitura,
        "secoes": [s.titulo for s in documento.secoes],
        "avisos": documento.avisos,
    }


def resultado_para_dict(resultado, sintese: str = "") -> dict:
    """Serializa um `ResultadoKeyword`. `sintese` fica vazia no scan puro."""
    return {
        "keyword": resultado.keyword,
        "sintese": sintese,
        "total": resultado.total,
        "paginas": resultado.paginas,
        "densidade_por_mil": resultado.densidade_por_mil,
        "encontrada": resultado.encontrada,
        "ocorrencias": [
            {
                "pagina": o.pagina,
                "secao": o.secao,
                "trecho": o.trecho,
                "termo": o.termo_encontrado,
            }
            for o in resultado.ocorrencias
        ],
    }


def analise_para_dict(analise: Analise | None) -> dict | None:
    if analise is None:
        return None
    return {
        "resumo": analise.resumo,
        "achados": [
            {"afirmacao": a.afirmacao, "evidencia": a.evidencia, "pagina": a.pagina}
            for a in analise.achados
        ],
        "limitacoes": analise.limitacoes,
        "keywords_sugeridas": analise.keywords_sugeridas,
        "erros": analise.erros,
        "keywords": [resultado_para_dict(s.resultado, s.resumo) for s in analise.sinteses],
    }


def item_para_dict(item: Item, completo: bool = False) -> dict:
    dados = {
        "id": item.assinatura,
        "nome": item.nome,
        "titulo": item.titulo,
        "analisado": item.analisado,
        "documento": documento_para_dict(item.documento),
    }
    if completo:
        dados["analise"] = analise_para_dict(item.analise)
    return dados


def lote_para_dict(itens: list[Item]) -> dict:
    analisados = [item for item in itens if item.analisado]
    return {
        "resumo": resumo_do_lote(itens),
        "comparacao": comparar_keywords(analisados),
        "ausentes": keywords_ausentes(analisados),
        "arquivos": [item.nome for item in itens],
    }

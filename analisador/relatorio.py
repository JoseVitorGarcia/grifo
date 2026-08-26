"""Geracao do relatorio final em Markdown e JSON."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

from .analise import Analise
from .pdf import Documento

ROTULOS = {
    "objetivo": "Objetivo",
    "metodologia": "Metodologia",
    "resultados": "Resultados",
    "conclusao": "Conclusao",
    "relevancia": "Relevancia",
}


def _cabecalho(documento: Documento) -> list[str]:
    meta = documento.metadados
    linhas = [f"# Analise — {meta.get('titulo', 'Artigo sem titulo identificado')}", ""]
    if meta.get("autores"):
        linhas.append(f"**Autores:** {meta['autores']}")
    if meta.get("doi"):
        linhas.append(f"**DOI:** {meta['doi']}")
    linhas.append(
        f"**Paginas:** {documento.n_paginas} · **Palavras:** {documento.n_palavras:,} · "
        f"**Leitura estimada:** {documento.minutos_de_leitura} min"
    )
    if meta.get("referencias_estimadas"):
        linhas.append(f"**Referencias identificadas:** {meta['referencias_estimadas']}")
    if documento.secoes:
        linhas.append("**Secoes detectadas:** " + ", ".join(s.titulo for s in documento.secoes))
    linhas.append(f"\n_Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}_\n")
    return linhas


def para_markdown(documento: Documento, analise: Analise, modelo: str = "") -> str:
    linhas = _cabecalho(documento)

    if analise.resumo:
        linhas.append("## Resumo estruturado\n")
        for chave, rotulo in ROTULOS.items():
            valor = analise.resumo.get(chave)
            if valor:
                linhas.append(f"**{rotulo}:** {valor}\n")

    if analise.achados:
        linhas.append("## Principais achados\n")
        for i, achado in enumerate(analise.achados, start=1):
            pagina = f" _(p. {achado.pagina})_" if achado.pagina else ""
            linhas.append(f"{i}. **{achado.afirmacao}**{pagina}")
            if achado.evidencia:
                linhas.append(f"   - Evidencia: {achado.evidencia}")
        linhas.append("")

    if analise.limitacoes:
        linhas.append("## Limitacoes e lacunas\n")
        linhas.extend(f"- {item}" for item in analise.limitacoes)
        linhas.append("")

    if analise.sinteses:
        linhas.append("## Keywords solicitadas\n")
        for sintese in analise.sinteses:
            resultado = sintese.resultado
            paginas = ", ".join(str(p) for p in resultado.paginas) or "—"
            linhas.append(f"### {sintese.keyword}\n")
            linhas.append(
                f"- Ocorrencias: **{resultado.total}** · Paginas: {paginas} · "
                f"Densidade: {resultado.densidade_por_mil} por mil palavras"
            )
            linhas.append(f"\n{sintese.resumo}\n")
            if resultado.ocorrencias:
                linhas.append("<details><summary>Trechos</summary>\n")
                for ocorrencia in resultado.ocorrencias[:10]:
                    linhas.append(f"- (p. {ocorrencia.pagina}) {ocorrencia.trecho}")
                linhas.append("\n</details>\n")

    if analise.keywords_sugeridas:
        linhas.append("## Termos-chave sugeridos pelo modelo\n")
        linhas.append(", ".join(f"`{k}`" for k in analise.keywords_sugeridas) + "\n")

    if documento.avisos:
        linhas.append("## Avisos da extracao\n")
        linhas.extend(f"- {aviso}" for aviso in documento.avisos)
        linhas.append("")

    if modelo:
        linhas.append(f"\n---\n_Analise gerada localmente com `{modelo}` via Ollama._")
    return "\n".join(linhas)


def para_json(documento: Documento, analise: Analise, modelo: str = "") -> str:
    dados = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "modelo": modelo,
        "documento": {
            "metadados": documento.metadados,
            "paginas": documento.n_paginas,
            "palavras": documento.n_palavras,
            "minutos_de_leitura": documento.minutos_de_leitura,
            "secoes": [s.titulo for s in documento.secoes],
            "avisos": documento.avisos,
        },
        "resumo": analise.resumo,
        "achados": [asdict(a) for a in analise.achados],
        "limitacoes": analise.limitacoes,
        "keywords_sugeridas": analise.keywords_sugeridas,
        "keywords": [
            {
                "keyword": s.keyword,
                "sintese": s.resumo,
                "total_ocorrencias": s.resultado.total,
                "paginas": s.resultado.paginas,
                "densidade_por_mil": s.resultado.densidade_por_mil,
                "ocorrencias": [
                    {"pagina": o.pagina, "secao": o.secao, "trecho": o.trecho}
                    for o in s.resultado.ocorrencias
                ],
            }
            for s in analise.sinteses
        ],
        "erros": analise.erros,
    }
    return json.dumps(dados, ensure_ascii=False, indent=2)


def _rebaixar_titulos(markdown: str) -> str:
    """Desce todos os cabecalhos um nivel (# -> ##, ## -> ###)."""
    saida = []
    for linha in markdown.split("\n"):
        saida.append("#" + linha if linha.startswith("#") else linha)
    return "\n".join(saida)


def para_markdown_lote(itens, modelo: str = "") -> str:
    """Relatorio consolidado: comparacao entre artigos + o relatorio de cada um."""
    from .lote import comparar_keywords, keywords_ausentes, resumo_do_lote

    analisados = [item for item in itens if item.analisado]
    linhas = [
        "# Relatorio consolidado do lote",
        "",
        f"**Artigos no lote:** {len(itens)} · **Analisados:** {len(analisados)}",
        f"\n_Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}_\n",
        "## Artigos",
        "",
    ]

    resumo = resumo_do_lote(itens)
    if resumo:
        colunas = list(resumo[0].keys())
        linhas.append("| " + " | ".join(colunas) + " |")
        linhas.append("|" + "---|" * len(colunas))
        for linha in resumo:
            linhas.append("| " + " | ".join(str(linha[c]) for c in colunas) + " |")
        linhas.append("")

    comparacao = comparar_keywords(analisados)
    if comparacao:
        linhas.append("## Keywords por artigo (ocorrencias)\n")
        colunas = list(comparacao[0].keys())
        linhas.append("| " + " | ".join(colunas) + " |")
        linhas.append("|" + "---|" * len(colunas))
        for linha in comparacao:
            linhas.append("| " + " | ".join(str(linha[c]) for c in colunas) + " |")
        linhas.append("")

        ausentes = keywords_ausentes(analisados)
        if ausentes:
            linhas.append("### Keywords ausentes\n")
            for keyword, arquivos in ausentes.items():
                linhas.append(f"- **{keyword}**: nao aparece em {', '.join(arquivos)}")
            linhas.append("")

    for item in analisados:
        linhas.append("\n---\n")
        linhas.append(f"# Arquivo: {item.nome}\n")
        # O relatorio individual traz seus proprios titulos; rebaixa um nivel
        # para nao competir com o titulo do consolidado.
        linhas.append(_rebaixar_titulos(para_markdown(item.documento, item.analise, modelo)))

    return "\n".join(linhas)


def para_json_lote(itens, modelo: str = "") -> str:
    return json.dumps(
        {
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "modelo": modelo,
            "artigos": [
                json.loads(para_json(item.documento, item.analise, modelo))
                | {"arquivo": item.nome}
                for item in itens
                if item.analisado
            ],
        },
        ensure_ascii=False,
        indent=2,
    )

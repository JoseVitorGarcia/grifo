"""Orquestracao da analise: resumo objetivo, achados, limitacoes e keywords.

Estrategia: uma unica passada cara sobre o artigo inteiro (map) produz notas
condensadas com paginas; todas as etapas seguintes (resumo, achados,
limitacoes) reaproveitam essas notas. Isso mantem o custo previsivel mesmo
rodando em CPU.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .blocos import Bloco, dividir
from .keywords import Ocorrencia, ResultadoKeyword
from .llm import ClienteOllama, ErroOllama

Progresso = Callable[[str, float], None]

SISTEMA = (
    "Voce e um assistente de leitura critica de artigos cientificos. "
    "Responda SEMPRE em portugues do Brasil. "
    "Seja objetivo e direto: frases curtas, sem adjetivos de elogio, sem repetir a pergunta, "
    "sem introducoes do tipo 'claro, aqui esta'. "
    "Use exclusivamente o conteudo do trecho fornecido. "
    "Se a informacao nao estiver no trecho, escreva exatamente 'nao informado'. "
    "Nunca invente numeros, autores ou citacoes."
)


_RE_PAGINA = re.compile(r"(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?")


def normalizar_pagina(valor: object) -> str:
    """Extrai "2" ou "1-3" do que o modelo devolver.

    O modelo costuma repetir o rotulo do bloco ("[p. 1-3]") em vez de um numero
    limpo; sem isso, a pagina vaza formatada para a tela e para o grifo.
    """
    achado = _RE_PAGINA.search(str(valor or ""))
    if not achado:
        return ""
    inicio, fim = achado.group(1), achado.group(2)
    return f"{inicio}-{fim}" if fim and fim != inicio else inicio


@dataclass
class Achado:
    afirmacao: str
    evidencia: str = ""
    pagina: str = ""


@dataclass
class SinteseKeyword:
    keyword: str
    resumo: str
    resultado: ResultadoKeyword


@dataclass
class Analise:
    notas: list[str] = field(default_factory=list)
    resumo: dict[str, str] = field(default_factory=dict)
    achados: list[Achado] = field(default_factory=list)
    limitacoes: list[str] = field(default_factory=list)
    keywords_sugeridas: list[str] = field(default_factory=list)
    sinteses: list[SinteseKeyword] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)


CAMPOS_RESUMO = [
    ("objetivo", "O que o estudo se propos a responder"),
    ("metodologia", "Como foi feito: desenho, dados, amostra, tecnicas"),
    ("resultados", "Os principais resultados, com numeros quando houver"),
    ("conclusao", "O que os autores concluem"),
    ("relevancia", "Por que isso importa e para quem"),
]


def _notas_do_bloco(cliente: ClienteOllama, bloco: Bloco) -> str:
    prompt = (
        f"Trecho do artigo ({bloco.rotulo}):\n\n{bloco.texto}\n\n"
        "Extraia no maximo 5 pontos factuais deste trecho, um por linha, no formato "
        f"'- [{bloco.rotulo}] ponto'. Priorize objetivo, metodo, dados, numeros, "
        "resultados e limitacoes. Ignore cabecalhos, referencias e agradecimentos. "
        "Nao comente, nao conclua, apenas liste."
    )
    return cliente.conversar(prompt, sistema=SISTEMA).strip()


def levantar_notas(
    cliente: ClienteOllama,
    documento,
    *,
    tamanho_bloco: int = 6000,
    sobreposicao: int = 400,
    max_blocos: int = 24,
    progresso: Progresso | None = None,
) -> tuple[list[str], list[Bloco]]:
    """Passada de map: condensa cada bloco do artigo em pontos factuais."""
    blocos = dividir(documento, tamanho=tamanho_bloco, sobreposicao=sobreposicao)
    selecionados = blocos[:max_blocos]
    notas: list[str] = []
    for posicao, bloco in enumerate(selecionados, start=1):
        if progresso:
            progresso(
                f"Lendo bloco {posicao}/{len(selecionados)} ({bloco.rotulo})",
                posicao / max(1, len(selecionados)),
            )
        try:
            nota = _notas_do_bloco(cliente, bloco)
        except ErroOllama as erro:
            nota = f"- [{bloco.rotulo}] (falha ao ler este bloco: {erro})"
        if nota:
            notas.append(nota)
    return notas, blocos


def _contexto(notas: list[str], documento, limite: int = 14000) -> str:
    corpo = "\n".join(notas)
    extras = []
    for nome in ("resumo", "conclusao"):
        trecho = documento.trecho_secao(nome, limite=2500)
        if trecho:
            extras.append(f"### Secao {nome}\n{trecho}")
    juncao = "### Notas de leitura\n" + corpo
    if extras:
        juncao += "\n\n" + "\n\n".join(extras)
    return juncao[:limite]


def montar_resumo(cliente: ClienteOllama, notas: list[str], documento) -> dict[str, str]:
    campos = "\n".join(f'  "{chave}": "{descricao}"' for chave, descricao in CAMPOS_RESUMO)
    prompt = (
        f"{_contexto(notas, documento)}\n\n"
        "Com base apenas no material acima, devolva um JSON com exatamente estas chaves:\n"
        f"{{\n{campos}\n}}\n"
        "Cada valor deve ter no maximo 3 frases curtas, em portugues, sem enfeite. "
        "Use 'nao informado' quando o material nao disser."
    )
    dados = cliente.conversar_json(prompt, sistema=SISTEMA)
    if not isinstance(dados, dict):
        raise ErroOllama("Resumo veio em formato inesperado.")
    return {chave: str(dados.get(chave, "nao informado")).strip() for chave, _ in CAMPOS_RESUMO}


def extrair_achados(cliente: ClienteOllama, notas: list[str], documento, quantidade: int = 6) -> list[Achado]:
    prompt = (
        f"{_contexto(notas, documento)}\n\n"
        f"Liste ate {quantidade} achados centrais do artigo. Devolva JSON no formato "
        '{"achados": [{"afirmacao": "...", "evidencia": "...", "pagina": "..."}]}. '
        "'afirmacao' e o achado em uma frase; 'evidencia' e o dado ou trecho do material "
        "que o sustenta (numeros quando houver); 'pagina' e a pagina indicada entre colchetes "
        "nas notas, ou string vazia se nao houver. Nao repita achados."
    )
    dados = cliente.conversar_json(prompt, sistema=SISTEMA)
    itens = dados.get("achados", []) if isinstance(dados, dict) else dados
    achados: list[Achado] = []
    for item in itens or []:
        if isinstance(item, dict) and str(item.get("afirmacao", "")).strip():
            achados.append(
                Achado(
                    afirmacao=str(item.get("afirmacao", "")).strip(),
                    evidencia=str(item.get("evidencia", "")).strip(),
                    pagina=normalizar_pagina(item.get("pagina", "")),
                )
            )
        elif isinstance(item, str) and item.strip():
            achados.append(Achado(afirmacao=item.strip()))
    return achados[:quantidade]


def extrair_limitacoes(cliente: ClienteOllama, notas: list[str], documento, quantidade: int = 6) -> list[str]:
    trecho_discussao = documento.trecho_secao("limitacoes", 2500) or documento.trecho_secao("discussao", 2500)
    extra = f"\n\n### Trecho de discussao/limitacoes\n{trecho_discussao}" if trecho_discussao else ""
    prompt = (
        f"{_contexto(notas, documento, limite=11000)}{extra}\n\n"
        f"Liste ate {quantidade} limitacoes ou lacunas do estudo. Inclua tanto as que os "
        "autores admitem quanto perguntas que o artigo deixa sem resposta; marque as segundas "
        "com o prefixo 'Lacuna: '. Devolva JSON no formato "
        '{"limitacoes": ["...", "..."]}. Se o material nao permitir identificar nenhuma, '
        'devolva {"limitacoes": []}.'
    )
    dados = cliente.conversar_json(prompt, sistema=SISTEMA)
    itens = dados.get("limitacoes", []) if isinstance(dados, dict) else dados
    return [str(i).strip() for i in (itens or []) if str(i).strip()][:quantidade]


def sugerir_keywords(cliente: ClienteOllama, notas: list[str], documento, quantidade: int = 10) -> list[str]:
    prompt = (
        f"{_contexto(notas, documento, limite=9000)}\n\n"
        f"Liste ate {quantidade} termos-chave que representam o conteudo deste artigo "
        "(conceitos, metodos, variaveis, dominio de aplicacao). Sem siglas soltas sem "
        'explicacao. Devolva JSON no formato {"keywords": ["termo", "termo"]}.'
    )
    dados = cliente.conversar_json(prompt, sistema=SISTEMA)
    itens = dados.get("keywords", []) if isinstance(dados, dict) else dados
    return [str(i).strip() for i in (itens or []) if str(i).strip()][:quantidade]


def _amostra_ocorrencias(ocorrencias: list[Ocorrencia], limite: int = 8) -> str:
    linhas = []
    for ocorrencia in ocorrencias[:limite]:
        secao = f", secao {ocorrencia.secao}" if ocorrencia.secao else ""
        linhas.append(f"- (p. {ocorrencia.pagina}{secao}) {ocorrencia.trecho}")
    return "\n".join(linhas)


def sintetizar_keyword(cliente: ClienteOllama, resultado: ResultadoKeyword) -> SinteseKeyword:
    """Explica o que o artigo diz sobre a keyword, a partir dos trechos reais."""
    if not resultado.encontrada:
        return SinteseKeyword(
            keyword=resultado.keyword,
            resumo=(
                f"O termo \"{resultado.keyword}\" nao aparece literalmente no texto extraido "
                "do artigo. Verifique sinonimos ou variacoes."
            ),
            resultado=resultado,
        )
    prompt = (
        f'Trechos do artigo que contem o termo "{resultado.keyword}" '
        f"(o termo esta entre asteriscos):\n\n{_amostra_ocorrencias(resultado.ocorrencias)}\n\n"
        f'Em ate 5 frases, explique o que o artigo afirma sobre "{resultado.keyword}": '
        "qual o papel do termo no estudo, o que se conclui sobre ele e com que dado. "
        "Cite a pagina entre parenteses ao final de cada afirmacao. "
        "Use apenas os trechos acima."
    )
    try:
        resumo = cliente.conversar(prompt, sistema=SISTEMA).strip()
    except ErroOllama as erro:
        resumo = f"(falha ao sintetizar: {erro})"
    return SinteseKeyword(keyword=resultado.keyword, resumo=resumo, resultado=resultado)

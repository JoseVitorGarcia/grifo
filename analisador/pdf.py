"""Extracao e limpeza de texto de artigos em PDF.

O objetivo aqui e produzir um texto legivel por LLM a partir do PDF, mantendo
a rastreabilidade ate a pagina de origem: cada trecho do texto completo sabe
de que pagina veio, o que permite citar evidencias com numero de pagina.
"""

from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import BinaryIO

from pypdf import PdfReader

# Titulos de secao tipicos de artigo cientifico, em ingles e portugues.
_PADROES_SECAO = [
    ("resumo", r"(?:abstract|resumo)"),
    ("introducao", r"(?:introduction|introdu[cç][aã]o)"),
    ("revisao", r"(?:related\s+work|literature\s+review|revis[aã]o\s+(?:da\s+)?literatura|referencial\s+te[oó]rico)"),
    ("metodo", r"(?:methods?|methodology|materials?\s+and\s+methods|m[eé]todos?|metodologia|materiais\s+e\s+m[eé]todos)"),
    ("resultados", r"(?:results?|resultados?)"),
    ("discussao", r"(?:discussion|discuss[aã]o)"),
    ("conclusao", r"(?:conclusions?|considera[cç][oõ]es\s+finais|conclus[aã]o|conclus[oõ]es)"),
    ("limitacoes", r"(?:limitations?|limita[cç][oõ]es)"),
    ("referencias", r"(?:references?|bibliography|refer[eê]ncias?|bibliografia)"),
]

_RE_DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+\b")
_RE_ANO = re.compile(r"\b(19|20)\d{2}\b")
# Uma entrada de referencia costuma comecar com "[12]" ou "12." no inicio da linha.
_RE_ENTRADA_REF = re.compile(r"^\s*(?:\[\d{1,3}\]|\(\d{1,3}\)|\d{1,3}\.)\s+\S")

PALAVRAS_POR_MINUTO = 200


@dataclass
class Pagina:
    numero: int  # 1-indexado, como o leitor ve
    texto: str
    inicio: int  # offset da pagina dentro do texto completo
    fim: int


@dataclass
class Secao:
    nome: str
    titulo: str
    inicio: int
    fim: int

    @property
    def tamanho(self) -> int:
        return self.fim - self.inicio


@dataclass
class Documento:
    texto: str
    paginas: list[Pagina]
    metadados: dict[str, str] = field(default_factory=dict)
    secoes: list[Secao] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def n_paginas(self) -> int:
        return len(self.paginas)

    @property
    def n_palavras(self) -> int:
        return len(self.texto.split())

    @property
    def n_caracteres(self) -> int:
        return len(self.texto)

    @property
    def minutos_de_leitura(self) -> int:
        return max(1, round(self.n_palavras / PALAVRAS_POR_MINUTO))

    def pagina_do_offset(self, offset: int) -> int:
        """Numero da pagina que contem um offset do texto completo."""
        for pagina in self.paginas:
            if pagina.inicio <= offset < pagina.fim:
                return pagina.numero
        return self.paginas[-1].numero if self.paginas else 0

    def secao_do_offset(self, offset: int) -> str | None:
        for secao in self.secoes:
            if secao.inicio <= offset < secao.fim:
                return secao.titulo
        return None

    def trecho_secao(self, nome: str, limite: int = 4000) -> str:
        """Texto de uma secao pelo nome canonico (ex.: 'conclusao')."""
        for secao in self.secoes:
            if secao.nome == nome:
                return self.texto[secao.inicio : secao.fim][:limite]
        return ""


def _juntar_hifenizacao(texto: str) -> str:
    """Reconstroi palavras quebradas por hifen no fim da linha ("anali-\\nse")."""
    return re.sub(r"(\w)-\n(\w)", r"\1\2", texto)


def _normalizar_espacos(texto: str) -> str:
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = texto.replace("­", "")  # hifen suave
    texto = re.sub(r"[ \t ]+", " ", texto)
    texto = re.sub(r" ?\n ?", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def _detectar_repetidos(paginas: list[str], limiar: float = 0.6) -> set[str]:
    """Linhas que se repetem na maioria das paginas sao cabecalho/rodape."""
    if len(paginas) < 4:
        return set()
    contagem: Counter[str] = Counter()
    for texto in paginas:
        linhas = {linha.strip() for linha in texto.split("\n") if 3 < len(linha.strip()) < 120}
        contagem.update(linhas)
    minimo = max(3, int(len(paginas) * limiar))
    return {linha for linha, n in contagem.items() if n >= minimo}


def _remover_linhas(texto: str, alvos: set[str]) -> str:
    if not alvos:
        return texto
    mantidas = []
    for linha in texto.split("\n"):
        despida = linha.strip()
        if despida in alvos:
            continue
        # Numero de pagina solto
        if despida.isdigit() and len(despida) <= 4:
            continue
        mantidas.append(linha)
    return "\n".join(mantidas)


def _detectar_secoes(texto: str) -> list[Secao]:
    """Localiza titulos de secao e delimita cada uma ate o titulo seguinte."""
    achados: list[tuple[int, str, str]] = []
    for nome, padrao in _PADROES_SECAO:
        # Titulo sozinho na linha, opcionalmente numerado ("3. Metodos", "III - Results")
        regex = re.compile(
            rf"^[ \t]*(?:\d{{1,2}}(?:\.\d{{1,2}})*[.)]?[ \t]*|[IVXivx]{{1,5}}[.)\-][ \t]*)?({padrao})[ \t]*:?[ \t]*$",
            re.IGNORECASE | re.MULTILINE,
        )
        for m in regex.finditer(texto):
            achados.append((m.start(), nome, m.group(1).strip()))

    if not achados:
        return []

    achados.sort(key=lambda item: item[0])
    # Mantem so a primeira ocorrencia de cada secao (evita duplicar por sumario)
    vistos: set[str] = set()
    unicos = []
    for inicio, nome, titulo in achados:
        if nome in vistos:
            continue
        vistos.add(nome)
        unicos.append((inicio, nome, titulo))

    secoes = []
    for i, (inicio, nome, titulo) in enumerate(unicos):
        fim = unicos[i + 1][0] if i + 1 < len(unicos) else len(texto)
        secoes.append(Secao(nome=nome, titulo=titulo, inicio=inicio, fim=fim))
    return secoes


def _contar_referencias(documento_texto: str, secoes: list[Secao]) -> int:
    bloco = ""
    for secao in secoes:
        if secao.nome == "referencias":
            bloco = documento_texto[secao.inicio : secao.fim]
            break
    if not bloco:
        return 0
    numeradas = sum(1 for linha in bloco.split("\n") if _RE_ENTRADA_REF.match(linha))
    if numeradas >= 3:
        return numeradas
    # Sem numeracao: estima por linhas que carregam um ano entre parenteses/virgulas
    return sum(1 for linha in bloco.split("\n") if len(linha.strip()) > 40 and _RE_ANO.search(linha))


def _metadados_pdf(reader: PdfReader) -> dict[str, str]:
    dados: dict[str, str] = {}
    info = getattr(reader, "metadata", None)
    if not info:
        return dados
    mapa = {
        "/Title": "titulo",
        "/Author": "autores",
        "/Subject": "assunto",
        "/Keywords": "keywords_pdf",
        "/Producer": "produtor",
        "/CreationDate": "criado_em",
    }
    for chave_pdf, chave in mapa.items():
        valor = info.get(chave_pdf)
        if valor:
            texto = str(valor).strip()
            if texto:
                dados[chave] = texto
    return dados


def _inferir_titulo(paginas: list[str]) -> str:
    """Heuristica: primeira linha longa e nao-toda-maiuscula da primeira pagina."""
    if not paginas:
        return ""
    for linha in paginas[0].split("\n")[:15]:
        despida = linha.strip()
        if 25 <= len(despida) <= 200 and not despida.lower().startswith(("doi", "http", "www")):
            return despida
    return ""


# Nome proprio em Title Case ("Fulana de Tal"), com conectores comuns em
# nomes de lingua portuguesa; linhas em CAIXA ALTA (titulos/cabecalhos) nao
# casam, pois exigem letras minusculas apos a inicial de cada palavra.
_CONECTOR = r"de|da|do|dos|das|e|El|Von|von|van|Jr\.?"
_PALAVRA_NOME = rf"[A-ZÀ-Ý][a-zà-ÿ'\-]+|{_CONECTOR}"
_RE_LINHA_AUTOR = re.compile(rf"^(?:{_PALAVRA_NOME})(?:\s+(?:{_PALAVRA_NOME})){{1,5}}[\s\d,\*†‡]{{0,10}}$")
_RE_RODAPE_NOME = re.compile(r"[\s\d,\*†‡]+$")


def _inferir_autores(paginas: list[str]) -> str:
    """Heuristica: bloco de linhas em Title Case perto do topo da pagina 1,
    tipico da assinatura de autoria (com marcadores de nota de rodape, ex.:
    "Fulana de Tal 1"). Serve para nao depender so do metadado /Author do
    PDF, que normalmente reflete quem editou o arquivo por ultimo no Word
    (ex.: dono de um template reaproveitado) e nao quem escreveu o texto.
    """
    if not paginas:
        return ""
    candidatos: list[str] = []
    for linha in paginas[0].split("\n")[:25]:
        despida = linha.strip()
        if not despida:
            if candidatos:
                break
            continue
        if 4 <= len(despida) <= 70 and _RE_LINHA_AUTOR.match(despida):
            nome = _RE_RODAPE_NOME.sub("", despida)
            if nome:
                candidatos.append(nome)
        elif candidatos:
            break
    return "; ".join(candidatos)


def extrair_documento(fonte: BinaryIO | bytes | str) -> Documento:
    """Le um PDF (caminho, bytes ou file-like) e devolve o `Documento` limpo."""
    if isinstance(fonte, bytes):
        fonte = io.BytesIO(fonte)
    reader = PdfReader(fonte)

    avisos: list[str] = []
    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception:  # pragma: no cover - depende do PDF
            avisos.append("PDF protegido por senha: a extracao pode vir incompleta.")

    brutas = []
    for indice, pagina in enumerate(reader.pages, start=1):
        try:
            brutas.append(pagina.extract_text() or "")
        except Exception as erro:  # pragma: no cover - PDFs malformados
            avisos.append(f"Falha ao ler a pagina {indice}: {erro}")
            brutas.append("")

    repetidos = _detectar_repetidos(brutas)
    limpas = [_normalizar_espacos(_remover_linhas(_juntar_hifenizacao(t), repetidos)) for t in brutas]

    paginas: list[Pagina] = []
    partes: list[str] = []
    cursor = 0
    for numero, texto in enumerate(limpas, start=1):
        bloco = texto + "\n\n"
        paginas.append(Pagina(numero=numero, texto=texto, inicio=cursor, fim=cursor + len(bloco)))
        partes.append(bloco)
        cursor += len(bloco)

    texto_completo = "".join(partes).strip()
    secoes = _detectar_secoes(texto_completo)

    metadados = _metadados_pdf(reader)
    if not metadados.get("titulo"):
        inferido = _inferir_titulo(limpas)
        if inferido:
            metadados["titulo"] = inferido
    autores_do_texto = _inferir_autores(limpas)
    if autores_do_texto:
        metadados["autores"] = autores_do_texto
    doi = _RE_DOI.search(texto_completo[:6000])
    if doi:
        metadados["doi"] = doi.group(0).rstrip(".")
    n_refs = _contar_referencias(texto_completo, secoes)
    if n_refs:
        metadados["referencias_estimadas"] = str(n_refs)

    if len(texto_completo) < 200:
        avisos.append(
            "Quase nenhum texto foi extraido. O PDF provavelmente e digitalizado "
            "(imagem) e precisaria de OCR para ser analisado."
        )

    return Documento(
        texto=texto_completo,
        paginas=paginas,
        metadados=metadados,
        secoes=secoes,
        avisos=avisos,
    )

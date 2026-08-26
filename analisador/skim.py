"""Skimming mecanico: a leitura rapida que nao depende do modelo.

Skimming e passar o olho pela estrutura para captar o essencial. As tecnicas
sao mecanicas e cabem em codigo: titulo e subtitulos, primeiro paragrafo de
cada secao, primeira e ultima frase dos demais paragrafos, frases com numero e
frases com marcador de conclusao.

A entrada e o `Documento` em Markdown produzido por `markdown.converter`: ali os
paragrafos ja vem remontados e separados por linha em branco, e os offsets de
pagina continuam validos. No texto cru do PDF nao ha fronteira confiavel de
paragrafo, porque a extracao entrega uma linha por linha impressa.

Nada neste modulo chama o Ollama: o resultado sai em milissegundos e continua
saindo com o modelo fora do ar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .keywords import normalizar

# Marcadores de conclusao, ja normalizados (minusculas, sem acento), como sai de
# `normalizar`. Comparar normalizado evita duplicar cada termo com e sem acento.
MARCADORES_CONCLUSAO: tuple[str, ...] = (
    "concluimos",
    "conclui-se",
    "concluiu-se",
    "em conclusao",
    "os resultados mostram",
    "os resultados indicam",
    "os achados sugerem",
    "este estudo mostra",
    "portanto",
    "em suma",
    "por fim",
    "we conclude",
    "in conclusion",
    "the results show",
    "these findings suggest",
    "taken together",
    "therefore",
    "in summary",
)

# Corta depois de . ! ? seguidos de espaco e de um inicio de frase plausivel.
# O lookahead exige maiuscula (acompanhada opcionalmente de aspas retas/curvas ou
# parentese/colchete), o que preserva "0.001)" e "p. 3".
_RE_CORTE_FRASE = re.compile(r"(?<=[.!?])\s+(?=[\"“'(\[]?[A-ZÀ-Ú])")

# Dado de verdade: decimal, percentual ou inteiro de 2+ digitos.
# Deixa de fora "p. 3", que e referencia de pagina e nao achado.
_RE_NUMERO = re.compile(r"\d+[.,]\d+|\d+\s*%|\b\d{2,}\b")

# Cabecalho Markdown de secao (## ou mais fundo). O `#` sozinho e o titulo do
# artigo, tratado a parte.
_RE_CABECALHO = re.compile(r"^(#{2,6})\s+(.+?)\s*$")

# Marcador de pagina que `markdown.converter` insere.
_RE_MARCADOR_PAGINA = re.compile(r"^<!--\s*p\.\s*\d+\s*-->$")

ABERTURA_SEM_SECAO = "Inicio do artigo"


@dataclass
class Frase:
    texto: str
    pagina: int
    secao: str | None = None


@dataclass
class SecaoSkim:
    titulo: str
    pagina: int
    abertura: str = ""
    esqueleto: list[str] = field(default_factory=list)


@dataclass
class Skim:
    titulo: str = ""
    secoes: list[SecaoSkim] = field(default_factory=list)
    numeros: list[Frase] = field(default_factory=list)
    conclusoes: list[Frase] = field(default_factory=list)

    @property
    def vazio(self) -> bool:
        return not (self.secoes or self.numeros or self.conclusoes)


def separar_frases(texto: str) -> list[str]:
    """Quebra um paragrafo em frases, sem cortar decimais nem "p. 3"."""
    limpo = " ".join(texto.split())
    if not limpo:
        return []
    return [parte.strip() for parte in _RE_CORTE_FRASE.split(limpo) if parte.strip()]


def paragrafos_com_offset(documento) -> list[tuple[int, str]]:
    """Blocos do Markdown com o offset onde cada um comeca no texto completo.

    Cabecalhos de secao entram na lista (quem chama decide o que fazer com
    eles); marcador de pagina e o titulo do artigo ficam de fora.
    """
    saida: list[tuple[int, str]] = []
    cursor = 0
    for bruto in documento.texto.split("\n\n"):
        bloco = bruto.strip()
        if bloco and not _RE_MARCADOR_PAGINA.match(bloco) and not bloco.startswith("# "):
            deslocamento = len(bruto) - len(bruto.lstrip())
            saida.append((cursor + deslocamento, bloco))
        cursor += len(bruto) + 2  # o separador "\n\n" tem 2 caracteres
    return saida


def tem_numero(frase: str) -> bool:
    return bool(_RE_NUMERO.search(frase))


def e_conclusiva(frase: str) -> bool:
    normalizada = normalizar(frase)
    return any(marcador in normalizada for marcador in MARCADORES_CONCLUSAO)


def resumir(documento, *, max_numeros: int = 12, max_conclusoes: int = 8) -> Skim:
    """Le a estrutura do artigo e devolve o essencial, sem modelo."""
    skim = Skim(titulo=(documento.metadados.get("titulo") or "").strip())
    atual: SecaoSkim | None = None

    for offset, bloco in paragrafos_com_offset(documento):
        pagina = documento.pagina_do_offset(offset)

        cabecalho = _RE_CABECALHO.match(bloco)
        if cabecalho:
            atual = SecaoSkim(titulo=cabecalho.group(2).strip(), pagina=pagina)
            skim.secoes.append(atual)
            continue

        frases = separar_frases(bloco)
        if not frases:
            continue

        if atual is None:
            # Texto antes de qualquer titulo (abstract solto, folha de rosto).
            atual = SecaoSkim(titulo=ABERTURA_SEM_SECAO, pagina=pagina)
            skim.secoes.append(atual)

        if not atual.abertura:
            atual.abertura = " ".join(frases)
        else:
            atual.esqueleto.append(frases[0])
            if len(frases) > 1:
                atual.esqueleto.append(frases[-1])

        for frase in frases:
            if len(skim.numeros) < max_numeros and tem_numero(frase):
                skim.numeros.append(Frase(texto=frase, pagina=pagina, secao=atual.titulo))
            if len(skim.conclusoes) < max_conclusoes and e_conclusiva(frase):
                skim.conclusoes.append(Frase(texto=frase, pagina=pagina, secao=atual.titulo))

    return skim

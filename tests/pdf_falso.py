"""Gera PDFs minimos e validos em memoria, para testar a extracao sem fixtures binarias."""

from __future__ import annotations


# As fontes padrao do PDF usam WinAnsiEncoding: alguns caracteres comuns em
# artigos existem la, mas fora do latin-1 puro.
_WINANSI = {
    "\u2022": "\x95",  # bullet
    "\u2013": "\x96",  # en dash
    "\u2014": "\x97",  # em dash
    "\u201c": "\x93",
    "\u201d": "\x94",
    "\u2018": "\x91",
    "\u2019": "\x92",
}


def _escapar(texto: str) -> str:
    for original, substituto in _WINANSI.items():
        texto = texto.replace(original, substituto)
    return texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _fluxo(linhas: list[str]) -> bytes:
    corpo = ["BT", "/F1 12 Tf", "14 TL", "50 780 Td"]
    for linha in linhas:
        corpo.append(f"({_escapar(linha)}) Tj")
        corpo.append("T*")
    corpo.append("ET")
    return "\n".join(corpo).encode("latin-1")


def montar_pdf(paginas: list[list[str]], titulo: str = "", autores: str = "") -> bytes:
    """`paginas` e uma lista de paginas, cada uma sendo uma lista de linhas."""
    objetos: list[bytes] = []

    def adicionar(conteudo: bytes) -> int:
        objetos.append(conteudo)
        return len(objetos)  # numero do objeto (1-indexado)

    fonte = adicionar(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )

    ids_paginas: list[int] = []
    pendentes: list[tuple[int, bytes]] = []
    for linhas in paginas:
        fluxo = _fluxo(linhas)
        conteudo = adicionar(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(fluxo), fluxo))
        numero = adicionar(b"")  # reservado: preenchido apos conhecer o id do /Pages
        ids_paginas.append(numero)
        pendentes.append((numero, conteudo))

    pai = adicionar(
        b"<< /Type /Pages /Kids [%s] /Count %d >>"
        % (b" ".join(b"%d 0 R" % i for i in ids_paginas), len(ids_paginas))
    )
    for numero, conteudo in pendentes:
        objetos[numero - 1] = (
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (pai, fonte, conteudo)
        )

    catalogo = adicionar(b"<< /Type /Catalog /Pages %d 0 R >>" % pai)
    campos = b""
    if titulo:
        campos += b"/Title (%s) " % _escapar(titulo).encode("latin-1")
    if autores:
        campos += b"/Author (%s) " % _escapar(autores).encode("latin-1")
    info = adicionar(b"<< %s>>" % campos) if campos else 0

    saida = bytearray(b"%PDF-1.4\n")
    deslocamentos: list[int] = []
    for numero, conteudo in enumerate(objetos, start=1):
        deslocamentos.append(len(saida))
        saida += b"%d 0 obj\n" % numero + conteudo + b"\nendobj\n"

    inicio_xref = len(saida)
    saida += b"xref\n0 %d\n" % (len(objetos) + 1)
    saida += b"0000000000 65535 f \n"
    for deslocamento in deslocamentos:
        saida += b"%010d 00000 n \n" % deslocamento
    trailer = b"<< /Size %d /Root %d 0 R" % (len(objetos) + 1, catalogo)
    if info:
        trailer += b" /Info %d 0 R" % info
    trailer += b" >>"
    saida += b"trailer\n" + trailer + b"\nstartxref\n%d\n%%%%EOF\n" % inicio_xref
    return bytes(saida)

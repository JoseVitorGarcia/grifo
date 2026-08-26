"""Divisao do artigo em blocos que caibam na janela de contexto do modelo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Bloco:
    indice: int
    texto: str
    inicio: int
    fim: int
    pagina_inicial: int
    pagina_final: int

    @property
    def rotulo(self) -> str:
        if self.pagina_inicial == self.pagina_final:
            return f"p. {self.pagina_inicial}"
        return f"p. {self.pagina_inicial}-{self.pagina_final}"


def dividir(documento, tamanho: int = 6000, sobreposicao: int = 400) -> list[Bloco]:
    """Corta o texto em blocos de ~`tamanho` caracteres, quebrando em paragrafos.

    A sobreposicao evita que uma ideia partida ao meio se perca entre dois blocos.
    """
    if tamanho <= 0:
        raise ValueError("tamanho deve ser positivo")
    sobreposicao = max(0, min(sobreposicao, tamanho // 2))

    texto = documento.texto
    blocos: list[Bloco] = []
    inicio = 0
    indice = 0
    while inicio < len(texto):
        fim = min(len(texto), inicio + tamanho)
        if fim < len(texto):
            # Prefere cortar no fim de um paragrafo, depois no fim de uma frase.
            corte = texto.rfind("\n\n", inicio + tamanho // 2, fim)
            if corte == -1:
                corte = texto.rfind(". ", inicio + tamanho // 2, fim)
                corte = corte + 1 if corte != -1 else -1
            if corte != -1:
                fim = corte
        pedaco = texto[inicio:fim].strip()
        if pedaco:
            blocos.append(
                Bloco(
                    indice=indice,
                    texto=pedaco,
                    inicio=inicio,
                    fim=fim,
                    pagina_inicial=documento.pagina_do_offset(inicio),
                    pagina_final=documento.pagina_do_offset(max(inicio, fim - 1)),
                )
            )
            indice += 1
        if fim >= len(texto):
            break
        inicio = max(fim - sobreposicao, inicio + 1)
    return blocos

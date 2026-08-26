"""Estado por sessao do navegador.

A aplicacao e local e de um usuario so, mas guardar o lote por sessao evita que
duas abas do navegador briguem pelo mesmo estado. Tudo vive em memoria: fechar
o servidor zera o lote (o mesmo vale ao recarregar sem o cookie).
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

from analisador.lote import LIMITE_PADRAO, Item

COOKIE = "analisador_sessao"


@dataclass
class Sessao:
    identificador: str
    itens: dict[str, Item] = field(default_factory=dict)
    conteudos: dict[str, bytes] = field(default_factory=dict)  # PDF original, para o grifo
    modelo_usado: str = ""
    limite: int = LIMITE_PADRAO

    def lista(self) -> list[Item]:
        return list(self.itens.values())

    def item(self, identificador: str) -> Item | None:
        return self.itens.get(identificador)

    def limpar(self) -> None:
        self.itens.clear()
        self.conteudos.clear()

    def remover(self, identificador: str) -> bool:
        self.conteudos.pop(identificador, None)
        return self.itens.pop(identificador, None) is not None


class Repositorio:
    """Guarda as sessoes ativas. Seguro para uso concorrente."""

    def __init__(self, limite: int = LIMITE_PADRAO) -> None:
        self._sessoes: dict[str, Sessao] = {}
        self._trava = threading.Lock()
        self._limite = limite

    def obter(self, identificador: str | None) -> Sessao:
        with self._trava:
            if identificador and identificador in self._sessoes:
                return self._sessoes[identificador]
            nova = Sessao(identificador=identificador or uuid.uuid4().hex, limite=self._limite)
            self._sessoes[nova.identificador] = nova
            return nova

    def descartar(self, identificador: str) -> None:
        with self._trava:
            self._sessoes.pop(identificador, None)

    @property
    def total(self) -> int:
        return len(self._sessoes)

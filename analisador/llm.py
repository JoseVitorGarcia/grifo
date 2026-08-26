"""Cliente HTTP do Ollama (API nativa, sem SDK extra)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

import requests


class ErroOllama(RuntimeError):
    """Falha de comunicacao ou de execucao no servidor Ollama."""


@dataclass
class ClienteOllama:
    url: str = "http://localhost:11434"
    modelo: str = "gemma3:4b"
    num_ctx: int = 8192
    temperatura: float = 0.2
    timeout_s: int = 600

    # --- diagnostico -----------------------------------------------------

    def disponivel(self) -> bool:
        try:
            resposta = requests.get(f"{self.url}/api/tags", timeout=5)
            return resposta.status_code == 200
        except requests.RequestException:
            return False

    def listar_modelos(self) -> list[str]:
        try:
            resposta = requests.get(f"{self.url}/api/tags", timeout=10)
            resposta.raise_for_status()
        except requests.RequestException as erro:
            raise ErroOllama(f"Nao consegui falar com o Ollama em {self.url}: {erro}") from erro
        dados = resposta.json().get("models", [])
        return sorted(m.get("name", "") for m in dados if m.get("name"))

    def modelo_instalado(self) -> bool:
        try:
            instalados = self.listar_modelos()
        except ErroOllama:
            return False
        # "gemma3:4b" tambem deve casar quando o Ollama devolve "gemma3:4b".
        alvo = self.modelo if ":" in self.modelo else f"{self.modelo}:latest"
        return alvo in instalados or self.modelo in instalados

    def diagnostico(self) -> tuple[bool, str]:
        """(ok, mensagem) — usado pela UI para explicar o que falta."""
        if not self.disponivel():
            return False, (
                f"Ollama nao responde em {self.url}. Suba o container com "
                "`docker compose up -d` e rode `./setup.sh`."
            )
        if not self.modelo_instalado():
            return False, (
                f"O modelo `{self.modelo}` nao esta baixado. Rode "
                f"`docker compose exec ollama ollama pull {self.modelo}`."
            )
        return True, f"Ollama ok em {self.url} — modelo `{self.modelo}` pronto."

    # --- geracao ---------------------------------------------------------

    def _payload(self, prompt: str, sistema: str | None, json_saida: bool) -> dict[str, Any]:
        mensagens = []
        if sistema:
            mensagens.append({"role": "system", "content": sistema})
        mensagens.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": self.modelo,
            "messages": mensagens,
            "options": {"temperature": self.temperatura, "num_ctx": self.num_ctx},
        }
        if json_saida:
            payload["format"] = "json"
        return payload

    def conversar(
        self,
        prompt: str,
        *,
        sistema: str | None = None,
        json_saida: bool = False,
        ao_receber: Callable[[str], None] | None = None,
    ) -> str:
        """Envia um prompt e devolve a resposta completa.

        Se `ao_receber` for passado, transmite os pedacos conforme chegam
        (usado para preencher a tela enquanto o modelo escreve).
        """
        payload = self._payload(prompt, sistema, json_saida)
        payload["stream"] = ao_receber is not None

        try:
            resposta = requests.post(
                f"{self.url}/api/chat",
                json=payload,
                timeout=self.timeout_s,
                stream=payload["stream"],
            )
            resposta.raise_for_status()
        except requests.Timeout as erro:
            raise ErroOllama(
                f"O modelo passou de {self.timeout_s}s sem responder. Em CPU, "
                "considere um modelo menor ou reduza o tamanho do bloco."
            ) from erro
        except requests.RequestException as erro:
            raise ErroOllama(f"Falha ao chamar o Ollama: {erro}") from erro

        if not payload["stream"]:
            return resposta.json().get("message", {}).get("content", "")

        partes: list[str] = []
        for linha in resposta.iter_lines(decode_unicode=True):
            if not linha:
                continue
            try:
                evento = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if evento.get("error"):
                raise ErroOllama(str(evento["error"]))
            pedaco = evento.get("message", {}).get("content", "")
            if pedaco:
                partes.append(pedaco)
                ao_receber(pedaco)
            if evento.get("done"):
                break
        return "".join(partes)

    def conversar_json(self, prompt: str, *, sistema: str | None = None) -> Any:
        """Como `conversar`, mas garante JSON valido de volta.

        O modo `format: json` do Ollama forca JSON sintatico, porem o modelo
        as vezes embrulha em cerca de codigo; por isso a limpeza abaixo.
        """
        bruto = self.conversar(prompt, sistema=sistema, json_saida=True)
        return interpretar_json(bruto)


def interpretar_json(bruto: str) -> Any:
    """Extrai o primeiro objeto/array JSON de uma resposta do modelo."""
    texto = (bruto or "").strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto.lower().startswith("json"):
            texto = texto[4:]
        texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    for abre, fecha in (("{", "}"), ("[", "]")):
        i, j = texto.find(abre), texto.rfind(fecha)
        if i != -1 and j > i:
            try:
                return json.loads(texto[i : j + 1])
            except json.JSONDecodeError:
                continue
    raise ErroOllama(f"O modelo nao devolveu JSON valido. Resposta crua: {bruto[:300]}")

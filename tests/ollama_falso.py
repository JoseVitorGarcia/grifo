"""Servidor Ollama falso, compartilhado pelos testes de integracao e de API.

Responde /api/tags e /api/chat com conteudo deterministico, inclusive em modo
streaming e em modo JSON, para exercitar o pipeline sem o modelo real.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class OllamaFalso(BaseHTTPRequestHandler):
    def log_message(self, *_):  # silencia o log do servidor de teste
        pass

    def _responder(self, dados: dict) -> None:
        corpo = json.dumps(dados).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path == "/api/tags":
            self._responder({"models": [{"name": "gemma3:4b"}]})
        else:
            self.send_error(404)

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        pedido = json.loads(self.rfile.read(tamanho) or b"{}")
        prompt = pedido["messages"][-1]["content"]
        conteudo = self._conteudo(pedido, prompt)

        if pedido.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            for pedaco in conteudo.split(" "):
                linha = json.dumps({"message": {"content": pedaco + " "}, "done": False})
                self.wfile.write(linha.encode() + b"\n")
            self.wfile.write(json.dumps({"message": {"content": ""}, "done": True}).encode() + b"\n")
            return
        self._responder({"message": {"content": conteudo}})

    @staticmethod
    def _conteudo(pedido: dict, prompt: str) -> str:
        if pedido.get("format") == "json":
            if "achados" in prompt:
                return json.dumps(
                    {"achados": [{"afirmacao": "A adesao subiu 18%", "evidencia": "240 pacientes", "pagina": "2"}]}
                )
            if "limitacoes" in prompt:
                return "```json\n" + json.dumps({"limitacoes": ["Amostra de um unico hospital"]}) + "\n```"
            if "keywords" in prompt:
                return json.dumps({"keywords": ["telemedicina", "adesao ao tratamento"]})
            return json.dumps(
                {
                    "objetivo": "Avaliar telemedicina",
                    "metodologia": "Ensaio randomizado com 240 pacientes",
                    "resultados": "Adesao 18% maior",
                    "conclusao": "Recomenda-se ampliar",
                    "relevancia": "Gestao de doencas cronicas",
                }
            )
        return "Resposta objetiva do modelo (p. 2)."


def subir() -> tuple[HTTPServer, str]:
    """Sobe o servidor numa porta livre e devolve (servidor, url)."""
    httpd = HTTPServer(("127.0.0.1", 0), OllamaFalso)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"

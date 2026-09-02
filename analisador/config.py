"""Configuracao central, toda parametrizavel por variavel de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(nome: str, padrao: str) -> str:
    valor = os.environ.get(nome, "").strip()
    return valor or padrao


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(_env(nome, str(padrao)))
    except ValueError:
        return padrao


def _env_float(nome: str, padrao: float) -> float:
    try:
        return float(_env(nome, str(padrao)))
    except ValueError:
        return padrao


@dataclass(frozen=True)
class Config:
    """Parametros de execucao. Instancie com `Config.do_ambiente()`."""

    ollama_url: str = "http://localhost:11434"
    modelo: str = "gemma3:4b"
    # Janela de contexto pedida ao Ollama. O padrao do servidor e 2048/4096,
    # baixo demais para artigos; 6144 cobre um bloco de 8000 chars com folga e
    # segura a RAM em CPU (KV cache menor).
    num_ctx: int = 6144
    temperatura: float = 0.2
    timeout_s: int = 600
    # Tamanho dos blocos de texto enviados ao modelo, em caracteres. Blocos
    # maiores = menos chamadas ao modelo (a etapa mais cara em CPU).
    tamanho_bloco: int = 8000
    sobreposicao_bloco: int = 400
    # Limite de blocos processados na etapa de map (protege contra PDFs enormes).
    max_blocos: int = 24

    @classmethod
    def do_ambiente(cls) -> "Config":
        return cls(
            ollama_url=_env("OLLAMA_URL", cls.ollama_url).rstrip("/"),
            modelo=_env("OLLAMA_MODELO", cls.modelo),
            num_ctx=_env_int("OLLAMA_NUM_CTX", cls.num_ctx),
            temperatura=_env_float("OLLAMA_TEMPERATURA", cls.temperatura),
            timeout_s=_env_int("OLLAMA_TIMEOUT", cls.timeout_s),
            tamanho_bloco=_env_int("ANALISADOR_TAMANHO_BLOCO", cls.tamanho_bloco),
            sobreposicao_bloco=_env_int("ANALISADOR_SOBREPOSICAO", cls.sobreposicao_bloco),
            max_blocos=_env_int("ANALISADOR_MAX_BLOCOS", cls.max_blocos),
        )

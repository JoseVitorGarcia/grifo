import pytest

from analisador.llm import ClienteOllama, ErroOllama, interpretar_json


def test_json_simples():
    assert interpretar_json('{"a": 1}') == {"a": 1}


def test_json_dentro_de_cerca_de_codigo():
    assert interpretar_json('```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}


def test_json_com_texto_antes_e_depois():
    bruto = 'Claro, aqui esta:\n{"limitacoes": ["amostra pequena"]}\nEspero ter ajudado.'
    assert interpretar_json(bruto) == {"limitacoes": ["amostra pequena"]}


def test_array_no_topo():
    assert interpretar_json('["a", "b"]') == ["a", "b"]


def test_resposta_sem_json_levanta_erro():
    with pytest.raises(ErroOllama):
        interpretar_json("nao consegui responder")


def test_diagnostico_quando_ollama_esta_fora(monkeypatch):
    cliente = ClienteOllama(url="http://localhost:9")
    monkeypatch.setattr(cliente, "disponivel", lambda: False)
    ok, mensagem = cliente.diagnostico()
    assert not ok and "docker compose up" in mensagem


def test_diagnostico_quando_falta_o_modelo(monkeypatch):
    cliente = ClienteOllama(modelo="gemma3:4b")
    monkeypatch.setattr(cliente, "disponivel", lambda: True)
    monkeypatch.setattr(cliente, "listar_modelos", lambda: ["llama3:8b"])
    ok, mensagem = cliente.diagnostico()
    assert not ok and "ollama pull gemma3:4b" in mensagem


def test_modelo_sem_tag_casa_com_latest(monkeypatch):
    cliente = ClienteOllama(modelo="gemma3")
    monkeypatch.setattr(cliente, "listar_modelos", lambda: ["gemma3:latest"])
    assert cliente.modelo_instalado()


# O streaming token a token nao tem consumidor na aplicacao hoje (a pergunta
# livre foi retirada), mas segue no cliente para exibir texto sendo escrito.
# Estes testes o mantem coberto.

@pytest.fixture(scope="module")
def servidor():
    from ollama_falso import subir

    httpd, url = subir()
    yield url
    httpd.shutdown()


def test_resposta_completa_sem_streaming(servidor):
    cliente = ClienteOllama(url=servidor, modelo="gemma3:4b", timeout_s=15)
    assert "Resposta objetiva" in cliente.conversar("qual a amostra?")


def test_streaming_entrega_o_texto_em_pedacos(servidor):
    cliente = ClienteOllama(url=servidor, modelo="gemma3:4b", timeout_s=15)
    pedacos: list[str] = []
    resposta = cliente.conversar("qual a amostra?", ao_receber=pedacos.append)
    assert len(pedacos) > 1
    assert "".join(pedacos) == resposta
    assert "Resposta objetiva" in resposta


def test_modo_json_devolve_estrutura(servidor):
    cliente = ClienteOllama(url=servidor, modelo="gemma3:4b", timeout_s=15)
    dados = cliente.conversar_json("liste as limitacoes")
    assert dados == {"limitacoes": ["Amostra de um unico hospital"]}

# Skimming e Scanning — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar as três camadas de leitura do produto — Scan e Skim determinísticos e instantâneos, Leitura profunda pelo modelo — de modo que a aplicação seja útil em milissegundos e continue funcionando com o Ollama fora do ar.

**Architecture:** Um módulo novo e puro (`analisador/skim.py`) produz a leitura mecânica a partir do `Documento` em Markdown que `markdown.converter` já gera — ali os parágrafos vêm remontados, separados por linha em branco, com offsets de página válidos. Duas rotas GET novas (`/scan` e `/skim`) expõem o que hoje só sai por `POST /api/analise`, sem tocar no Ollama. O front passa a chamá-las no envio do PDF e renomeia as abas por intenção de leitura.

**Tech Stack:** Python 3.10+, FastAPI, pytest (sem novas dependências); front em HTML/CSS/JS puros, sem build.

**Spec:** `docs/spec-skimming-scanning.md`

## Global Constraints

Copiados de `docs/spec-skimming-scanning.md` §5. Valem para **todas** as tarefas:

- **Sem novas dependências.** Nada é adicionado a `requirements.txt` nem a `requirements-dev.txt`.
- **O núcleo não conhece HTTP.** Código em `analisador/` não importa `fastapi`, `servidor.*` nem faz I/O de rede.
- **Nenhuma chamada ao Ollama** em Scan ou Skim — nem opcional, nem com fallback.
- **Front sem framework e sem build**: só `web/index.html`, `web/estilo.css`, `web/app.js`, com APIs nativas.
- **Testes offline**, sem rede e sem navegador.
- **Código e nomes em português**, sem acento em identificadores (`buscar_varias`, `Ocorrencia`), seguindo a convenção do projeto. **Textos de UI com acentuação**, como já está em `web/index.html`.
- **Toda passagem exibida carrega o número da página.**
- Comando de teste: `./.venv/bin/python -m pytest` (ou `make test`). O `pytest.ini` já usa `testpaths = tests` e `addopts = -q`.
- Baseline: **135 testes passando** antes da Task 1.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade | Tarefa |
|---|---|---|
| `analisador/skim.py` | **Criar.** Skimming mecânico puro: frases, parágrafos, seções, números, conclusões. | 1 |
| `tests/test_skim.py` | **Criar.** Testes do módulo acima. | 1 |
| `servidor/esquemas.py` | **Modificar.** Extrair `resultado_para_dict`; adicionar `skim_para_dict`. | 2, 3 |
| `servidor/api.py` | **Modificar.** Duas rotas GET novas. | 2, 3 |
| `tests/test_api.py` | **Modificar.** Testes das rotas novas, inclusive com Ollama fora do ar. | 2, 3 |
| `web/app.js` | **Modificar.** `desenharScan`, `desenharSkim`, disparo no upload, fusão da visão geral. | 4, 5, 6 |
| `web/index.html` | **Modificar.** Abas renomeadas, painéis novos, nota do método. | 4, 5, 6 |
| `web/estilo.css` | **Modificar.** Estilos do skim e da nota do método. | 5, 6 |
| `README.md`, `docs/design-brief.md`, `docs/proximos-passos.md` | **Modificar.** Alinhar a documentação ao código. | 7 |

**Por que `skim.py` recebe o Markdown e não o texto cru:** `pdf._normalizar_espacos` colapsa `\n{3,}` em `\n\n`, mas a extração do PDF entrega uma linha por linha impressa — no texto cru não há fronteira confiável de parágrafo. Já `markdown._fechar_paragrafo` remonta os parágrafos e `markdown.converter` os emite separados por `\n\n`, preservando os offsets de página. É a fonte certa.

---

### Task 0: Colocar o projeto sob controle de versão

O diretório **não é um repositório git** hoje. As tarefas seguintes assumem commits por tarefa e revisão por diff. Se você preferir não versionar, pule esta tarefa e ignore os passos "Commit" das demais.

**Files:**
- Create: `.gitignore` já existe — apenas conferir

- [ ] **Step 1: Conferir o que será ignorado**

Run: `cat .gitignore`
Esperado: contém `.venv` e `__pycache__`. Se `.pytest_cache` não estiver lá, acrescente:

```bash
grep -q '.pytest_cache' .gitignore || echo '.pytest_cache/' >> .gitignore
```

- [ ] **Step 2: Inicializar e commitar o estado atual**

```bash
git init
git add -A
git status --short | head -30
```
Esperado: nenhum arquivo dentro de `.venv/` na lista. Se aparecer, corrija o `.gitignore` e refaça `git add -A`.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: versionar o estado atual do analisador"
```

---

### Task 1: Módulo de skimming mecânico

**Files:**
- Create: `analisador/skim.py`
- Test: `tests/test_skim.py`

**Interfaces:**
- Consumes: `analisador.pdf.Documento` (campos `texto`, `paginas`, `secoes`, `metadados`; método `pagina_do_offset(offset) -> int`); `analisador.keywords.normalizar(texto) -> str`.
- Produces:
  - `MARCADORES_CONCLUSAO: tuple[str, ...]`
  - `separar_frases(texto: str) -> list[str]`
  - `paragrafos_com_offset(documento) -> list[tuple[int, str]]`
  - `tem_numero(frase: str) -> bool`
  - `e_conclusiva(frase: str) -> bool`
  - `resumir(documento, *, max_numeros: int = 12, max_conclusoes: int = 8) -> Skim`
  - `@dataclass Frase(texto: str, pagina: int, secao: str | None = None)`
  - `@dataclass SecaoSkim(titulo: str, pagina: int, abertura: str = "", esqueleto: list[str] = [])`
  - `@dataclass Skim(titulo: str = "", secoes: list[SecaoSkim] = [], numeros: list[Frase] = [], conclusoes: list[Frase] = [])` com `@property vazio -> bool`

- [ ] **Step 1: Escrever os testes que falham**

Crie `tests/test_skim.py`:

```python
"""Testes do skimming mecanico: nada aqui toca o Ollama."""

from __future__ import annotations

from analisador.markdown import converter
from analisador.pdf import Documento, Pagina
from analisador.skim import (
    e_conclusiva,
    paragrafos_com_offset,
    resumir,
    separar_frases,
    tem_numero,
)


def documento_de(paginas: list[str], titulo: str = "") -> Documento:
    """Monta um Documento cru com offsets de pagina corretos, como o pdf.py faz."""
    objetos, partes, cursor = [], [], 0
    for numero, texto in enumerate(paginas, start=1):
        bloco = texto + "\n\n"
        objetos.append(Pagina(numero, texto, cursor, cursor + len(bloco)))
        partes.append(bloco)
        cursor += len(bloco)
    return Documento(
        texto="".join(partes).strip(),
        paginas=objetos,
        metadados={"titulo": titulo} if titulo else {},
    )


ARTIGO = [
    "\n".join([
        "Telemedicina e adesao ao tratamento",
        "Abstract",
        "Este estudo avaliou a telemedicina em pacientes cronicos.",
        "A adesao foi o desfecho primario.",
        "",
        "Introduction",
        "A adesao ao tratamento e um problema antigo.",
        "",
        "Varios trabalhos ja mediram o efeito de lembretes.",
        "Portanto, faltava um ensaio randomizado de porte.",
    ]),
    "\n".join([
        "Methods",
        "Ensaio clinico randomizado com 240 pacientes acompanhados por 12 meses.",
        "A alocacao foi feita por sorteio central.",
        "",
        "Results",
        "A adesao subiu 18 pontos percentuais no grupo telemedicina.",
        "Os resultados mostram beneficio consistente entre subgrupos.",
    ]),
]


# --- separacao de frases ---------------------------------------------------

def test_separa_frases_por_pontuacao():
    frases = separar_frases("O estudo foi randomizado. A amostra tinha 240 pacientes.")
    assert frases == [
        "O estudo foi randomizado.",
        "A amostra tinha 240 pacientes.",
    ]


def test_nao_quebra_frase_em_numero_decimal():
    frases = separar_frases("A diferenca foi significativa (p < 0.001) no grupo tratado.")
    assert len(frases) == 1


def test_frase_unica_sem_ponto_final_e_preservada():
    assert separar_frases("Methods") == ["Methods"]


def test_corta_frase_antes_de_aspas_curvas():
    # A classe do lookahead inclui a aspas curva; sem ela, falas citadas em
    # artigos com tipografia real deixariam de abrir frase nova.
    frases = separar_frases('Ele concluiu o argumento. “Vamos adiante”, escreveu.')
    assert len(frases) == 2
    assert frases[1].startswith("“Vamos adiante")


def test_texto_vazio_nao_gera_frase():
    assert separar_frases("   \n  ") == []


# --- deteccao de numeros e de conclusao ------------------------------------

def test_reconhece_frase_com_percentual():
    assert tem_numero("A adesao subiu 18% no grupo telemedicina.") is True


def test_reconhece_frase_com_decimal():
    assert tem_numero("O valor de p foi 0,001 no desfecho primario.") is True


def test_numero_de_pagina_solto_nao_conta_como_dado():
    assert tem_numero("Ver p. 3 para o fluxograma.") is False


def test_reconhece_marcador_de_conclusao_com_acento():
    assert e_conclusiva("Concluímos que a intervenção é viável.") is True


def test_reconhece_marcador_de_conclusao_em_ingles():
    assert e_conclusiva("The results show a consistent benefit.") is True


def test_frase_comum_nao_e_conclusiva():
    assert e_conclusiva("A alocacao foi feita por sorteio central.") is False


# --- paragrafos ------------------------------------------------------------

def test_paragrafos_ignoram_marcador_de_pagina_e_titulo_do_artigo():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    blocos = [texto for _, texto in paragrafos_com_offset(markdown)]
    assert not any(bloco.startswith("<!--") for bloco in blocos)
    assert not any(bloco.startswith("# ") for bloco in blocos)


def test_offset_do_paragrafo_aponta_para_a_pagina_certa():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    for offset, texto in paragrafos_com_offset(markdown):
        if "240 pacientes" in texto:
            assert markdown.pagina_do_offset(offset) == 2
            return
    raise AssertionError("paragrafo de metodos nao encontrado")


# --- resumir ---------------------------------------------------------------

def test_resumir_usa_o_titulo_dos_metadados():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    assert resumir(markdown).titulo == "Telemedicina e adesao"


def test_resumir_lista_as_secoes_detectadas():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    titulos = [s.titulo for s in resumir(markdown).secoes]
    assert "Abstract" in titulos
    assert "Methods" in titulos
    assert "Results" in titulos


def test_primeiro_paragrafo_da_secao_vira_abertura():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    metodos = next(s for s in resumir(markdown).secoes if s.titulo == "Methods")
    assert "240 pacientes" in metodos.abertura


def test_esqueleto_guarda_primeira_e_ultima_frase_dos_demais_paragrafos():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    intro = next(s for s in resumir(markdown).secoes if s.titulo == "Introduction")
    # 1o paragrafo vira abertura; o 2o entra no esqueleto pela 1a e pela ultima frase.
    assert "problema antigo" in intro.abertura
    assert intro.esqueleto[0].startswith("Varios trabalhos")
    assert intro.esqueleto[-1].startswith("Portanto")


def test_secao_registra_a_pagina_em_que_comeca():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    metodos = next(s for s in resumir(markdown).secoes if s.titulo == "Methods")
    assert metodos.pagina == 2


def test_frases_com_numero_carregam_pagina():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    numeros = resumir(markdown).numeros
    assert numeros, "nenhuma frase com numero foi capturada"
    assert all(f.pagina >= 1 for f in numeros)
    assert any("240" in f.texto for f in numeros)


def test_frases_conclusivas_sao_capturadas_com_pagina():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    conclusoes = resumir(markdown).conclusoes
    assert any("resultados mostram" in f.texto.lower() for f in conclusoes)
    assert all(f.pagina >= 1 for f in conclusoes)


def test_limites_de_quantidade_sao_respeitados():
    markdown = converter(documento_de(ARTIGO, titulo="Telemedicina e adesao"))
    skim = resumir(markdown, max_numeros=1, max_conclusoes=1)
    assert len(skim.numeros) == 1
    assert len(skim.conclusoes) == 1


def test_texto_antes_da_primeira_secao_nao_e_perdido():
    documento = documento_de(["Um paragrafo solto com 42 casos e nenhum titulo de secao."])
    skim = resumir(converter(documento))
    assert skim.secoes, "o texto antes da primeira secao deve virar uma secao"
    assert any("42 casos" in f.texto for f in skim.numeros)


def test_documento_vazio_devolve_skim_vazio():
    skim = resumir(converter(documento_de([""])))
    assert skim.vazio is True
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `./.venv/bin/python -m pytest tests/test_skim.py -q`
Esperado: FAIL — `ModuleNotFoundError: No module named 'analisador.skim'`

- [ ] **Step 3: Escrever a implementação mínima**

Crie `analisador/skim.py`:

```python
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
# O lookahead exige maiuscula (opcionalmente precedida de aspas ou parentese),
# o que preserva "0.001)" e "p. 3" sem quebrar.
_RE_CORTE_FRASE = re.compile(r"(?<=[.!?])\s+(?=[\"'“(\[]?[A-ZÀ-Ú])")

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
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

Run: `./.venv/bin/python -m pytest tests/test_skim.py -q`
Esperado: PASS, 23 testes.

Se `test_secao_registra_a_pagina_em_que_comeca` falhar por página errada, confira `paragrafos_com_offset`: o cursor precisa avançar `len(bruto) + 2`, com `bruto` **não** despido, senão os offsets desandam a partir do primeiro bloco com espaço à esquerda.

- [ ] **Step 5: Rodar a suíte inteira**

Run: `./.venv/bin/python -m pytest -q`
Esperado: PASS, 158 testes (135 + 23). Nenhum teste existente pode quebrar — este módulo não é importado por ninguém ainda.

- [ ] **Step 6: Commit**

```bash
git add analisador/skim.py tests/test_skim.py
git commit -m "feat: skimming mecanico sem modelo"
```

---

### Task 2: Rota de Scan determinístico

Desacopla a busca literal de keywords do `POST /api/analise`. É a tarefa de maior impacto do plano: torna a "tela mais importante do produto" instantânea e faz a aplicação funcionar com o Ollama fora do ar.

**Files:**
- Modify: `servidor/esquemas.py` (extrair `resultado_para_dict` de `analise_para_dict`)
- Modify: `servidor/api.py` (rota nova, após a rota `pagina`, por volta da linha 270)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `analisador.keywords.buscar_varias(documento, keywords, **kwargs) -> list[ResultadoKeyword]`, `analisador.keywords.separar_keywords(entrada: str) -> list[str]`; `servidor.api.sessao_do`, `servidor.api.com_cookie`.
- Produces:
  - `servidor.esquemas.resultado_para_dict(resultado, sintese: str = "") -> dict` com as chaves `keyword`, `sintese`, `total`, `paginas`, `densidade_por_mil`, `encontrada`, `ocorrencias` (lista de `{pagina, secao, trecho, termo}`) — exatamente o formato que o front já consome hoje.
  - Rota `GET /api/itens/{identificador}/scan?keywords=a,b&flexivel=true` devolvendo `{"id": str, "keywords": [<resultado_para_dict>...]}`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `tests/test_api.py`:

```python
# --- scan deterministico ---------------------------------------------------

def test_scan_responde_sem_analise_previa(cliente):
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    dados = cliente.get(f"/api/itens/{id_a}/scan?keywords=telemedicina,adesao").json()
    assert [k["keyword"] for k in dados["keywords"]] == ["telemedicina", "adesao"]
    assert dados["keywords"][0]["total"] >= 1
    assert dados["keywords"][0]["encontrada"] is True
    assert dados["keywords"][0]["ocorrencias"][0]["pagina"] >= 1


def test_scan_marca_keyword_ausente(cliente):
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    dados = cliente.get(f"/api/itens/{id_a}/scan?keywords=quimioterapia").json()
    ausente = dados["keywords"][0]
    assert ausente["total"] == 0
    assert ausente["encontrada"] is False
    assert ausente["ocorrencias"] == []


def test_scan_funciona_com_ollama_fora_do_ar(cliente, monkeypatch):
    # A promessa central: scanning nao depende do modelo. Aponta a config para
    # uma porta morta e confirma que a rota continua respondendo.
    monkeypatch.setattr(
        modulo_api, "CONFIG",
        dataclasses.replace(Config.do_ambiente(), ollama_url="http://127.0.0.1:9"),
    )
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    resposta = cliente.get(f"/api/itens/{id_a}/scan?keywords=telemedicina")
    assert resposta.status_code == 200
    assert resposta.json()["keywords"][0]["total"] >= 1


def test_scan_sem_keywords_devolve_lista_vazia(cliente):
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    assert cliente.get(f"/api/itens/{id_a}/scan?keywords=").json()["keywords"] == []


def test_scan_de_artigo_inexistente_da_404(cliente):
    assert cliente.get("/api/itens/naoexiste/scan?keywords=a").status_code == 404
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `./.venv/bin/python -m pytest tests/test_api.py -q -k scan`
Esperado: FAIL — todos com `assert 404 == 200` (a rota não existe), menos o último, que passa por acidente.

- [ ] **Step 3: Extrair o serializador em `servidor/esquemas.py`**

Substitua a lista `"keywords"` dentro de `analise_para_dict` por uma chamada à função nova. O arquivo passa a ter, antes de `analise_para_dict`:

```python
def resultado_para_dict(resultado, sintese: str = "") -> dict:
    """Serializa um `ResultadoKeyword`. `sintese` fica vazia no scan puro."""
    return {
        "keyword": resultado.keyword,
        "sintese": sintese,
        "total": resultado.total,
        "paginas": resultado.paginas,
        "densidade_por_mil": resultado.densidade_por_mil,
        "encontrada": resultado.encontrada,
        "ocorrencias": [
            {
                "pagina": o.pagina,
                "secao": o.secao,
                "trecho": o.trecho,
                "termo": o.termo_encontrado,
            }
            for o in resultado.ocorrencias
        ],
    }
```

E dentro de `analise_para_dict`, troque o bloco `"keywords": [ ... ]` inteiro por:

```python
        "keywords": [resultado_para_dict(s.resultado, s.resumo) for s in analise.sinteses],
```

- [ ] **Step 4: Escrever a rota em `servidor/api.py`**

No bloco de imports, troque a linha 51 para incluir o serializador novo:

```python
from servidor.esquemas import item_para_dict, lote_para_dict, resultado_para_dict
```

Logo depois da rota `pagina` (que termina por volta da linha 269) e antes de `@app.get("/api/comparacao")`, acrescente:

```python
@app.get("/api/itens/{identificador}/scan")
def scan(
    requisicao: Request,
    identificador: str,
    keywords: str = "",
    flexivel: bool = True,
) -> Response:
    """Busca literal das keywords, sem passar pelo modelo.

    Scanning e deterministico e sai em milissegundos: esta rota existe para que
    a tela nao precise esperar a leitura profunda — nem o Ollama estar no ar.
    """
    sessao = sessao_do(requisicao)
    item = sessao.item(identificador)
    if not item:
        return JSONResponse({"erro": "artigo nao encontrado nesta sessao"}, status_code=404)

    resultados = buscar_varias(item.documento, separar_keywords(keywords), flexivel=flexivel)
    corpo = {"id": identificador, "keywords": [resultado_para_dict(r) for r in resultados]}
    return com_cookie(JSONResponse(corpo), sessao)
```

- [ ] **Step 5: Rodar os testes para confirmar que passam**

Run: `./.venv/bin/python -m pytest tests/test_api.py -q -k scan`
Esperado: PASS, 5 testes.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `./.venv/bin/python -m pytest -q`
Esperado: PASS, 163 testes. Atenção especial aos testes existentes de `POST /api/analise` — a refatoração de `esquemas.py` mudou o caminho do código, mas o JSON tem de sair idêntico. Se algum quebrar, o formato divergiu: compare campo a campo com o bloco original.

- [ ] **Step 7: Commit**

```bash
git add servidor/api.py servidor/esquemas.py tests/test_api.py
git commit -m "feat: rota de scan deterministico, sem depender do Ollama"
```

---

### Task 3: Rota de Skim

**Files:**
- Modify: `servidor/esquemas.py` (adicionar `skim_para_dict`)
- Modify: `servidor/api.py` (rota nova, logo após a rota `scan`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `analisador.skim.resumir(documento, *, max_numeros, max_conclusoes) -> Skim` (Task 1); `Item.para_o_modelo` (o `Documento` em Markdown quando disponível).
- Produces:
  - `servidor.esquemas.skim_para_dict(skim) -> dict` com `{titulo, secoes: [{titulo, pagina, abertura, esqueleto}], numeros: [{texto, pagina, secao}], conclusoes: [...], vazio: bool}`
  - Rota `GET /api/itens/{identificador}/skim` devolvendo `{"id": str, "skim": <skim_para_dict>}`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `tests/test_api.py`:

```python
# --- skim mecanico ---------------------------------------------------------

def test_skim_responde_sem_analise_previa(cliente):
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    skim = cliente.get(f"/api/itens/{id_a}/skim").json()["skim"]
    assert skim["vazio"] is False
    titulos = [s["titulo"] for s in skim["secoes"]]
    assert "Methods" in titulos or "Abstract" in titulos


def test_skim_traz_paginas_em_todas_as_frases(cliente):
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    skim = cliente.get(f"/api/itens/{id_a}/skim").json()["skim"]
    for lista in (skim["numeros"], skim["conclusoes"]):
        assert all(item["pagina"] >= 1 for item in lista)


def test_skim_captura_o_numero_do_artigo(cliente):
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    skim = cliente.get(f"/api/itens/{id_a}/skim").json()["skim"]
    assert any("240" in f["texto"] for f in skim["numeros"])


def test_skim_funciona_com_ollama_fora_do_ar(cliente, monkeypatch):
    monkeypatch.setattr(
        modulo_api, "CONFIG",
        dataclasses.replace(Config.do_ambiente(), ollama_url="http://127.0.0.1:9"),
    )
    id_a = enviar(cliente, [("a.pdf", ARTIGO_A)]).json()["itens"][0]["id"]
    assert cliente.get(f"/api/itens/{id_a}/skim").status_code == 200


def test_skim_de_artigo_inexistente_da_404(cliente):
    assert cliente.get("/api/itens/naoexiste/skim").status_code == 404
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `./.venv/bin/python -m pytest tests/test_api.py -q -k skim`
Esperado: FAIL — `KeyError: 'skim'` / `assert 404 == 200`.

- [ ] **Step 3: Escrever o serializador em `servidor/esquemas.py`**

No topo do arquivo, junto dos outros imports do núcleo:

```python
from analisador.skim import Skim
```

E ao fim do arquivo:

```python
def skim_para_dict(skim: Skim) -> dict:
    """Serializa a leitura rapida mecanica. Toda frase carrega a pagina."""
    def frase(f) -> dict:
        return {"texto": f.texto, "pagina": f.pagina, "secao": f.secao}

    return {
        "titulo": skim.titulo,
        "vazio": skim.vazio,
        "secoes": [
            {
                "titulo": s.titulo,
                "pagina": s.pagina,
                "abertura": s.abertura,
                "esqueleto": s.esqueleto,
            }
            for s in skim.secoes
        ],
        "numeros": [frase(f) for f in skim.numeros],
        "conclusoes": [frase(f) for f in skim.conclusoes],
    }
```

- [ ] **Step 4: Escrever a rota em `servidor/api.py`**

Nos imports do núcleo, depois da linha `from analisador.pdf import extrair_documento`:

```python
from analisador.skim import resumir as resumir_skim
```

E troque o import de `servidor.esquemas` para:

```python
from servidor.esquemas import item_para_dict, lote_para_dict, resultado_para_dict, skim_para_dict
```

Logo depois da rota `scan`, acrescente:

```python
@app.get("/api/itens/{identificador}/skim")
def skim(requisicao: Request, identificador: str) -> Response:
    """Leitura rapida mecanica: estrutura, aberturas, numeros e conclusoes.

    Le a versao em Markdown, onde os paragrafos ja vem remontados. Como o scan,
    nao toca no modelo.
    """
    sessao = sessao_do(requisicao)
    item = sessao.item(identificador)
    if not item:
        return JSONResponse({"erro": "artigo nao encontrado nesta sessao"}, status_code=404)

    corpo = {"id": identificador, "skim": skim_para_dict(resumir_skim(item.para_o_modelo))}
    return com_cookie(JSONResponse(corpo), sessao)
```

- [ ] **Step 5: Rodar os testes para confirmar que passam**

Run: `./.venv/bin/python -m pytest tests/test_api.py -q -k skim`
Esperado: PASS, 5 testes.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `./.venv/bin/python -m pytest -q`
Esperado: PASS, 168 testes.

- [ ] **Step 7: Commit**

```bash
git add servidor/api.py servidor/esquemas.py tests/test_api.py
git commit -m "feat: rota de skim mecanico"
```

---

### Task 4: Aba Scan instantânea no front

**Files:**
- Modify: `web/index.html` (abas e painéis, linhas 98-112)
- Modify: `web/app.js` (estado, `desenharScan`, disparo no upload e ao editar keywords)

**Interfaces:**
- Consumes: `GET /api/itens/{id}/scan?keywords=...&flexivel=...` (Task 2); helpers já existentes em `web/app.js`: `api`, `elemento`, `$`, `$$`, `numero`, `comDestaque`.
- Produces: `estado.scan` (`{[id]: {keywords: [...]}}`), `carregarScan(id)`, `desenharScan()`.

- [ ] **Step 1: Trocar a aba "Keywords" por "Scan" em `web/index.html`**

Na linha 101, troque:

```html
        <button role="tab" data-aba="keywords">Keywords</button>
```

por:

```html
        <button role="tab" data-aba="scan">Scan · achar termos</button>
```

E na linha 109, troque:

```html
      <div class="painel" id="painel-keywords"></div>
```

por:

```html
      <div class="painel" id="painel-scan"></div>
```

- [ ] **Step 2: Guardar o scan no estado, em `web/app.js`**

No objeto `estado` (linha 8), acrescente uma linha depois de `detalhes`:

```javascript
  scan: {},           // id -> {keywords: [...]} vindo de /scan, sem LLM
```

- [ ] **Step 3: Renomear `desenharKeywords` para `desenharScan` e ler a fonte certa**

A função `desenharKeywords` (linha 403) passa a se chamar `desenharScan`, a escrever em `#painel-scan` e a preferir o scan determinístico, caindo para a análise só pela síntese. Troque o cabeçalho e as seis primeiras linhas da função por:

```javascript
function desenharScan(dado) {
  const alvo = $('#painel-scan');
  // O scan deterministico chega em milissegundos; a sintese do modelo, minutos
  // depois. Casamos os dois por keyword para nao esperar um pelo outro.
  const sinteses = {};
  (dado.analise?.keywords || []).forEach((k) => { sinteses[k.keyword] = k.sintese; });
  const keywords = (estado.scan[dado.id]?.keywords || dado.analise?.keywords || [])
    .map((k) => ({ ...k, sintese: sinteses[k.keyword] || k.sintese || '' }));

  if (!keywords.length) {
    alvo.replaceChildren(elemento('p', {
      class: 'sutil',
      texto: 'Informe as keywords no campo acima para varrer o artigo. O scan é instantâneo e não usa o modelo.',
    }));
    return;
  }
```

Dentro do laço `keywords.forEach((k) => {` (linha 446), a linha que monta a síntese passa a esconder o parágrafo quando ela ainda não existe. Troque:

```javascript
      elemento('p', { texto: k.sintese }),
```

por:

```javascript
      k.sintese
        ? elemento('p', { texto: k.sintese })
        : elemento('p', { class: 'sutil', texto: 'Síntese do modelo ainda não gerada — rode a leitura profunda.' }),
```

- [ ] **Step 4: Trocar a chamada em `desenharArtigo`**

Na função `desenharArtigo` (linha 297), troque `desenharKeywords(dado);` por `desenharScan(dado);`.

- [ ] **Step 5: Trocar o `data-aba` no tratador de abas**

No tratador de cliques das abas (por volta da linha 639) não há referência a `keywords`, então nada muda ali. Confirme com:

Run: `grep -n "keywords" web/app.js`
Esperado: nenhuma linha referindo `painel-keywords` ou `desenharKeywords`.

- [ ] **Step 6: Buscar o scan no envio e ao editar as keywords**

Acrescente, logo depois da função `abrirArtigo` (que termina por volta da linha 291):

```javascript
/** Varre o artigo pelas keywords atuais. Nao usa o modelo: pode rodar sempre. */
async function carregarScan(id) {
  const termos = $('#keywords').value.trim();
  const flexivel = $('#flexivel').checked;
  try {
    estado.scan[id] = await api(
      `/api/itens/${id}/scan?keywords=${encodeURIComponent(termos)}&flexivel=${flexivel}`,
    );
  } catch (_) {
    delete estado.scan[id];  // sem scan a tela cai para o que a analise tiver
  }
}
```

Em `abrirArtigo`, antes de `desenharArtigo()`, acrescente a busca:

```javascript
  await carregarScan(id);
```

E no tratador de `input` do campo de keywords (linha 622), depois de redesenhar as etiquetas, acrescente um disparo com atraso — sem isso o scan roda a cada tecla:

```javascript
  let agendado = null;
  $('#keywords').addEventListener('input', (e) => {
    const termos = e.target.value.split(/[,;\n]+/).map((t) => t.trim()).filter(Boolean);
    $('#etiquetas-keywords').replaceChildren(...termos.map((t) =>
      elemento('span', { class: 'etiqueta', texto: t })));
    clearTimeout(agendado);
    agendado = setTimeout(async () => {
      if (!estado.atual) return;
      await carregarScan(estado.atual);
      desenharArtigo();
    }, 400);
  });
```

(Substitua o tratador inteiro que já existe; a declaração `let agendado = null;` vai imediatamente antes dele.)

- [ ] **Step 7: Verificar no navegador**

```bash
docker compose up -d ollama && ./iniciar.sh --reload
```

Abra `http://localhost:8000`, envie `exemplos/artigo_exemplo.pdf`, digite `telemedicina, adesao, quimioterapia` e abra a aba **Scan · achar termos** — **sem clicar em Analisar**. Esperado: tabela com contagens, gráfico por página e os trechos com o termo em destaque, tudo em menos de um segundo. `quimioterapia` aparece com 0 ocorrências e o marcador `⚠️`.

Depois, derrube o Ollama (`docker compose stop ollama`), recarregue e repita: o Scan deve continuar funcionando por inteiro.

- [ ] **Step 8: Rodar a suíte**

Run: `./.venv/bin/python -m pytest -q`
Esperado: PASS, 168 testes. Um teste existente verifica que a página inicial entrega o front (`test_pagina_inicial_entrega_o_front`); se ele checar a string "Keywords" no HTML, atualize-o para a aba nova.

- [ ] **Step 9: Commit**

```bash
git add web/index.html web/app.js tests/test_api.py
git commit -m "feat: aba Scan instantanea, sem esperar o modelo"
```

---

### Task 5: Aba Skim, absorvendo a Visão geral

Skim = estrutura + essencial. Metadados e seções detectadas *são* skimming: cabem na mesma aba, e fundi-las mantém o total em 6 abas (o design-brief §8.7 pede menos, não mais).

**Files:**
- Modify: `web/index.html` (aba `visao` → `skim`, painel correspondente)
- Modify: `web/app.js` (`desenharVisao` vira `desenharSkim`)
- Modify: `web/estilo.css` (blocos do skim)

**Interfaces:**
- Consumes: `GET /api/itens/{id}/skim` (Task 3); `desenharVisao` existente (linha 308) como base do cabeçalho de metadados.
- Produces: `estado.skims` (`{[id]: <skim>}`), `carregarSkim(id)`, `desenharSkim(dado)`.

- [ ] **Step 1: Renomear a aba e o painel em `web/index.html`**

Linha 99, troque:

```html
        <button role="tab" data-aba="visao" class="ativa">Visão geral</button>
```

por:

```html
        <button role="tab" data-aba="skim" class="ativa">Skim · o essencial</button>
```

Linha 107, troque:

```html
      <div class="painel ativa" id="painel-visao"></div>
```

por:

```html
      <div class="painel ativa" id="painel-skim"></div>
```

- [ ] **Step 2: Guardar o skim no estado**

No objeto `estado`, depois da linha `scan: {},` acrescente:

```javascript
  skims: {},          // id -> leitura rapida mecanica, sem LLM
```

- [ ] **Step 3: Buscar o skim junto com o scan**

Depois de `carregarScan`, acrescente:

```javascript
/** Leitura rapida mecanica. Como o scan, roda sem o modelo. */
async function carregarSkim(id) {
  if (estado.skims[id]) return;  // o skim nao muda com as keywords
  try {
    estado.skims[id] = (await api(`/api/itens/${id}/skim`)).skim;
  } catch (_) { /* sem skim a aba mostra so os metadados */ }
}
```

Em `abrirArtigo`, ao lado da chamada de `carregarScan`, acrescente:

```javascript
  await carregarSkim(id);
```

- [ ] **Step 4: Transformar `desenharVisao` em `desenharSkim`**

Renomeie a função `desenharVisao` (linha 308) para `desenharSkim`, troque `$('#painel-visao')` por `$('#painel-skim')` e, **antes** do `alvo.replaceChildren(...)` final, acrescente os blocos do skim:

```javascript
  const skim = estado.skims[dado.id];
  if (skim && !skim.vazio) {
    filhos.push(elemento('p', {
      class: 'nota-metodo',
      texto: 'Leitura rápida mecânica: abertura de cada seção, dados numéricos e frases de conclusão. Sai em milissegundos e não usa o modelo.',
    }));

    if (skim.secoes.length) {
      filhos.push(elemento('h3', { class: 'secao', texto: 'Estrutura do artigo' }));
      filhos.push(elemento('div', { class: 'skim-secoes' }, skim.secoes.map((s) =>
        elemento('div', { class: 'skim-secao' }, [
          elemento('div', { class: 'skim-topo' }, [
            elemento('h4', { texto: s.titulo }),
            elemento('span', { class: 'fonte', texto: `p. ${s.pagina}` }),
          ]),
          s.abertura ? elemento('p', { texto: s.abertura }) : null,
          s.esqueleto.length
            ? elemento('ul', { class: 'skim-esqueleto' },
                s.esqueleto.map((frase) => elemento('li', { texto: frase })))
            : null,
        ].filter(Boolean)))));
    }

    const listas = [
      ['Dados numéricos', skim.numeros],
      ['Frases de conclusão', skim.conclusoes],
    ];
    for (const [rotulo, frases] of listas) {
      if (!frases.length) continue;
      filhos.push(elemento('h3', { class: 'secao', texto: rotulo }));
      filhos.push(elemento('div', {}, frases.map((f) =>
        elemento('div', { class: 'trecho' }, [
          elemento('span', { class: 'fonte', texto: `p. ${f.pagina}${f.secao ? ` · ${f.secao}` : ''}` }),
          elemento('span', { texto: f.texto }),
        ]))));
    }
  }
```

- [ ] **Step 5: Trocar a chamada em `desenharArtigo`**

Troque `desenharVisao(dado);` por `desenharSkim(dado);`.

Run: `grep -n "desenharVisao\|painel-visao" web/app.js web/index.html`
Esperado: nenhuma linha.

- [ ] **Step 6: Estilos em `web/estilo.css`**

Acrescente ao fim do arquivo:

```css
/* --- Skim: leitura rapida mecanica ------------------------------------- */

.nota-metodo {
  font-size: .85rem;
  color: var(--texto-sutil, #5c6472);
  border-left: 3px solid var(--primaria, #2f6feb);
  padding: .4rem .7rem;
  margin: .8rem 0;
}

.skim-secoes { display: grid; gap: .9rem; }

.skim-secao {
  border: 1px solid var(--borda, #d9dde5);
  border-radius: 6px;
  padding: .7rem .9rem;
}

.skim-topo {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: .6rem;
}

.skim-topo h4 { margin: 0; }

.skim-esqueleto {
  margin: .5rem 0 0;
  padding-left: 1.1rem;
  font-size: .9rem;
  color: var(--texto-sutil, #5c6472);
}

.skim-esqueleto li { margin: .2rem 0; }
```

Antes de colar, confira os nomes reais das variáveis CSS:

Run: `grep -n "^\s*--" web/estilo.css | head -20`
Os nomes reais neste projeto são `--texto-sutil`, `--borda` e `--primaria` (conferido na Task 5); se divergirem, use os que estiverem lá (os *fallbacks* após a vírgula já garantem que nada fica sem cor, mas o tema escuro só funciona com a variável certa).

- [ ] **Step 7: Verificar no navegador**

Recarregue `http://localhost:8000`, envie `exemplos/artigo_exemplo.pdf` e olhe a primeira aba, agora **Skim · o essencial**, **sem clicar em Analisar**. Esperado: métricas do artigo, seções detectadas com a abertura de cada uma, a lista de dados numéricos e as frases de conclusão — todas com `p. N`. Confira em ambos os temas (claro e escuro, via `prefers-color-scheme`).

- [ ] **Step 8: Rodar a suíte**

Run: `./.venv/bin/python -m pytest -q`
Esperado: PASS, 168 testes.

- [ ] **Step 9: Commit**

```bash
git add web/index.html web/app.js web/estilo.css
git commit -m "feat: aba Skim com a leitura rapida mecanica"
```

---

### Task 6: Nomear a Leitura profunda e explicar o método

**Files:**
- Modify: `web/index.html` (aba `leitura`, botão de análise, nota do método)
- Modify: `web/app.js` (texto do botão, se houver rótulo dinâmico)

**Interfaces:**
- Consumes: as abas de Tasks 4 e 5.
- Produces: nenhuma interface nova — só rótulos e copy.

- [ ] **Step 1: Renomear a aba de leitura em `web/index.html`**

Linha 100, troque:

```html
        <button role="tab" data-aba="leitura">Leitura</button>
```

por:

```html
        <button role="tab" data-aba="leitura">Leitura profunda</button>
```

- [ ] **Step 1b: Reordenar para agrupar as camadas por custo**

As Tasks 4 e 5 renomearam as abas no lugar, então `leitura` ficou entre `skim` e `scan` — a camada de minutos encaixada entre as duas de milissegundos, contradizendo a nota do método que o Step 2 acrescenta ("os dois saem em milissegundos"). Mova o botão `data-aba="leitura"` para **depois** do botão `data-aba="scan"`, e faça o mesmo com `<div class="painel" id="painel-leitura">`, que vai para depois de `<div class="painel" id="painel-scan">`.

Mova as linhas inteiras, preservando `data-aba`, `id`, o `class="ativa"` do botão `skim` e o `class="painel ativa"` do `painel-skim`.

A ordem final das abas fica: **Skim · o essencial · Scan · achar termos · Leitura profunda · Comparar lote · Texto extraído · Exportar** — seis, como antes.

Run: `grep -n "data-aba=\|id=\"painel-" web/index.html`
Esperado: as duas listas na mesma ordem — skim, scan, leitura, comparar, texto, exportar.

- [ ] **Step 2: Acrescentar a nota do método**

Logo depois do `<div class="abas" ...>` fechado (linha 105), antes do primeiro painel, acrescente:

```html
      <p class="nota-metodo" id="nota-metodo">
        <b>Skim</b> mostra o essencial pela estrutura do artigo e <b>Scan</b> varre os termos
        que você pediu — os dois saem em milissegundos e não usam o modelo.
        <b>Leitura profunda</b> é a análise do modelo: leva minutos em CPU e só roda quando
        você clica em Analisar.
      </p>
```

- [ ] **Step 3: Deixar o custo explícito no botão**

O rótulo existe em dois lugares: estático em `web/index.html:88` e recalculado em `web/app.js:137`.

Em `web/index.html`, linha 88, troque:

```html
        <button class="primario" id="btn-analisar">Analisar pendentes</button>
```

por:

```html
        <button class="primario" id="btn-analisar">Leitura profunda dos pendentes</button>
```

Em `web/app.js`, linha 137, troque:

```javascript
  $('#btn-analisar').textContent = pendentes ? `Analisar ${pendentes} pendente(s)` : 'Nada pendente';
```

por:

```javascript
  $('#btn-analisar').textContent = pendentes
    ? `Leitura profunda — ${pendentes} pendente(s)`
    : 'Nada pendente';
```

Run: `grep -n "Analisar pendentes" web/index.html web/app.js`
Esperado: nenhuma linha.

- [ ] **Step 4: Verificar no navegador**

Recarregue e confirme: as três camadas aparecem nomeadas, a nota do método está visível acima das abas, e o botão principal diz "Leitura profunda". Com o Ollama parado, Skim e Scan continuam preenchidos e só a Leitura profunda avisa que o modelo está fora.

- [ ] **Step 5: Rodar a suíte**

Run: `./.venv/bin/python -m pytest -q`
Esperado: PASS, 168 testes.

- [ ] **Step 6: Commit**

```bash
git add web/index.html web/app.js
git commit -m "feat: nomear as tres camadas de leitura na interface"
```

---

### Task 7: Alinhar a documentação ao código

**Files:**
- Modify: `README.md`
- Modify: `docs/design-brief.md`
- Modify: `docs/proximos-passos.md`

**Interfaces:**
- Consumes: tudo o que as Tasks 1-6 entregaram.
- Produces: documentação que descreve o comportamento real.

- [ ] **Step 1: Corrigir a afirmação falsa do design-brief**

`docs/design-brief.md` §7, regra 8, hoje diz que a busca literal de keywords funciona sem o Ollama — o que só passou a ser verdade na Task 2. Substitua a regra 8 por:

```markdown
8. Sem Ollama conectado, **Skim e Scan funcionam por inteiro** — são determinísticos e
   não passam pelo modelo (`GET /api/itens/{id}/skim`, `GET /api/itens/{id}/scan`). Só a
   Leitura profunda avisa que o modelo está fora e para. O PDF grifado por keywords
   também não depende do modelo (`?keywords=a,b`).
```

Na §5, atualize a lista de abas de "Visão geral · Leitura · Keywords · Comparar lote · Texto extraído · Exportar" para "Skim · Scan · Leitura profunda · Comparar lote · Texto extraído · Exportar", e renomeie os títulos §4.1 (`Visao geral` → `Skim`) e §4.5 (`Keywords` → `Scan`).

- [ ] **Step 2: Atualizar o README**

Na tabela "O que ela entrega", acrescente duas linhas no topo:

```markdown
| **Skim (o essencial)** | Leitura rápida mecânica, em milissegundos e sem modelo: estrutura do artigo, abertura de cada seção, frases com dados numéricos e frases de conclusão — todas com a página. |
| **Scan (achar termos)** | Busca literal das suas keywords assim que o PDF é enviado: contagem, páginas, densidade por mil palavras e os trechos com o termo destacado. Não passa pelo modelo e funciona com o Ollama fora do ar. |
```

Na seção **API**, acrescente à tabela de rotas:

```markdown
| `GET /api/itens/{id}/skim` · `GET /api/itens/{id}/scan?keywords=a,b` | Skim e Scan determinísticos, sem passar pelo modelo |
```

Na seção **Arquitetura**, acrescente `skim.py` ao diagrama e uma sexta decisão explicada:

```markdown
- **Três camadas, separadas por custo.** *Scan* (busca literal) e *Skim* (leitura mecânica
  da estrutura) são determinísticos e saem em milissegundos; *Leitura profunda* é o modelo,
  e leva minutos em CPU. As duas primeiras têm rotas próprias e não tocam no Ollama, então
  a aplicação é útil no instante do envio — e continua útil com o modelo fora do ar.
```

Na seção **Estrutura**, acrescente a linha:

```
  skim.py          skimming mecanico: estrutura, numeros e conclusoes, sem LLM
```

Atualize a contagem de testes de "135 testes" para o número real:

Run: `./.venv/bin/python -m pytest -q 2>&1 | tail -2`

- [ ] **Step 3: Riscar o item concluído em `docs/proximos-passos.md`**

Remova a seção "## 1. Enquadrar o produto em skimming e scanning" inteira e acrescente à nota de concluídos no topo:

```markdown
_Concluído e removido desta lista: a retirada da pergunta livre ao modelo (a aba
"Perguntar"), feita em 19/08/2026; o enquadramento do produto em skimming e scanning,
feito em 26/08/2026 (spec em `docs/spec-skimming-scanning.md`, plano em
`docs/superpowers/plans/2026-08-26-skimming-scanning.md`)._
```

Renumere as seções restantes (a antiga §2 vira §1, a antiga §3 vira §2). Na lista da §3 antiga, remova o item "**A espera é longa e o feedback é uma barra de progresso**" da referência ao design-brief, já resolvido pelas Tasks 4 e 5.

- [ ] **Step 4: Conferir que nada ficou desatualizado**

Run: `grep -rn "painel-visao\|painel-keywords\|desenharKeywords\|desenharVisao" . --include=*.md --include=*.js --include=*.html`
Esperado: nenhuma linha.

Run: `grep -n "135 testes" README.md`
Esperado: nenhuma linha.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/
git commit -m "docs: alinhar README, brief e proximos passos ao codigo"
```

---

## Verificação final

- [ ] `./.venv/bin/python -m pytest -q` — todos os testes passam
- [ ] Com o Ollama **parado**: envio de PDF preenche Skim e Scan por completo; só a Leitura profunda avisa que o modelo está fora
- [ ] Com o Ollama **no ar**: a síntese do modelo aparece dentro do Scan já preenchido, sem apagar os dados literais
- [ ] As seis abas estão nomeadas por intenção de leitura e a nota do método está visível
- [ ] `grep -rn "skim\|scan" analisador/ servidor/ web/ --include=*.py --include=*.js -il` lista os arquivos esperados

# Analisador de Artigos em PDF

Aplicação web local que lê artigos científicos em PDF (**até 5 por sessão**), procura as
**keywords que você informa** e produz uma **leitura objetiva** de cada um — resumo
estruturado, achados com evidência, limitações e lacunas — além de comparar os artigos
entre si e devolver o **PDF grifado** nas passagens relevantes.

Todo o processamento acontece na sua máquina: extração em Python e modelo rodando no
container do **Ollama** (`gemma3:4b` por padrão). Nenhum trecho do artigo sai do seu
computador.

## O que ela entrega

| Recurso | O que faz |
|---|---|
| **Conversão para Markdown** | No envio, o PDF vira Markdown: título vira `#`, seções viram `##`, listas são normalizadas, linhas quebradas pelo PDF voltam a ser parágrafos e cada página ganha um marcador em comentário. **É esse texto que o modelo lê** — a estrutura explícita ajuda o SLM a distinguir cabeçalho de corpo e a atribuir a seção certa. Dá para ver e baixar o resultado na aplicação. |
| **Modo lote** | Até 5 PDFs por sessão, analisados em fila com progresso por artigo em tempo real. O resultado de cada um aparece assim que fica pronto. Duplicatas (mesmo conteúdo) são detectadas por hash e não consomem vaga. |
| **Keywords híbridas** | Para cada termo: contagem, páginas, densidade por mil palavras, todos os trechos originais com o termo destacado **e** uma síntese do modelo sobre o que o artigo afirma, citando página. O dado bruto fica ao lado da síntese, então dá para conferir se o modelo inventou. |
| **PDF grifado** | O PDF original de volta com marcações de verdade (anotações PDF, não imagem): amarelo nas keywords, verde nas frases que sustentam cada achado. Abre marcado em qualquer leitor e o texto continua selecionável. |
| **Resumo estruturado** | Objetivo, metodologia, resultados, conclusão e relevância — no máximo 3 frases por campo. |
| **Achados + evidências** | Até 6 afirmações centrais, cada uma com o dado que a sustenta e a página. |
| **Limitações e lacunas** | O que os autores admitem e o que o artigo deixa sem resposta (marcado com `Lacuna:`). |
| **Comparação entre artigos** | Tabela com as ocorrências de cada keyword em cada artigo, keywords ausentes em algum deles e os resumos lado a lado. Usa contagem literal, então vale mesmo se a síntese do modelo falhar. |
| **Metadados e estrutura** | Título, autores, DOI, páginas, palavras, tempo estimado de leitura, seções detectadas e número de referências. |
| **Termos-chave sugeridos** | O modelo propõe termos do artigo que você não pediu. |
| **Exportação** | Relatório em Markdown e JSON por artigo, mais um consolidado do lote com a tabela comparativa. |

## Requisitos

- Docker com o plugin `compose`
- Python 3.10+
- ~4 GB de disco para o modelo (`gemma3:4b`) e ~6 GB de RAM livre para rodá-lo em CPU

## Como rodar

### Tudo em container (mais simples)

```bash
docker compose up -d        # ou: make up   → http://localhost:8000
```

Um comando sobe os três serviços, nesta ordem:

1. **`ollama`** — o servidor do modelo, na porta 11434, com volume persistente
2. **`preparar-modelo`** — baixa o `gemma3:4b` (~3,3 GB, só na primeira vez) e encerra;
   nas próximas subidas sai em segundos porque o modelo já está no volume
3. **`app`** — a aplicação, que só arranca depois que o modelo terminou de baixar

Dentro da rede do compose a aplicação fala com o Ollama por `http://ollama:11434` — o nome
do serviço, não `localhost`, que ali dentro seria o próprio container da app.

```bash
make ps       # estado dos containers
make logs     # todos os logs; S=ollama filtra um serviço
make down     # derruba tudo (os modelos ficam no volume)
```

### Desenvolvendo (app fora do container, com recarga)

```bash
./setup.sh    # Ollama + modelo + venv com as dependências de teste
make dev      # Ollama em container, app no venv recarregando ao editar
```

`make dev` equivale a `docker compose up -d ollama && ./iniciar.sh --reload`. Como o
Ollama publica a porta 11434 no host, a app no venv o encontra em `localhost`.

### Usando

Arraste de 1 a 5 PDFs, digite as keywords separadas por vírgula (ou uma por linha — valem
para todo o lote) e clique em **Analisar**. Os artigos são processados em fila e cada
resultado aparece assim que fica pronto.

O limite de 5 PDFs vale para a sessão inteira: cheio, os próximos são recusados com aviso
até você clicar em **Limpar lote**.

## Arquitetura

```
┌─ container: app ──────────────────────────────┐   ┌─ container: ollama ─┐
│  navegador ──HTTP/SSE──► servidor/api.py      │   │  gemma3:4b          │
│    web/                    │                  │──►│  volume persistente │
│                       analisador/ (núcleo)    │   └─────────────────────┘
└───────────────────────────────────────────────┘
```

Três camadas, com uma regra: **o núcleo não conhece HTTP e a API não conhece PDF**.

```
PDFs ─► pdf.py ────► Documento (texto limpo + páginas + seções + metadados)
                        │
              ┌─────────┴──────────┐
              │                    │
        keywords.py          markdown.py
     (busca literal no      (mesma fonte em
      texto cru, offset      Markdown: o que
      → página/seção)        o modelo lê)
              │                    │
              │         ┌──────────┼──────────┐
              │    blocos.py   marcacao.py  lote.py
              │   (blocos com  (grifa o PDF (fila de até 5,
              │   sobreposição) original)    comparação)
              │                    │
              └──────────► analise.py ◄──────┘
                   (map: notas por bloco →
                    reduce: resumo, achados,
                    limitações, sínteses)
                          │
                     relatorio.py ─► Markdown / JSON
```

Cinco decisões que valem explicação:

- **Rastreabilidade.** A busca de keywords não passa pelo LLM. O texto é normalizado
  (minúsculas, sem acento) mantendo um mapa de índices de volta ao original, então toda
  ocorrência sabe seu offset exato, sua página e sua seção. A síntese do modelo é gerada
  *a partir desses trechos*, e os trechos ficam visíveis ao lado dela.
- **Duas visões do mesmo artigo.** O modelo lê a versão em Markdown, onde a hierarquia é
  explícita; a busca de keywords fica no texto cru, onde cada ocorrência tem offset exato.
  As duas visões compartilham a numeração de páginas, então o bloco enviado ao modelo e o
  trecho mostrado na tela apontam para a mesma página — sem o Markdown vazar para as
  citações que você confere.
- **Custo previsível em CPU.** Uma única passada cara percorre o artigo condensando cada
  bloco em pontos factuais com a página. Resumo, achados e limitações reaproveitam essas
  notas em vez de reler o artigo.
- **Grifo que não mente.** Keyword é casamento literal, sempre exato. Já a evidência de um
  achado costuma vir parafraseada pelo modelo, então é localizada por similaridade
  (`difflib`) contra as frases da página citada — e abaixo do limiar **nada é marcado**.
  Grifar a frase errada seria pior do que não grifar.
- **Streaming de verdade.** O cliente do Ollama é bloqueante, então a análise roda numa
  thread produtora e os eventos vão para o navegador por SSE conforme acontecem — barra de
  progresso por artigo e resposta do chat aparecendo enquanto o modelo escreve.

## Configuração

Ajustável pela barra lateral e por variáveis de ambiente (veja `.env.example`):

| Variável | Padrão | Para que serve |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Endereço do Ollama |
| `OLLAMA_MODELO` | `gemma3:4b` | Modelo usado na análise |
| `OLLAMA_NUM_CTX` | `8192` | Janela de contexto pedida ao modelo |
| `OLLAMA_TEMPERATURA` | `0.2` | Baixa, para leitura factual |
| `OLLAMA_TIMEOUT` | `600` | Segundos de espera por resposta |
| `ANALISADOR_TAMANHO_BLOCO` | `6000` | Caracteres por bloco enviado ao modelo |
| `ANALISADOR_MAX_BLOCOS` | `24` | Teto de blocos lidos por artigo |
| `PORTA` | `8000` | Porta publicada da aplicação web |

No modo container, essas variáveis podem ir num `.env` ao lado do `docker-compose.yml` — o
compose as repassa para o serviço `app`. A única que ele fixa é `OLLAMA_URL`, que precisa
apontar para o nome do serviço.

## API

O front é só um cliente da API — dá para usar por script:

| Rota | O que faz |
|---|---|
| `GET /api/config` · `GET /api/status` | Padrões da aplicação e diagnóstico do Ollama |
| `POST /api/pdfs` · `GET /api/pdfs` · `DELETE /api/pdfs[/{id}]` | Envio e gestão do lote |
| `POST /api/analise` | Análise do lote (SSE: `inicio`, `artigo_inicio`, `progresso`, `artigo_fim`, `fim`) |
| `GET /api/itens/{id}` · `GET /api/itens/{id}/pagina/{n}` | Análise completa e texto por página |
| `GET /api/itens/{id}/markdown` | O artigo em Markdown (`?download=true` baixa o arquivo) |
| `GET /api/comparacao` | Tabelas comparativas do lote |
| `GET /api/itens/{id}/anotado.pdf` | PDF grifado (`?keywords=a,b`, `?evidencias=false`) |
| `GET /api/itens/{id}/relatorio.{md,json}` · `GET /api/lote/relatorio.{md,json}` | Downloads |

O estado do lote vive por sessão (cookie), em memória.

## Testes

```bash
make test      # ou: ./.venv/bin/python -m pytest
```

Os testes precisam do venv (`./setup.sh`), que instala `requirements-dev.txt` — o
`requirements.txt` tem só o necessário para rodar, que é o que entra na imagem.

135 testes, todos offline e sem navegador: a extração e o grifo rodam sobre PDFs gerados em
memória (`tests/pdf_falso.py`), e o pipeline completo — incluindo os endpoints SSE — roda
contra um servidor Ollama falso (`tests/ollama_falso.py`).

## Próximos passos

Ideias levantadas e ainda não implementadas — incluindo enquadrar o produto nas técnicas de
**skimming e scanning** e retirar a pergunta livre ao modelo — estão em
[`docs/proximos-passos.md`](docs/proximos-passos.md).

## Limitações conhecidas

- **PDFs digitalizados** (imagem, sem camada de texto) não são analisados nem grifados — a
  aplicação avisa que seria preciso OCR.
- **Em CPU o modelo é lento**: um artigo de 10 páginas leva alguns minutos, e um lote de 5
  pode passar de meia hora. Por isso o limite é 5 e cada resultado aparece assim que fica
  pronto. Com GPU NVIDIA, descomente o bloco `deploy:` do `docker-compose.yml`.
- **Palavra quebrada por hífen** no fim da linha não é localizada pelo grifo (a análise
  rejunta o texto, mas o PDF original mantém a quebra).
- **O lote vive na sessão**, em memória: reiniciar o servidor (ou o container `app`) zera
  os artigos carregados. Baixe os relatórios antes.
- **Extração de colunas duplas** pode intercalar linhas em alguns layouts; o texto de cada
  página fica visível na aba "Texto extraído" para conferência.
- A síntese vem de um modelo de 4B parâmetros: confira os números contra os trechos citados
  antes de usar em algo publicável.

## Estrutura

```
analisador/        núcleo, sem HTTP e sem UI
  config.py        parâmetros por variável de ambiente
  pdf.py           extração, limpeza, seções, metadados
  keywords.py      busca determinística com rastreabilidade
  markdown.py      conversão do artigo para Markdown (a visão do modelo)
  blocos.py        divisão do texto em blocos com sobreposição
  llm.py           cliente HTTP do Ollama (streaming + JSON)
  analise.py       orquestração map/reduce e prompts
  marcacao.py      grifo das passagens no PDF original
  lote.py          fila de artigos, triagem com limite e comparação
  relatorio.py     Markdown e JSON (individual e consolidado)
servidor/          API HTTP
  api.py           rotas REST e SSE
  sessao.py        estado por sessão do navegador
  esquemas.py      objetos do núcleo → JSON
web/               front sem framework e sem build
  index.html · estilo.css · app.js
docs/              briefing de design e próximos passos
exemplos/          PDF fictício para testar
tests/             135 testes offline
Dockerfile         imagem da aplicação
docker-compose.yml ollama + download do modelo + app
```

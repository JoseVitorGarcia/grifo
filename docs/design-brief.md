# Briefing de design — Analisador de Artigos em PDF

Documento de referência para gerar as telas da aplicação. Descreve o produto, cada tela,
cada estado, os dados reais que aparecem em tela e os textos exatos usados hoje.

---

## 1. O produto em uma frase

Ferramenta web local onde um pesquisador envia até 5 artigos científicos em PDF, informa as
palavras-chave que lhe interessam e recebe, para cada artigo, uma leitura objetiva gerada
por um modelo de IA rodando na própria máquina — sempre acompanhada dos trechos originais
que sustentam cada afirmação.

**Usuário-alvo:** pesquisador, estudante de pós-graduação ou analista fazendo revisão de
literatura. Lê muito, tem pouco tempo, desconfia de resumo automático.

**Promessa central:** *velocidade sem perder a rastreabilidade*. Toda síntese da IA vem
colada ao trecho literal do artigo, com número de página. O design precisa deixar essa
dupla — síntese + evidência — visualmente inseparável.

**Tom:** técnico, sóbrio, denso de informação. Nada de linguagem motivacional, ilustrações
decorativas ou emoji fora dos poucos usados como status. É uma ferramenta de trabalho,
mais próxima de um leitor de PDF profissional do que de um app de produtividade colorido.

**Diferencial a comunicar visualmente:** roda 100% local. Nenhum trecho do artigo sai da
máquina do usuário. Isso deve ficar legível na interface, não escondido no rodapé.

---

## 2. Contexto técnico (o design tem liberdade total)

- Front em **HTML + CSS + JavaScript puros**, sem framework e sem etapa de build. Três
  arquivos: `web/index.html`, `web/estilo.css`, `web/app.js`.
- Backend em **FastAPI**; o front só consome a API (`/api/...`) e desenha o DOM.
- Qualquer layout é implementável — não há componente de biblioteca limitando nada.
- Paleta atual em variáveis CSS, com tema claro e escuro por `prefers-color-scheme`:
  primária `#2f6feb`, fundo `#f6f7f9` (claro) / `#12151b` (escuro), grifo amarelo `#ffe066`
  e verde `#8ce99a`.
- Barra lateral fixa de 300px + conteúdo até 1180px; abaixo de 900px vira coluna única.
- O processamento é **lento em CPU** (minutos por artigo) e o progresso chega por SSE em
  tempo real. Progresso e resultado parcial são parte essencial da experiência.

---

## 3. Arquitetura da interface

```
┌──────────────┬────────────────────────────────────────────────────────┐
│  BARRA       │  Cabeçalho: título + subtítulo                         │
│  LATERAL     ├────────────────────────────────────────────────────────┤
│              │  Upload de PDFs (múltiplo, até 5)                      │
│  Conexão     ├────────────────────────────────────────────────────────┤
│  Lote        │  Campo de keywords (vale para todo o lote)             │
│  Análise     ├────────────────────────────────────────────────────────┤
│  Ajustes     │  Ações: Analisar · Reanalisar · status do Ollama       │
│              ├────────────────────────────────────────────────────────┤
│              │  Seletor de artigo em exibição (aparece com 2+)        │
│              ├────────────────────────────────────────────────────────┤
│              │  6 abas de resultado                                   │
└──────────────┴────────────────────────────────────────────────────────┘
```

---

## 4. Barra lateral (presente em todas as telas)

**Topo:** título `📄 Analisador de Artigos`, legenda `v1.0.0 · 100% local via Ollama`.

### Bloco "Conexao"
- Campo de texto **URL do Ollama** — valor `http://localhost:11434`, ajuda: `Container: docker compose up -d`
- **Online:** seletor **Modelo** com os modelos instalados + faixa verde `Ollama online · 2 modelo(s)`
- **Offline:** campo de texto livre **Modelo** + faixa vermelha `Ollama offline. Rode docker compose up -d e depois ./setup.sh.`
- Botão largura total: `Reconsultar modelos`

### Bloco "Lote"
- Barra de progresso com texto `3/5 PDFs nesta sessao`
- Lista dos arquivos carregados, um por linha, com marcador de estado:
  `✅ telemedicina_adesao.pdf` (analisado) · `⏳ custo_telessaude.pdf` (pendente)
- Botão largura total `Limpar lote` — **só aparece quando há arquivos**

### Bloco "Analise" — cinco caixas de seleção, todas marcadas por padrão
`Resumo estruturado` · `Achados + evidencias` · `Limitacoes e lacunas` ·
`Sintese por keyword` · `Sugerir termos-chave`

Mais uma: `Busca flexivel de keywords` (ajuda: *Casa também plural e flexões simples —
algoritmo → algoritmos*).

### Expansor "Ajustes do modelo" (fechado por padrão)
`Temperatura` 0–1 (padrão 0.2) · `Janela de contexto (num_ctx)` entre 2048 e 32768 (padrão
8192) · `Tamanho do bloco (caracteres)` 2000–12000 (padrão 6000) · `Maximo de blocos lidos`
4–60 (padrão 24).

---

## 5. Telas e estados

### Tela 1 — Vazio (nenhum PDF carregado)

- Cabeçalho: **Analise objetiva de artigos em PDF**
- Legenda: *Envie ate 5 artigos por sessao, informe as keywords e receba leitura objetiva
  com trechos rastreaveis e comparacao entre os artigos.*
- Área de upload: `Artigos em PDF (ate 5 por sessao · 5 vaga(s) restante(s))`, aceita
  múltiplos arquivos, só `.pdf`
- Aviso informativo: *Comece enviando de 1 a 5 PDFs. Nada sai da sua maquina: extracao
  local + modelo local.*
- **Nada mais é exibido.** Sem keywords, sem botões, sem abas.

Esta é a tela que mais precisa de trabalho de design: hoje é funcional e sem personalidade.
É o momento de comunicar a promessa (local, rastreável, lote).

### Tela 2 — PDFs carregados, análise ainda não rodou

Acrescenta à tela 1:
- Campo de texto multilinha: *Keywords (separadas por virgula ou uma por linha) — valem
  para todos os artigos do lote*, exemplo em placeholder: `vies amostral, aprendizado de
  maquina, validacao cruzada`
- Abaixo dele, as keywords reconhecidas viram etiquetas: `` `telemedicina` · `adesao` · `randomizado` ``
- Linha de ações em três colunas:
  - botão primário `🔍 Analisar 2 pendente(s)`
  - botão secundário `↻ Reanalisar tudo`
  - status do Ollama: `Ollama ok em http://localhost:11434 — modelo gemma3:4b pronto.`
- Abaixo, o painel de **visão geral** do artigo selecionado (metadados, sem análise) e o
  aviso: *Clique em Analisar para gerar resumo, achados, limitacoes e sintese das keywords.*

**Estado de recusa** (usuário tenta passar de 5, ou manda o mesmo PDF duas vezes):
- vermelho: *custo.pdf ficou de fora: limite de 5 PDFs por sessao atingido. Use Limpar lote para recomecar.*
- azul: *copia.pdf ignorado: ja esta no lote (mesmo conteudo).*

### Tela 3 — Análise em andamento (crítica)

Um bloco de status **por artigo**, empilhados. O artigo em processamento fica expandido,
os concluídos colapsam.

- Cabeçalho do bloco: `Analisando telemedicina_adesao.pdf (1/3)`
- Barra de progresso com texto dinâmico, nesta ordem:
  1. `[1/3] telemedicina_adesao.pdf — Lendo bloco 4/12 (p. 5-6)`  ← ocupa os primeiros 45%
  2. `[1/3] telemedicina_adesao.pdf — Montando o resumo estruturado`
  3. `... — Extraindo achados e evidencias`
  4. `... — Levantando limitacoes e lacunas`
  5. `... — Sugerindo termos-chave`
  6. `... — Keyword 2/3: adesao`
  7. `... — Concluido`
- Concluído: `telemedicina_adesao.pdf — concluido` (verde, colapsa)
- Com falha parcial: `telemedicina_adesao.pdf — concluido (1 etapa(s) com erro)` (vermelho)
- Falha total: `telemedicina_adesao.pdf — falhou: O modelo passou de 600s sem responder.`
- Ao fim de todos: `Lote concluido: 3 artigo(s) em 12.4 min.`

Como cada artigo leva minutos, esta tela fica visível bastante tempo — merece atenção real
de design, não ser tratada como estado transitório.

### Tela 4 — Resultado

Quando há 2+ artigos, aparece antes das abas um seletor horizontal:
`✅ telemedicina_adesao.pdf` | `⏳ custo_telessaude.pdf`

Seis abas: **Skim · Scan · Leitura profunda · Comparar lote · Texto extraído · Exportar**.
(Resumo, achados e limitações estão em "Leitura profunda"; a "Visão geral" antiga foi absorvida
em "Skim" junto com os metadados, seções e termos sugeridos; e a aba de perguntas ao modelo
foi retirada — o produto é leitura objetiva, não conversa.)

#### 4.1 Skim
- Título do artigo em destaque, autores como legenda
- Quatro métricas lado a lado: `Paginas 3` · `Palavras 350` · `Leitura 2 min` · `Referencias 3`
- `**Secoes detectadas:** Abstract · Introduction · Methods · Results · Discussion · Conclusion · References`
- `**DOI:** 10.1234/abcd.2020.567` (link)
- `**Termos-chave sugeridos pelo modelo:**` seguido de etiquetas
- Avisos da extração, quando houver (ex.: *Quase nenhum texto foi extraido. O PDF
  provavelmente e digitalizado (imagem) e precisaria de OCR para ser analisado.*)

#### 4.2 Leitura profunda — resumo, achados e limitações numa leitura contínua

**Resumo** — cinco campos rotulados, no máximo 3 frases cada
`Objetivo` · `Metodologia` · `Resultados` · `Conclusao` · `Relevancia`

Exemplo real de conteúdo:
> **Metodologia:** Ensaio clínico randomizado, aberto, com 240 pacientes acompanhados por
> 12 meses em um único hospital universitário.

**Achados** — lista numerada, até 6 itens
Cada item: afirmação em negrito + página em itálico + linha de evidência em legenda.
> **1. A adesão subiu 18 pontos percentuais no grupo telemedicina** *(p. 2)*
> Evidência: 78% vs 60%, IC 95% 11 a 25, p < 0,001

**Limitações** — lista simples
> - Estudo conduzido em um único centro, o que restringe a generalização
> - Desenho aberto pode ter introduzido viés de aferição
> - Lacuna: não foi avaliado o custo-efetividade da intervenção

Itens que começam com `Lacuna:` são perguntas não respondidas pelo artigo — merecem
tratamento visual distinto das limitações admitidas pelos autores.

#### 4.5 Scan — a tela mais importante do produto
1. Tabela: `Keyword` · `Ocorrencias` · `Paginas` · `Por mil palavras`
   Ex.: `telemedicina | 8 | 1, 2, 3 | 22.86`
2. Gráfico de barras: distribuição das ocorrências por página, uma série por keyword
3. Um expansor por keyword, aberto por padrão:
   - Cabeçalho: `✅ telemedicina — 8 ocorrencia(s)` ou `⚠️ quimioterapia — 0 ocorrencia(s)`
   - Síntese do modelo (parágrafo curto, com páginas entre parênteses)
   - Legenda: *Trechos no artigo (termo entre **asteriscos**)*
   - Lista de citações, cada uma assim:
     > **p. 2** · Methods — ...ensaio clínico randomizado avaliando **telemedicina**
     > quinzenal em 240 pacientes...

   O termo buscado aparece destacado dentro do trecho. **Esse destaque é o coração do
   produto** — é o que permite conferir a síntese contra a fonte.
   - Keyword ausente: *O termo "quimioterapia" nao aparece literalmente no texto extraido
     do artigo. Verifique sinonimos ou variacoes.*

#### 4.6 Comparar lote
- Tabela geral: `Arquivo · Titulo · Paginas · Palavras · Leitura (min) · Keywords encontradas (2/3) · Analisado (sim/nao)`
- Matriz keyword × artigo com as contagens, legenda: *Ocorrencias de cada keyword por
  artigo (contagem literal, sem LLM)* — mais gráfico de barras agrupadas
- *Keywords que nao aparecem em algum artigo*: `**randomizado** — ausente em: custo.pdf`
- Resumos lado a lado, um expansor por artigo

#### 4.7 Texto extraído — controle de qualidade
Dois modos, alternados por um seletor:

- **Texto extraído**: seletor numérico de página + caixa grande só leitura, com o texto
  cru daquela página. Serve para conferir se a extração funcionou.
- **Markdown (o que o modelo lê)**: o artigo inteiro convertido — `#` no título, `##` nas
  seções, listas normalizadas, parágrafos remontados e `<!-- p. N -->` marcando a página.
  É a transparência do produto: mostra exatamente o que foi enviado ao modelo.

Vale desenhar melhor: hoje o Markdown aparece cru numa `textarea` monoespaçada. Renderizado
ao lado do original, ou com destaque de sintaxe, comunicaria muito mais.

#### 4.8 Exportar
- *PDF com marcações* (o mais importante da aba): `⬇️ PDF grifado (keywords + evidências)` e
  `⬇️ PDF grifado (só keywords)`, com legenda das cores — amarelo para keyword (casamento
  literal) e verde para evidência de achado (casada por similaridade)
- *Relatório deste artigo*: `⬇️ Markdown`, `⬇️ JSON`
- *Lote inteiro (3 artigos analisados)*: `⬇️ Consolidado em Markdown`, `⬇️ Consolidado em JSON`
  (só aparece com 2+ analisados)

---

## 6. Dados reais para preencher as telas

Use estes valores nas maquetes — são a saída real do PDF de exemplo do projeto.

| Campo | Valor |
|---|---|
| Título | Telemedicina e adesão ao tratamento em pacientes crônicos |
| Autores | Autoria de Exemplo |
| Páginas / Palavras / Leitura | 3 · 350 · 2 min |
| Referências | 3 |
| Seções | Abstract, Introduction, Methods, Results, Discussion, Conclusion, References |
| Keyword `telemedicina` | 8 ocorrências, páginas 1–3, 22.86 por mil palavras |
| Keyword `adesao` | 6 ocorrências, páginas 1–3 |
| Keyword `quimioterapia` | 0 ocorrências (estado vazio) |
| Modelo | `gemma3:4b` via Ollama local |

Nomes de arquivo para o lote: `telemedicina_adesao.pdf`, `custo_telessaude.pdf`,
`revisao_sistematica.pdf`.

---

## 6-B. O PDF grifado

Funcionalidade nova e a mais visual do produto: a aplicação devolve o PDF **original** com
anotações de destaque gravadas — não é imagem, abre marcado em qualquer leitor e o texto
continua selecionável.

- **Amarelo `#ffe066`**: keyword, casamento literal, sempre exato.
- **Verde `#8ce99a`**: frase que sustenta um achado, localizada por similaridade contra a
  página que o modelo citou. Abaixo do limiar de confiança, nada é marcado.
- Cada marcação carrega um comentário (`Keyword: telemedicina`, `Achado: a adesão subiu 18
  pontos percentuais`) que aparece ao passar o mouse no leitor de PDF.

Vale desenhar: a legenda das cores, o estado "nenhuma passagem localizada" e — se quiser ir
além — um visualizador do PDF grifado dentro da própria página.

## 7. Regras de interação

1. O limite de **5 PDFs vale para a sessão inteira**, não por upload. Cheio, os próximos
   são recusados com aviso até o usuário clicar em `Limpar lote`.
2. PDF duplicado (mesmo conteúdo, detectado por hash) é ignorado e **não consome vaga**.
3. As keywords são as mesmas para todo o lote — um único campo, não um por artigo.
4. O botão principal analisa **apenas os pendentes**; reprocessar tudo é ação separada.
5. Resultado aparece assim que cada artigo termina — não espera o lote inteiro.
6. Falha em um artigo não derruba os outros; o erro fica marcado naquele artigo.
7. Recarregar a página zera o lote (estado vive na sessão). Vale sinalizar isso antes que
   o usuário perca trabalho.
8. Sem Ollama conectado, **Skim e Scan funcionam por inteiro** — são determinísticos e
   não passam pelo modelo (`GET /api/itens/{id}/skim`, `GET /api/itens/{id}/scan`). Só a
   Leitura profunda avisa que o modelo está fora e para. O PDF grifado por keywords
   também não depende do modelo (`?keywords=a,b`).

---

## 8. O que o design precisa resolver

Problemas conhecidos da interface atual, em ordem de impacto:

1. **A tela vazia não vende nada.** É onde explicar lote, rastreabilidade, grifo no PDF e
   execução local.
2. **A espera é longa e o feedback é uma barra de progresso.** Há espaço para mostrar
   resultado parcial: metadados e contagem de keywords ficam prontos em segundos, antes de
   qualquer chamada ao modelo.
3. **Síntese e evidência competem por espaço.** Hoje a citação vem abaixo do parágrafo;
   lado a lado, ou com a página clicável levando ao texto extraído, seria melhor.
4. **A comparação entre artigos está enterrada** na quarta aba, sendo o principal motivo de
   alguém usar o modo lote.
5. **Nada indica quanto tempo falta.** Com tempo por bloco conhecido, dá para estimar.
6. **O PDF grifado só existe como botão de download.** Um visualizador embutido, mostrando
   as marcações na hora, seria bem mais forte — e o backend já devolve o PDF anotado.
7. **Potencial de poda nas abas.** Texto extraído é ferramenta de conferência e debugging,
   não conteúdo de leitura — poderia ser acessível por outro caminho (ex.: modal) para
   desafogar a navegação.

---

## 9. Referência do projeto

- Código: `/home/jose-garcia/Projetos/Playground/analisador_pdf`
- Front atual: `web/index.html`, `web/estilo.css`, `web/app.js`
- API que alimenta as telas: `servidor/api.py` (rotas listadas no `README.md`)
- Documentação técnica: `README.md`
- PDF de exemplo: `exemplos/artigo_exemplo.pdf`

# Spec — Enquadrar o produto em skimming e scanning

Documento de requisitos para a reestruturação descrita em `docs/proximos-passos.md` §1.
O plano de implementação que o realiza está em
`docs/superpowers/plans/2026-08-26-skimming-scanning.md`.

---

## 1. O problema

O projeto já executa, na prática, as duas técnicas clássicas de leitura rápida — mas não as
nomeia, não as separa e, pior, **acopla a barata à cara**.

Diagnóstico levantado no código em 26/08/2026:

1. **O scanning está refém do LLM.** `buscar_varias()` é chamada em `servidor/api.py:287`,
   dentro de `_analisar_item()`. A única forma de obter contagem, páginas, densidade e
   trechos é rodando `POST /api/analise`, que em `servidor/api.py:358` chama
   `cliente.diagnostico()` e aborta se o Ollama estiver fora. Com o modelo offline o
   usuário não recebe um único número de scanning, apesar de a busca ser `re` sobre string.
   `web/app.js` lê `dado.analise?.keywords` — a aba Keywords, descrita no design-brief como
   "a tela mais importante do produto", só existe depois de minutos de inferência em CPU
   para produzir um dado que leva milissegundos.
2. **Não existe skimming sem modelo.** Nenhuma função em `analisador/` faz leitura
   mecânica. O `gemma3:4b` é a única fonte de "o essencial", a um custo de minutos.
3. **A UI é nomeada por artefato, não por intenção.** `web/index.html:99-104`:
   *Visão geral · Leitura · Keywords · Comparar lote · Texto extraído · Exportar*.

Há ainda uma inconsistência de documentação: `docs/design-brief.md` §7.8 afirma que "a
busca literal de keywords e o PDF grifado não dependem do modelo e funcionam mesmo assim".
Só a segunda metade é verdade — `GET /api/itens/{id}/anotado.pdf?keywords=a,b` funciona
offline; a tela, não.

## 2. O vocabulário que o produto passa a usar

Três camadas, distintas por **custo** e por **intenção de leitura**:

| Camada | O que é | Custo | Depende do Ollama |
|---|---|---|---|
| **Scan** | Varrer o texto atrás de termos específicos, ignorando o resto | milissegundos | não |
| **Skim** | Passar o olho pela estrutura para captar o essencial | milissegundos | não |
| **Leitura profunda** | O modelo lê o artigo inteiro e sintetiza | minutos | sim |

A camada do LLM **não** é chamada de skimming. Pelo custo e pela profundidade ela é leitura
profunda; vendê-la como leitura rápida seria enganoso para algo que leva meia hora num lote
de 5.

## 3. Requisitos

### R1 — Scan instantâneo e independente do modelo
- A busca literal de keywords deve estar disponível por uma rota própria, sem passar por
  `POST /api/analise` e sem qualquer chamada ao Ollama.
- O front deve exibir contagem, páginas, densidade por mil palavras e os trechos com o termo
  destacado **assim que o PDF é enviado e as keywords informadas** — antes de qualquer
  análise.
- Com o Ollama fora do ar, o Scan continua funcionando por inteiro.
- Quando a leitura profunda terminar, a síntese do modelo é **acrescentada** ao Scan já
  exibido, não o substitui.

### R2 — Skim mecânico, sem modelo
- Um módulo novo em `analisador/`, puro (sem HTTP, sem LLM, sem I/O), que produz uma leitura
  rápida a partir do `Documento` já extraído.
- O skim deve conter, no mínimo:
  - o título do artigo e os títulos de seção detectados;
  - o primeiro parágrafo de cada seção;
  - a primeira e a última frase dos demais parágrafos de cada seção;
  - as frases que contêm números (dados, percentuais, medidas);
  - as frases com marcadores de conclusão ("concluímos", "os resultados mostram",
    "portanto", "conclui-se", "em suma", e equivalentes em inglês).
- Cada item do skim carrega a **página** de onde veio, para manter a rastreabilidade que é a
  promessa central do produto.
- Disponível por rota própria, exibido no upload.

### R3 — Nomear as camadas na interface
- As abas passam a ser nomeadas por intenção de leitura, não por artefato.
- Uma nota curta na interface explica o que cada modo faz e quando usar — o produto ensina o
  método, não só entrega o resultado.
- O número de abas não deve aumentar (hoje são 6; o design-brief §8.7 pede menos, não mais).

### R4 — Documentação coerente com o código
- `docs/design-brief.md` §7.8 corrigido para descrever o comportamento real.
- `README.md` e `docs/proximos-passos.md` atualizados ao fim da implementação.

## 4. Não-objetivos

Fora do escopo desta spec, ainda que citados em `docs/proximos-passos.md`:

- Precisão de página nos achados (§2 do proximos-passos) — trabalho de prompt, independente.
- Visualizador de PDF grifado embutido, persistência do lote, OCR, estimativa de tempo
  restante, hifenização no grifo.
- Qualquer mudança nos prompts ou na estratégia map/reduce de `analisador/analise.py`.
- Redesenho visual (paleta, tipografia, layout da barra lateral).

## 5. Restrições globais

Valem para todas as tarefas do plano:

- **Python 3.10+**. Sem novas dependências: `requirements.txt` só contém o necessário para
  rodar, e é ele que entra na imagem Docker.
- **O núcleo não conhece HTTP e a API não conhece PDF.** Código novo em `analisador/` não
  importa nada de `servidor/` nem de `fastapi`.
- **Nenhuma chamada ao Ollama** em Scan ou Skim — nem opcional, nem com fallback.
- **Front sem framework e sem etapa de build**: só `web/index.html`, `web/estilo.css`,
  `web/app.js`, com as APIs nativas do navegador.
- **Testes offline**, sem rede e sem navegador, no padrão já existente em `tests/`.
- **Código e nomes em português**, seguindo a convenção do projeto (`buscar_varias`,
  `desenharKeywords`, `Ocorrencia`). Textos de UI **com** acentuação, como em
  `web/index.html`.
- Toda passagem exibida ao usuário carrega o número da página.

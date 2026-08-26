# Esboço — Artigo para Mostra de Iniciação Científica (Cesuca)

**Autores:** Eduardo Mello Garcia, José Vitor Guilhem Garcia
**Curso:** Ciência da Computação
**Artefato:** Grifo — leitura assistida de PDFs acadêmicos
**Método:** Design Science Research (Peffers et al., 2007 — DSRM em 6 atividades)

Fontes internas usadas como base factual: `README.md`, `docs/design-brief.md`,
`docs/spec-skimming-scanning.md`.

---

## 1. Introdução

- Contexto: volume crescente de literatura científica que um discente precisa
  processar em revisões de literatura; leitura integral de tudo não escala.
- Skimming e scanning como técnicas clássicas de leitura acadêmica — o
  discente já as usa manualmente, mas sem apoio de ferramenta.
- Lacuna: ferramentas de IA para PDFs em geral colapsam tudo em "resumo
  automático", sem distinguir varredura rápida (segundos) de leitura
  aprofundada (minutos) — e sem manter rastreabilidade até o trecho original.
- Pergunta de pesquisa / objetivo: como projetar um artefato que ofereça
  skimming e scanning como camadas de leitura independentes, instantâneas e
  rastreáveis, dissociadas do custo computacional de uma síntese por modelo
  de linguagem?
- Contribuição do artigo: relatar, sob a ótica de DSR, o ciclo de
  diagnóstico → requisitos → decisão arquitetural que reestruturou o Grifo
  nesse sentido.

## 2. Referencial teórico

### 2.1 Skimming e scanning como técnicas de leitura
- Definições canônicas: skimming (varredura estrutural em busca do
  essencial — título, seções, aberturas de parágrafo, conclusões) vs.
  scanning (busca literal por termos específicos, ignorando o resto).
- Por que são tratadas como técnicas distintas na pedagogia da leitura
  (propósitos de leitura diferentes: visão geral vs. localização de
  informação).
- Papel de cada técnica na leitura acadêmica: scanning para triagem de
  relevância (o termo aparece no artigo?), skimming para decisão de
  aprofundamento (vale a pena ler por inteiro?).

### 2.2 Leitura automática por modelos de linguagem — por que não é skimming
- Custo: um SLM local processando um artigo inteiro leva minutos, não
  segundos — descasa da própria definição de leitura rápida.
- Diferença de natureza: síntese interpretativa (o modelo "entende" e
  reformula) vs. operação mecânica sobre a estrutura do texto (skim) ou
  correspondência literal (scan).
- Por isso o artigo trata a leitura via LLM como uma terceira categoria —
  "leitura profunda" — e não como uma forma de skimming.

### 2.3 Design Science Research
- DSR como método para pesquisa que produz e avalia artefatos que resolvem
  problemas organizacionais/práticos.
- DSRM (Peffers et al., 2007): as 6 atividades — identificação do problema,
  definição de objetivos, design e desenvolvimento, demonstração, avaliação,
  comunicação — e como este artigo mapeia cada uma a uma seção.

## 3. Metodologia

- Enquadramento do artigo como relato de um ciclo DSR já executado no
  desenvolvimento do Grifo (não um ciclo conduzido especificamente para o
  artigo).
- Fonte de evidência: diagnóstico de código (`spec-skimming-scanning.md`,
  levantado em 26/08/2026) e documentação de produto (`design-brief.md`).
- Tabela mapeando as 6 atividades do DSRM às seções 4–7 deste artigo.

## 4. O artefato: Grifo

### 4.1 Visão geral
- O que é: aplicação web local, processamento 100% na máquina do usuário
  (extração em Python + SLM via Ollama), até 5 PDFs por sessão.
- Usuário-alvo: pesquisador/discente fazendo revisão de literatura — lê
  muito, tem pouco tempo, desconfia de resumo automático.
- Promessa central do produto: velocidade sem perder rastreabilidade — toda
  síntese vem colada ao trecho original com número de página.

### 4.2 Identificação do problema (diagnóstico)
- Estado anterior: scanning só existia embutido em `POST /api/analise`,
  refém de uma chamada ao Ollama — sem modelo rodando, o usuário não recebia
  nem uma contagem de keyword, apesar de a busca ser regex sobre string.
- Não existia skimming algum: "o essencial" só era produzido pelo SLM, a um
  custo de minutos.
- Sintoma de interface: abas nomeadas por artefato de dado ("Keywords",
  "Visão geral"), não por intenção de leitura — o produto não ensinava o
  método que ele mesmo executava.
- Inconsistência documentada entre o que a documentação afirmava (busca
  literal funciona offline) e o comportamento real da tela (não funcionava).

### 4.3 Objetivos da solução
- Desacoplar scan e skim de qualquer chamada ao modelo — devem ser
  determinísticos e funcionar com o Ollama fora do ar.
- Nomear as camadas por intenção de leitura, não por artefato técnico.
- Preservar a rastreabilidade (página de origem) em todas as camadas.

### 4.4 Design e desenvolvimento — arquitetura em três camadas
- Tabela das três camadas por custo e dependência: Scan (ms, sem modelo),
  Skim (ms, sem modelo), Leitura profunda (minutos, com modelo).
- Requisitos que operacionalizam a separação:
  - **R1** — Scan instantâneo por rota própria, disponível antes de
    qualquer análise, funcional com Ollama offline.
  - **R2** — Skim mecânico como módulo puro em `analisador/` (sem HTTP, sem
    LLM), com regras determinísticas: título e seções, primeiro parágrafo
    de cada seção, primeira/última frase dos demais parágrafos, frases com
    dados numéricos, frases com marcadores de conclusão — cada item com
    página de origem.
  - **R3** — Interface renomeada por intenção (abas Skim / Scan / Leitura
    profunda), com nota curta explicando quando usar cada modo.
  - **R4** — Documentação corrigida para refletir o comportamento real.
- Restrições de projeto relevantes para a discussão: núcleo desacoplado de
  HTTP, zero dependências novas, nenhuma chamada ao Ollama em scan/skim
  nem como fallback.

## 5. Demonstração

- Cenário de uso narrado: um discente sobe um PDF, informa keywords —
  recebe scan (contagem, páginas, densidade, trechos destacados) e skim
  (estrutura, aberturas de seção, frases-chave) em milissegundos, antes de
  decidir se vale disparar a leitura profunda.
- Uso dos dados reais do artigo de exemplo do projeto (telemedicina e
  adesão ao tratamento) para ilustrar as três camadas lado a lado.
- Ênfase no ponto pedagógico: o discente decide onde investir tempo de
  leitura profunda com base num scan/skim que não custou nada de espera.

## 6. Avaliação

- Escolha metodológica: avaliação por rastreamento de requisitos (evidência
  de que R1–R4 foram satisfeitos), não avaliação empírica com usuários —
  registrado como limitação e trabalho futuro na seção 8.
- Tabela requisito × evidência, por exemplo:
  - R1 → rota própria de scan responde sem chamar `POST /api/analise`;
    scan permanece funcional com Ollama desligado.
  - R2 → módulo de skim não importa `servidor/` nem `fastapi`; roda em
    teste offline sem rede.
  - R3 → abas da interface renomeadas; nota explicativa presente.
  - R4 → `design-brief.md` §7.8 corrigido; `README.md` atualizado.
- Discussão honesta do que essa avaliação cobre (a solução foi implementada
  conforme especificado) e do que não cobre (não mede ganho de tempo ou
  compreensão do discente).

## 7. Discussão

- Como a separação em camadas otimiza o estudo do discente:
  - Custo zero de espera para a etapa de triagem (scan/skim) — decisão de
    aprofundar ou descartar um artigo não compete mais com o tempo de
    inferência do modelo.
  - Rastreabilidade (página de origem) em toda camada reduz o custo de
    verificação — o discente confere a fonte sem procurar manualmente.
  - Separação nomeada ensina o método: a interface comunica quando usar
    scan (localizar termo) vs. skim (decidir se lê) vs. leitura profunda
    (ler de fato), reforçando o uso consciente das técnicas.
- Relação de volta com a literatura de leitura (seção 2.1): o artefato
  operacionaliza scanning e skimming como funções computáveis, sem alterar
  a definição pedagógica das técnicas.

## 8. Considerações finais e trabalhos futuros

- Síntese da contribuição: relato de um ciclo DSR que reposicionou leitura
  automática por IA como uma terceira categoria (leitura profunda),
  preservando skimming e scanning como camadas rápidas e independentes.
- Limitações: ausência de avaliação empírica com usuários; precisão de
  página nos achados da leitura profunda ainda é trabalho de prompt em
  aberto (fora do escopo desta spec).
- Trabalhos futuros, ancorados nos não-objetivos já registrados no projeto:
  avaliação empírica com discentes (tempo até decisão, compreensão),
  visualizador de PDF grifado embutido, precisão de página nos achados.

## 9. Referências

### Skimming e scanning (seção 2.1)

- GRELLET, Françoise. **Developing Reading Skills: A Practical Guide to
  Reading Comprehension Exercises**. Cambridge: Cambridge University Press,
  1981. — Referência clássica que define skimming ("correr os olhos pelo
  texto para captar a ideia geral") e scanning ("percorrer o texto em busca
  de uma informação específica") e organiza exercícios progressivos entre
  as duas técnicas. Boa citação de abertura da seção 2.1.
- NUTTALL, Christine. **Teaching Reading Skills in a Foreign Language**. 2.
  ed. Oxford: Macmillan Heinemann, 1996. — Trata skimming como "leitura
  pelo sentido geral" e scanning como "leitura por informação específica",
  com foco em estratégias de ensino; útil para justificar por que as duas
  técnicas têm propósitos de leitura diferentes (seção 2.1).
- SOLÉ, Isabel. **Estratégias de leitura**. Porto Alegre: Artmed, 1998. —
  Referência em português sobre estratégias de leitura e formação do leitor
  autônomo; reforça a seção 2.1 com uma fonte não anglófona, adequada a um
  artigo em português.

### Design Science Research (seção 2.2 e 3)

- PEFFERS, K.; TUUNANEN, T.; ROTHENBERGER, M.; CHATTERJEE, S. A design
  science research methodology for information systems research.
  **Journal of Management Information Systems**, v. 24, n. 3, p. 45-77,
  2007. DOI: 10.2753/MIS0742-1222240302. — Fonte do DSRM em 6 atividades
  usado como espinha dorsal do artigo (seções 3 a 8).
- HEVNER, A. R.; MARCH, S. T.; PARK, J.; RAM, S. Design science in
  information systems research. **MIS Quarterly**, v. 28, n. 1, p. 75-105,
  2004. DOI: 10.2307/25148625. — Citação de apoio/contraste sobre os
  fundamentos de DSR (guidelines e ciclos de relevância/rigor), útil na
  seção 2.2 para situar o DSRM dentro do campo.

### Fontes primárias do projeto

- Documentação interna como evidência de design: `spec-skimming-scanning.md`
  e `design-brief.md` (usadas nas seções 4, 6 e 7).

---

## Pontos em aberto (não resolvidos neste esboço)

- Template/limite de páginas exato do edital da Mostra Cesuca — ainda não
  verificado.
- Confirmar acesso aos textos completos de Grellet (1981) e Nuttall (1996)
  — livros impressos/fora de catálogo; verificar se a biblioteca do Cesuca
  ou um repositório acadêmico tem cópia acessível antes de citar trechos
  específicos (as buscas retornaram apenas resumos e digitalizações de
  terceiros, não a fonte oficial).

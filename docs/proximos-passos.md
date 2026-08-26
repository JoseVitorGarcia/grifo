# Próximos passos

Itens levantados e ainda não implementados, em ordem de impacto. Nada aqui está no código
hoje — o que está pronto é o que o `README.md` descreve.

_Concluído e removido desta lista: a retirada da pergunta livre ao modelo (a aba
"Perguntar"), feita em 19/08/2026._

---

## 1. Enquadrar o produto em skimming e scanning

**A ideia.** O projeto já faz, na prática, as duas técnicas clássicas de leitura rápida —
mas sem nomeá-las e sem separá-las. Nomear dá espinha dorsal à interface e ao roteiro de
uso:

| Técnica | O que é | O que já existe no projeto |
|---|---|---|
| **Scanning** | Varrer o texto atrás de uma informação específica, ignorando o resto | A busca literal de keywords: contagem, páginas, densidade, trechos com o termo destacado e o PDF grifado |
| **Skimming** | Passar o olho para captar o essencial sem ler tudo | O resumo estruturado, os achados com evidência e as limitações |

**Por que separar importa.** Scanning é **determinístico e instantâneo** — não depende do
modelo. Skimming, do jeito que está hoje, depende: são minutos de inferência em CPU. Essa
diferença de custo está escondida do usuário, que espera igual pelos dois.

**O que fazer:**

1. **Separar os dois momentos na interface.** Ao enviar o PDF, entregar *na hora* o que é
   scanning puro: metadados, seções detectadas, ocorrências das keywords, PDF grifado. A
   análise do modelo entra depois, como camada de skimming, sem bloquear o resto. Isso
   resolve de uma vez o problema nº 2 do `design-brief.md` ("a espera é longa e o feedback
   é uma barra de progresso").
2. **Criar um skimming sem modelo.** Técnicas de skimming são mecânicas e cabem em código:
   título e subtítulos, primeira e última frase de cada parágrafo, primeiro parágrafo de
   cada seção, frases com números e com marcadores de conclusão ("concluímos", "os
   resultados mostram", "portanto"). Isso dá uma leitura rápida **em milissegundos**, útil
   por si só e ótima como preview enquanto o `gemma3:4b` trabalha. A conversão para
   Markdown já entrega a estrutura necessária.
3. **Nomear na UI.** Rotular as abas e o vocabulário do produto com os termos que o usuário
   de revisão de literatura já conhece: *Skim* (o essencial), *Scan* (achar termos),
   *Leitura profunda* (a análise do modelo). Hoje as abas são nomeadas por artefato
   ("Resumo", "Keywords"), não por intenção de leitura.
4. **Documentar a técnica.** Uma nota curta na interface explicando o que cada modo faz e
   quando usar — o produto ensina o método, não só entrega o resultado.

**Impacto colateral:** o item 2 torna a aplicação útil mesmo com o Ollama fora do ar, o que
hoje não acontece.

---

## 2. Precisão de página nos achados

**O problema, observado em execução real com o `gemma3:4b`:** os achados voltam com
`pagina: "1-3"` quando o artigo inteiro cabe num bloco. A página fica imprecisa demais para
ser útil, e o grifo da evidência precisa varrer as três páginas.

**Por que acontece:** o prompt de `_notas_do_bloco` manda o modelo anotar cada ponto com o
rótulo do bloco (`- [p. 1-3] ponto`), e `extrair_achados` pede "a página indicada entre
colchetes nas notas". O Markdown já carrega `<!-- p. N -->` marcando cada página **dentro**
do bloco, mas nenhum prompt manda usar isso.

**O que fazer:** trocar a instrução para pedir a página do comentário `<!-- p. N -->` mais
próximo do trecho, em vez do rótulo do bloco. São ~2 linhas de prompt, mais um teste, mais
uma verificação com o modelo real para confirmar que ele obedece (o modelo é pequeno; pode
ignorar a instrução, e nesse caso o fallback para o rótulo do bloco deve continuar valendo).

---

## 3. Outros itens já levantados

Do `design-brief.md`, seção "o que o design precisa resolver":

- **Visualizador do PDF grifado embutido** na página, em vez de só o botão de download — o
  backend já devolve o PDF anotado.
- **Comparação entre artigos mais visível**: é o motivo principal do modo lote e está na
  quarta aba.
- **Estimativa de tempo restante** na fila de análise: o tempo por bloco é conhecido.
- **Tela vazia sem discurso**: não comunica lote, rastreabilidade nem execução local.
- **Síntese e evidência lado a lado**, com a página clicável levando ao texto extraído.

Da operação:

- **Persistir o lote** (hoje vive em memória; reiniciar o container zera).
- **OCR para PDFs digitalizados** (`ocrmypdf`/`tesseract`), hoje apenas avisados.
- **Palavra quebrada por hífen** não é localizada pelo grifo no PDF original.

# Próximos passos

Itens levantados e ainda não implementados, em ordem de impacto. Nada aqui está no código
hoje — o que está pronto é o que o `README.md` descreve.

_Concluído e removido desta lista: a retirada da pergunta livre ao modelo (a aba
"Perguntar"), feita em 19/08/2026; o enquadramento do produto em skimming e scanning,
feito em 26/08/2026 (spec em `docs/spec-skimming-scanning.md`, plano em
`docs/superpowers/plans/2026-08-26-skimming-scanning.md`)._

---

## 1. Precisão de página nos achados

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

## 2. Outros itens já levantados

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

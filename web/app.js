/* Analisador de Artigos — front sem framework nem build.
   Conversa com a API em /api e desenha tudo com DOM puro. */

'use strict';

const OPCOES_CTX = [2048, 4096, 8192, 16384, 32768];

const estado = {
  limite: 5,
  itens: [],          // {id, nome, titulo, analisado, documento}
  detalhes: {},       // id -> objeto completo com analise
  scan: {},           // id -> {keywords: [...]} vindo de /scan, sem LLM
  skims: {},          // id -> leitura rapida mecanica, sem LLM
  atual: null,
  comparacao: null,
  analisando: false,
};

const $ = (selecao) => document.querySelector(selecao);
const $$ = (selecao) => Array.from(document.querySelectorAll(selecao));

function elemento(tag, atributos = {}, filhos = []) {
  const no = document.createElement(tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (valor === null || valor === undefined || valor === false) continue;
    if (chave === 'class') no.className = valor;
    else if (chave === 'texto') no.textContent = valor;
    else if (chave === 'html') no.innerHTML = valor;
    else if (chave.startsWith('on')) no.addEventListener(chave.slice(2), valor);
    else no.setAttribute(chave, valor);
  }
  for (const filho of [].concat(filhos)) {
    if (filho) no.append(filho.nodeType ? filho : document.createTextNode(filho));
  }
  return no;
}

function escapar(texto) {
  return String(texto ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/** Converte o **destaque** que o backend coloca no trecho em <mark>. */
function comDestaque(trecho) {
  return escapar(trecho).replace(/\*\*(.+?)\*\*/g, '<mark>$1</mark>');
}

const numero = (valor) => Number(valor || 0).toLocaleString('pt-BR');

// ---------------------------------------------------------------- API

async function api(caminho, opcoes = {}) {
  const resposta = await fetch(caminho, { credentials: 'same-origin', ...opcoes });
  if (!resposta.ok) {
    let detalhe = `HTTP ${resposta.status}`;
    try { detalhe = (await resposta.json()).erro || detalhe; } catch (_) { /* corpo nao-JSON */ }
    throw new Error(detalhe);
  }
  return resposta.json();
}

function conexao() {
  return {
    url: $('#url').value.trim(),
    modelo: $('#modelo').value,
    temperatura: Number($('#temperatura').value),
    num_ctx: OPCOES_CTX[Number($('#num-ctx').value)],
  };
}

/** Consome um endpoint SSE, chamando `aoEvento` para cada evento recebido. */
async function fluxoSSE(caminho, corpo, aoEvento) {
  const resposta = await fetch(caminho, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(corpo),
  });
  if (!resposta.ok || !resposta.body) throw new Error(`HTTP ${resposta.status}`);

  const leitor = resposta.body.getReader();
  const decodificador = new TextDecoder();
  let restante = '';
  while (true) {
    const { done, value } = await leitor.read();
    if (done) break;
    restante += decodificador.decode(value, { stream: true });
    const partes = restante.split('\n\n');
    restante = partes.pop();
    for (const parte of partes) {
      const linha = parte.split('\n').find((l) => l.startsWith('data: '));
      if (linha) aoEvento(JSON.parse(linha.slice(6)));
    }
  }
}

// ---------------------------------------------------------------- estado do Ollama

async function verificarOllama() {
  const alvo = $('#estado-ollama');
  alvo.className = 'estado';
  alvo.textContent = 'verificando…';
  try {
    const dados = await api(`/api/status?url=${encodeURIComponent($('#url').value)}&modelo=${encodeURIComponent($('#modelo').value || '')}`);
    const seletor = $('#modelo');
    const escolhido = seletor.value;
    seletor.replaceChildren(...(dados.modelos.length ? dados.modelos : [dados.modelo])
      .map((nome) => elemento('option', { value: nome, texto: nome })));
    seletor.value = dados.modelos.includes(escolhido) ? escolhido : dados.modelo;
    alvo.textContent = dados.mensagem;
    alvo.classList.add(dados.ok ? 'ok' : 'ruim');
  } catch (erro) {
    alvo.textContent = `Falha ao consultar o servidor: ${erro.message}`;
    alvo.classList.add('ruim');
  }
}

// ---------------------------------------------------------------- lote

function desenharLote(vagas) {
  const total = estado.itens.length;
  $('#medidor-lote').style.width = `${(total / estado.limite) * 100}%`;
  $('#contador-lote').textContent = `${total}/${estado.limite} PDFs nesta sessão`;
  $('#vagas-texto').textContent = `${vagas ?? estado.limite - total} vaga(s) restante(s) · somente .pdf`;
  $('#btn-limpar').classList.toggle('oculto', total === 0);
  $('#area-keywords').classList.toggle('oculto', total === 0);

  $('#lista-arquivos').replaceChildren(...estado.itens.map((item) =>
    elemento('li', {}, [
      elemento('span', { texto: item.analisado ? '✅' : '⏳' }),
      elemento('span', { texto: item.nome, title: item.titulo }),
      elemento('button', {
        title: 'Remover do lote', texto: '×',
        onclick: () => removerItem(item.id),
      }),
    ])));

  const pendentes = estado.itens.filter((i) => !i.analisado).length;
  $('#btn-analisar').textContent = pendentes
    ? `Leitura profunda — ${pendentes} pendente(s)`
    : 'Nada pendente';
  $('#btn-analisar').disabled = pendentes === 0 || estado.analisando;
  $('#btn-reanalisar').disabled = total === 0 || estado.analisando;
  $('#area-resultado').classList.toggle('oculto', total === 0);
  desenharSeletor();
}

async function carregarLote() {
  const dados = await api('/api/pdfs');
  estado.limite = dados.limite;
  estado.itens = dados.itens;
  $('#limite-texto').textContent = dados.limite;
  if (!estado.atual && dados.itens.length) estado.atual = dados.itens[0].id;
  desenharLote(dados.vagas);
  if (estado.atual) await abrirArtigo(estado.atual);
}

async function enviarArquivos(arquivos) {
  const pdfs = Array.from(arquivos).filter((a) => a.type === 'application/pdf' || a.name.toLowerCase().endsWith('.pdf'));
  if (!pdfs.length) return;

  const formulario = new FormData();
  pdfs.forEach((arquivo) => formulario.append('arquivos', arquivo));
  $('#avisos-envio').replaceChildren(elemento('li', { class: 'info', texto: 'Extraindo o texto…' }));

  try {
    const dados = await api('/api/pdfs', { method: 'POST', body: formulario });
    $('#avisos-envio').replaceChildren(...dados.recusados.map((r) =>
      elemento('li', {
        class: r.motivo.includes('limite') ? 'erro' : 'info',
        texto: `${r.nome} — ${r.motivo}`,
      })));
    if (dados.itens.length && !estado.atual) estado.atual = dados.itens[0].id;
    await carregarLote();
  } catch (erro) {
    $('#avisos-envio').replaceChildren(elemento('li', { class: 'erro', texto: `Falha no envio: ${erro.message}` }));
  }
}

async function removerItem(id) {
  await api(`/api/pdfs/${id}`, { method: 'DELETE' });
  delete estado.detalhes[id];
  if (estado.atual === id) estado.atual = null;
  await carregarLote();
}

// ---------------------------------------------------------------- analise

async function analisar(reanalisar) {
  if (estado.analisando) return;
  estado.analisando = true;
  desenharLote();

  const fila = $('#area-fila');
  fila.classList.remove('oculto');
  fila.replaceChildren();
  const cartoes = {};

  const corpo = {
    ...conexao(),
    keywords: $('#keywords').value,
    flexivel: $('#flexivel').checked,
    reanalisar,
    tamanho_bloco: Number($('#tamanho-bloco').value),
    max_blocos: Number($('#max-blocos').value),
    etapas: Object.fromEntries($$('[data-etapa]').map((c) => [c.dataset.etapa, c.checked])),
  };

  const aoEvento = (evento) => {
    if (evento.tipo === 'erro') {
      fila.append(elemento('div', { class: 'erro-bloco', texto: evento.mensagem }));
      return;
    }
    if (evento.tipo === 'artigo_inicio') {
      const etapa = elemento('p', { class: 'fila-etapa', texto: 'preparando…' });
      const preenchida = elemento('div', { class: 'barra-preenchida', style: 'width:0' });
      const cartao = elemento('div', { class: 'fila-item' }, [
        elemento('div', { class: 'fila-topo' }, [
          elemento('b', { texto: evento.nome }),
          elemento('span', { class: 'sutil', texto: `${evento.posicao}/${evento.total}` }),
        ]),
        etapa,
        elemento('div', { class: 'barra-trilho' }, [preenchida]),
      ]);
      cartoes[evento.id] = { cartao, etapa, preenchida };
      fila.append(cartao);
      return;
    }
    const alvo = cartoes[evento.id];
    if (evento.tipo === 'progresso' && alvo) {
      alvo.etapa.textContent = evento.etapa;
      alvo.preenchida.style.width = `${Math.round(evento.fracao * 100)}%`;
    }
    if (evento.tipo === 'artigo_fim') {
      estado.detalhes[evento.id] = evento.dados;
      const item = estado.itens.find((i) => i.id === evento.id);
      if (item) item.analisado = true;
      if (alvo) {
        alvo.cartao.classList.add('ok');
        alvo.preenchida.style.width = '100%';
        alvo.etapa.textContent = evento.erros?.length
          ? `concluído com ${evento.erros.length} etapa(s) com erro`
          : 'concluído';
      }
      estado.comparacao = null;
      if (!estado.atual || estado.atual === evento.id) {
        estado.atual = evento.id;
        desenharArtigo();
      }
      desenharLote();
    }
    if (evento.tipo === 'artigo_erro' && alvo) {
      alvo.cartao.classList.add('falhou');
      alvo.etapa.textContent = `falhou: ${evento.mensagem}`;
    }
    if (evento.tipo === 'fim') {
      const minutos = ((evento.segundos || 0) / 60).toFixed(1);
      fila.append(elemento('p', {
        class: 'sutil',
        texto: evento.aviso || `Lote concluído: ${evento.analisados} artigo(s) em ${minutos} min.`,
      }));
    }
  };

  try {
    await fluxoSSE('/api/analise', corpo, aoEvento);
  } catch (erro) {
    fila.append(elemento('div', { class: 'erro-bloco', texto: `Falha na análise: ${erro.message}` }));
  } finally {
    estado.analisando = false;
    await carregarLote();
  }
}

// ---------------------------------------------------------------- artigos

function desenharSeletor() {
  const alvo = $('#seletor-artigos');
  alvo.classList.toggle('oculto', estado.itens.length < 2);
  alvo.replaceChildren(...estado.itens.map((item) =>
    elemento('button', {
      class: item.id === estado.atual ? 'ativa' : '',
      texto: `${item.analisado ? '✅' : '⏳'} ${item.nome}`,
      onclick: () => abrirArtigo(item.id),
    })));
}

async function abrirArtigo(id) {
  estado.atual = id;
  if (!estado.detalhes[id]) {
    try { estado.detalhes[id] = await api(`/api/itens/${id}`); } catch (_) { return; }
  }
  await carregarScan(id);
  await carregarSkim(id);
  desenharSeletor();
  desenharArtigo();
}

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

/** Leitura rapida mecanica. Como o scan, roda sem o modelo. */
async function carregarSkim(id) {
  if (estado.skims[id]) return;  // o skim nao muda com as keywords
  try {
    estado.skims[id] = (await api(`/api/itens/${id}/skim`)).skim;
  } catch (_) { /* sem skim a aba mostra so os metadados */ }
}

function artigoAtual() {
  return estado.detalhes[estado.atual];
}

function desenharArtigo() {
  const dado = artigoAtual();
  if (!dado) return;
  desenharSkim(dado);
  desenharLeitura(dado);
  desenharScan(dado);
  desenharTexto(dado);
  desenharExportar(dado);
  desenharComparacao();
}

function desenharSkim(dado) {
  const doc = dado.documento;
  const meta = doc.metadados || {};
  const filhos = [
    elemento('h3', { class: 'titulo-artigo', texto: meta.titulo || dado.nome }),
    meta.autores ? elemento('p', { class: 'autoria', texto: meta.autores }) : null,
    elemento('div', { class: 'metricas' }, [
      metrica('Páginas', numero(doc.paginas)),
      metrica('Palavras', numero(doc.palavras)),
      metrica('Leitura', `${doc.minutos_de_leitura} min`),
      metrica('Referências', meta.referencias_estimadas || '—'),
    ]),
  ];

  if (doc.secoes?.length) {
    filhos.push(elemento('p', { class: 'sutil', html: `<b>Seções detectadas:</b> ${escapar(doc.secoes.join(' · '))}` }));
  }
  if (meta.doi) {
    filhos.push(elemento('p', { class: 'sutil', html: `<b>DOI:</b> <a href="https://doi.org/${escapar(meta.doi)}" target="_blank" rel="noreferrer">${escapar(meta.doi)}</a>` }));
  }
  if (meta.keywords_pdf) {
    filhos.push(elemento('p', { class: 'sutil', html: `<b>Keywords declaradas no PDF:</b> ${escapar(meta.keywords_pdf)}` }));
  }
  const sugeridas = dado.analise?.keywords_sugeridas || [];
  if (sugeridas.length) {
    filhos.push(elemento('h3', { class: 'secao', texto: 'Termos-chave sugeridos pelo modelo' }));
    filhos.push(elemento('div', { class: 'etiquetas' },
      sugeridas.map((k) => elemento('span', { class: 'etiqueta', texto: k }))));
  }
  (doc.avisos || []).forEach((aviso) =>
    filhos.push(elemento('div', { class: 'aviso-extracao', texto: aviso })));
  (dado.analise?.erros || []).forEach((erro) =>
    filhos.push(elemento('div', { class: 'erro-bloco', texto: erro })));

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

  $('#painel-skim').replaceChildren(...filhos.filter(Boolean));
}

function metrica(rotulo, valor) {
  return elemento('div', { class: 'metrica' }, [
    elemento('span', { texto: rotulo }),
    elemento('b', { texto: String(valor) }),
  ]);
}

const ROTULOS_RESUMO = {
  objetivo: 'Objetivo', metodologia: 'Metodologia', resultados: 'Resultados',
  conclusao: 'Conclusão', relevancia: 'Relevância',
};

function desenharLeitura(dado) {
  const analise = dado.analise;
  const alvo = $('#painel-leitura');
  if (!analise) {
    alvo.replaceChildren(elemento('p', { class: 'sutil', texto: 'Artigo ainda não analisado.' }));
    return;
  }
  const filhos = [];

  if (Object.keys(analise.resumo || {}).length) {
    filhos.push(elemento('h3', { class: 'secao', texto: 'Resumo estruturado' }));
    for (const [chave, rotulo] of Object.entries(ROTULOS_RESUMO)) {
      if (!analise.resumo[chave]) continue;
      filhos.push(elemento('div', { class: 'campo-resumo' }, [
        elemento('b', { texto: rotulo }),
        elemento('span', { texto: analise.resumo[chave] }),
      ]));
    }
  }

  if (analise.achados?.length) {
    filhos.push(elemento('h3', { class: 'secao', texto: 'Principais achados' }));
    analise.achados.forEach((achado, indice) => {
      filhos.push(elemento('div', { class: 'achado' }, [
        elemento('div', {}, [
          elemento('b', { texto: `${indice + 1}. ${achado.afirmacao}` }),
          achado.pagina ? elemento('span', { class: 'pagina', texto: ` (p. ${achado.pagina})` }) : null,
        ]),
        achado.evidencia ? elemento('p', { class: 'evidencia', texto: achado.evidencia }) : null,
      ]));
    });
  }

  if (analise.limitacoes?.length) {
    filhos.push(elemento('h3', { class: 'secao', texto: 'Limitações e lacunas' }));
    analise.limitacoes.forEach((texto) => {
      const lacuna = /^lacuna:/i.test(texto);
      filhos.push(elemento('div', {
        class: `achado limitacao${lacuna ? ' lacuna' : ''}`,
      }, [elemento('span', { texto })]));
    });
  }

  alvo.replaceChildren(...(filhos.length ? filhos : [elemento('p', { class: 'sutil', texto: 'Nada gerado nesta execução.' })]));
}

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

  const tabela = elemento('table', {}, [
    elemento('thead', {}, [elemento('tr', {}, [
      elemento('th', { texto: 'Keyword' }),
      elemento('th', { class: 'numero', texto: 'Ocorrências' }),
      elemento('th', { texto: 'Páginas' }),
      elemento('th', { class: 'numero', texto: 'Por mil palavras' }),
    ])]),
    elemento('tbody', {}, keywords.map((k) => elemento('tr', {}, [
      elemento('td', { texto: k.keyword }),
      elemento('td', { class: 'numero', texto: numero(k.total) }),
      elemento('td', { texto: k.paginas.join(', ') || '—' }),
      elemento('td', { class: 'numero', texto: String(k.densidade_por_mil) }),
    ]))),
  ]);

  const filhos = [elemento('div', { class: 'tabela-rolavel' }, [tabela])];

  const porPagina = {};
  keywords.forEach((k) => k.ocorrencias.forEach((o) => {
    porPagina[o.pagina] = (porPagina[o.pagina] || 0) + 1;
  }));
  const paginas = Object.keys(porPagina).map(Number).sort((a, b) => a - b);
  if (paginas.length) {
    const maximo = Math.max(...Object.values(porPagina));
    filhos.push(elemento('h3', { class: 'secao', texto: 'Distribuição das ocorrências por página' }));
    filhos.push(elemento('div', { class: 'barras' }, paginas.map((pagina) =>
      elemento('div', { class: 'barra-linha' }, [
        elemento('span', { texto: `p. ${pagina}` }),
        elemento('div', { class: 'barra-trilho' }, [
          elemento('div', { class: 'barra-preenchida', style: `width:${(porPagina[pagina] / maximo) * 100}%` }),
        ]),
        elemento('span', { class: 'numero', texto: String(porPagina[pagina]) }),
      ]))));
  }

  keywords.forEach((k) => {
    const corpo = elemento('div', { class: 'keyword-corpo' }, [
      k.sintese
        ? elemento('p', { texto: k.sintese })
        : elemento('p', { class: 'sutil', texto: 'Síntese do modelo ainda não gerada — rode a leitura profunda.' }),
      k.ocorrencias.length ? elemento('p', { class: 'sutil', texto: 'Trechos no artigo:' }) : null,
      ...k.ocorrencias.map((o) => elemento('div', { class: 'trecho' }, [
        elemento('span', { class: 'fonte', texto: `p. ${o.pagina}${o.secao ? ` · ${o.secao}` : ''}` }),
        elemento('span', { html: comDestaque(o.trecho) }),
      ])),
    ].filter(Boolean));

    const topo = elemento('div', { class: 'keyword-topo', onclick: () => corpo.classList.toggle('oculto') }, [
      elemento('span', { texto: k.encontrada ? '✅' : '⚠️' }),
      elemento('h4', { texto: k.keyword }),
      elemento('span', { class: 'contagem', texto: `${k.total} ocorrência(s) · ${k.paginas.length} página(s)` }),
    ]);
    filhos.push(elemento('div', { class: `keyword-bloco${k.encontrada ? '' : ' ausente'}` }, [topo, corpo]));
  });

  alvo.replaceChildren(...filhos);
}

async function desenharComparacao() {
  const alvo = $('#painel-comparar');
  if (!estado.comparacao) {
    try { estado.comparacao = await api('/api/comparacao'); } catch (_) { return; }
  }
  const dados = estado.comparacao;
  const filhos = [elemento('h3', { class: 'secao', texto: 'Artigos do lote' })];

  if (dados.resumo?.length) {
    const colunas = Object.keys(dados.resumo[0]);
    filhos.push(elemento('div', { class: 'tabela-rolavel' }, [
      elemento('table', {}, [
        elemento('thead', {}, [elemento('tr', {}, colunas.map((c) => elemento('th', { texto: c })))]),
        elemento('tbody', {}, dados.resumo.map((linha) =>
          elemento('tr', {}, colunas.map((c) => elemento('td', { texto: String(linha[c]) }))))),
      ]),
    ]));
  }

  if (dados.comparacao?.length) {
    const colunas = Object.keys(dados.comparacao[0]);
    filhos.push(elemento('h3', { class: 'secao', texto: 'Ocorrências por artigo' }));
    filhos.push(elemento('p', { class: 'sutil', texto: 'Contagem literal no texto, sem participação do modelo.' }));
    filhos.push(elemento('div', { class: 'tabela-rolavel' }, [
      elemento('table', {}, [
        elemento('thead', {}, [elemento('tr', {}, colunas.map((c, i) =>
          elemento('th', { class: i ? 'numero' : '', texto: c })))]),
        elemento('tbody', {}, dados.comparacao.map((linha) =>
          elemento('tr', {}, colunas.map((c, i) =>
            elemento('td', { class: i ? 'numero' : '', texto: String(linha[c]) }))))),
      ]),
    ]));

    const ausentes = Object.entries(dados.ausentes || {});
    if (ausentes.length) {
      filhos.push(elemento('h3', { class: 'secao', texto: 'Keywords ausentes em algum artigo' }));
      ausentes.forEach(([keyword, arquivos]) => filhos.push(
        elemento('p', { class: 'sutil', html: `<b>${escapar(keyword)}</b> — ausente em: ${escapar(arquivos.join(', '))}` })));
    }
  } else {
    filhos.push(elemento('p', { class: 'sutil', texto: 'Analise ao menos um artigo para comparar as keywords.' }));
  }

  alvo.replaceChildren(...filhos);
}

function desenharTexto(dado) {
  const alvo = $('#painel-texto');
  const total = dado.documento.paginas;
  const seletor = elemento('input', { type: 'number', min: '1', max: String(total), value: '1' });
  const caixa = elemento('textarea', { class: 'texto-pagina', readonly: 'readonly' });
  const navegacao = elemento('div', { class: 'navegacao-pagina' }, [
    elemento('label', { texto: `Página (1–${total})` }), seletor,
  ]);
  const explicacao = elemento('p', { class: 'sutil' });

  let modo = 'cru';

  const carregarPagina = async () => {
    const pagina = Math.min(Math.max(1, Number(seletor.value) || 1), total);
    try {
      const dados = await api(`/api/itens/${dado.id}/pagina/${pagina}`);
      caixa.value = dados.texto || '(página sem texto extraído)';
    } catch (erro) {
      caixa.value = `Falha ao carregar a página: ${erro.message}`;
    }
  };

  const carregarMarkdown = async () => {
    caixa.value = 'carregando…';
    try {
      const dados = await api(`/api/itens/${dado.id}/markdown`);
      caixa.value = dados.markdown;
    } catch (erro) {
      caixa.value = `Falha ao carregar o Markdown: ${erro.message}`;
    }
  };

  const aplicarModo = () => {
    const markdown = modo === 'markdown';
    navegacao.classList.toggle('oculto', markdown);
    explicacao.textContent = markdown
      ? 'Este é exatamente o texto enviado ao modelo: títulos e listas remontados, linhas quebradas pelo PDF reunidas em parágrafos e a página marcada em comentário.'
      : 'Texto cru extraído do PDF, página a página. Confira aqui se a extração leu o arquivo corretamente.';
    $$('#seletor-visao button').forEach((b) => b.classList.toggle('ativa', b.dataset.modo === modo));
    return markdown ? carregarMarkdown() : carregarPagina();
  };

  const trocar = (novoModo) => { modo = novoModo; aplicarModo(); };
  const seletorVisao = elemento('nav', { class: 'seletor', id: 'seletor-visao' }, [
    elemento('button', { 'data-modo': 'cru', texto: 'Texto extraído', onclick: () => trocar('cru') }),
    elemento('button', { 'data-modo': 'markdown', texto: 'Markdown (o que o modelo lê)', onclick: () => trocar('markdown') }),
  ]);

  seletor.addEventListener('change', carregarPagina);
  alvo.replaceChildren(seletorVisao, explicacao, navegacao, caixa);
  aplicarModo();
}

function desenharExportar(dado) {
  const alvo = $('#painel-exportar');
  const base = `/api/itens/${dado.id}`;
  const analisados = estado.itens.filter((i) => i.analisado).length;
  // Leva as keywords digitadas junto: permite grifar mesmo sem ter analisado.
  const termos = `keywords=${encodeURIComponent($('#keywords').value)}`;

  const filhos = [
    elemento('h3', { class: 'secao', texto: 'PDF com marcações' }),
    elemento('p', { class: 'sutil', texto: 'O PDF original com as passagens grifadas como marca-texto. Abre marcado em qualquer leitor.' }),
    elemento('div', { class: 'grade-download' }, [
      elemento('a', { class: 'botao-download', href: `${base}/anotado.pdf?${termos}`, texto: '⬇️ PDF grifado (keywords + evidências)' }),
      elemento('a', { class: 'botao-download', href: `${base}/anotado.pdf?evidencias=false&${termos}`, texto: '⬇️ PDF grifado (só keywords)' }),
    ]),
    elemento('div', { class: 'legenda-grifo' }, [
      elemento('span', { html: '<i class="amostra keyword"></i> keyword — casamento literal' }),
      elemento('span', { html: '<i class="amostra evidencia"></i> evidência de achado — casada por similaridade' }),
    ]),
    elemento('h3', { class: 'secao', texto: 'Relatório deste artigo' }),
    elemento('div', { class: 'grade-download' }, [
      elemento('a', { class: 'botao-download', href: `${base}/relatorio.md`, texto: '⬇️ Markdown' }),
      elemento('a', { class: 'botao-download', href: `${base}/relatorio.json`, texto: '⬇️ JSON' }),
    ]),
    elemento('h3', { class: 'secao', texto: 'Artigo convertido' }),
    elemento('p', { class: 'sutil', texto: 'O PDF em Markdown, como o modelo o recebe — útil para reaproveitar em outra ferramenta.' }),
    elemento('div', { class: 'grade-download' }, [
      elemento('a', { class: 'botao-download', href: `${base}/markdown?download=true`, texto: '⬇️ Artigo em Markdown' }),
    ]),
  ];

  if (analisados > 1) {
    filhos.push(elemento('h3', { class: 'secao', texto: `Lote inteiro (${analisados} artigos analisados)` }));
    filhos.push(elemento('div', { class: 'grade-download' }, [
      elemento('a', { class: 'botao-download', href: '/api/lote/relatorio.md', texto: '⬇️ Consolidado em Markdown' }),
      elemento('a', { class: 'botao-download', href: '/api/lote/relatorio.json', texto: '⬇️ Consolidado em JSON' }),
    ]));
  }
  alvo.replaceChildren(...filhos);
}

// ---------------------------------------------------------------- ligacoes

function ligarEventos() {
  const solta = $('#solta');
  const campo = $('#arquivo');
  solta.addEventListener('click', () => campo.click());
  solta.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') campo.click(); });
  campo.addEventListener('change', () => { enviarArquivos(campo.files); campo.value = ''; });
  ['dragenter', 'dragover'].forEach((nome) => solta.addEventListener(nome, (e) => {
    e.preventDefault(); solta.classList.add('ativo');
  }));
  ['dragleave', 'drop'].forEach((nome) => solta.addEventListener(nome, (e) => {
    e.preventDefault(); solta.classList.remove('ativo');
  }));
  solta.addEventListener('drop', (e) => enviarArquivos(e.dataTransfer.files));

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

  $('#btn-analisar').addEventListener('click', () => analisar(false));
  $('#btn-reanalisar').addEventListener('click', () => analisar(true));
  $('#btn-limpar').addEventListener('click', async () => {
    await api('/api/pdfs', { method: 'DELETE' });
    estado.detalhes = {}; estado.atual = null; estado.comparacao = null;
    $('#area-fila').classList.add('oculto');
    await carregarLote();
  });
  $('#btn-reconsultar').addEventListener('click', verificarOllama);
  $('#url').addEventListener('change', verificarOllama);

  $$('.abas button').forEach((botao) => botao.addEventListener('click', () => {
    $$('.abas button').forEach((b) => b.classList.toggle('ativa', b === botao));
    $$('.painel').forEach((p) => p.classList.toggle('ativa', p.id === `painel-${botao.dataset.aba}`));
    if (botao.dataset.aba === 'comparar') { estado.comparacao = null; desenharComparacao(); }
  }));

  $('#temperatura').addEventListener('input', (e) => { $('#saida-temperatura').value = e.target.value; });
  $('#num-ctx').addEventListener('input', (e) => { $('#saida-ctx').value = OPCOES_CTX[Number(e.target.value)]; });
  $('#tamanho-bloco').addEventListener('input', (e) => { $('#saida-bloco').value = e.target.value; });
  $('#max-blocos').addEventListener('input', (e) => { $('#saida-blocos').value = e.target.value; });
}

async function iniciar() {
  ligarEventos();
  try {
    const config = await api('/api/config');
    estado.limite = config.limite_pdfs;
    $('#versao').textContent = `v${config.versao} · 100% local via Ollama`;
    $('#url').value = config.padroes.ollama_url;
    $('#temperatura').value = config.padroes.temperatura;
    $('#saida-temperatura').value = config.padroes.temperatura;
    $('#num-ctx').value = String(Math.max(0, OPCOES_CTX.indexOf(config.padroes.num_ctx)));
    $('#saida-ctx').value = config.padroes.num_ctx;
    $('#tamanho-bloco').value = config.padroes.tamanho_bloco;
    $('#saida-bloco').value = config.padroes.tamanho_bloco;
    $('#max-blocos').value = config.padroes.max_blocos;
    $('#saida-blocos').value = config.padroes.max_blocos;
  } catch (erro) {
    console.error('falha ao carregar a configuração', erro);
  }
  await verificarOllama();
  await carregarLote();
}

iniciar();

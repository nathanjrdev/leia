// API falsa para revisão visual: responde as rotas que a web usa com dados fictícios fixos,
// sem banco, sem LLM e sem rede. Não substitui o E2E (que usa a API real em MODO_TESTE);
// serve para ver todos os estados das telas (capas geradas, atraso, reserva pronta, chat com
// cartões e proposta) ao comparar o antes e o depois de uma mudança visual.
//
// Uso (em web/):
//   node scripts/api-falsa.mjs            # porta 8001
//   LEIA_API_URL=http://127.0.0.1:8001 npm run build && npm run start
import http from "node:http";

const PORTA = Number(process.env.PORTA ?? 8001);
const ATRASO_MS = Number(process.env.ATRASO_MS ?? 250);

const CONTA = { nome: "Leitora Demo", email: "demo@leia.example" };

const CATEGORIAS = [
  { slug: "romance", nome: "Romance" },
  { slug: "poesia", nome: "Poesia" },
  { slug: "contos", nome: "Contos" },
  { slug: "cronica", nome: "Crônica" },
];

const LIVROS = [
  { id: 1, titulo: "Dom Casmurro", autores: ["Machado de Assis"], ano: 1899, cat: "romance", livres: 2, fila: 0 },
  { id: 2, titulo: "Memórias Póstumas de Brás Cubas", autores: ["Machado de Assis"], ano: 1881, cat: "romance", livres: 1, fila: 0 },
  { id: 3, titulo: "Quincas Borba", autores: ["Machado de Assis"], ano: 1891, cat: "romance", livres: 0, fila: 2 },
  { id: 4, titulo: "Vidas Secas", autores: ["Graciliano Ramos"], ano: 1938, cat: "romance", livres: 3, fila: 0 },
  { id: 5, titulo: "Sagarana", autores: ["João Guimarães Rosa"], ano: 1946, cat: "contos", livres: 0, fila: 0 },
  { id: 6, titulo: "A Hora da Estrela", autores: ["Clarice Lispector"], ano: 1977, cat: "romance", livres: 1, fila: 0 },
  { id: 7, titulo: "Ou isto ou aquilo", autores: ["Cecília Meireles"], ano: 1964, cat: "poesia", livres: 2, fila: 0 },
  { id: 8, titulo: "Macunaíma: o herói sem nenhum caráter", autores: ["Mário de Andrade"], ano: 1928, cat: "romance", livres: 0, fila: 1 },
  { id: 9, titulo: "O Cortiço", autores: ["Aluísio Azevedo"], ano: 1890, cat: "romance", livres: 2, fila: 0 },
  { id: 10, titulo: "Iracema", autores: ["José de Alencar"], ano: 1865, cat: "romance", livres: 1, fila: 0 },
  { id: 11, titulo: "Triste Fim de Policarpo Quaresma", autores: ["Lima Barreto"], ano: 1915, cat: "romance", livres: 0, fila: 3 },
  { id: 12, titulo: "Antologia Poética", autores: ["Carlos Drummond de Andrade", "Organização fictícia"], ano: 1962, cat: "poesia", livres: 1, fila: 0 },
];

const item = (l) => ({
  id: l.id,
  titulo: l.titulo,
  autores: l.autores,
  ano: l.ano,
  capa_url: null,
  livres: l.livres,
  fila: l.fila,
});

const ficha = (l) => ({
  ...item(l),
  categorias: [CATEGORIAS.find((c) => c.slug === l.cat)?.nome ?? "Romance"],
  sinopse:
    l.id === 1
      ? "Bento Santiago, já velho, conta a própria vida para tentar entender a juventude ao lado de Capitu e a dúvida que nunca o deixou."
      : "Sinopse fictícia de demonstração: um parágrafo curto, do tamanho das sinopses reais do acervo, para conferir a medida da linha.",
  editora: "Editora Exemplo",
  paginas: 180 + l.id * 7,
  exemplares: Math.max(l.livres, 1) + 1,
});

const dia = (d) => new Date(Date.UTC(2026, 10, d, 12)).toISOString();

const resumo = (l) => ({
  livro_id: l.id,
  titulo: l.titulo,
  autores: l.autores,
  capa_url: null,
});

const ESTANTE = {
  ativas: [
    { locacao_id: 11, ...resumo(LIVROS[0]), retirada_em: dia(1), prevista_em: dia(15), devolvida_em: null, renovacoes: 0, atrasada: false },
    { locacao_id: 12, ...resumo(LIVROS[3]), retirada_em: dia(1), prevista_em: dia(8), devolvida_em: null, renovacoes: 1, atrasada: true },
  ],
  reservas: [
    { reserva_id: 21, ...resumo(LIVROS[2]), posicao: 1, pronta: true, retirar_ate: dia(14) },
    { reserva_id: 22, ...resumo(LIVROS[10]), posicao: 2, pronta: false, retirar_ate: null },
  ],
  historico: [
    { locacao_id: 31, ...resumo(LIVROS[6]), retirada_em: dia(2), prevista_em: dia(16), devolvida_em: dia(6), renovacoes: 0, atrasada: false },
    { locacao_id: 32, ...resumo(LIVROS[9]), retirada_em: dia(3), prevista_em: dia(17), devolvida_em: dia(9), renovacoes: 0, atrasada: false },
    { locacao_id: 33, ...resumo(LIVROS[8]), retirada_em: dia(4), prevista_em: dia(18), devolvida_em: dia(10), renovacoes: 0, atrasada: false },
  ],
};

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

function json(res, status, corpo) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(corpo === undefined ? "" : JSON.stringify(corpo));
}

async function sse(res, eventos) {
  res.writeHead(200, {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
  });
  for (const [evento, dados] of eventos) {
    res.write(`event: ${evento}\ndata: ${JSON.stringify(dados)}\n\n`);
    await esperar(ATRASO_MS);
  }
  res.end();
}

const livroDoChat = (l) => ({ id: l.id, titulo: l.titulo, autores: l.autores, capa_url: null, livres: l.livres });

function lerCorpo(req) {
  return new Promise((resolve) => {
    let b = "";
    req.on("data", (c) => (b += c));
    req.on("end", () => {
      try {
        resolve(b ? JSON.parse(b) : {});
      } catch {
        resolve({});
      }
    });
  });
}

function listar(url) {
  const q = (url.searchParams.get("q") ?? "").toLowerCase();
  const cat = url.searchParams.get("categoria");
  const so = url.searchParams.get("apenas_disponiveis") === "true";
  const limite = Number(url.searchParams.get("limite") ?? 20);
  const pagina = Number(url.searchParams.get("pagina") ?? 1);
  let itens = LIVROS.filter(
    (l) =>
      (!q || l.titulo.toLowerCase().includes(q) || l.autores.join(" ").toLowerCase().includes(q)) &&
      (!cat || l.cat === cat) &&
      (!so || l.livres > 0),
  );
  const total = itens.length;
  itens = itens.slice((pagina - 1) * limite, pagina * limite);
  return { itens: itens.map(item), total, pagina };
}

const servidor = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", "http://local");
  const p = url.pathname;
  const m = req.method ?? "GET";
  let r;

  if (p === "/health") return json(res, 200, { ok: true });
  if (p === "/auth/eu") return json(res, 200, CONTA);
  if (p === "/auth/logout") return json(res, 200, {});
  if (p === "/auth/login" || p === "/auth/cadastro") return json(res, 200, CONTA);
  if (p === "/categorias") return json(res, 200, CATEGORIAS);
  if (p === "/livros" || p === "/livros/busca") return json(res, 200, listar(url));
  if ((r = p.match(/^\/livros\/(\d+)$/))) {
    const l = LIVROS.find((x) => x.id === Number(r[1]));
    return l ? json(res, 200, ficha(l)) : json(res, 404, { erro: "nao_encontrado", mensagem: "Livro não encontrado." });
  }
  if (/^\/livros\/\d+\/locar$/.test(p)) return json(res, 200, { prevista_em: dia(25) });
  if (/^\/livros\/\d+\/reservar$/.test(p)) return json(res, 200, { posicao: 2 });
  if (p === "/estante") return json(res, 200, ESTANTE);
  if (/^\/(locacoes|reservas)\/\d+\/(renovar|devolver|cancelar)$/.test(p)) return json(res, 200, {});
  if (p === "/conversas" && m === "POST") return json(res, 200, { id: 1 });
  if (/^\/conversas\/\d+\/mensagens$/.test(p) && m === "GET") return json(res, 200, []);
  if (/^\/conversas\/\d+\/mensagens$/.test(p) && m === "POST") {
    const { texto = "" } = await lerCorpo(req);
    const locar = /locar|alugar/i.test(texto);
    const eventos = [
      ["ferramenta", { nome: "buscar_livros" }],
      ["etapa", { etapa: "escrevendo" }],
      ["etapa", { etapa: "revisando" }],
      [
        "resposta",
        {
          texto: locar
            ? "Encontrei “Dom Casmurro”, de Machado de Assis, com 2 exemplares livres. Preparei a ação para você confirmar."
            : "Encontrei “Dom Casmurro”, de Machado de Assis. Se quiser algo na mesma linha, “Memórias Póstumas de Brás Cubas” também está no acervo.",
        },
      ],
      ["livros", { livros: locar ? [livroDoChat(LIVROS[0])] : [livroDoChat(LIVROS[0]), livroDoChat(LIVROS[1]), livroDoChat(LIVROS[2])] }],
    ];
    if (locar) eventos.push(["propostas", { propostas: [{ confirmacao_id: "c1", resumo: "Locar “Dom Casmurro” por 14 dias." }] }]);
    eventos.push(["fim", {}]);
    return sse(res, eventos);
  }
  if (/^\/conversas\/\d+\/(confirmacoes\/[\w-]+|acoes)$/.test(p) && m === "POST") {
    return sse(res, [
      ["acao", { ok: true }],
      ["resposta", { texto: "Locação concluída. Boa leitura!" }],
      ["fim", {}],
    ]);
  }
  return json(res, 404, { erro: "nao_encontrado", mensagem: "Rota não existe na API falsa." });
});

servidor.listen(PORTA, "127.0.0.1", () => {
  console.log(`API falsa em http://127.0.0.1:${PORTA}`);
});

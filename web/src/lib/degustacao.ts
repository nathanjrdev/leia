/**
 * Degustação: as primeiras páginas de alguns livros da estante da página inicial, já em imagem
 * (geradas por `data/gerar_degustacao.py` em `public/degustacao/`). Sem o índice, ou sem o livro
 * nele, não há degustação e a capa leva à ficha, como sempre.
 */

export type Degustacao = {
  titulo: string;
  /** Proporção do miolo, em px da imagem gerada. */
  largura: number;
  altura: number;
  /** URLs das páginas, na ordem de leitura; a primeira é a capa. */
  paginas: string[];
};

type Indice = { versao: number; livros: Degustacao[] };

export const URL_INDICE = "/degustacao/indice.json";

/** Chave de comparação de títulos: o catálogo e o índice podem divergir em caixa ou em NFC/NFD. */
export function chaveTitulo(titulo: string): string {
  return titulo.normalize("NFC").trim().toLocaleLowerCase("pt-BR");
}

function valida(d: unknown): d is Degustacao {
  if (!d || typeof d !== "object") return false;
  const x = d as Record<string, unknown>;
  return (
    typeof x.titulo === "string" &&
    typeof x.largura === "number" &&
    typeof x.altura === "number" &&
    x.largura > 0 &&
    x.altura > 0 &&
    Array.isArray(x.paginas) &&
    x.paginas.length > 0 &&
    x.paginas.every((p) => typeof p === "string" && p.startsWith("/degustacao/"))
  );
}

/** Lê o índice das degustações. Nunca falha: sem índice (ou inválido), devolve um mapa vazio. */
export async function carregarDegustacoes(): Promise<Map<string, Degustacao>> {
  try {
    const r = await fetch(URL_INDICE);
    if (!r.ok) return new Map();
    const indice = (await r.json()) as Indice;
    const livros = Array.isArray(indice?.livros) ? indice.livros.filter(valida) : [];
    return new Map(livros.map((d) => [chaveTitulo(d.titulo), d]));
  } catch {
    return new Map();
  }
}

/**
 * Item que ocupa um lado da vista: índice da página (0 = capa), a página de fim da degustação
 * (`total`) ou `null` (lado vazio, como à esquerda da capa num livro fechado).
 */
export type Lado = number | null;

/**
 * As vistas do leitor. Em página dupla, a capa abre sozinha à direita (como um livro fechado) e
 * depois vêm pares; em página simples, uma por vez. O último item é a página de fim.
 */
export function vistas(totalPaginas: number, dupla: boolean): Lado[][] {
  const itens = totalPaginas + 1; // + página de fim
  if (!dupla) return Array.from({ length: itens }, (_, i) => [i]);
  const resultado: Lado[][] = [[null, 0]];
  for (let esq = 1; esq < itens; esq += 2) {
    resultado.push([esq, esq + 1 < itens ? esq + 1 : null]);
  }
  return resultado;
}

/** Em que vista está um item: para manter o lugar quando o leitor muda de simples para dupla. */
export function vistaDoItem(item: number, dupla: boolean): number {
  if (!dupla) return item;
  return item === 0 ? 0 : Math.floor((item - 1) / 2) + 1;
}

/** Texto do contador: "Capa", "Páginas 2 e 3 de 10", "Página 4 de 10", "Fim da degustação". */
export function rotuloVista(lados: Lado[], totalPaginas: number): string {
  const paginas = lados.filter((l): l is number => l !== null && l < totalPaginas);
  if (paginas.length === 0) return "Fim da degustação";
  if (paginas.length === 1 && paginas[0] === 0) return "Capa";
  // A capa não conta como página: o leitor lê "página 1" na primeira depois dela.
  const de = totalPaginas - 1;
  return paginas.length === 2
    ? `Páginas ${paginas[0]} e ${paginas[1]} de ${de}`
    : `Página ${paginas[0]} de ${de}`;
}

/**
 * Regras da capa gerada (livros sem imagem): tipografia sobre um tom de encadernação em tecido.
 * Os tons vivem em `globals.css` (`.capa-tom-N`); aqui só se escolhe qual.
 */

export const TONS_DE_CAPA = 6;

/** Tom estável por livro; ids vizinhos ganham tons diferentes, então a lista não fica monótona. */
export function tomDaCapa(semente: number): number {
  return (((Math.trunc(semente) % TONS_DE_CAPA) + TONS_DE_CAPA) % TONS_DE_CAPA) + 1;
}

// Subtítulo começa em " (", ": " ou " - " / " – " / " — " (hífen colado em palavra não conta).
const INICIO_DO_SUBTITULO = /\s+\(|:\s|\s[-–—]\s/;

/** Na capa vai o título principal; o subtítulo fica para a ficha. */
export function tituloDaCapa(titulo: string): string {
  const limpo = titulo.trim();
  const corte = limpo.search(INICIO_DO_SUBTITULO);
  return corte > 0 ? limpo.slice(0, corte).trim() : limpo;
}

export function autoriaDaCapa(autores: readonly string[]): string {
  if (autores.length === 0) return "";
  if (autores.length === 1) return autores[0];
  if (autores.length === 2) return `${autores[0]} e ${autores[1]}`;
  return `${autores[0]} e outros`;
}

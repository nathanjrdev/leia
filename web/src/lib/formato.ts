/** Data curta em pt-BR (dd/mm/aaaa) a partir de um ISO da API. */
export function data(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR");
}

/** Ano de publicação; anos negativos (obras da Antiguidade) saem como "N a.C.". */
export function ano(valor: number): string {
  return valor < 0 ? `${-valor} a.C.` : String(valor);
}

/** Selo de disponibilidade usado nas listas. */
export function selo(livres: number, fila: number): string {
  if (livres > 0) return livres === 1 ? "1 disponível" : `${livres} disponíveis`;
  return fila > 0 ? `Indisponível, fila de ${fila}` : "Indisponível";
}

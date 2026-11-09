/** Formatos do contrato da API (ver `api/src/leia_api/acervo.py`, `chat.py`, `auth.py`). */

export type Conta = { nome: string; email: string };

export type Categoria = { slug: string; nome: string };

export type ItemLivro = {
  id: number;
  titulo: string;
  autores: string[];
  ano: number | null;
  capa_url: string | null;
  livres: number;
  fila: number;
};

export type Listagem = { itens: ItemLivro[]; total: number; pagina: number };

export type Ficha = {
  id: number;
  titulo: string;
  autores: string[];
  categorias: string[];
  sinopse: string | null;
  ano: number | null;
  editora: string | null;
  paginas: number | null;
  capa_url: string | null;
  exemplares: number;
  livres: number;
  fila: number;
};

export type LocacaoResumo = {
  locacao_id: number;
  livro_id: number;
  titulo: string;
  retirada_em: string;
  prevista_em: string;
  devolvida_em: string | null;
  renovacoes: number;
  atrasada: boolean;
};

export type ReservaResumo = {
  reserva_id: number;
  livro_id: number;
  titulo: string;
  posicao: number;
  pronta: boolean;
  retirar_ate: string | null;
};

export type Estante = {
  ativas: LocacaoResumo[];
  reservas: ReservaResumo[];
  historico: LocacaoResumo[];
};

export type MensagemHistorico = { papel: "usuario" | "assistente"; conteudo: string };

export type Proposta = { confirmacao_id: string; resumo: string };

/** Cartão de livro do evento SSE `livros`: dados do banco, só dos livros que a resposta cita. */
export type LivroDoChat = {
  id: number;
  titulo: string;
  autores: string[];
  capa_url: string | null;
  livres: number;
};

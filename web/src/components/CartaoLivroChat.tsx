"use client";

import Link from "next/link";
import { useState } from "react";
import type { LivroDoChat } from "@/lib/tipos";
import { AcaoComConfirmacao } from "./AcaoComConfirmacao";
import { Capa } from "./Capa";
import { Selo } from "./ui/Selo";

export type AcaoDoCartao = "locar" | "reservar";

/**
 * Cartão de um livro citado pela Léia. Os dados vêm do banco (evento SSE `livros`), nunca do texto
 * do modelo. Locar e reservar pedem confirmação em duas etapas e passam pelo chat (`aoAgir`): a API
 * executa a ação e a Léia responde na conversa, com o prazo e um comentário sobre o livro.
 */
export function CartaoLivroChat({
  livro,
  comAcao = true,
  antigo = false,
  ocupado = false,
  aoAgir,
}: {
  livro: LivroDoChat;
  comAcao?: boolean;
  /** Cartão de uma resposta anterior à fala ou à decisão mais recente do leitor: só leitura. */
  antigo?: boolean;
  ocupado?: boolean;
  aoAgir: (acao: AcaoDoCartao, livroId: number) => Promise<boolean>;
}) {
  const [feito, setFeito] = useState(false);
  const livre = livro.livres > 0;

  async function agir(acao: AcaoDoCartao) {
    if (await aoAgir(acao, livro.id)) setFeito(true);
  }

  return (
    <div
      role="group"
      aria-label={`Livro: ${livro.titulo}`}
      className="vidro mt-3 flex gap-4 p-3"
    >
      <Capa
        url={livro.capa_url}
        titulo={livro.titulo}
        autores={livro.autores}
        semente={livro.id}
        className="livro-capa h-28 w-20 shrink-0 rounded-sm"
      />
      <div className="flex min-w-0 flex-col gap-1">
        <Link
          href={`/livro/${livro.id}`}
          className="text-lg leading-snug font-semibold underline decoration-white/40 underline-offset-[0.2em] hover:decoration-current"
        >
          {livro.titulo}
        </Link>
        {livro.autores.length > 0 && (
          <p className="text-texto-suave">{livro.autores.join(", ")}</p>
        )}
        <Selo tom={livre ? "disponivel" : "indisponivel"}>
          {livre
            ? livro.livres === 1
              ? "1 exemplar livre"
              : `${livro.livres} exemplares livres`
            : "Sem exemplar livre agora"}
        </Selo>
        {feito ? (
          <Link href="/estante" className="font-semibold text-rosa underline">
            Ver minha estante
          </Link>
        ) : !comAcao ? (
          antigo ? (
            <p className="text-sm text-texto-suave">Para locar ou reservar, peça de novo à Léia.</p>
          ) : null
        ) : livre ? (
          <AcaoComConfirmacao
            primaria
            rotulo="Locar"
            pergunta={`Locar “${livro.titulo}”?`}
            rotuloConfirmar="Confirmar locação"
            desabilitado={ocupado}
            aoConfirmar={() => agir("locar")}
          />
        ) : (
          <AcaoComConfirmacao
            rotulo="Reservar"
            pergunta={`Entrar na fila de “${livro.titulo}”?`}
            rotuloConfirmar="Confirmar reserva"
            desabilitado={ocupado}
            aoConfirmar={() => agir("reservar")}
          />
        )}
      </div>
    </div>
  );
}

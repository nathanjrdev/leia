"use client";

import Link from "next/link";
import { useState } from "react";
import type { LivroDoChat } from "@/lib/tipos";
import { AcaoComConfirmacao } from "./AcaoComConfirmacao";
import { Capa } from "./Capa";

export type AcaoDoCartao = "locar" | "reservar";

/**
 * Cartão de um livro citado pela Léia. Os dados vêm do banco (evento SSE `livros`), nunca do texto
 * do modelo. Locar e reservar pedem confirmação em duas etapas e passam pelo chat (`aoAgir`): a API
 * executa a ação e a Léia responde na conversa, com o prazo e um comentário sobre o livro.
 */
export function CartaoLivroChat({
  livro,
  comAcao = true,
  ocupado = false,
  aoAgir,
}: {
  livro: LivroDoChat;
  comAcao?: boolean;
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
      className="mt-3 flex gap-4 rounded-md border border-linha bg-papel-2 p-3"
    >
      <Capa
        url={livro.capa_url}
        titulo={livro.titulo}
        autores={livro.autores}
        semente={livro.id}
        className="h-28 w-20 shrink-0 rounded-sm"
      />
      <div className="flex min-w-0 flex-col gap-1">
        <Link href={`/livro/${livro.id}`} className="font-serif text-lg font-semibold underline">
          {livro.titulo}
        </Link>
        {livro.autores.length > 0 && (
          <p className="text-tinta-suave">{livro.autores.join(", ")}</p>
        )}
        <p className={livre ? "text-lombada" : "text-tinta-suave"}>
          {livre
            ? livro.livres === 1
              ? "1 exemplar livre"
              : `${livro.livres} exemplares livres`
            : "Sem exemplar livre agora"}
        </p>
        {feito ? (
          <Link href="/estante" className="text-lombada underline">
            Ver minha estante
          </Link>
        ) : !comAcao ? null : livre ? (
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

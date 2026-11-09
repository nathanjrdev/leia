"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { data } from "@/lib/formato";
import type { LivroDoChat } from "@/lib/tipos";
import { AcaoComConfirmacao } from "./AcaoComConfirmacao";
import { Capa } from "./CartaoLivro";

/**
 * Cartão de um livro citado pela Léia. Os dados vêm do banco (evento SSE `livros`), nunca do texto
 * do modelo. Locar e reservar são os mesmos endpoints da ficha, em duas etapas (clique + confirmar).
 */
export function CartaoLivroChat({ livro }: { livro: LivroDoChat }) {
  const [aviso, setAviso] = useState<string | null>(null);
  const livre = livro.livres > 0;

  async function locar() {
    const r = await api<{ prevista_em: string }>(`/livros/${livro.id}/locar`, {
      metodo: "POST",
      corpo: { confirmo: true },
    });
    setAviso(`Locação feita. Devolver até ${data(r.prevista_em)}.`);
  }

  async function reservar() {
    const r = await api<{ posicao: number }>(`/livros/${livro.id}/reservar`, {
      metodo: "POST",
      corpo: { confirmo: true },
    });
    setAviso(`Reserva feita, posição ${r.posicao} na fila.`);
  }

  return (
    <div
      role="group"
      aria-label={`Livro: ${livro.titulo}`}
      className="mt-3 flex gap-4 rounded-md border border-linha bg-papel-2 p-3"
    >
      <Capa url={livro.capa_url} className="h-28 w-20 shrink-0 rounded-sm" />
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
        {aviso ? (
          <p role="status" className="border-l-4 border-lombada pl-3">
            {aviso}{" "}
            <Link href="/estante" className="text-lombada underline">
              Ver minha estante
            </Link>
          </p>
        ) : livre ? (
          <AcaoComConfirmacao
            primaria
            rotulo="Locar"
            pergunta={`Locar “${livro.titulo}”?`}
            rotuloConfirmar="Confirmar locação"
            aoConfirmar={locar}
          />
        ) : (
          <AcaoComConfirmacao
            rotulo="Reservar"
            pergunta={`Entrar na fila de “${livro.titulo}”?`}
            rotuloConfirmar="Confirmar reserva"
            aoConfirmar={reservar}
          />
        )}
      </div>
    </div>
  );
}

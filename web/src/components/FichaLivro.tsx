"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, mensagemDoErro } from "@/lib/api";
import { ano, avisoLocacao } from "@/lib/formato";
import type { Ficha } from "@/lib/tipos";
import { AcaoComConfirmacao } from "./AcaoComConfirmacao";
import { Capa } from "./Capa";
import { useSessao } from "./SessaoProvider";

type ResultadoLocacao = { prevista_em: string };
type ResultadoReserva = { posicao: number };

export function FichaLivro({ id }: { id: number }) {
  const { conta } = useSessao();
  const [ficha, setFicha] = useState<Ficha | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const recarregar = useCallback(
    () => api<Ficha>(`/livros/${id}`).then(setFicha),
    [id],
  );

  useEffect(() => {
    let vivo = true;
    api<Ficha>(`/livros/${id}`)
      .then((f) => vivo && setFicha(f))
      .catch((e) => vivo && setErro(mensagemDoErro(e)));
    return () => {
      vivo = false;
    };
  }, [id]);

  if (erro) {
    return (
      <p role="alert" className="border-l-4 border-alerta pl-3 text-alerta">
        {erro}
      </p>
    );
  }
  if (!ficha) return <p className="text-tinta-suave">Carregando…</p>;

  const livre = ficha.livres > 0;

  async function locar() {
    const r = await api<ResultadoLocacao>(`/livros/${id}/locar`, {
      metodo: "POST",
      corpo: { confirmo: true },
    });
    setAviso(avisoLocacao(r.prevista_em));
    await recarregar();
  }

  async function reservar() {
    const r = await api<ResultadoReserva>(`/livros/${id}/reservar`, {
      metodo: "POST",
      corpo: { confirmo: true },
    });
    setAviso(`Reserva feita, posição ${r.posicao} na fila.`);
    await recarregar();
  }

  const meta = [ficha.ano ? ano(ficha.ano) : null, ficha.editora, ficha.paginas ? `${ficha.paginas} páginas` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <article className="flex flex-col gap-6 sm:flex-row">
      <Capa
        url={ficha.capa_url}
        titulo={ficha.titulo}
        autores={ficha.autores}
        semente={ficha.id}
        className="h-72 w-48 shrink-0 rounded-sm"
      />
      <div className="flex flex-col gap-4">
        <header className="flex flex-col gap-1">
          <h1 className="text-4xl font-semibold">{ficha.titulo}</h1>
          <p className="text-lg">{ficha.autores.join(", ")}</p>
          {meta && <p className="text-tinta-suave">{meta}</p>}
          {ficha.categorias.length > 0 && (
            <p className="text-tinta-suave">{ficha.categorias.join(", ")}</p>
          )}
        </header>

        {ficha.sinopse && (
          <p className="medida font-serif text-lg leading-relaxed">{ficha.sinopse}</p>
        )}

        <p className={livre ? "font-medium text-lombada" : "font-medium text-tinta-suave"}>
          {livre
            ? `${ficha.livres} de ${ficha.exemplares} exemplares disponíveis`
            : ficha.fila > 0
              ? `Indisponível, fila de ${ficha.fila}`
              : "Indisponível"}
        </p>

        {conta ? (
          livre ? (
            <AcaoComConfirmacao
              primaria
              rotulo="Locar"
              pergunta={`Locar “${ficha.titulo}”?`}
              rotuloConfirmar="Confirmar locação"
              aoConfirmar={locar}
            />
          ) : (
            <AcaoComConfirmacao
              primaria
              rotulo="Reservar"
              pergunta={`Entrar na fila de “${ficha.titulo}”?`}
              rotuloConfirmar="Confirmar reserva"
              aoConfirmar={reservar}
            />
          )
        ) : (
          <Link href="/entrar" className="text-lombada underline">
            {livre ? "Entre para locar" : "Entre para reservar"}
          </Link>
        )}

        {aviso && (
          <p role="status" className="border-l-4 border-lombada pl-3">
            {aviso}{" "}
            <Link href="/estante" className="text-lombada underline">
              Ver minha estante
            </Link>
          </p>
        )}
      </div>
    </article>
  );
}

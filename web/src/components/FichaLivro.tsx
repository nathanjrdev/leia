"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, mensagemDoErro } from "@/lib/api";
import { ano, avisoLocacao } from "@/lib/formato";
import type { Ficha } from "@/lib/tipos";
import { AcaoComConfirmacao } from "./AcaoComConfirmacao";
import { Capa } from "./Capa";
import { useSessao } from "./SessaoProvider";
import { Aviso } from "./ui/Aviso";
import { classesBotao } from "./ui/Botao";
import { Prateleira } from "./ui/Prateleira";
import { Selo } from "./ui/Selo";

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

  if (erro) return <Aviso tipo="erro">{erro}</Aviso>;
  if (!ficha) return <p className="text-texto-suave">Carregando…</p>;

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
    <article className="entra grid gap-8 md:grid-cols-[minmax(0,17rem)_1fr] md:items-start md:gap-14">
      <Prateleira className="mx-auto w-56 md:w-full">
        <Capa
          url={ficha.capa_url}
          titulo={ficha.titulo}
          autores={ficha.autores}
          semente={ficha.id}
          className="livro-capa aspect-[2/3] w-full rounded-sm"
        />
      </Prateleira>
      <div className="flex min-w-0 flex-col gap-6">
        <header className="flex flex-col gap-2">
          <h1 className="text-4xl font-bold sm:text-5xl">{ficha.titulo}</h1>
          <p className="text-xl">{ficha.autores.join(", ")}</p>
          {meta && <p className="text-texto-suave">{meta}</p>}
          {ficha.categorias.length > 0 && (
            <p className="text-texto-suave">{ficha.categorias.join(", ")}</p>
          )}
        </header>

        {ficha.sinopse && <p className="medida text-lg leading-relaxed">{ficha.sinopse}</p>}

        <Selo tom={livre ? "disponivel" : "indisponivel"} className="font-semibold">
          {livre
            ? `${ficha.livres} de ${ficha.exemplares} exemplares disponíveis`
            : ficha.fila > 0
              ? `Indisponível, fila de ${ficha.fila}`
              : "Indisponível"}
        </Selo>

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
          <Link href="/entrar" className={classesBotao("primaria", "self-start")}>
            {livre ? "Entre para locar" : "Entre para reservar"}
          </Link>
        )}

        {aviso && (
          <Aviso tipo="sucesso" className="medida">
            {aviso}{" "}
            <Link href="/estante" className="font-semibold text-rosa underline">
              Ver minha estante
            </Link>
          </Aviso>
        )}
      </div>
    </article>
  );
}

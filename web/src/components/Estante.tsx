"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, mensagemDoErro } from "@/lib/api";
import { data } from "@/lib/formato";
import type { Estante as DadosEstante, LocacaoResumo, ReservaResumo } from "@/lib/tipos";
import { AcaoComConfirmacao } from "./AcaoComConfirmacao";
import { Capa } from "./Capa";
import { useSessao } from "./SessaoProvider";
import { Aviso } from "./ui/Aviso";
import { Botao, classesBotao } from "./ui/Botao";
import { Selo } from "./ui/Selo";

const confirmo = { metodo: "POST", corpo: { confirmo: true } } as const;

export function Estante() {
  const { conta, carregando: carregandoConta } = useSessao();
  const logado = !!conta;
  const [estante, setEstante] = useState<DadosEstante | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const recarregar = useCallback(() => api<DadosEstante>("/estante").then(setEstante), []);

  useEffect(() => {
    if (!logado) return;
    let vivo = true;
    api<DadosEstante>("/estante")
      .then((e) => vivo && setEstante(e))
      .catch((e) => vivo && setErro(mensagemDoErro(e)));
    return () => {
      vivo = false;
    };
  }, [logado]);

  function tentarDeNovo() {
    setErro(null);
    recarregar().catch((e) => setErro(mensagemDoErro(e)));
  }

  if (carregandoConta) return <p className="text-texto-suave">Carregando…</p>;
  if (!logado) {
    return (
      <section className="medida flex flex-col gap-5">
        <h1 className="text-4xl font-bold sm:text-5xl">Minha estante</h1>
        <p className="text-lg text-texto-suave">Entre na sua conta para ver seus livros e reservas.</p>
        <Link href="/entrar" className={classesBotao("primaria", "self-start")}>
          Entrar
        </Link>
      </section>
    );
  }

  const vazia = estante && !estante.ativas.length && !estante.reservas.length;

  return (
    <div className="flex flex-col gap-12">
      <h1 className="text-4xl font-bold sm:text-5xl">Minha estante</h1>

      {erro && (
        <div className="flex flex-col items-start gap-3">
          <Aviso tipo="erro">{erro}</Aviso>
          <Botao onClick={tentarDeNovo}>Tentar de novo</Botao>
        </div>
      )}

      {!estante && !erro && <p className="text-texto-suave">Carregando…</p>}

      {vazia && (
        <div className="vidro medida entra flex flex-col gap-2 p-6 sm:p-8">
          <p className="text-lg">
            Você não tem livros locados nem reservas.{" "}
            <Link href="/conversa" className="font-semibold text-rosa underline">
              Peça uma sugestão à Léia
            </Link>
            .
          </p>
        </div>
      )}

      {estante && estante.ativas.length > 0 && (
        <Secao id="ativas" titulo="Locações ativas">
          {estante.ativas.map((l) => (
            <ItemLocacao key={l.locacao_id} l={l} aoMudar={recarregar} />
          ))}
        </Secao>
      )}

      {estante && estante.reservas.length > 0 && (
        <Secao id="reservas" titulo="Reservas">
          {estante.reservas.map((r) => (
            <ItemReserva key={r.reserva_id} r={r} aoMudar={recarregar} />
          ))}
        </Secao>
      )}

      {estante && estante.historico.length > 0 && (
        <Secao id="historico" titulo="Histórico" lista="vidro divide-y divide-white/15 px-4 sm:px-6">
          {estante.historico.map((l) => (
            <li key={l.locacao_id} className="flex items-center gap-4 py-4">
              <CapaDaEstante livro={l} className="aspect-[2/3] w-12" />
              <div className="min-w-0">
                <Link
                  href={`/livro/${l.livro_id}`}
                  className="font-semibold underline decoration-white/40 underline-offset-[0.2em] hover:decoration-current"
                >
                  {l.titulo}
                </Link>
                <p className="text-[0.9375rem] text-texto-suave">
                  Retirado em {data(l.retirada_em)}
                  {l.devolvida_em ? `, devolvido em ${data(l.devolvida_em)}` : ""}
                </p>
              </div>
            </li>
          ))}
        </Secao>
      )}
    </div>
  );
}

/** Capa de um item da estante; sem imagem, a capa gerada (a mesma do chat e do catálogo). */
function CapaDaEstante({
  livro,
  className,
}: {
  livro: LocacaoResumo | ReservaResumo;
  className: string;
}) {
  return (
    <Capa
      url={livro.capa_url}
      titulo={livro.titulo}
      autores={livro.autores}
      semente={livro.livro_id}
      className={`${className} livro-capa shrink-0 rounded-sm`}
    />
  );
}

// Grade de livros em pé; o histórico passa uma lista compacta num painel de vidro.
const GRADE = "grid gap-x-10 gap-y-12 sm:grid-cols-2 xl:grid-cols-3";

function Secao({
  id,
  titulo,
  children,
  lista = GRADE,
}: {
  id: string;
  titulo: string;
  children: React.ReactNode;
  lista?: string;
}) {
  return (
    <section aria-labelledby={`sec-${id}`} className="flex flex-col gap-5">
      <h2 id={`sec-${id}`} className="text-2xl font-bold sm:text-3xl">
        {titulo}
      </h2>
      <ul className={lista}>{children}</ul>
    </section>
  );
}

function ItemLocacao({ l, aoMudar }: { l: LocacaoResumo; aoMudar: () => Promise<unknown> }) {
  const agir = (acao: "renovar" | "devolver") => async () => {
    await api(`/locacoes/${l.locacao_id}/${acao}`, confirmo);
    await aoMudar();
  };
  return (
    <li className="flex gap-5">
      <span className="livro-em-pe w-28 shrink-0 self-start">
        <CapaDaEstante livro={l} className="aspect-[2/3] w-full" />
      </span>
      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex flex-col gap-1">
          <Link
            href={`/livro/${l.livro_id}`}
            className="text-lg leading-snug font-semibold underline decoration-white/40 underline-offset-[0.2em] hover:decoration-current"
          >
            {l.titulo}
          </Link>
          {l.autores.length > 0 && <p className="text-texto-suave">{l.autores.join(", ")}</p>}
          <Selo tom={l.atrasada ? "alerta" : "neutro"} className="text-[0.9375rem]">
            {`Devolver até ${data(l.prevista_em)}${l.atrasada ? " · Atrasada" : ""}${
              l.renovacoes > 0 ? ` · Renovada ${l.renovacoes} ${l.renovacoes === 1 ? "vez" : "vezes"}` : ""
            }`}
          </Selo>
        </div>
        <div className="flex flex-wrap gap-2">
          <AcaoComConfirmacao
            rotulo="Renovar"
            pergunta={`Renovar “${l.titulo}”?`}
            rotuloConfirmar="Confirmar renovação"
            aoConfirmar={agir("renovar")}
          />
          <AcaoComConfirmacao
            rotulo="Devolver"
            pergunta={`Devolver “${l.titulo}” agora?`}
            rotuloConfirmar="Confirmar devolução"
            aoConfirmar={agir("devolver")}
          />
        </div>
      </div>
    </li>
  );
}

function ItemReserva({ r, aoMudar }: { r: ReservaResumo; aoMudar: () => Promise<unknown> }) {
  async function cancelar() {
    await api(`/reservas/${r.reserva_id}/cancelar`, confirmo);
    await aoMudar();
  }
  return (
    <li className="flex gap-5">
      <span className="livro-em-pe w-28 shrink-0 self-start">
        <CapaDaEstante livro={r} className="aspect-[2/3] w-full" />
      </span>
      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex flex-col gap-1">
          <Link
            href={`/livro/${r.livro_id}`}
            className="text-lg leading-snug font-semibold underline decoration-white/40 underline-offset-[0.2em] hover:decoration-current"
          >
            {r.titulo}
          </Link>
          {r.autores.length > 0 && <p className="text-texto-suave">{r.autores.join(", ")}</p>}
          <Selo tom={r.pronta ? "disponivel" : "neutro"} className={`text-[0.9375rem] ${r.pronta ? "font-semibold" : ""}`}>
            {r.pronta && r.retirar_ate
              ? `Pronto para retirar até ${data(r.retirar_ate)}`
              : `Posição ${r.posicao} na fila`}
          </Selo>
        </div>
        <AcaoComConfirmacao
          rotulo="Cancelar reserva"
          pergunta={`Cancelar a reserva de “${r.titulo}”?`}
          rotuloConfirmar="Confirmar cancelamento"
          aoConfirmar={cancelar}
        />
      </div>
    </li>
  );
}

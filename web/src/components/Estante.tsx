"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, mensagemDoErro } from "@/lib/api";
import { data } from "@/lib/formato";
import type { Estante as DadosEstante, LocacaoResumo, ReservaResumo } from "@/lib/tipos";
import { AcaoComConfirmacao } from "./AcaoComConfirmacao";
import { useSessao } from "./SessaoProvider";

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

  if (carregandoConta) return <p className="text-tinta-suave">Carregando…</p>;
  if (!logado) {
    return (
      <section className="medida flex flex-col gap-4">
        <h1 className="text-3xl font-semibold">Minha estante</h1>
        <p className="text-tinta-suave">Entre na sua conta para ver seus livros e reservas.</p>
        <Link href="/entrar" className="text-lombada underline">
          Entrar
        </Link>
      </section>
    );
  }

  const vazia = estante && !estante.ativas.length && !estante.reservas.length;

  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-3xl font-semibold">Minha estante</h1>

      {erro && (
        <div className="flex flex-col items-start gap-3">
          <p role="alert" className="border-l-4 border-alerta pl-3 text-alerta">
            {erro}
          </p>
          <button type="button" onClick={tentarDeNovo} className="text-lombada underline">
            Tentar de novo
          </button>
        </div>
      )}

      {!estante && !erro && <p className="text-tinta-suave">Carregando…</p>}

      {vazia && (
        <p className="text-tinta-suave">
          Você não tem livros locados nem reservas.{" "}
          <Link href="/conversa" className="text-lombada underline">
            Peça uma sugestão à Léia
          </Link>
          .
        </p>
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
        <Secao id="historico" titulo="Histórico">
          {estante.historico.map((l) => (
            <li key={l.locacao_id} className="border-b border-linha py-3">
              <Link href={`/livro/${l.livro_id}`} className="font-serif text-lg underline">
                {l.titulo}
              </Link>
              <p className="text-tinta-suave">
                Retirado em {data(l.retirada_em)}
                {l.devolvida_em ? `, devolvido em ${data(l.devolvida_em)}` : ""}
              </p>
            </li>
          ))}
        </Secao>
      )}
    </div>
  );
}

function Secao({ id, titulo, children }: { id: string; titulo: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={`sec-${id}`} className="flex flex-col gap-2">
      <h2 id={`sec-${id}`} className="text-2xl font-semibold">
        {titulo}
      </h2>
      <ul>{children}</ul>
    </section>
  );
}

function ItemLocacao({ l, aoMudar }: { l: LocacaoResumo; aoMudar: () => Promise<unknown> }) {
  const agir = (acao: "renovar" | "devolver") => async () => {
    await api(`/locacoes/${l.locacao_id}/${acao}`, confirmo);
    await aoMudar();
  };
  return (
    <li className="flex flex-col gap-3 border-b border-linha py-4">
      <div>
        <Link href={`/livro/${l.livro_id}`} className="font-serif text-xl font-semibold underline">
          {l.titulo}
        </Link>
        <p className={l.atrasada ? "text-alerta" : "text-tinta-suave"}>
          Devolver até {data(l.prevista_em)}
          {l.atrasada ? " · Atrasada" : ""}
          {l.renovacoes > 0 ? ` · Renovada ${l.renovacoes} ${l.renovacoes === 1 ? "vez" : "vezes"}` : ""}
        </p>
      </div>
      <div className="flex flex-wrap gap-4">
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
    </li>
  );
}

function ItemReserva({ r, aoMudar }: { r: ReservaResumo; aoMudar: () => Promise<unknown> }) {
  async function cancelar() {
    await api(`/reservas/${r.reserva_id}/cancelar`, confirmo);
    await aoMudar();
  }
  return (
    <li className="flex flex-col gap-3 border-b border-linha py-4">
      <div>
        <Link href={`/livro/${r.livro_id}`} className="font-serif text-xl font-semibold underline">
          {r.titulo}
        </Link>
        <p className={r.pronta ? "font-medium text-lombada" : "text-tinta-suave"}>
          {r.pronta && r.retirar_ate
            ? `Pronto para retirar até ${data(r.retirar_ate)}`
            : `Posição ${r.posicao} na fila`}
        </p>
      </div>
      <AcaoComConfirmacao
        rotulo="Cancelar reserva"
        pergunta={`Cancelar a reserva de “${r.titulo}”?`}
        rotuloConfirmar="Confirmar cancelamento"
        aoConfirmar={cancelar}
      />
    </li>
  );
}

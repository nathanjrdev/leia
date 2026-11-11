"use client";

import { useState } from "react";
import { mensagemDoErro } from "@/lib/api";

type Props = {
  rotulo: string;
  pergunta: string;
  rotuloConfirmar: string;
  aoConfirmar: () => Promise<void>;
  primaria?: boolean;
  // outro trabalho em curso (a Léia respondendo): não deixa começar nem confirmar
  desabilitado?: boolean;
};

/** Toda escrita da tela passa por aqui: o 1º clique só pergunta, a ação só roda no 2º. */
export function AcaoComConfirmacao({
  rotulo,
  pergunta,
  rotuloConfirmar,
  aoConfirmar,
  primaria = false,
  desabilitado = false,
}: Props) {
  const [etapa, setEtapa] = useState<"inicio" | "perguntando" | "enviando">("inicio");
  const [erro, setErro] = useState<string | null>(null);

  async function confirmar() {
    setEtapa("enviando");
    setErro(null);
    try {
      await aoConfirmar();
    } catch (e) {
      setErro(mensagemDoErro(e));
    } finally {
      setEtapa("inicio");
    }
  }

  const botaoPrimario =
    "transicao rounded-md bg-lombada px-4 py-2 font-medium text-lombada-texto hover:opacity-90 disabled:opacity-60";
  const botaoSecundario =
    "transicao rounded-md border border-controle px-4 py-2 hover:bg-papel-2 disabled:opacity-60";

  return (
    <div className="flex flex-col gap-2">
      {etapa === "inicio" ? (
        <button
          type="button"
          disabled={desabilitado}
          onClick={() => {
            setErro(null);
            setEtapa("perguntando");
          }}
          className={primaria ? botaoPrimario : botaoSecundario}
        >
          {rotulo}
        </button>
      ) : (
        <div role="group" aria-label={`Confirmar: ${rotulo}`} className="flex flex-col gap-2">
          <p className="font-medium">{pergunta}</p>
          <div className="flex gap-3">
            <button
              type="button"
              disabled={etapa === "enviando" || desabilitado}
              onClick={confirmar}
              className={botaoPrimario}
            >
              {rotuloConfirmar}
            </button>
            <button
              type="button"
              disabled={etapa === "enviando"}
              onClick={() => setEtapa("inicio")}
              className={botaoSecundario}
            >
              Voltar
            </button>
          </div>
        </div>
      )}
      {erro && (
        <p role="alert" className="border-l-4 border-alerta pl-3 text-alerta">
          {erro}
        </p>
      )}
    </div>
  );
}

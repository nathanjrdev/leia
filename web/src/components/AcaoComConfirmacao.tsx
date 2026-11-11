"use client";

import { useState } from "react";
import { mensagemDoErro } from "@/lib/api";
import { Aviso } from "./ui/Aviso";
import { Botao } from "./ui/Botao";

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

  return (
    <div className="flex flex-col gap-2">
      {etapa === "inicio" ? (
        <Botao
          variante={primaria ? "primaria" : "secundaria"}
          disabled={desabilitado}
          onClick={() => {
            setErro(null);
            setEtapa("perguntando");
          }}
          className="self-start"
        >
          {rotulo}
        </Botao>
      ) : (
        <div role="group" aria-label={`Confirmar: ${rotulo}`} className="entra flex flex-col gap-2">
          <p className="font-medium">{pergunta}</p>
          <div className="flex flex-wrap gap-2">
            <Botao variante="primaria" disabled={etapa === "enviando" || desabilitado} onClick={confirmar}>
              {rotuloConfirmar}
            </Botao>
            <Botao disabled={etapa === "enviando"} onClick={() => setEtapa("inicio")}>
              Voltar
            </Botao>
          </div>
        </div>
      )}
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
    </div>
  );
}

import type { ReactNode } from "react";
import { IconeAlerta, IconeCheck, IconeInfo } from "./Icones";

type Tipo = "erro" | "sucesso" | "info";

const PAPEL: Record<Tipo, "alert" | "status"> = { erro: "alert", sucesso: "status", info: "status" };

/** Faixa de vidro com ícone para erro, sucesso ou aviso. O papel ARIA fica no próprio elemento
 * que contém o texto (os testes e os leitores de tela leem dali). */
export function Aviso({ tipo, children, className = "" }: { tipo: Tipo; children: ReactNode; className?: string }) {
  const Icone = tipo === "erro" ? IconeAlerta : tipo === "sucesso" ? IconeCheck : IconeInfo;
  return (
    <div role={PAPEL[tipo]} className={`aviso aviso-${tipo} ${className}`}>
      <Icone className="aviso-icone" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

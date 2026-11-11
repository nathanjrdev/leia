import type { ReactNode } from "react";
import { IconeAlerta } from "./Icones";

export type TomSelo = "disponivel" | "indisponivel" | "alerta" | "neutro";

/**
 * Estado de um livro ou de um prazo: ponto (ou ícone, no alerta) + texto. A cor ajuda, mas quem
 * informa é o texto. Menta = disponível; ponto vazado = indisponível; ícone + alerta = atraso.
 */
export function Selo({ tom, children, className = "" }: { tom: TomSelo; children: ReactNode; className?: string }) {
  return (
    <span className={`selo selo-${tom} ${className}`}>
      {tom === "alerta" ? <IconeAlerta className="shrink-0" /> : <span aria-hidden="true" className="selo-ponto" />}
      <span>{children}</span>
    </span>
  );
}

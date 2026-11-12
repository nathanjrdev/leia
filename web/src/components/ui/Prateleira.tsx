import type { ReactNode } from "react";

/**
 * Prateleira de vidro: os livros ficam em pé e a tábua da frente, de vidro fosco, cobre a base
 * deles. A tábua é decoração (`aria-hidden`, sem eventos de ponteiro): os links e botões dos
 * livros continuam clicáveis através dela.
 */
export function Prateleira({
  children,
  className = "",
  como: Tag = "div",
  rotulo,
}: {
  children: ReactNode;
  className?: string;
  como?: "div" | "ul";
  rotulo?: string;
}) {
  return (
    <div className={`prateleira ${className}`}>
      <Tag className="prateleira-livros" aria-label={rotulo}>
        {children}
      </Tag>
      <span aria-hidden="true" className="prateleira-tabua" />
    </div>
  );
}

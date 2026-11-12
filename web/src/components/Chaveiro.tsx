"use client";

import { useState } from "react";

/**
 * Chaveiro de livros pendurado na prateleira da página inicial (plano, seção 11). Decorativo.
 * Balança amortecido ao aparecer e de novo ao passar o ponteiro ou tocar; nunca em loop; parado
 * com movimento reduzido (CSS em globals.css, `.chaveiro`).
 *
 * Desenho nosso em SVG (anelzinho + correntinha + três lombadas em leque), nas cores que já
 * existem para capa gerada (`--capa-celeste/--capa-rosa/--capa-verde`). Não depende de nenhum
 * asset externo, então não há arquivo para gerar nem para conferir antes de subir.
 */
const LARGURA = 72;
const ALTURA = 160;

export function Chaveiro() {
  const [balanco, setBalanco] = useState(0);
  return (
    <svg
      key={balanco}
      viewBox={`0 0 ${LARGURA} ${ALTURA}`}
      width={LARGURA}
      height={ALTURA}
      aria-hidden="true"
      className="chaveiro"
      onPointerEnter={() => setBalanco((n) => n + 1)}
    >
      <circle cx="36" cy="12" r="7" fill="none" stroke="var(--controle)" strokeWidth="3" />
      <line
        x1="36"
        y1="19"
        x2="36"
        y2="58"
        stroke="var(--controle)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeDasharray="0.1 8"
      />
      <g transform="translate(36 100)">
        <rect x="-19" y="-42" width="15" height="80" rx="3" transform="rotate(-8)" fill="var(--capa-celeste)" />
        <rect x="4" y="-42" width="15" height="80" rx="3" transform="rotate(8)" fill="var(--capa-verde)" />
        <rect x="-7.5" y="-46" width="15" height="84" rx="3" fill="var(--capa-rosa)" />
        <rect x="-4.5" y="-38" width="9" height="2.5" rx="1.25" fill="var(--capa-rosa-letra)" opacity="0.35" />
      </g>
    </svg>
  );
}

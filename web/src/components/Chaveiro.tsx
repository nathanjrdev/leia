"use client";

import { useState } from "react";

/**
 * Chaveiro de livros pendurado na prateleira da página inicial (plano, seção 11). Decorativo.
 * Balança amortecido ao aparecer e de novo ao passar o ponteiro ou tocar; nunca em loop; parado
 * com movimento reduzido (CSS em globals.css, `.chaveiro`).
 *
 * O asset ainda não existe: enquanto `ARQUIVO` for null, o componente não desenha nada e a
 * página não pede arquivo nenhum. Quando o WebP chegar em `public/objetos/`, basta apontar aqui.
 */
const ARQUIVO: string | null = null; // "/objetos/chaveiro-livros.webp"
const LARGURA = 72;
const ALTURA = 168;

export function Chaveiro() {
  const [balanco, setBalanco] = useState(0);
  if (!ARQUIVO) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      key={balanco}
      src={ARQUIVO}
      alt=""
      aria-hidden="true"
      width={LARGURA}
      height={ALTURA}
      decoding="async"
      className="chaveiro"
      onPointerEnter={() => setBalanco((n) => n + 1)}
    />
  );
}

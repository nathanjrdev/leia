"use client";

import { useState } from "react";
import { autoriaDaCapa, tituloDaCapa, tomDaCapa } from "@/lib/capa";

// A Open Library responde 200 com uma imagem de 1×1 px quando a capa não existe.
const LARGURA_MINIMA = 10;

type Props = {
  url: string | null;
  titulo: string;
  autores?: readonly string[];
  /** Escolhe o tom da capa gerada; use o id do livro para ser estável entre telas. */
  semente: number;
  className?: string;
};

/**
 * Capa do livro: a imagem real quando existe e carrega; senão, uma capa tipográfica gerada
 * (título e autoria sobre um tom de encadernação). A gerada é decorativa (`aria-hidden`): o
 * título e o autor de verdade já estão ao lado, no cartão ou na ficha.
 */
export function Capa({ url, titulo, autores = [], semente, className = "" }: Props) {
  // Guarda a URL que falhou: se a URL mudar, a nova imagem é tentada.
  const [urlFalhou, setUrlFalhou] = useState<string | null>(null);

  if (url && urlFalhou !== url) {
    return (
      // Capas vêm de hosts externos do catálogo; <img> evita configurar domínios do next/image.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
        alt=""
        loading="lazy"
        className={`object-cover ${className}`}
        onError={() => setUrlFalhou(url)}
        onLoad={(e) => {
          if (e.currentTarget.naturalWidth < LARGURA_MINIMA) setUrlFalhou(url);
        }}
      />
    );
  }

  const autoria = autoriaDaCapa(autores);
  return (
    <div
      aria-hidden="true"
      data-capa="gerada"
      className={`capa-gerada capa-tom-${tomDaCapa(semente)} ${className}`}
    >
      <div className="capa-gerada-miolo">
        <p lang="pt-BR" className="capa-gerada-titulo">
          {tituloDaCapa(titulo)}
        </p>
        {autoria && <p className="capa-gerada-autor">{autoria}</p>}
      </div>
    </div>
  );
}

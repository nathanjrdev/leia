import type { ReactNode } from "react";

/** Moldura das páginas de texto corrido (privacidade, termos): título, data e seções na medida
 * de leitura. Sem vidro: é texto para ler, não superfície. */
export function TextoLegal({
  titulo,
  atualizadaEm,
  children,
}: {
  titulo: string;
  atualizadaEm: string;
  children: ReactNode;
}) {
  return (
    <article className="entra texto-legal medida mx-auto flex flex-col gap-8 sm:py-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-4xl font-bold sm:text-5xl">{titulo}</h1>
        <p className="text-texto-suave">Atualizada em {atualizadaEm}.</p>
      </header>
      {children}
    </article>
  );
}

export function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-[1.375rem] font-semibold tracking-[-0.02em]">{titulo}</h2>
      {children}
    </section>
  );
}

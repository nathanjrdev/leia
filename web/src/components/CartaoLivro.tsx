import Link from "next/link";
import { ano, selo } from "@/lib/formato";
import type { ItemLivro } from "@/lib/tipos";
import { Capa } from "./Capa";
import { Selo } from "./ui/Selo";

/** Livro em pé na prateleira do catálogo: capa sobre o trecho de tábua, título, autoria e selo. */
export function CartaoLivro({ livro }: { livro: ItemLivro }) {
  const disponivel = livro.livres > 0;
  const href = `/livro/${livro.id}`;
  return (
    <li className="flex min-w-0 flex-col gap-3">
      {/* A capa também leva à ficha, mas fora do Tab e do leitor de tela: o link é o título. */}
      <Link href={href} tabIndex={-1} aria-hidden="true" className="livro-em-pe">
        <Capa
          url={livro.capa_url}
          titulo={livro.titulo}
          autores={livro.autores}
          semente={livro.id}
          className="livro-capa aspect-[2/3] w-full rounded-sm"
        />
      </Link>
      <div className="flex min-w-0 flex-col gap-1">
        <Link
          href={href}
          className="leading-snug font-semibold text-texto underline decoration-white/40 underline-offset-[0.2em] hover:decoration-current"
        >
          {livro.titulo}
        </Link>
        <p className="text-[0.9375rem] leading-snug text-texto-suave">
          {livro.autores.join(", ")}
          {livro.ano ? ` · ${ano(livro.ano)}` : ""}
        </p>
        <Selo tom={disponivel ? "disponivel" : "indisponivel"} className="text-[0.9375rem]">
          {selo(livro.livres, livro.fila)}
        </Selo>
      </div>
    </li>
  );
}

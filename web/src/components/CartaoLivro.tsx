import Link from "next/link";
import { ano, selo } from "@/lib/formato";
import type { ItemLivro } from "@/lib/tipos";

export function Capa({ url, className = "" }: { url: string | null; className?: string }) {
  return url ? (
    // Capas vêm de hosts externos do catálogo; <img> evita configurar domínios do next/image.
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt="" loading="lazy" className={`object-cover ${className}`} />
  ) : (
    <div
      aria-hidden="true"
      className={`flex items-center justify-center border border-linha bg-papel-2 text-sm text-tinta-suave ${className}`}
    >
      Sem capa
    </div>
  );
}

export function CartaoLivro({ livro }: { livro: ItemLivro }) {
  const disponivel = livro.livres > 0;
  return (
    <li className="flex gap-4 border-b border-linha py-4">
      <Capa url={livro.capa_url} className="h-32 w-22 shrink-0 rounded-sm" />
      <div className="flex flex-col gap-1">
        <Link href={`/livro/${livro.id}`} className="font-serif text-xl font-semibold underline">
          {livro.titulo}
        </Link>
        <p className="text-tinta-suave">
          {livro.autores.join(", ")}
          {livro.ano ? ` · ${ano(livro.ano)}` : ""}
        </p>
        <p className={disponivel ? "text-lombada" : "text-tinta-suave"}>
          {selo(livro.livres, livro.fila)}
        </p>
      </div>
    </li>
  );
}

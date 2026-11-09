"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSessao } from "./SessaoProvider";

const LINKS = [
  { href: "/conversa", rotulo: "Conversa" },
  { href: "/catalogo", rotulo: "Catálogo" },
  { href: "/estante", rotulo: "Minha estante" },
];

export function Cabecalho() {
  const { conta, carregando, sair } = useSessao();
  const router = useRouter();

  async function aoSair() {
    await sair();
    router.push("/");
  }

  return (
    <header className="border-b border-linha bg-papel-2">
      <a
        href="#conteudo"
        className="sr-only rounded-md bg-lombada px-4 py-2 font-medium text-lombada-texto focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-10"
      >
        Pular para o conteúdo
      </a>
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="font-serif text-2xl font-semibold">
          Léia
        </Link>
        <nav aria-label="Principal" className="flex flex-wrap gap-x-5 gap-y-1">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="hover:underline">
              {l.rotulo}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-4">
          {carregando ? null : conta ? (
            <>
              <span className="text-tinta-suave">{conta.nome}</span>
              <button type="button" onClick={aoSair} className="text-lombada underline">
                Sair
              </button>
            </>
          ) : (
            <Link href="/entrar" className="text-lombada underline">
              Entrar
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

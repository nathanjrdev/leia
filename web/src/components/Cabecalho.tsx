"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSessao } from "./SessaoProvider";
import { Botao, classesBotao } from "./ui/Botao";

// Os rótulos ficam com maiúscula no DOM (nome acessível e testes); a tela mostra em minúsculas.
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
    <header className="pt-[env(safe-area-inset-top)]">
      <a
        href="#conteudo"
        className="sr-only rounded-full bg-rosa px-4 py-2 font-semibold text-rosa-texto focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-10"
      >
        Pular para o conteúdo
      </a>
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-3 px-4 py-4 sm:gap-x-6">
        <Link
          href="/"
          className="rounded-md text-[1.75rem] leading-none font-bold tracking-[-0.03em] text-rosa no-underline"
        >
          Léia
        </Link>
        <nav
          aria-label="Principal"
          className="vidro order-last flex w-full gap-1 rounded-full p-1 sm:order-none sm:w-auto"
        >
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="minusculas flex min-h-10 flex-1 items-center justify-center rounded-full px-4 text-center whitespace-nowrap text-texto transition-colors duration-200 hover:bg-white/15 sm:flex-none"
            >
              {l.rotulo}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {carregando ? null : conta ? (
            <>
              <span className="text-texto-suave">{conta.nome}</span>
              <Botao variante="texto" onClick={aoSair}>
                Sair
              </Botao>
            </>
          ) : (
            <Link href="/entrar" className={classesBotao("secundaria", "min-h-10 py-1.5")}>
              Entrar
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

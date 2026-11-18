import Link from "next/link";

/** Rodapé discreto com os links legais (o Google exige a política acessível pela página inicial). */
export function Rodape() {
  return (
    <footer className="mx-auto w-full max-w-6xl px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] text-sm text-texto-suave">
      <nav aria-label="Rodapé" className="flex flex-wrap gap-x-5 gap-y-2 border-t border-vidro-filete pt-5">
        <Link href="/privacidade" className="text-texto-suave hover:text-texto">
          Política de Privacidade
        </Link>
        <Link href="/termos" className="text-texto-suave hover:text-texto">
          Termos de Uso
        </Link>
      </nav>
    </footer>
  );
}

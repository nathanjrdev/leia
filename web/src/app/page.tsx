import Link from "next/link";
import { EstanteDaHome } from "@/components/EstanteDaHome";
import { classesBotao } from "@/components/ui/Botao";
import { Prateleira } from "@/components/ui/Prateleira";

export default function Inicio() {
  return (
    <section className="grid items-center gap-12 py-4 lg:grid-cols-[1.05fr_1fr] lg:gap-16 lg:py-10">
      <div className="flex flex-col gap-7">
        {/* A marca em pé na prateleira: a tábua de vidro cobre a base das letras. */}
        <Prateleira className="inicio-marca self-start">
          <span aria-hidden="true" className="marca-grande">
            Léia
          </span>
        </Prateleira>
        <h1 className="inicio-titulo max-w-[18ch] text-4xl font-bold sm:text-5xl">
          Converse com a Léia. Ela conhece o acervo.
        </h1>
        <p className="inicio-texto medida text-lg text-texto-suave">
          Diga o que você quer ler: um tema, um autor, um sentimento. A Léia procura nos livros que a
          biblioteca realmente tem, mostra a disponibilidade e prepara a locação. Você confirma com um
          clique.
        </p>
        <div className="inicio-acoes flex flex-wrap gap-3">
          <Link href="/conversa" className={classesBotao("primaria", "min-h-12 px-7 text-lg")}>
            Conversar com a Léia
          </Link>
          <Link href="/catalogo" className={classesBotao("secundaria", "min-h-12 px-7 text-lg")}>
            Ver o catálogo
          </Link>
        </div>
      </div>
      <EstanteDaHome />
    </section>
  );
}

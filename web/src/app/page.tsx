import Link from "next/link";

export default function Inicio() {
  return (
    <section className="medida flex flex-col gap-6 py-10">
      <h1 className="text-4xl font-semibold">Converse com a Léia. Ela conhece o acervo.</h1>
      <p className="text-lg text-tinta-suave">
        Diga o que você quer ler: um tema, um autor, um sentimento. A Léia procura nos livros que a
        biblioteca realmente tem, mostra a disponibilidade e prepara a locação. Você confirma com um
        clique.
      </p>
      <div className="flex flex-wrap gap-4">
        <Link
          href="/conversa"
          className="transicao rounded-md bg-lombada px-5 py-3 font-medium text-lombada-texto hover:opacity-90"
        >
          Conversar com a Léia
        </Link>
        <Link
          href="/catalogo"
          className="transicao rounded-md border border-linha px-5 py-3 hover:bg-papel-2"
        >
          Ver o catálogo
        </Link>
      </div>
    </section>
  );
}

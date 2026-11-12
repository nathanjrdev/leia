import { notFound } from "next/navigation";
import { Suspense } from "react";
import { FichaLivro } from "@/components/FichaLivro";

export default function PaginaLivro({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<p className="text-texto-suave">Carregando…</p>}>
      <Conteudo params={params} />
    </Suspense>
  );
}

async function Conteudo({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const numero = Number(id);
  if (!Number.isInteger(numero) || numero < 1) notFound();
  return <FichaLivro id={numero} />;
}

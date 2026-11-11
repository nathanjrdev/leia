import type { Metadata } from "next";
import { FormularioAuth } from "@/components/FormularioAuth";

export const metadata: Metadata = { title: "Entrar · Léia" };

export default function Entrar() {
  return (
    <section className="entra mx-auto flex w-full max-w-md flex-col gap-6 sm:py-6">
      <h1 className="text-4xl font-bold sm:text-5xl">Entrar</h1>
      <div className="vidro vidro-fosco p-6 sm:p-8">
        <FormularioAuth modo="entrar" />
      </div>
    </section>
  );
}

import type { Metadata } from "next";
import { FormularioAuth } from "@/components/FormularioAuth";

export const metadata: Metadata = { title: "Entrar · Léia" };

export default function Entrar() {
  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-3xl font-semibold">Entrar</h1>
      <FormularioAuth modo="entrar" />
    </section>
  );
}

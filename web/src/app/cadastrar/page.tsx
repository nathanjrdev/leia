import type { Metadata } from "next";
import { FormularioAuth } from "@/components/FormularioAuth";

export const metadata: Metadata = { title: "Criar conta · Léia" };

export default function Cadastrar() {
  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-3xl font-semibold">Criar conta</h1>
      <FormularioAuth modo="cadastrar" />
    </section>
  );
}

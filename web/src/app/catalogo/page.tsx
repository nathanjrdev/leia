import type { Metadata } from "next";
import { Catalogo } from "@/components/Catalogo";

export const metadata: Metadata = { title: "Catálogo · Léia" };

export default function PaginaCatalogo() {
  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-3xl font-semibold">Catálogo</h1>
      <Catalogo />
    </section>
  );
}

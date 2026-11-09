import type { Metadata } from "next";
import { Estante } from "@/components/Estante";

export const metadata: Metadata = { title: "Minha estante · Léia" };

export default function PaginaEstante() {
  return <Estante />;
}

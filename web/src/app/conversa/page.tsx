import type { Metadata } from "next";
import { Conversa } from "@/components/Conversa";

export const metadata: Metadata = { title: "Conversa · Léia" };

export default function PaginaConversa() {
  return <Conversa />;
}

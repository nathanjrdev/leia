import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Fraunces, Inter } from "next/font/google";
import { Cabecalho } from "@/components/Cabecalho";
import { SessaoProvider } from "@/components/SessaoProvider";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const fraunces = Fraunces({ variable: "--font-fraunces", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Léia, a bibliotecária virtual",
  description: "Converse com a Léia, ache livros do acervo e faça sua locação.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="pt-BR" className={`${inter.variable} ${fraunces.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <SessaoProvider>
          <Cabecalho />
          <main
            id="conteudo"
            tabIndex={-1}
            className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 outline-none"
          >{children}</main>
        </SessaoProvider>
      </body>
    </html>
  );
}

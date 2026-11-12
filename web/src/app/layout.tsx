import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Inter } from "next/font/google";
import { Cabecalho } from "@/components/Cabecalho";
import { SessaoProvider } from "@/components/SessaoProvider";
import "./globals.css";

// Uma família só (DESIGN.md): a Inter faz títulos, interface e capas geradas.
const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Léia, a bibliotecária virtual",
  description: "Converse com a Léia, ache livros do acervo e faça sua locação.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // safe-area (env()) só vale com cover; o teclado do Android encolhe o layout como no iOS.
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
  colorScheme: "dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#7a0ccf" },
    { media: "(prefers-color-scheme: dark)", color: "#1b0b2a" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="pt-BR" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <SessaoProvider>
          <Cabecalho />
          <main
            id="conteudo"
            tabIndex={-1}
            className="mx-auto w-full max-w-6xl flex-1 pt-6 pr-[max(1rem,env(safe-area-inset-right))] pb-[max(2rem,env(safe-area-inset-bottom))] pl-[max(1rem,env(safe-area-inset-left))] outline-none sm:pt-10"
          >{children}</main>
        </SessaoProvider>
      </body>
    </html>
  );
}

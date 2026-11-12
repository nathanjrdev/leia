"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ItemLivro, Listagem } from "@/lib/tipos";
import { Capa } from "./Capa";
import { Chaveiro } from "./Chaveiro";
import { Prateleira } from "./ui/Prateleira";

const POR_PRATELEIRA = 4;
const QUANTIDADE = POR_PRATELEIRA * 2;
// Candidatos de sobra (máximo aceito pela API): a vitrine só mostra capa de verdade, nunca a
// gerada por CSS, então pedimos mais do que cabe e filtramos as que não têm capa_url real.
const CANDIDATOS = 48;
// Atrasos variados (não uniformes) e curtos: a fileira assenta em ~300 ms, sem segurar clique.
const ATRASOS_MS = [0, 70, 110, 190];

/**
 * As duas prateleiras de vidro da página inicial, só com capas reais do acervo (livros sem capa
 * verificada nunca aparecem aqui). Enquanto carrega, ou se a API falhar, ficam espaços vazios
 * decorativos: a página inicial não mostra erro.
 */
export function EstanteDaHome() {
  const [livros, setLivros] = useState<ItemLivro[] | null>(null);

  useEffect(() => {
    let vivo = true;
    api<Listagem>(`/livros?pagina=1&limite=${CANDIDATOS}`)
      .then((d) => vivo && setLivros(d.itens.filter((l) => l.capa_url).slice(0, QUANTIDADE)))
      .catch(() => vivo && setLivros([]));
    return () => {
      vivo = false;
    };
  }, []);

  const fileiras = [0, 1].map((f) => livros?.slice(f * POR_PRATELEIRA, (f + 1) * POR_PRATELEIRA) ?? []);

  return (
    <div className="relative flex flex-col gap-10 sm:gap-14">
      {fileiras.map((fileira, f) => (
        <div key={f} className={f === 1 ? "lg:ml-14" : "lg:mr-14"}>
          <Prateleira className="pt-2">
            {Array.from({ length: POR_PRATELEIRA }, (_, i) => {
              const l = fileira[i];
              return l ? (
                <Link
                  key={l.id}
                  href={`/livro/${l.id}`}
                  className="inicio-capa entra w-[22%] min-w-0 shrink-0 rounded-sm"
                  style={{ animationDelay: `${ATRASOS_MS[i]}ms` }}
                >
                  <span className="sr-only">{l.titulo}</span>
                  <Capa
                    url={l.capa_url}
                    titulo={l.titulo}
                    autores={l.autores}
                    semente={l.id}
                    className="livro-capa aspect-[2/3] w-full rounded-sm"
                  />
                </Link>
              ) : (
                <span
                  key={`vazio-${i}`}
                  aria-hidden="true"
                  className="aspect-[2/3] w-[22%] shrink-0 rounded-sm bg-white/10"
                />
              );
            })}
          </Prateleira>
          {f === 0 && <Chaveiro />}
        </div>
      ))}
    </div>
  );
}

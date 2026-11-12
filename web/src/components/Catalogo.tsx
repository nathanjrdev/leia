"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, mensagemDoErro } from "@/lib/api";
import type { Categoria, Listagem } from "@/lib/tipos";
import { CartaoLivro } from "./CartaoLivro";
import { Aviso } from "./ui/Aviso";
import { Botao } from "./ui/Botao";
import { IconeBusca } from "./ui/Icones";

const POR_PAGINA = 20;

export function Catalogo() {
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [categoria, setCategoria] = useState("");
  const [soDisponiveis, setSoDisponiveis] = useState(false);
  const [rascunho, setRascunho] = useState("");
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const [dados, setDados] = useState<Listagem | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api<Categoria[]>("/categorias")
      .then(setCategorias)
      .catch(() => setCategorias([]));
  }, []);

  useEffect(() => {
    let vivo = true;
    const p = new URLSearchParams();
    if (busca) p.set("q", busca);
    else p.set("pagina", String(pagina));
    p.set("limite", String(POR_PAGINA));
    if (categoria) p.set("categoria", categoria);
    if (soDisponiveis) p.set("apenas_disponiveis", "true");
    api<Listagem>(`${busca ? "/livros/busca" : "/livros"}?${p}`)
      .then((d) => {
        if (!vivo) return;
        setDados(d);
        setErro(null);
      })
      .catch((e) => vivo && setErro(mensagemDoErro(e)))
      .finally(() => vivo && setCarregando(false));
    return () => {
      vivo = false;
    };
  }, [busca, categoria, soDisponiveis, pagina]);

  function buscar(e: FormEvent) {
    e.preventDefault();
    setCarregando(true);
    setPagina(1);
    setBusca(rascunho.trim());
  }

  const paginas = dados ? Math.max(1, Math.ceil(dados.total / POR_PAGINA)) : 1;

  return (
    <div className="flex flex-col gap-8">
      <div className="vidro vidro-fosco flex flex-col gap-5 p-4 sm:p-6">
      <form onSubmit={buscar} className="flex flex-wrap items-end gap-x-3 gap-y-3">
        <div className="flex min-w-60 flex-1 flex-col gap-1.5">
          <label htmlFor="busca" className="font-semibold">
            Buscar no acervo
          </label>
          <div className="relative">
            <IconeBusca className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-texto-suave" />
            <input
              id="busca"
              type="search"
              value={rascunho}
              onChange={(e) => setRascunho(e.target.value)}
              maxLength={300}
              className="campo min-h-14 pl-12 text-lg"
            />
          </div>
        </div>
        <Botao type="submit" variante="primaria" className="min-h-14 px-7">
          Buscar
        </Botao>
      </form>

      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="categoria" className="font-semibold">
            Categoria
          </label>
          <select
            id="categoria"
            value={categoria}
            onChange={(e) => {
              setCarregando(true);
              setPagina(1);
              setCategoria(e.target.value);
            }}
            className="campo w-auto min-w-44"
          >
            <option value="">Todas</option>
            {categorias.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.nome}
              </option>
            ))}
          </select>
        </div>
        <label className="flex min-h-12 items-center gap-2.5">
          <input
            type="checkbox"
            checked={soDisponiveis}
            onChange={(e) => {
              setCarregando(true);
              setPagina(1);
              setSoDisponiveis(e.target.checked);
            }}
            className="size-5 accent-rosa"
          />
          Só disponíveis
        </label>
      </div>
      </div>

      {erro && <Aviso tipo="erro">{erro}</Aviso>}

      {carregando && !dados ? (
        <p className="text-texto-suave">Carregando…</p>
      ) : dados && dados.itens.length === 0 && !erro ? (
        <div className="vidro flex flex-col gap-1 p-6">
          <p className="text-lg font-semibold">Nenhum livro encontrado.</p>
          <p className="text-texto-suave">Tente outra palavra, outra categoria ou tire o filtro de disponíveis.</p>
        </div>
      ) : (
        dados && (
          <>
            <p className="text-texto-suave" aria-live="polite">
              {carregando ? "Buscando…" : busca ? `Resultados para “${busca}”` : `${dados.total} livros`}
            </p>
            <ul
              className={`grid grid-cols-2 gap-x-6 gap-y-10 px-3 transition-opacity duration-150 sm:grid-cols-3 lg:grid-cols-5 ${carregando ? "opacity-60" : ""}`}
            >
              {dados.itens.map((l) => (
                <CartaoLivro key={l.id} livro={l} />
              ))}
            </ul>
          </>
        )
      )}

      {!busca && dados && paginas > 1 && (
        <nav aria-label="Páginas" className="flex items-center justify-center gap-4">
          <Botao disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}>
            Anterior
          </Botao>
          <span className="text-texto-suave tabular-nums">
            Página {pagina} de {paginas}
          </span>
          <Botao disabled={pagina >= paginas} onClick={() => setPagina((p) => p + 1)}>
            Próxima
          </Botao>
        </nav>
      )}
    </div>
  );
}

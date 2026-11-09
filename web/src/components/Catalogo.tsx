"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, mensagemDoErro } from "@/lib/api";
import type { Categoria, Listagem } from "@/lib/tipos";
import { CartaoLivro } from "./CartaoLivro";

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
    <div className="flex flex-col gap-6">
      <form onSubmit={buscar} className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <div className="flex min-w-60 flex-1 flex-col gap-1.5">
          <label htmlFor="busca" className="font-medium">
            Buscar no acervo
          </label>
          <input
            id="busca"
            type="search"
            value={rascunho}
            onChange={(e) => setRascunho(e.target.value)}
            maxLength={300}
            className="rounded-md border border-linha bg-papel-2 px-3 py-2.5"
          />
        </div>
        <button
          type="submit"
          className="transicao rounded-md bg-lombada px-5 py-2.5 font-medium text-lombada-texto hover:opacity-90"
        >
          Buscar
        </button>
      </form>

      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="categoria" className="font-medium">
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
            className="rounded-md border border-linha bg-papel-2 px-3 py-2.5"
          >
            <option value="">Todas</option>
            {categorias.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.nome}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 py-2.5">
          <input
            type="checkbox"
            checked={soDisponiveis}
            onChange={(e) => {
              setCarregando(true);
              setPagina(1);
              setSoDisponiveis(e.target.checked);
            }}
            className="size-5 accent-lombada"
          />
          Só disponíveis
        </label>
      </div>

      {erro && (
        <p role="alert" className="border-l-4 border-alerta pl-3 text-alerta">
          {erro}
        </p>
      )}

      {carregando && !dados ? (
        <p className="text-tinta-suave">Carregando…</p>
      ) : dados && dados.itens.length === 0 && !erro ? (
        <p className="text-tinta-suave">Nenhum livro encontrado.</p>
      ) : (
        dados && (
          <>
            <p className="text-tinta-suave" aria-live="polite">
              {carregando ? "Buscando…" : busca ? `Resultados para “${busca}”` : `${dados.total} livros`}
            </p>
            <ul>
              {dados.itens.map((l) => (
                <CartaoLivro key={l.id} livro={l} />
              ))}
            </ul>
          </>
        )
      )}

      {!busca && dados && paginas > 1 && (
        <nav aria-label="Páginas" className="flex items-center gap-4">
          <button
            type="button"
            disabled={pagina <= 1}
            onClick={() => setPagina((p) => p - 1)}
            className="rounded-md border border-linha px-4 py-2 disabled:opacity-50"
          >
            Anterior
          </button>
          <span>
            Página {pagina} de {paginas}
          </span>
          <button
            type="button"
            disabled={pagina >= paginas}
            onClick={() => setPagina((p) => p + 1)}
            className="rounded-md border border-linha px-4 py-2 disabled:opacity-50"
          >
            Próxima
          </button>
        </nav>
      )}
    </div>
  );
}

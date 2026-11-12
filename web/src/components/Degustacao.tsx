"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent as KeyboardEventReact,
  type PointerEvent as PointerEventReact,
} from "react";
import { createPortal } from "react-dom";
import { rotuloVista, vistaDoItem, vistas, type Degustacao as DadosDegustacao, type Lado } from "@/lib/degustacao";
import { classesBotao } from "./ui/Botao";
import { IconeSeta } from "./ui/Icones";

// Folha em pé de virada; o fim da animação limpa a folha, e este prazo garante a limpeza mesmo
// se o `animationend` não vier (aba em segundo plano, por exemplo).
const PRAZO_VIRADA_MS = 900;
// Deslize mínimo (px) para virar a página no toque.
const DESLIZE_MIN = 48;

function useMidia(consulta: string): boolean {
  return useSyncExternalStore(
    (avisar) => {
      if (typeof window === "undefined" || !window.matchMedia) return () => {};
      const m = window.matchMedia(consulta);
      m.addEventListener("change", avisar);
      return () => m.removeEventListener("change", avisar);
    },
    () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(consulta).matches : false),
    () => false,
  );
}

type Livro = { id: number; titulo: string; autores: string[] };

type Props = {
  livro: Livro;
  degustacao: DadosDegustacao;
  onFechar: () => void;
};

type Virada = { de: number; dir: 1 | -1; n: number };

/**
 * Degustação: folhear as primeiras páginas de um livro, como num livro de papel. Em tela larga,
 * páginas duplas com a folha virando sobre a lombada; em tela estreita, uma página por vez.
 * Setas do teclado, botões, clique no lado da página ou deslize viram a página; Esc fecha.
 * A última página leva à ficha (para locar) e à conversa com a Léia.
 */
export function Degustacao({ livro, degustacao, onFechar }: Props) {
  const dupla = useMidia("(min-width: 768px)");
  const reduzido = useMidia("(prefers-reduced-motion: reduce)");
  const total = degustacao.paginas.length;
  const lista = useMemo(() => vistas(total, dupla), [total, dupla]);

  // O lugar é guardado como item (página), não como vista: muda de simples para dupla sem pular.
  const [item, setItem] = useState(0);
  const [virada, setVirada] = useState<Virada | null>(null);
  const vista = Math.min(vistaDoItem(item, dupla), lista.length - 1);
  const lados = lista[vista];

  const caixa = useRef<HTMLDivElement>(null);
  const fechar = useRef<HTMLButtonElement>(null);
  const toque = useRef<{ x: number; y: number } | null>(null);
  const deslizou = useRef(false);
  const contador = useRef(0);

  const ir = useCallback(
    (dir: 1 | -1, animar: boolean) => {
      const destino = vista + dir;
      if (destino < 0 || destino >= lista.length) return;
      const primeiro = lista[destino].find((l): l is number => l !== null) ?? 0;
      setItem(primeiro);
      if (animar && dupla && !reduzido) {
        contador.current += 1;
        setVirada({ de: vista, dir, n: contador.current });
      } else {
        setVirada(null);
      }
    },
    [vista, lista, dupla, reduzido],
  );

  // Foco entra no leitor; a página de trás não rola enquanto ele está aberto.
  useEffect(() => {
    fechar.current?.focus();
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = antes;
    };
  }, []);

  useEffect(() => {
    if (!virada) return;
    const t = window.setTimeout(() => setVirada((v) => (v?.n === virada.n ? null : v)), PRAZO_VIRADA_MS);
    return () => window.clearTimeout(t);
  }, [virada]);

  // Pré-carrega as vistas vizinhas: a próxima página já está pronta quando a folha vira.
  useEffect(() => {
    for (const v of [lista[vista + 1], lista[vista - 1]]) {
      for (const l of v ?? []) {
        if (l !== null && l < total) new Image().src = degustacao.paginas[l];
      }
    }
  }, [vista, lista, total, degustacao.paginas]);

  function teclas(e: KeyboardEventReact<HTMLDivElement>) {
    // Ação de teclado não anima (DESIGN.md, Movimento): a página troca na hora.
    if (e.key === "Escape") {
      e.preventDefault();
      onFechar();
    } else if (e.key === "ArrowRight" || e.key === "PageDown") {
      e.preventDefault();
      ir(1, false);
    } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
      e.preventDefault();
      ir(-1, false);
    } else if (e.key === "Tab") {
      // Foco preso no diálogo.
      const focaveis = caixa.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focaveis || focaveis.length === 0) return;
      const primeiro = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];
      if (e.shiftKey && document.activeElement === primeiro) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault();
        primeiro.focus();
      }
    }
  }

  function inicioToque(e: PointerEventReact) {
    deslizou.current = false;
    toque.current = e.pointerType === "mouse" ? null : { x: e.clientX, y: e.clientY };
  }

  function fimToque(e: PointerEventReact) {
    const t = toque.current;
    toque.current = null;
    if (!t) return;
    const dx = e.clientX - t.x;
    if (Math.abs(dx) >= DESLIZE_MIN && Math.abs(dx) > Math.abs(e.clientY - t.y)) {
      deslizou.current = true;
      ir(dx < 0 ? 1 : -1, true);
    }
  }

  /** Clique no lado da página: o lado direito avança, o esquerdo volta (como no papel). */
  function cliqueNaPagina(lado: "esq" | "dir") {
    if (deslizou.current) {
      deslizou.current = false;
      return;
    }
    ir(lado === "dir" ? 1 : -1, true);
  }

  function pagina(l: Lado, extra = "") {
    if (l === null) return <div aria-hidden="true" className={`degustacao-pagina degustacao-vazia ${extra}`} />;
    if (l >= total) {
      return (
        <div className={`degustacao-pagina degustacao-fim ${extra}`}>
          <p className="degustacao-fim-titulo">Fim da degustação</p>
          <p>
            Gostou de <cite>{livro.titulo}</cite>? O livro inteiro está no acervo da Léia.
          </p>
          <div className="flex flex-col gap-2">
            <Link href={`/livro/${livro.id}`} className={classesBotao("primaria", "degustacao-fim-acao")}>
              Ver ficha e locar
            </Link>
            <Link href="/conversa" className="degustacao-fim-link">
              Conversar com a Léia
            </Link>
          </div>
        </div>
      );
    }
    return (
      <div className={`degustacao-pagina ${extra}`}>
        {/* Páginas geradas localmente (public/degustacao); next/image não ajuda aqui. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={degustacao.paginas[l]}
          alt={l === 0 ? `Capa de ${livro.titulo}` : `Página ${l} de ${livro.titulo}`}
          draggable={false}
          decoding="async"
        />
      </div>
    );
  }

  // Durante a virada, por baixo ficam o lado que a folha ainda não cobriu (da vista anterior) e
  // o lado que ela já descobriu (da vista nova). A folha leva a frente e o verso.
  const de = virada ? lista[virada.de] : null;
  const base: Lado[] =
    dupla && virada && de
      ? virada.dir === 1
        ? [de[0], lados[1]]
        : [lados[0], de[1]]
      : lados;
  const rotulo = rotuloVista(lados, total);
  const razao = (degustacao.largura * (dupla ? 2 : 1)) / degustacao.altura;
  const noInicio = vista === 0;
  const noFim = vista === lista.length - 1;

  return createPortal(
    <div
      ref={caixa}
      role="dialog"
      aria-modal="true"
      aria-label={`Degustação: ${livro.titulo}`}
      className="degustacao vidro-fosco"
      onKeyDown={teclas}
    >
      <div className="degustacao-topo">
        <div className="min-w-0">
          <h2 className="truncate text-xl font-bold">{livro.titulo}</h2>
          {livro.autores.length > 0 && (
            <p className="truncate text-sm text-texto-suave">{livro.autores.join(", ")}</p>
          )}
        </div>
        <button ref={fechar} type="button" className={classesBotao("secundaria", "shrink-0")} onClick={onFechar}>
          Fechar
        </button>
      </div>

      <div className="degustacao-palco">
        <button
          type="button"
          className="degustacao-seta degustacao-seta-voltar"
          onClick={() => ir(-1, true)}
          disabled={noInicio}
        >
          <IconeSeta className="rotate-180" />
          <span className="sr-only">Página anterior</span>
        </button>

        <div
          className="degustacao-livro"
          data-dupla={dupla || undefined}
          data-so={dupla ? (lados[0] === null ? "dir" : lados[1] === null ? "esq" : undefined) : undefined}
          style={{ ["--razao" as string]: razao }}
          onPointerDown={inicioToque}
          onPointerUp={fimToque}
          onPointerCancel={() => (toque.current = null)}
        >
          {dupla ? (
            <>
              <div className="degustacao-lado degustacao-lado-esq" onClick={() => cliqueNaPagina("esq")}>
                {pagina(base[0], "degustacao-pagina-esq")}
              </div>
              <div className="degustacao-lado degustacao-lado-dir" onClick={() => cliqueNaPagina("dir")}>
                {pagina(base[1], "degustacao-pagina-dir")}
              </div>
              {virada && de && (
                <div
                  key={virada.n}
                  aria-hidden="true"
                  className="degustacao-folha"
                  data-dir={virada.dir === 1 ? "avanca" : "volta"}
                  onAnimationEnd={() => setVirada((v) => (v?.n === virada.n ? null : v))}
                >
                  <div className="degustacao-face">
                    {pagina(virada.dir === 1 ? de[1] : de[0], virada.dir === 1 ? "degustacao-pagina-dir" : "degustacao-pagina-esq")}
                  </div>
                  <div className="degustacao-face degustacao-verso">
                    {pagina(virada.dir === 1 ? lados[0] : lados[1], virada.dir === 1 ? "degustacao-pagina-esq" : "degustacao-pagina-dir")}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div
              key={vista}
              className="degustacao-lado degustacao-unica"
              onClick={(e) => {
                const r = e.currentTarget.getBoundingClientRect();
                cliqueNaPagina(e.clientX - r.left < r.width / 2 ? "esq" : "dir");
              }}
            >
              {pagina(lados[0])}
            </div>
          )}
        </div>

        <button
          type="button"
          className="degustacao-seta degustacao-seta-avancar"
          onClick={() => ir(1, true)}
          disabled={noFim}
        >
          <IconeSeta />
          <span className="sr-only">Próxima página</span>
        </button>
      </div>

      <p className="degustacao-rodape" aria-live="polite">
        {rotulo}
      </p>
    </div>,
    document.body,
  );
}

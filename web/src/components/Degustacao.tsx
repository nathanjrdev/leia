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
import { progressoDaBorda } from "@/lib/curvatura";
import { rotuloVista, vistaDoItem, vistas, type Degustacao as DadosDegustacao, type Lado } from "@/lib/degustacao";
import { conduz, decodifica, FolhaCurva, imagem, novoMotor, type Face, type Motor } from "./FolhaCurva";
import { classesBotao } from "./ui/Botao";
import { IconeSeta } from "./ui/Icones";

// Prazo de segurança: se o requestAnimationFrame parar (aba em segundo plano) ou a página de
// baixo demorar a decodificar, a folha some mesmo assim.
const FOLGA_PRAZO_MS = 1200;
// Virada inteira pelo botão ou clique (momento focal, um pouco acima de --dur-foco).
const DUR_VIRADA_MS = 720;
// Deslize mínimo (px) para virar a página no toque sem arrastar a folha.
const DESLIZE_MIN = 48;
// Distância (px) a partir da qual o gesto vira arrasto da folha.
const ARRASTO_MIN = 8;

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

/**
 * A folha entre a vista `k` e a `k + 1`. `final` é o lado em que vai assentar (1 = vira para a
 * vista k + 1, 0 = fica na k); `null` enquanto o dedo a segura.
 */
type Virada = { k: number; n: number; dir: 1 | -1; final: 0 | 1 | null };

type Gesto = {
  id: number;
  x: number;
  y: number;
  toque: boolean;
  arrasto: { dir: 1 | -1; desvio: number; rastro: { x: number; t: number }[] } | null;
};

/**
 * Degustação: folhear as primeiras páginas de um livro, como num livro de papel. Em tela larga,
 * páginas duplas; em tela estreita, uma página por vez. A folha enrola de verdade ao virar
 * (FolhaCurva) e pode ser puxada com o dedo ou o mouse. Setas do teclado, botões, clique no lado
 * da página ou deslize viram a página; Esc fecha. A última página leva à ficha e à conversa.
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
  const livroEl = useRef<HTMLDivElement>(null);
  const fechar = useRef<HTMLButtonElement>(null);
  const gesto = useRef<Gesto | null>(null);
  const deslizou = useRef(false);
  const contador = useRef(0);
  const motor = useRef<Motor>(novoMotor(0));

  const irPara = useCallback(
    (destino: number) => {
      const primeiro = lista[destino].find((l): l is number => l !== null) ?? 0;
      setItem(primeiro);
    },
    [lista],
  );

  const ir = useCallback(
    (dir: 1 | -1, animar: boolean) => {
      const destino = vista + dir;
      if (destino < 0 || destino >= lista.length) return;
      irPara(destino);
      if (animar && !reduzido) {
        // A folha sai de onde está; o conteúdo novo já entrou no DOM.
        const m = novoMotor(dir === 1 ? 0 : 1);
        conduz(m, dir === 1 ? 1 : 0, DUR_VIRADA_MS, "suave");
        motor.current = m;
        contador.current += 1;
        setVirada({ k: dir === 1 ? vista : destino, n: contador.current, dir, final: dir === 1 ? 1 : 0 });
      } else {
        setVirada(null);
      }
    },
    [vista, lista, reduzido, irPara],
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
    if (!virada || virada.final === null) return;
    const t = window.setTimeout(
      () => setVirada((v) => (v?.n === virada.n ? null : v)),
      motor.current.dur + FOLGA_PRAZO_MS,
    );
    return () => window.clearTimeout(t);
  }, [virada]);

  // Pré-carrega e decodifica todas as páginas ao abrir (são ~10 imagens leves), começando pelas
  // vizinhas: quando a folha vira, a página já está pronta e nada pisca.
  useEffect(() => {
    const perto = [lista[vista + 1], lista[vista - 1]].flatMap((v) => v ?? []);
    for (const l of perto) if (l !== null && l < total) imagem(degustacao.paginas[l]);
    for (const src of degustacao.paginas) imagem(src);
  }, [vista, lista, total, degustacao.paginas]);

  /** A folha assentou: só sai de cima quando as páginas do DOM já estão decodificadas. */
  const folhaAssentou = useCallback((n: number) => {
    const imgs = Array.from(livroEl.current?.querySelectorAll("img") ?? []);
    Promise.all(imgs.map(decodifica)).then(() => setVirada((v) => (v?.n === n ? null : v)));
  }, []);

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

  /** Onde está o ponteiro, medido a partir da lombada, e a largura de uma página. */
  function medida(clientX: number) {
    const r = livroEl.current!.getBoundingClientRect();
    const W = dupla ? r.width / 2 : r.width;
    return { x: clientX - (r.left + (dupla ? W : 0)), W };
  }

  function inicioGesto(e: PointerEventReact) {
    deslizou.current = false;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    // Enquanto a folha anda sozinha, um novo toque não a agarra (o clique ainda vira).
    gesto.current = { id: e.pointerId, x: e.clientX, y: e.clientY, toque: e.pointerType !== "mouse", arrasto: null };
  }

  function moveGesto(e: PointerEventReact) {
    const g = gesto.current;
    if (!g || g.id !== e.pointerId || reduzido) return;
    if (!g.arrasto) {
      const dx = e.clientX - g.x;
      const dy = e.clientY - g.y;
      if (Math.abs(dx) < ARRASTO_MIN || Math.abs(dx) <= Math.abs(dy)) return;
      const dir: 1 | -1 = dx < 0 ? 1 : -1;
      const destino = vista + dir;
      if (destino < 0 || destino >= lista.length || (virada && virada.final !== null)) {
        gesto.current = null;
        return;
      }
      // A borda da folha acompanha a mão a partir de onde ela agarrou.
      const { x, W } = medida(g.x);
      const desvio = (dir === 1 ? W : -W) - x;
      g.arrasto = { dir, desvio, rastro: [] };
      motor.current = novoMotor(dir === 1 ? 0 : 1);
      contador.current += 1;
      setVirada({ k: dir === 1 ? vista : destino, n: contador.current, dir, final: null });
      try {
        livroEl.current?.setPointerCapture(e.pointerId);
      } catch {
        // Sem captura (ponteiro sintético): o gesto segue pelos eventos do próprio livro.
      }
    }
    const { x, W } = medida(e.clientX);
    motor.current.dedo = progressoDaBorda(x + g.arrasto.desvio, W, g.arrasto.dir);
    const agora = performance.now();
    g.arrasto.rastro.push({ x: e.clientX, t: agora });
    while (g.arrasto.rastro.length > 2 && agora - g.arrasto.rastro[0].t > 100) g.arrasto.rastro.shift();
  }

  function fimGesto(e: PointerEventReact) {
    const g = gesto.current;
    gesto.current = null;
    if (!g || g.id !== e.pointerId) return;
    if (g.arrasto) {
      deslizou.current = true;
      const { dir, rastro } = g.arrasto;
      const r0 = rastro[0];
      const dt = r0 ? performance.now() - r0.t : 0;
      const vel = r0 && dt > 0 ? (e.clientX - r0.x) / dt : 0; // px/ms; negativo = para a esquerda
      const m = motor.current;
      m.dedo = m.p;
      // Vira se passou de ~40% do caminho ou se foi um peteleco para o lado certo.
      const vira =
        dir === 1 ? vel < -0.45 || (m.p > 0.4 && vel < 0.3) : vel > 0.45 || (m.p < 0.6 && vel > -0.3);
      const final: 0 | 1 = dir === 1 ? (vira ? 1 : 0) : vira ? 0 : 1;
      if (vira) irPara(vista + dir);
      conduz(m, final, Math.max(160, 560 * Math.abs(final - m.p)), "assenta");
      setVirada((v) => (v ? { ...v, final } : v));
      return;
    }
    // Deslize curto no toque, sem mover a folha (ou com movimento reduzido).
    const dx = e.clientX - g.x;
    if (g.toque && Math.abs(dx) >= DESLIZE_MIN && Math.abs(dx) > Math.abs(e.clientY - g.y)) {
      deslizou.current = true;
      ir(dx < 0 ? 1 : -1, true);
    }
  }

  function cancelaGesto(e: PointerEventReact) {
    const g = gesto.current;
    gesto.current = null;
    if (!g?.arrasto || g.id !== e.pointerId) return;
    const m = motor.current;
    const final: 0 | 1 = g.arrasto.dir === 1 ? 0 : 1;
    conduz(m, final, Math.max(160, 560 * Math.abs(final - m.p)), "assenta");
    setVirada((v) => (v ? { ...v, final } : v));
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

  // Durante a virada, o canvas pinta o livro: por baixo, o lado esquerdo da vista k e o direito
  // da k + 1; a folha leva a frente (direita da k) e o verso (esquerda da k + 1). Em página
  // simples, por baixo fica a k + 1 e a folha (a k) sai pela esquerda, de costas em branco.
  const face = (l: Lado | undefined): Face =>
    l === null || l === undefined ? null : l >= total ? { tipo: "fim" } : { tipo: "pagina", src: degustacao.paginas[l] };
  const vk = virada ? lista[virada.k] : null;
  const vk1 = virada ? lista[virada.k + 1] : null;
  const sombraDe: Lado[] = vk && vk1 ? [vk[0], vk1[1]] : lados;
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
          ref={livroEl}
          className="degustacao-livro"
          data-dupla={dupla || undefined}
          data-so={dupla ? (sombraDe[0] === null ? "dir" : sombraDe[1] === null ? "esq" : undefined) : undefined}
          data-arrastando={virada?.final === null || undefined}
          style={{ ["--razao" as string]: razao }}
          onPointerDown={inicioGesto}
          onPointerMove={moveGesto}
          onPointerUp={fimGesto}
          onPointerCancel={cancelaGesto}
        >
          {dupla ? (
            <>
              <div className="degustacao-lado degustacao-lado-esq" onClick={() => cliqueNaPagina("esq")}>
                {pagina(lados[0], "degustacao-pagina-esq")}
              </div>
              <div className="degustacao-lado degustacao-lado-dir" onClick={() => cliqueNaPagina("dir")}>
                {pagina(lados[1], "degustacao-pagina-dir")}
              </div>
            </>
          ) : (
            <div
              className="degustacao-lado degustacao-unica"
              onClick={(e) => {
                const r = e.currentTarget.getBoundingClientRect();
                cliqueNaPagina(e.clientX - r.left < r.width / 2 ? "esq" : "dir");
              }}
            >
              {pagina(lados[0])}
            </div>
          )}
          {virada && vk && vk1 && (
            <FolhaCurva
              key={virada.n}
              dupla={dupla}
              baixoEsq={dupla ? face(vk[0]) : null}
              baixoDir={face(dupla ? vk1[1] : vk1[0])}
              frente={face(dupla ? vk[1] : vk[0])}
              verso={dupla ? face(vk1[0]) : { tipo: "papel" }}
              motor={motor}
              titulo={livro.titulo}
              livro={livroEl}
              dir={virada.dir}
              onFim={() => folhaAssentou(virada.n)}
            />
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

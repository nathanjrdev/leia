"use client";

import { useEffect, useRef } from "react";

/**
 * Chaveiro de livros pendurado na prateleira da página inicial (plano, seção 11). Decorativo.
 *
 * Asset nosso: o render 3D "Chaveiro Livros Prata 3D" (argola, corrente articulada e pilha de
 * três livros em prata), exportado em camadas para `public/objetos/` e montado aqui num SVG com
 * as mesmas coordenadas do arquivo de origem (quadro de 1400 × 1400). Separar as camadas é o que
 * deixa a corrente e a pilha girarem cada uma no seu ponto.
 *
 * Movimento: pêndulo duplo amortecido (a corrente gira no topo da argola; a pilha gira no elo de
 * baixo, com atraso), calculado em requestAnimationFrame. Balança ao aparecer, quando o cursor
 * passa perto (o empurrão segue a velocidade horizontal do ponteiro) e ao tocar. O laço para
 * sozinho quando assenta, então nunca fica em loop. Com movimento reduzido, fica parado.
 * Não captura eventos (`pointer-events: none`): as capas embaixo continuam clicáveis.
 */
// Recorte do quadro de origem, centrado na corrente (x = 745) para o ponto de pendura ficar no meio.
const CAIXA = { x: 445, y: 110, largura: 600, altura: 1175 };
const TOPO = { x: 745, y: 122 }; // alto da argola: ponto de pendura
const ELO = { x: 742, y: 738 }; // último elo, preso à argolinha da pilha: onde a pilha gira

// Camadas na posição e tamanho do arquivo de origem.
const ARGOLA = { href: "/objetos/chaveiro-argola.webp", x: 698, y: 113, largura: 94, altura: 221 };
const CORRENTE = { href: "/objetos/chaveiro-corrente.webp", x: 712, y: 314, largura: 62, altura: 440 };
const LIVROS = { href: "/objetos/chaveiro-livros.webp", x: 450, y: 697, largura: 500, altura: 583 };

// Física em graus e segundos.
const MOLA_CORRENTE = 30;
const ATRITO_CORRENTE = 2.9;
const MOLA_PILHA = 70;
const ATRITO_PILHA = 4;
const ACOPLAMENTO = 0.85; // quanto a pilha "fica para trás" quando a corrente acelera
const MAX_ANGULO = 32;
const MAX_EMPURRAO = 140; // graus/s
const ALCANCE_PX = 48; // margem em volta do chaveiro onde o cursor empurra

const limitar = (v: number, m: number) => Math.max(-m, Math.min(m, v));

export function Chaveiro() {
  const raiz = useRef<HTMLDivElement>(null);
  const corrente = useRef<SVGGElement>(null);
  const pilha = useRef<SVGGElement>(null);

  useEffect(() => {
    const el = raiz.current;
    if (!el) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;

    const s = { a1: 9, v1: 0, a2: -6, v2: 0 };
    let quadro = 0;
    let ultimo = 0;
    let ponteiro: { x: number; t: number } | null = null;

    const desenhar = () => {
      corrente.current?.setAttribute("transform", `rotate(${s.a1.toFixed(3)} ${TOPO.x} ${TOPO.y})`);
      pilha.current?.setAttribute("transform", `rotate(${s.a2.toFixed(3)} ${ELO.x} ${ELO.y})`);
    };

    const passo = (agora: number) => {
      const dt = Math.min((agora - (ultimo || agora)) / 1000, 1 / 30);
      ultimo = agora;
      const sub = 4;
      const h = dt / sub;
      for (let i = 0; i < sub; i++) {
        const ac1 = -MOLA_CORRENTE * s.a1 - ATRITO_CORRENTE * s.v1;
        const ac2 = -MOLA_PILHA * s.a2 - ATRITO_PILHA * s.v2 - ACOPLAMENTO * ac1;
        s.v1 += ac1 * h;
        s.v2 += ac2 * h;
        s.a1 = limitar(s.a1 + s.v1 * h, MAX_ANGULO);
        s.a2 = limitar(s.a2 + s.v2 * h, MAX_ANGULO);
      }
      desenhar();
      const parado =
        Math.abs(s.a1) < 0.03 && Math.abs(s.v1) < 0.05 && Math.abs(s.a2) < 0.03 && Math.abs(s.v2) < 0.05;
      if (parado) {
        Object.assign(s, { a1: 0, v1: 0, a2: 0, v2: 0 });
        desenhar();
        quadro = 0;
        ultimo = 0;
        return;
      }
      quadro = requestAnimationFrame(passo);
    };

    const acordar = () => {
      if (!quadro) quadro = requestAnimationFrame(passo);
    };

    const perto = (x: number, y: number) => {
      const r = el.getBoundingClientRect();
      return (
        x > r.left - ALCANCE_PX && x < r.right + ALCANCE_PX && y > r.top - ALCANCE_PX && y < r.bottom + ALCANCE_PX
      );
    };

    const aoMover = (e: PointerEvent) => {
      const anterior = ponteiro;
      ponteiro = { x: e.clientX, t: e.timeStamp };
      if (!anterior || !perto(e.clientX, e.clientY)) return;
      const ms = Math.max(e.timeStamp - anterior.t, 8);
      const vx = (e.clientX - anterior.x) / ms; // px/ms
      const empurrao = limitar(vx * 55, MAX_EMPURRAO) * (1 / 6);
      if (Math.abs(empurrao) < 0.5) return;
      s.v1 -= empurrao; // rotate() positivo leva a pilha para a esquerda: o cursor empurra no sentido dele
      s.v2 -= empurrao * 1.4;
      acordar();
    };

    const aoTocar = (e: PointerEvent) => {
      if (!perto(e.clientX, e.clientY)) return;
      const r = el.getBoundingClientRect();
      const lado = e.clientX < r.left + r.width / 2 ? -1 : 1;
      s.v1 += 70 * lado;
      s.v2 += 90 * lado;
      acordar();
    };

    desenhar();
    acordar();
    window.addEventListener("pointermove", aoMover, { passive: true });
    window.addEventListener("pointerdown", aoTocar, { passive: true });
    return () => {
      cancelAnimationFrame(quadro);
      window.removeEventListener("pointermove", aoMover);
      window.removeEventListener("pointerdown", aoTocar);
    };
  }, []);


  return (
    <div ref={raiz} className="chaveiro" aria-hidden="true">
      <svg
        viewBox={`${CAIXA.x} ${CAIXA.y} ${CAIXA.largura} ${CAIXA.altura}`}
        width={CAIXA.largura}
        height={CAIXA.altura}
        focusable="false"
      >
        <g ref={corrente}>
          <g ref={pilha}>
            <Camada {...LIVROS} />
          </g>
          {/* a corrente vem depois da pilha: o último elo passa por cima da argolinha dos livros */}
          <Camada {...CORRENTE} />
          <Camada {...ARGOLA} />
        </g>
      </svg>
    </div>
  );
}

function Camada({ href, x, y, largura, altura }: { href: string; x: number; y: number; largura: number; altura: number }) {
  return <image href={href} x={x} y={y} width={largura} height={altura} preserveAspectRatio="none" />;
}

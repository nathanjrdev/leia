"use client";

import { useEffect, useLayoutEffect, useRef } from "react";
import { assenta, curva, projeta, suaviza } from "@/lib/curvatura";

/**
 * A folha que vira na Degustação, desenhada num canvas: em vez de girar dura sobre a lombada, ela
 * enrola sobre um cilindro (ver `lib/curvatura.ts`), com sombra na página de baixo, brilho na
 * dobra e um leve ganho de escala onde sobe na direção do leitor. Puxada pelo dedo (ou mouse),
 * segue a mão; solta, termina a virada ou volta ao lugar.
 *
 * O canvas pinta o livro inteiro enquanto a folha anda (páginas de baixo e folha); o DOM por baixo
 * já mostra a vista nova (leitor de tela e testes leem o DOM) e só fica transparente depois do
 * primeiro quadro pintado, para não piscar. Decorativo: `aria-hidden`.
 */

/** O que vai numa face: uma página (URL), a página de fim, papel em branco ou nada (lado vazio). */
export type Face = { tipo: "pagina"; src: string } | { tipo: "fim" } | { tipo: "papel" } | null;

/**
 * Quem move a folha. `alvo === null`: segue `dedo` (arrasto). Com alvo: vai de `p0` ao alvo em
 * `dur` ms a partir de `t0`, na curva `curvaTempo`.
 */
export type Motor = {
  p: number;
  dedo: number;
  alvo: 0 | 1 | null;
  p0: number;
  t0: number;
  dur: number;
  curvaTempo: "suave" | "assenta";
};

export function novoMotor(p: number): Motor {
  return { p, dedo: p, alvo: null, p0: p, t0: 0, dur: 0, curvaTempo: "suave" };
}

export function conduz(m: Motor, alvo: 0 | 1, dur: number, curvaTempo: Motor["curvaTempo"]) {
  m.p0 = m.p;
  m.alvo = alvo;
  m.t0 = performance.now();
  m.dur = dur;
  m.curvaTempo = curvaTempo;
}

type Props = {
  dupla: boolean;
  /** Para onde o leitor está indo (só para o estilo e para quem inspeciona o DOM). */
  dir: 1 | -1;
  /** Página de baixo à esquerda (só em dupla) e à direita (ou a única). */
  baixoEsq: Face;
  baixoDir: Face;
  frente: Face;
  verso: Face;
  motor: React.RefObject<Motor>;
  titulo: string;
  /** Chamado quando a folha assenta num dos lados (0 = à direita, 1 = à esquerda). */
  onFim: (lado: 0 | 1) => void;
  /** O livro (DOM) recebe `data-coberta` enquanto o canvas o cobre. */
  livro: React.RefObject<HTMLDivElement | null>;
};

// Folga acima e abaixo do livro: a parte que sobe cresce com a perspectiva.
const FOLGA = 0.14;
// Distância da câmera, em larguras de página (quanto menor, mais forte a perspectiva).
const DISTANCIA = 5;

const imagens = new Map<string, HTMLImageElement>();

/** Imagem já decodificada (o leitor pré-carrega as vistas vizinhas por aqui). */
export function imagem(src: string): HTMLImageElement {
  let img = imagens.get(src);
  if (!img) {
    img = new Image();
    img.decoding = "async";
    img.src = src;
    imagens.set(src, img);
    void decodifica(img); // decodifica já: a folha e a página não esperam por isso depois
  }
  return img;
}

/** Espera a imagem estar pronta para pintar (sem `decode`, como no jsdom, só segue). */
export function decodifica(img: HTMLImageElement): Promise<void> {
  return typeof img.decode === "function" ? img.decode().catch(() => undefined) : Promise.resolve();
}

function pronta(f: Face): boolean {
  if (f?.tipo !== "pagina") return true;
  const img = imagem(f.src);
  return img.complete && img.naturalWidth > 0;
}

type Lombada = "esq" | "dir" | null;

/** Pinta uma face num canvas do tamanho da página, como o DOM a mostra (papel, imagem contida). */
function pintaFace(f: Face, w: number, h: number, dpr: number, lombada: Lombada, titulo: string) {
  if (!f) return null;
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w * dpr));
  c.height = Math.max(1, Math.round(h * dpr));
  const ctx = c.getContext("2d");
  if (!ctx) return null;
  ctx.scale(dpr, dpr);
  const css = getComputedStyle(document.documentElement);
  const creme = css.getPropertyValue("--capa-creme").trim() || "#f1ece2";
  const tinta = css.getPropertyValue("--capa-creme-letra").trim() || "#1a1a1a";
  ctx.fillStyle = creme;
  ctx.fillRect(0, 0, w, h);

  if (f.tipo === "pagina") {
    const img = imagem(f.src);
    if (img.naturalWidth > 0) {
      const r = Math.min(w / img.naturalWidth, h / img.naturalHeight);
      const iw = img.naturalWidth * r;
      const ih = img.naturalHeight * r;
      ctx.drawImage(img, (w - iw) / 2, (h - ih) / 2, iw, ih);
    }
  } else if (f.tipo === "fim") {
    // Só um esboço da página de fim (ela passa em meio segundo); a de verdade está no DOM.
    const fonte = getComputedStyle(document.body).fontFamily || "sans-serif";
    const pad = Math.max(20, Math.min(40, w * 0.06));
    const corpo = Math.max(14, Math.min(17, w * 0.032));
    const tit = Math.max(21, Math.min(32, w * 0.06));
    ctx.fillStyle = tinta;
    ctx.textBaseline = "top";
    ctx.font = `700 ${tit}px ${fonte}`;
    let y = h / 2 - tit * 2.4;
    ctx.fillText("Fim da degustação", pad, y);
    y += tit * 1.5;
    ctx.font = `400 ${corpo}px ${fonte}`;
    const palavras = `Gostou de ${titulo}? O livro inteiro está no acervo da Léia.`.split(" ");
    let linha = "";
    for (const p of palavras) {
      const tenta = linha ? `${linha} ${p}` : p;
      if (ctx.measureText(tenta).width > w - 2 * pad && linha) {
        ctx.fillText(linha, pad, y);
        y += corpo * 1.5;
        linha = p;
      } else linha = tenta;
    }
    if (linha) ctx.fillText(linha, pad, y);
    y += corpo * 2.6;
    ctx.fillStyle = css.getPropertyValue("--fundo").trim() || "#1a1030";
    const bw = Math.min(w - 2 * pad, corpo * 12);
    ctx.beginPath();
    ctx.roundRect(pad, y, bw, 44, 22);
    ctx.fill();
  }

  // A mesma sombra de lombada do CSS (.degustacao-pagina-esq/-dir::after).
  if (lombada === "dir") {
    const g = ctx.createLinearGradient(0, 0, w * 0.08, 0);
    g.addColorStop(0, "rgb(0 0 0 / 0.2)");
    g.addColorStop(1, "rgb(0 0 0 / 0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w * 0.08, h);
  } else if (lombada === "esq") {
    const g = ctx.createLinearGradient(w, 0, w * 0.91, 0);
    g.addColorStop(0, "rgb(0 0 0 / 0.22)");
    g.addColorStop(1, "rgb(0 0 0 / 0)");
    ctx.fillStyle = g;
    ctx.fillRect(w * 0.91, 0, w * 0.09, h);
  }
  return c;
}

export function FolhaCurva({ dupla, dir, baixoEsq, baixoDir, frente, verso, motor: motorRef, titulo, onFim, livro }: Props) {
  const tela = useRef<HTMLCanvasElement>(null);
  const aoFim = useRef(onFim);
  useLayoutEffect(() => {
    aoFim.current = onFim;
  });

  useLayoutEffect(() => {
    const canvas = tela.current;
    const caixa = livro.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !caixa || !ctx) return;

    const motor = motorRef.current;
    let vivo = true;
    let quadro = 0;
    let faces: ReturnType<typeof montaFaces> | null = null;
    let medida = { W: 0, H: 0, dpr: 1 };

    function mede() {
      const r = caixa!.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const W = dupla ? r.width / 2 : r.width;
      const H = r.height;
      if (W !== medida.W || H !== medida.H || dpr !== medida.dpr) {
        medida = { W, H, dpr };
        canvas!.width = Math.round(r.width * dpr);
        canvas!.height = Math.round(H * (1 + 2 * FOLGA) * dpr);
        faces = null;
      }
    }

    function montaFaces() {
      const { W, H, dpr } = medida;
      return {
        baixoEsq: dupla ? pintaFace(baixoEsq, W, H, dpr, "esq", titulo) : null,
        baixoDir: pintaFace(baixoDir, W, H, dpr, dupla ? "dir" : null, titulo),
        frente: pintaFace(frente, W, H, dpr, dupla ? "dir" : null, titulo),
        verso: pintaFace(verso, W, H, dpr, dupla ? "esq" : null, titulo),
      };
    }

    function progresso(agora: number): number {
      const m = motor;
      if (m.alvo === null) {
        // Segue o dedo com um pouco de inércia (sem atraso perceptível).
        m.p += (m.dedo - m.p) * 0.45;
        return m.p;
      }
      const t = m.dur > 0 ? (agora - m.t0) / m.dur : 1;
      const e = m.curvaTempo === "assenta" ? assenta(t) : suaviza(t);
      m.p = m.p0 + (m.alvo - m.p0) * e;
      return m.p;
    }

    function desenha(agora: number) {
      if (!vivo) return;
      mede();
      const { W, H, dpr } = medida;
      if (W <= 0 || H <= 0) {
        quadro = requestAnimationFrame(desenha);
        return;
      }
      if (!faces) faces = montaFaces();
      const p = progresso(agora);
      const topo = H * FOLGA;
      const lombada = dupla ? W : 0;

      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx!.clearRect(0, 0, canvas!.width, canvas!.height);

      // Páginas de baixo.
      if (faces.baixoEsq) ctx!.drawImage(faces.baixoEsq, 0, topo, W, H);
      if (faces.baixoDir) ctx!.drawImage(faces.baixoDir, lombada, topo, W, H);

      const c = curva(p, W, dir);
      const forca = Math.sin(Math.PI * p);
      // Perspectiva: a câmera fica sobre o meio do livro aberto (a lombada) ou da página única.
      const cx = dupla ? 0 : W / 2;
      const meioY = topo + H / 2;
      const dist = W * DISTANCIA;
      const n = Math.min(240, Math.max(64, Math.ceil(W / 2)));
      const passo = W / n;
      const pts = Array.from({ length: n + 1 }, (_, i) => {
        const q = projeta(i * passo, c);
        const esc = dist / (dist - q.z);
        return { ...q, X: lombada + cx + (q.x - cx) * esc, esc };
      });
      let maxX = -Infinity;
      let minX = Infinity;
      for (const q of pts) {
        maxX = Math.max(maxX, q.X);
        minX = Math.min(minX, q.X);
      }

      // Sombra que a folha joga na página da direita, logo além de onde ela alcança.
      if (forca > 0.001 && faces.baixoDir && maxX < lombada + W) {
        const ini = Math.max(lombada, maxX);
        const larg = W * (0.04 + 0.16 * forca);
        const g = ctx!.createLinearGradient(ini, 0, ini + larg, 0);
        g.addColorStop(0, `rgb(0 0 0 / ${0.3 * forca})`);
        g.addColorStop(1, "rgb(0 0 0 / 0)");
        ctx!.fillStyle = g;
        ctx!.fillRect(ini, topo, Math.min(larg, lombada + W - ini), H);
      }
      // E na da esquerda, antes de onde ela vai deitar.
      if (dupla && forca > 0.001 && faces.baixoEsq && minX > 0) {
        const fim = Math.min(lombada, minX);
        const larg = W * (0.04 + 0.16 * forca);
        const g = ctx!.createLinearGradient(fim, 0, fim - larg, 0);
        g.addColorStop(0, `rgb(0 0 0 / ${0.26 * forca})`);
        g.addColorStop(1, "rgb(0 0 0 / 0)");
        ctx!.fillStyle = g;
        ctx!.fillRect(Math.max(0, fim - larg), topo, Math.min(larg, fim), H);
      }

      // A folha, em fatias finas, da lombada para a borda: a altura só cresce nesse sentido, então
      // a ordem de pintura já põe por cima o que está mais perto do leitor. Cada trecho de uma
      // mesma face recebe a imagem em fatias e depois a luz num polígono só (sem emendas).
      const costasDe = (i: number) => (pts[i].angulo + pts[i + 1].angulo) / 2 > Math.PI / 2;
      let i0 = 0;
      while (i0 < n) {
        const costas = costasDe(i0);
        let i1 = i0;
        while (i1 < n && costasDe(i1) === costas) i1++;
        const face = costas ? faces.verso : faces.frente;
        for (let i = i0; i < i1; i++) {
          const a0 = pts[i];
          const a1 = pts[i + 1];
          const largo = Math.abs(a1.X - a0.X);
          if (!face || largo < 0.05) continue;
          const esc = (a0.esc + a1.esc) / 2;
          const dh = H * esc;
          const x0 = i * passo;
          const u = costas ? W - x0 - passo : x0;
          const k = face.width / W;
          // A imagem sobrepõe 0,6 px: sem frestas entre fatias.
          ctx!.drawImage(face, u * k, 0, passo * k, face.height, Math.min(a0.X, a1.X), meioY - dh / 2, largo + 0.6, dh);
        }
        luz(pts.slice(i0, i1 + 1), costas);
        i0 = i1;
      }

      function luz(trecho: typeof pts, costas: boolean) {
        let xMin = Infinity;
        let xMax = -Infinity;
        for (const q of trecho) {
          xMin = Math.min(xMin, q.X);
          xMax = Math.max(xMax, q.X);
        }
        if (xMax - xMin < 0.5) return;
        const contorno = () => {
          ctx!.beginPath();
          trecho.forEach((q, j) => {
            const y = meioY - (H * q.esc) / 2;
            if (j === 0) ctx!.moveTo(q.X, y);
            else ctx!.lineTo(q.X, y);
          });
          for (let j = trecho.length - 1; j >= 0; j--) ctx!.lineTo(trecho[j].X, meioY + (H * trecho[j].esc) / 2);
          ctx!.closePath();
        };
        const passoCor = Math.max(1, Math.floor(trecho.length / 32));
        // Escurece onde a folha fica de lado para o leitor (luz de cima); brilho na dobra.
        const sombra = ctx!.createLinearGradient(xMin, 0, xMax, 0);
        const reflexo = ctx!.createLinearGradient(xMin, 0, xMax, 0);
        let temSombra = false;
        let temReflexo = false;
        for (let j = 0; j < trecho.length; j += passoCor) {
          const q = trecho[j];
          const o = (q.X - xMin) / (xMax - xMin);
          const lado = Math.abs(Math.sin(q.angulo));
          const escuro = costas ? 0.3 * Math.pow(lado, 1.8) : 0.34 * Math.pow(lado, 1.5);
          const brilho = costas
            ? 0.18 * Math.exp(-(((q.angulo - 2.2) / 0.3) ** 2))
            : 0.1 * Math.exp(-(((q.angulo - 0.7) / 0.28) ** 2));
          sombra.addColorStop(o, `rgb(0 0 0 / ${escuro})`);
          reflexo.addColorStop(o, `rgb(255 255 255 / ${brilho})`);
          temSombra ||= escuro > 0.004;
          temReflexo ||= brilho > 0.004;
        }
        if (temSombra) {
          contorno();
          ctx!.fillStyle = sombra;
          ctx!.fill();
        }
        if (temReflexo) {
          contorno();
          ctx!.fillStyle = reflexo;
          ctx!.fill();
        }
      }

      caixa!.dataset.coberta = "";
      const m = motor;
      if (m.alvo !== null && Math.abs(m.p - m.alvo) < 0.0005) {
        m.p = m.alvo;
        aoFim.current(m.alvo);
        return;
      }
      quadro = requestAnimationFrame(desenha);
    }

    function comeca() {
      if (!vivo) return;
      mede();
      desenha(performance.now());
    }

    // Pinta já no layout, sempre: o primeiro quadro sai antes do navegador mostrar o DOM novo, e
    // o livro nunca fica um instante com a vista nova antes da folha (era o "pisca"). Página que
    // ainda não chegou sai como papel e entra assim que decodificar.
    comeca();
    for (const f of [baixoEsq, baixoDir, frente, verso]) {
      if (f?.tipo !== "pagina" || pronta(f)) continue;
      decodifica(imagem(f.src)).then(() => {
        faces = null;
      });
    }

    return () => {
      vivo = false;
      cancelAnimationFrame(quadro);
      delete caixa.dataset.coberta;
    };
    // A folha é montada de novo (key) a cada virada: faces e motor não mudam durante ela.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const t = tela.current;
    return () => {
      if (t) t.width = 0; // solta a memória do canvas
    };
  }, []);

  return (
    <canvas
      ref={tela}
      aria-hidden="true"
      className="degustacao-folha"
      data-dir={dir === 1 ? "avanca" : "volta"}
    />
  );
}

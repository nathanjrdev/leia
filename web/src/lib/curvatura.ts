/**
 * Geometria da folha que vira (Degustação). A folha, de largura `L`, fica presa na lombada e sai
 * dela num ângulo `beta` (0 = deitada à direita, π = deitada à esquerda); ao longo dela o ângulo
 * muda por igual até a ponta (`beta + gama`): é um arco, como papel puxado pela borda. A ponta vai
 * na frente de quem vira: indo para a esquerda, a borda sobe antes da lombada; voltando, o
 * contrário. Vista de cima, com perspectiva aplicada por quem desenha (`z` = altura).
 *
 * `p` vai de 0 (deitada à direita) a 1 (deitada à esquerda). Puro e sem DOM: testável.
 */

export type Ponto = {
  /** Posição vista de cima, a partir da lombada (negativa = sobre a página da esquerda). */
  x: number;
  /** Altura sobre o livro (0 = deitada). */
  z: number;
  /** Inclinação da folha naquele ponto, de 0 (deitada de frente) a π (deitada de costas). */
  angulo: number;
};

export type Curva = { beta: number; gama: number; largura: number };

/** 1 = a folha vai para a esquerda (avança), -1 = volta para a direita. */
export type Sentido = 1 | -1;

const ATRASO = 1.6;

/** Ângulo na lombada e quanto a folha curva até a ponta, para o progresso `p`. */
export function curva(p: number, largura: number, sentido: Sentido = 1): Curva {
  const t = Math.min(1, Math.max(0, p));
  const atras = Math.PI * Math.pow(t, ATRASO); // o lado que vai atrás
  const frente = Math.PI * (1 - Math.pow(1 - t, ATRASO)); // o lado que puxa
  // Avançando, a ponta puxa (frente) e a lombada vai atrás; voltando, ao contrário.
  const beta = sentido === 1 ? atras : frente;
  const ponta = sentido === 1 ? frente : atras;
  return { beta, gama: ponta - beta, largura };
}

/** Onde fica, no espaço, o ponto a `s` da lombada ao longo da folha. */
export function projeta(s: number, { beta, gama, largura }: Curva): Ponto {
  if (Math.abs(gama) < 1e-6) {
    return { x: s * Math.cos(beta), z: s * Math.sin(beta), angulo: beta };
  }
  const r = largura / gama;
  const angulo = beta + s / r;
  return {
    x: r * (Math.sin(angulo) - Math.sin(beta)),
    z: r * (Math.cos(beta) - Math.cos(angulo)),
    angulo,
  };
}

/** Posição da borda (vista de cima, sem perspectiva) para o progresso `p`. */
export function borda(p: number, largura: number, sentido: Sentido = 1): number {
  return projeta(largura, curva(p, largura, sentido)).x;
}

/**
 * O progresso em que a borda fica sob o dedo (`x` a partir da lombada). A borda só anda para um
 * lado com `p`, então basta uma busca binária.
 */
export function progressoDaBorda(x: number, largura: number, sentido: Sentido = 1): number {
  if (x >= largura) return 0;
  if (x <= -largura) return 1;
  let lo = 0;
  let hi = 1;
  for (let i = 0; i < 30; i++) {
    const meio = (lo + hi) / 2;
    if (borda(meio, largura, sentido) > x) lo = meio;
    else hi = meio;
  }
  return (lo + hi) / 2;
}

/** Curva de tempo da virada automática (ease-in-out, próxima de `--ease-in-out`). */
export function suaviza(t: number): number {
  const x = Math.min(1, Math.max(0, t));
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

/** Depois de soltar o dedo: sai com a velocidade da mão e assenta (ease-out). */
export function assenta(t: number): number {
  const x = Math.min(1, Math.max(0, t));
  return 1 - Math.pow(1 - x, 3);
}

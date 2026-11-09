/** Cliente da API do Léia. Tudo passa por `/api` (rewrite do Next), então o cookie de sessão
 * `leia_sessao` (HttpOnly) é de mesma origem e o JavaScript nunca o enxerga. */

export class ErroApi extends Error {
  readonly status: number;
  readonly codigo: string;

  constructor(status: number, codigo: string, mensagem: string) {
    super(mensagem);
    this.name = "ErroApi";
    this.status = status;
    this.codigo = codigo;
  }
}

const BASE = "/api";

type Opcoes = { metodo?: "GET" | "POST"; corpo?: unknown; sinal?: AbortSignal };

async function erroDe(resp: Response): Promise<ErroApi> {
  try {
    const j = (await resp.json()) as { erro?: string; mensagem?: string };
    if (typeof j?.erro === "string") {
      return new ErroApi(resp.status, j.erro, j.mensagem ?? "");
    }
  } catch {
    // corpo que não é JSON: cai no genérico
  }
  if (resp.status === 422) {
    return new ErroApi(422, "dados_invalidos", "Confira os dados informados e tente de novo.");
  }
  return new ErroApi(resp.status, "erro_servidor", "");
}

async function pedir(caminho: string, o: Opcoes, aceita?: string): Promise<Response> {
  const headers: Record<string, string> = {};
  if (o.corpo !== undefined) headers["Content-Type"] = "application/json";
  if (aceita) headers.Accept = aceita;
  let resp: Response;
  try {
    resp = await fetch(`${BASE}${caminho}`, {
      method: o.metodo ?? "GET",
      credentials: "same-origin",
      headers,
      body: o.corpo === undefined ? undefined : JSON.stringify(o.corpo),
      signal: o.sinal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ErroApi(0, "sem_conexao", "Não consegui falar com o servidor.");
  }
  if (!resp.ok) throw await erroDe(resp);
  return resp;
}

export async function api<T = unknown>(caminho: string, o: Opcoes = {}): Promise<T> {
  const resp = await pedir(caminho, o);
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

/** Texto para o leitor. Nunca expõe detalhe técnico. */
export function mensagemDoErro(e: unknown): string {
  if (e instanceof ErroApi) {
    if (e.status === 401) return "Sua sessão acabou. Entre de novo para continuar.";
    if (e.status === 0) return "Sem conexão com o servidor. Verifique a internet e tente de novo.";
    if (e.message) return e.message;
    if (e.status === 429) return "Muitas tentativas seguidas. Aguarde um instante.";
  }
  return "Algo deu errado. Tente de novo em instantes.";
}

export type EventoSSE = { evento: string; dados: unknown };

export async function* lerSSE(resp: Response): AsyncGenerator<EventoSSE> {
  if (!resp.body) return;
  const leitor = resp.body.pipeThrough(new TextDecoderStream()).getReader();
  let resto = "";
  try {
    for (;;) {
      const { value, done } = await leitor.read();
      if (done) break;
      resto += value;
      let corte: number;
      while ((corte = resto.indexOf("\n\n")) >= 0) {
        const bloco = resto.slice(0, corte);
        resto = resto.slice(corte + 2);
        const e = analisar(bloco);
        if (e) yield e;
      }
    }
    const final = analisar(resto);
    if (final) yield final;
  } finally {
    leitor.releaseLock();
  }
}

function analisar(bloco: string): EventoSSE | null {
  let evento = "message";
  const dados: string[] = [];
  for (const linha of bloco.split("\n")) {
    if (linha.startsWith("event:")) evento = linha.slice(6).trim();
    else if (linha.startsWith("data:")) dados.push(linha.slice(5).trim());
  }
  if (!dados.length) return null;
  try {
    return { evento, dados: JSON.parse(dados.join("\n")) };
  } catch {
    return null;
  }
}

/** POST que responde em SSE: chama `aoEvento` para cada evento, na ordem. */
export async function postarSSE(
  caminho: string,
  corpo: unknown,
  aoEvento: (e: EventoSSE) => void,
  sinal?: AbortSignal,
): Promise<void> {
  const resp = await pedir(caminho, { metodo: "POST", corpo, sinal }, "text/event-stream");
  for await (const e of lerSSE(resp)) aoEvento(e);
}

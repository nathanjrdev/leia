import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ErroApi, lerSSE, mensagemDoErro, postarSSE } from "@/lib/api";

function resposta(corpo: unknown, status = 200) {
  return new Response(corpo === null ? null : JSON.stringify(corpo), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function fluxo(pedacos: string[], status = 200) {
  const enc = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(c) {
        pedacos.forEach((p) => c.enqueue(enc.encode(p)));
        c.close();
      },
    }),
    { status, headers: { "content-type": "text/event-stream" } },
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("api", () => {
  it("chama /api, com cookie e devolve o JSON", async () => {
    const f = vi.fn().mockResolvedValue(resposta({ nome: "Ana" }));
    vi.stubGlobal("fetch", f);
    await expect(api("/auth/eu")).resolves.toEqual({ nome: "Ana" });
    expect(f).toHaveBeenCalledWith(
      "/api/auth/eu",
      expect.objectContaining({ credentials: "same-origin", method: "GET" }),
    );
  });

  it("envia o corpo como JSON no POST", async () => {
    const f = vi.fn().mockResolvedValue(resposta({ ok: 1 }));
    vi.stubGlobal("fetch", f);
    await api("/auth/login", { metodo: "POST", corpo: { email: "a@b.c" } });
    const init = f.mock.calls[0][1];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ email: "a@b.c" }));
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("204 devolve undefined", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(api("/auth/logout", { metodo: "POST" })).resolves.toBeUndefined();
  });

  it("erro do contrato vira ErroApi com código e mensagem", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(resposta({ erro: "muitas_tentativas", mensagem: "Calma." }, 429)),
    );
    const e = await api("/auth/login", { metodo: "POST", corpo: {} }).catch((x) => x);
    expect(e).toBeInstanceOf(ErroApi);
    expect(e).toMatchObject({ status: 429, codigo: "muitas_tentativas", message: "Calma." });
  });

  it("422 do FastAPI (sem contrato) vira erro genérico de dados inválidos", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(resposta({ detail: [] }, 422)));
    const e = await api("/auth/cadastro", { metodo: "POST", corpo: {} }).catch((x) => x);
    expect(e).toMatchObject({ status: 422, codigo: "dados_invalidos" });
  });

  it("falha de rede vira ErroApi sem_conexao", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fail")));
    const e = await api("/livros").catch((x) => x);
    expect(e).toMatchObject({ status: 0, codigo: "sem_conexao" });
  });
});

describe("mensagemDoErro", () => {
  it("usa a mensagem do servidor quando existe", () => {
    expect(mensagemDoErro(new ErroApi(409, "email_em_uso", "E-mail já cadastrado."))).toBe(
      "E-mail já cadastrado.",
    );
  });
  it("trata 401 como sessão expirada", () => {
    expect(mensagemDoErro(new ErroApi(401, "nao_autenticado", ""))).toMatch(/entre/i);
  });
  it("erro desconhecido vira texto genérico", () => {
    expect(mensagemDoErro(new Error("x"))).toMatch(/algo deu errado/i);
  });
});

describe("lerSSE", () => {
  it("separa eventos mesmo quando o pedaço corta no meio", async () => {
    const r = fluxo([
      'event: ferramenta\ndata: {"nome":"buscar_livros"}\n\nevent: resp',
      'osta\ndata: {"texto":"Olá"}\n\n',
      'event: fim\ndata: {"erro":null}\n\n',
    ]);
    const vistos = [];
    for await (const e of lerSSE(r)) vistos.push(e);
    expect(vistos).toEqual([
      { evento: "ferramenta", dados: { nome: "buscar_livros" } },
      { evento: "resposta", dados: { texto: "Olá" } },
      { evento: "fim", dados: { erro: null } },
    ]);
  });

  it("entende acentos partidos entre pedaços", async () => {
    const bytes = new TextEncoder().encode('event: resposta\ndata: {"texto":"é"}\n\n');
    const meio = bytes.indexOf(0xc3) + 1;
    const r = new Response(
      new ReadableStream({
        start(c) {
          c.enqueue(bytes.slice(0, meio));
          c.enqueue(bytes.slice(meio));
          c.close();
        },
      }),
    );
    const vistos = [];
    for await (const e of lerSSE(r)) vistos.push(e);
    expect(vistos[0].dados).toEqual({ texto: "é" });
  });
});

describe("postarSSE", () => {
  it("entrega cada evento ao callback", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(fluxo(['event: fim\ndata: {"erro":null}\n\n'])),
    );
    const recebidos: string[] = [];
    await postarSSE("/conversas/1/mensagens", { texto: "oi" }, (e) => recebidos.push(e.evento));
    expect(recebidos).toEqual(["fim"]);
  });

  it("status de erro antes do fluxo vira ErroApi", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(resposta({ erro: "limite_diario", mensagem: "Volte amanhã." }, 429)),
    );
    const e = await postarSSE("/conversas/1/mensagens", { texto: "oi" }, () => {}).catch(
      (x) => x,
    );
    expect(e).toMatchObject({ status: 429, codigo: "limite_diario" });
  });
});

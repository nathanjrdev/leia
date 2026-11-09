import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ErroApi } from "@/lib/api";
import type { EventoSSE } from "@/lib/api";
import { Conversa } from "@/components/Conversa";

let conta: { nome: string; email: string } | null = { nome: "Ana", email: "ana@leia.example" };
let carregando = false;
vi.mock("@/components/SessaoProvider", () => ({
  useSessao: () => ({ conta, carregando, definirConta: vi.fn(), sair: vi.fn() }),
}));

const apiMock = vi.fn();
const postarMock = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  api: (...a: unknown[]) => apiMock(...a),
  postarSSE: (...a: unknown[]) => postarMock(...a),
}));

function turno(eventos: EventoSSE[]) {
  postarMock.mockImplementationOnce(
    async (_c: string, _b: unknown, aoEvento: (e: EventoSSE) => void) => {
      eventos.forEach(aoEvento);
    },
  );
}

beforeEach(() => {
  conta = { nome: "Ana", email: "ana@leia.example" };
  carregando = false;
  sessionStorage.clear();
  apiMock.mockReset();
  postarMock.mockReset();
  apiMock.mockImplementation((caminho: string, o?: { metodo?: string }) => {
    if (caminho === "/conversas" && o?.metodo === "POST") return Promise.resolve({ id: 7 });
    if (caminho === "/conversas/7/mensagens") return Promise.resolve([]);
    return Promise.reject(new Error("inesperado " + caminho));
  });
});

async function enviar(texto: string) {
  const u = userEvent.setup();
  await u.type(await screen.findByLabelText("Mensagem para a Léia"), texto);
  await u.click(screen.getByRole("button", { name: "Enviar" }));
  return u;
}

describe("Conversa", () => {
  it("sem sessão, convida a entrar e não cria conversa", () => {
    conta = null;
    render(<Conversa />);
    expect(screen.getByRole("link", { name: "Entrar" })).toHaveAttribute("href", "/entrar");
    expect(apiMock).not.toHaveBeenCalled();
  });

  it("cria a conversa, envia a mensagem e mostra a resposta em pedaços", async () => {
    turno([
      { evento: "ferramenta", dados: { nome: "buscar_livros" } },
      { evento: "resposta", dados: { texto: "Achei " } },
      { evento: "resposta", dados: { texto: "três livros." } },
      { evento: "fim", dados: { erro: null } },
    ]);
    render(<Conversa />);
    await enviar("um romance sobre memória");
    expect(await screen.findByText("Achei três livros.")).toBeInTheDocument();
    expect(screen.getByText("um romance sobre memória")).toBeInTheDocument();
    expect(postarMock).toHaveBeenCalledWith(
      "/conversas/7/mensagens",
      { texto: "um romance sobre memória" },
      expect.any(Function),
      expect.anything(),
    );
  });

  it("mostra o que a Léia está fazendo enquanto consulta uma ferramenta", async () => {
    let liberar: () => void = () => {};
    postarMock.mockImplementationOnce(
      (_c: string, _b: unknown, aoEvento: (e: EventoSSE) => void) =>
        new Promise<void>((r) => {
          aoEvento({ evento: "ferramenta", dados: { nome: "buscar_livros" } });
          liberar = r;
        }),
    );
    render(<Conversa />);
    await enviar("poesia");
    expect(await screen.findByText(/Buscando no acervo/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enviar" })).toBeDisabled();
    liberar();
    await waitFor(() => expect(screen.getByRole("button", { name: "Enviar" })).toBeEnabled());
  });

  it("mostra o cartão do livro citado e Locar passa por confirmação antes de chamar a API", async () => {
    turno([
      { evento: "resposta", dados: { texto: "Achei “Dom Casmurro”." } },
      {
        evento: "livros",
        dados: {
          livros: [
            {
              id: 5,
              titulo: "Dom Casmurro",
              autores: ["Machado de Assis"],
              capa_url: "https://covers.example/dc.jpg",
              livres: 2,
            },
          ],
        },
      },
      { evento: "fim", dados: { erro: null } },
    ]);
    render(<Conversa />);
    const u = await enviar("um clássico");
    const cartao = await screen.findByRole("group", { name: "Livro: Dom Casmurro" });
    expect(within(cartao).getByRole("link", { name: "Dom Casmurro" })).toHaveAttribute(
      "href",
      "/livro/5",
    );
    expect(within(cartao).getByText("Machado de Assis")).toBeInTheDocument();
    expect(within(cartao).getByText("2 exemplares livres")).toBeInTheDocument();

    apiMock.mockImplementation((caminho: string) =>
      caminho === "/livros/5/locar"
        ? Promise.resolve({ prevista_em: "2026-12-01T12:00:00Z" })
        : Promise.reject(new Error("inesperado " + caminho)),
    );
    await u.click(within(cartao).getByRole("button", { name: "Locar" }));
    expect(apiMock).not.toHaveBeenCalledWith("/livros/5/locar", expect.anything());
    await u.click(within(cartao).getByRole("button", { name: "Confirmar locação" }));
    expect(apiMock).toHaveBeenCalledWith("/livros/5/locar", {
      metodo: "POST",
      corpo: { confirmo: true },
    });
    expect(await within(cartao).findByRole("status")).toHaveTextContent("Locação feita");
    expect(within(cartao).queryByRole("button", { name: "Locar" })).not.toBeInTheDocument();
  });

  it("livro sem exemplar livre oferece Reservar, não Locar", async () => {
    turno([
      { evento: "resposta", dados: { texto: "“Sagarana” está emprestado." } },
      {
        evento: "livros",
        dados: {
          livros: [{ id: 9, titulo: "Sagarana", autores: ["Guimarães Rosa"], capa_url: null, livres: 0 }],
        },
      },
      { evento: "fim", dados: { erro: null } },
    ]);
    render(<Conversa />);
    await enviar("sagarana");
    const cartao = await screen.findByRole("group", { name: "Livro: Sagarana" });
    expect(within(cartao).getByText("Sem exemplar livre agora")).toBeInTheDocument();
    expect(within(cartao).getByRole("button", { name: "Reservar" })).toBeInTheDocument();
    expect(within(cartao).queryByRole("button", { name: "Locar" })).not.toBeInTheDocument();
  });

  it("uma nova mensagem não apaga os cartões já mostrados", async () => {
    turno([
      { evento: "resposta", dados: { texto: "Achei “A”." } },
      {
        evento: "livros",
        dados: { livros: [{ id: 1, titulo: "A", autores: [], capa_url: null, livres: 1 }] },
      },
      { evento: "fim", dados: { erro: null } },
    ]);
    render(<Conversa />);
    const u = await enviar("algo");
    await screen.findByRole("group", { name: "Livro: A" });
    turno([
      { evento: "resposta", dados: { texto: "Ok." } },
      { evento: "fim", dados: { erro: null } },
    ]);
    await u.type(screen.getByLabelText("Mensagem para a Léia"), "obrigado");
    await u.click(screen.getByRole("button", { name: "Enviar" }));
    await screen.findByText("Ok.");
    expect(screen.getByRole("group", { name: "Livro: A" })).toBeInTheDocument();
  });

  it("proposta: mostra o resumo e Confirmar envia a decisão ao endpoint do clique", async () => {
    turno([
      { evento: "resposta", dados: { texto: "Preparei a locação." } },
      {
        evento: "propostas",
        dados: { propostas: [{ confirmacao_id: "abc", resumo: "Locar “Ou isto ou aquilo”" }] },
      },
      { evento: "fim", dados: { erro: null } },
    ]);
    render(<Conversa />);
    const u = await enviar("quero locar");
    expect(await screen.findByText("Locar “Ou isto ou aquilo”")).toBeInTheDocument();

    turno([
      { evento: "acao", dados: { decisao: "confirmar", ok: true, erro: null } },
      { evento: "resposta", dados: { texto: "Locação concluída." } },
      { evento: "fim", dados: { erro: null } },
    ]);
    await u.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(await screen.findByText("Locação concluída.")).toBeInTheDocument();
    expect(postarMock).toHaveBeenLastCalledWith(
      "/conversas/7/confirmacoes/abc",
      { decisao: "confirmar" },
      expect.any(Function),
      expect.anything(),
    );
    expect(screen.queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
  });

  it("proposta: Cancelar envia decisao cancelar", async () => {
    turno([
      {
        evento: "propostas",
        dados: { propostas: [{ confirmacao_id: "xyz", resumo: "Locar “Dom Casmurro”" }] },
      },
      { evento: "fim", dados: { erro: null } },
    ]);
    render(<Conversa />);
    const u = await enviar("quero locar");
    turno([{ evento: "fim", dados: { erro: null } }]);
    await u.click(await screen.findByRole("button", { name: "Cancelar" }));
    await waitFor(() =>
      expect(postarMock).toHaveBeenLastCalledWith(
        "/conversas/7/confirmacoes/xyz",
        { decisao: "cancelar" },
        expect.any(Function),
        expect.anything(),
      ),
    );
  });

  it("uma nova mensagem tira os botões da proposta anterior (ela expira no servidor)", async () => {
    turno([
      {
        evento: "propostas",
        dados: { propostas: [{ confirmacao_id: "p1", resumo: "Locar “A”" }] },
      },
      { evento: "fim", dados: { erro: null } },
    ]);
    render(<Conversa />);
    const u = await enviar("quero locar");
    await screen.findByRole("button", { name: "Confirmar" });
    turno([
      { evento: "resposta", dados: { texto: "Tudo bem." } },
      { evento: "fim", dados: { erro: null } },
    ]);
    await u.type(screen.getByLabelText("Mensagem para a Léia"), "esquece");
    await u.click(screen.getByRole("button", { name: "Enviar" }));
    await screen.findByText("Tudo bem.");
    expect(screen.queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
  });

  it("limite diário (429) aparece como alerta com a mensagem do servidor", async () => {
    postarMock.mockRejectedValueOnce(
      new ErroApi(429, "limite_diario", "Você atingiu o limite de mensagens de hoje."),
    );
    render(<Conversa />);
    await enviar("oi");
    expect(await screen.findByRole("alert")).toHaveTextContent("limite de mensagens de hoje");
    expect(screen.getByRole("button", { name: "Enviar" })).toBeEnabled();
  });

  it("carrega o histórico da conversa guardada na aba", async () => {
    sessionStorage.setItem("leia:conversa", "7");
    apiMock.mockImplementation((caminho: string) =>
      caminho === "/conversas/7/mensagens"
        ? Promise.resolve([
            { papel: "usuario", conteudo: "Olá" },
            { papel: "assistente", conteudo: "Oi! Como posso ajudar?" },
          ])
        : Promise.reject(new Error("inesperado " + caminho)),
    );
    render(<Conversa />);
    expect(await screen.findByText("Oi! Como posso ajudar?")).toBeInTheDocument();
    expect(apiMock).not.toHaveBeenCalledWith("/conversas", expect.anything());
  });

  it("Nova conversa começa uma conversa vazia", async () => {
    sessionStorage.setItem("leia:conversa", "7");
    apiMock.mockImplementation((caminho: string, o?: { metodo?: string }) => {
      if (caminho === "/conversas" && o?.metodo === "POST") return Promise.resolve({ id: 8 });
      if (caminho === "/conversas/7/mensagens")
        return Promise.resolve([{ papel: "usuario", conteudo: "Olá antigo" }]);
      return Promise.resolve([]);
    });
    render(<Conversa />);
    const u = userEvent.setup();
    await screen.findByText("Olá antigo");
    await u.click(screen.getByRole("button", { name: "Nova conversa" }));
    await waitFor(() => expect(screen.queryByText("Olá antigo")).not.toBeInTheDocument());
    expect(sessionStorage.getItem("leia:conversa")).toBe("8");
  });
});

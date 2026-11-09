import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ErroApi } from "@/lib/api";
import type { Estante as TEstante } from "@/lib/tipos";
import { Estante } from "@/components/Estante";

let conta: { nome: string; email: string } | null = { nome: "Ana", email: "a@leia.example" };
vi.mock("@/components/SessaoProvider", () => ({
  useSessao: () => ({ conta, carregando: false, definirConta: vi.fn(), sair: vi.fn() }),
}));

const apiMock = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  api: (...a: unknown[]) => apiMock(...a),
}));

const dados: TEstante = {
  ativas: [
    {
      locacao_id: 11,
      livro_id: 3,
      titulo: "Dom Casmurro",
      retirada_em: "2026-11-01T12:00:00Z",
      prevista_em: "2026-11-15T12:00:00Z",
      devolvida_em: null,
      renovacoes: 0,
      atrasada: false,
    },
    {
      locacao_id: 12,
      livro_id: 4,
      titulo: "Vidas Secas",
      retirada_em: "2026-10-01T12:00:00Z",
      prevista_em: "2026-10-15T12:00:00Z",
      devolvida_em: null,
      renovacoes: 1,
      atrasada: true,
    },
  ],
  reservas: [
    { reserva_id: 21, livro_id: 5, titulo: "Quincas Borba", posicao: 2, pronta: false, retirar_ate: null },
    {
      reserva_id: 22,
      livro_id: 6,
      titulo: "O Cortiço",
      posicao: 1,
      pronta: true,
      retirar_ate: "2026-11-12T12:00:00Z",
    },
  ],
  historico: [
    {
      locacao_id: 9,
      livro_id: 7,
      titulo: "Memórias Póstumas",
      retirada_em: "2026-09-01T12:00:00Z",
      prevista_em: "2026-09-15T12:00:00Z",
      devolvida_em: "2026-09-10T12:00:00Z",
      renovacoes: 0,
      atrasada: false,
    },
  ],
};

beforeEach(() => {
  conta = { nome: "Ana", email: "a@leia.example" };
  apiMock.mockReset();
  apiMock.mockImplementation((caminho: string) =>
    caminho === "/estante" ? Promise.resolve(dados) : Promise.resolve({}),
  );
});

describe("Estante", () => {
  it("sem sessão, convida a entrar", () => {
    conta = null;
    render(<Estante />);
    expect(screen.getByRole("link", { name: "Entrar" })).toHaveAttribute("href", "/entrar");
  });

  it("lista locações ativas com a data de devolução e marca o atraso", async () => {
    render(<Estante />);
    const secao = await screen.findByRole("region", { name: "Locações ativas" });
    expect(within(secao).getByText("Dom Casmurro")).toBeInTheDocument();
    expect(within(secao).getByText(/Devolver até 15\/11\/2026/)).toBeInTheDocument();
    expect(within(secao).getByText(/Atrasada/)).toBeInTheDocument();
  });

  it("reserva pronta mostra até quando retirar; na fila mostra a posição", async () => {
    render(<Estante />);
    const secao = await screen.findByRole("region", { name: "Reservas" });
    expect(within(secao).getByText(/Pronto para retirar até 12\/11\/2026/)).toBeInTheDocument();
    expect(within(secao).getByText(/Posição 2 na fila/)).toBeInTheDocument();
  });

  it("mostra o histórico", async () => {
    render(<Estante />);
    const secao = await screen.findByRole("region", { name: "Histórico" });
    expect(within(secao).getByText("Memórias Póstumas")).toBeInTheDocument();
  });

  it("devolver pede confirmação e então chama a API com confirmo: true", async () => {
    const u = userEvent.setup();
    render(<Estante />);
    const secao = await screen.findByRole("region", { name: "Locações ativas" });
    const cartao = within(secao).getByText("Dom Casmurro").closest("li") as HTMLElement;
    await u.click(within(cartao).getByRole("button", { name: "Devolver" }));
    expect(apiMock).not.toHaveBeenCalledWith("/locacoes/11/devolver", expect.anything());
    await u.click(within(cartao).getByRole("button", { name: "Confirmar devolução" }));
    await waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith("/locacoes/11/devolver", {
        metodo: "POST",
        corpo: { confirmo: true },
      }),
    );
    // recarrega a estante depois da ação
    await waitFor(() => expect(apiMock.mock.calls.filter((c) => c[0] === "/estante")).toHaveLength(2));
  });

  it("renovar e cancelar reserva usam os endpoints certos", async () => {
    const u = userEvent.setup();
    render(<Estante />);
    const ativas = await screen.findByRole("region", { name: "Locações ativas" });
    const cartao = within(ativas).getByText("Dom Casmurro").closest("li") as HTMLElement;
    await u.click(within(cartao).getByRole("button", { name: "Renovar" }));
    await u.click(within(cartao).getByRole("button", { name: "Confirmar renovação" }));
    await waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith("/locacoes/11/renovar", {
        metodo: "POST",
        corpo: { confirmo: true },
      }),
    );
    const reservas = screen.getByRole("region", { name: "Reservas" });
    const res = within(reservas).getByText("Quincas Borba").closest("li") as HTMLElement;
    await u.click(within(res).getByRole("button", { name: "Cancelar reserva" }));
    await u.click(within(res).getByRole("button", { name: "Confirmar cancelamento" }));
    await waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith("/reservas/21/cancelar", {
        metodo: "POST",
        corpo: { confirmo: true },
      }),
    );
  });

  it("estante vazia mostra um convite", async () => {
    apiMock.mockImplementation(() => Promise.resolve({ ativas: [], reservas: [], historico: [] }));
    render(<Estante />);
    expect(await screen.findByText(/Você não tem livros locados/)).toBeInTheDocument();
  });

  it("erro ao carregar mostra alerta e botão para tentar de novo", async () => {
    const u = userEvent.setup();
    apiMock.mockRejectedValueOnce(new ErroApi(0, "sem_conexao", "Não consegui falar com o servidor."));
    render(<Estante />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByRole("region", { name: "Locações ativas" })).toBeInTheDocument();
  });
});

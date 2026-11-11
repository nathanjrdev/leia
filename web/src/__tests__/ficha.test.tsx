import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ErroApi } from "@/lib/api";
import type { Ficha } from "@/lib/tipos";
import { FichaLivro } from "@/components/FichaLivro";

let conta: { nome: string; email: string } | null = { nome: "Ana", email: "a@leia.example" };
vi.mock("@/components/SessaoProvider", () => ({
  useSessao: () => ({ conta, carregando: false, definirConta: vi.fn(), sair: vi.fn() }),
}));

const apiMock = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  api: (...a: unknown[]) => apiMock(...a),
}));

const ficha = (extra: Partial<Ficha> = {}): Ficha => ({
  id: 3,
  titulo: "Dom Casmurro",
  autores: ["Machado de Assis"],
  categorias: ["Romance"],
  sinopse: "Bentinho conta a sua vida e a dúvida sobre Capitu.",
  ano: 1899,
  editora: "Garnier",
  paginas: 256,
  capa_url: null,
  exemplares: 3,
  livres: 2,
  fila: 0,
  ...extra,
});

function responder(f: Ficha, escrita?: unknown) {
  apiMock.mockImplementation((caminho: string, o?: { metodo?: string }) => {
    if (o?.metodo === "POST") return escrita instanceof Error ? Promise.reject(escrita) : Promise.resolve(escrita);
    return caminho === "/livros/3" ? Promise.resolve(f) : Promise.reject(new Error(caminho));
  });
}

beforeEach(() => {
  conta = { nome: "Ana", email: "a@leia.example" };
  apiMock.mockReset();
});

describe("FichaLivro", () => {
  it("mostra título, autor, sinopse, dados e disponibilidade", async () => {
    responder(ficha());
    render(<FichaLivro id={3} />);
    expect(await screen.findByRole("heading", { name: "Dom Casmurro" })).toBeInTheDocument();
    // A capa gerada repete o autor, mas é decorativa (aria-hidden): vale o texto da ficha.
    expect(
      screen.getByText("Machado de Assis", { ignore: "[aria-hidden='true'] *" }),
    ).toBeInTheDocument();
    expect(document.querySelector("[data-capa='gerada']")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText(/dúvida sobre Capitu/)).toBeInTheDocument();
    expect(screen.getByText(/Garnier/)).toBeInTheDocument();
    expect(screen.getByText("2 de 3 exemplares disponíveis")).toBeInTheDocument();
  });

  it("locar pede confirmação e depois chama a API com confirmo: true", async () => {
    const u = userEvent.setup();
    responder(ficha(), {
      locacao_id: 1,
      livro_id: 3,
      titulo: "Dom Casmurro",
      exemplar_codigo: "L3-1",
      retirada_em: "2026-11-09T12:00:00Z",
      prevista_em: "2026-11-23T12:00:00Z",
      renovacoes: 0,
    });
    render(<FichaLivro id={3} />);
    await u.click(await screen.findByRole("button", { name: "Locar" }));
    expect(apiMock).not.toHaveBeenCalledWith("/livros/3/locar", expect.anything());
    await u.click(screen.getByRole("button", { name: "Confirmar locação" }));
    await waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith("/livros/3/locar", {
        metodo: "POST",
        corpo: { confirmo: true },
      }),
    );
    const aviso = await screen.findByRole("status");
    expect(aviso).toHaveTextContent("Devolver até 23/11/2026");
    expect(aviso).toHaveTextContent("Boa leitura");
  });

  it("sem exemplar livre oferece reservar e mostra a posição", async () => {
    const u = userEvent.setup();
    responder(ficha({ livres: 0, fila: 1 }), {
      reserva_id: 5,
      livro_id: 3,
      titulo: "Dom Casmurro",
      posicao: 2,
    });
    render(<FichaLivro id={3} />);
    expect(await screen.findByText("Indisponível, fila de 1")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Reservar" }));
    await u.click(screen.getByRole("button", { name: "Confirmar reserva" }));
    await waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith("/livros/3/reservar", {
        metodo: "POST",
        corpo: { confirmo: true },
      }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("posição 2 na fila");
  });

  it("regra negada (limite de locações) aparece como alerta", async () => {
    const u = userEvent.setup();
    responder(
      ficha(),
      new ErroApi(409, "limite_locacoes", "Você já tem 3 livros locados."),
    );
    render(<FichaLivro id={3} />);
    await u.click(await screen.findByRole("button", { name: "Locar" }));
    await u.click(screen.getByRole("button", { name: "Confirmar locação" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Você já tem 3 livros locados.");
  });

  it("sem sessão, em vez de locar pede para entrar", async () => {
    conta = null;
    responder(ficha());
    render(<FichaLivro id={3} />);
    expect(await screen.findByRole("link", { name: "Entre para locar" })).toHaveAttribute(
      "href",
      "/entrar",
    );
    expect(screen.queryByRole("button", { name: "Locar" })).not.toBeInTheDocument();
  });

  it("livro inexistente (404) mostra mensagem", async () => {
    apiMock.mockRejectedValue(new ErroApi(404, "livro_inexistente", "Livro não encontrado."));
    render(<FichaLivro id={999} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Livro não encontrado.");
  });
});

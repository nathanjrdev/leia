import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ErroApi } from "@/lib/api";
import { EstanteDaHome } from "@/components/EstanteDaHome";

const apiMock = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  api: (...a: unknown[]) => apiMock(...a),
}));

const livro = (id: number, titulo: string) => ({
  id,
  titulo,
  autores: ["Autoria"],
  ano: 1900,
  capa_url: null,
  livres: 1,
  fila: 0,
});

beforeEach(() => {
  apiMock.mockReset();
});

describe("EstanteDaHome", () => {
  it("põe capas reais do acervo na prateleira, cada uma com link nomeado para a ficha", async () => {
    apiMock.mockResolvedValue({ itens: [livro(1, "Dom Casmurro"), livro(2, "Iracema")], total: 2, pagina: 1 });
    render(<EstanteDaHome />);
    expect(await screen.findByRole("link", { name: "Dom Casmurro" })).toHaveAttribute("href", "/livro/1");
    expect(screen.getByRole("link", { name: "Iracema" })).toHaveAttribute("href", "/livro/2");
    expect(apiMock).toHaveBeenCalledWith(expect.stringMatching(/^\/livros\?.*limite=8/));
  });

  it("se a API falha, a prateleira fica só com espaços vazios: nada de erro na página inicial", async () => {
    apiMock.mockImplementation(() =>
      Promise.reject(new ErroApi(0, "sem_conexao", "Não consegui falar com o servidor.")),
    );
    render(<EstanteDaHome />);
    await waitFor(() => expect(apiMock).toHaveBeenCalled());
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

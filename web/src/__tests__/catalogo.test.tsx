import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ErroApi } from "@/lib/api";
import type { ItemLivro } from "@/lib/tipos";
import { Catalogo } from "@/components/Catalogo";

const apiMock = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  api: (...a: unknown[]) => apiMock(...a),
}));

const livro = (id: number, extra: Partial<ItemLivro> = {}): ItemLivro => ({
  id,
  titulo: `Livro ${id}`,
  autores: ["Machado de Assis"],
  ano: 1899,
  capa_url: null,
  livres: 2,
  fila: 0,
  ...extra,
});

function listagem(itens: ItemLivro[], total = itens.length, pagina = 1) {
  return { itens, total, pagina };
}

beforeEach(() => {
  apiMock.mockReset();
  apiMock.mockImplementation((caminho: string) => {
    if (caminho === "/categorias")
      return Promise.resolve([
        { slug: "poesia", nome: "Poesia" },
        { slug: "romance", nome: "Romance" },
      ]);
    return Promise.resolve(listagem([livro(1), livro(2, { livres: 0, fila: 3 })]));
  });
});

const ultimaListagem = () =>
  String(apiMock.mock.calls.filter((c) => String(c[0]).startsWith("/livros")).at(-1)?.[0]);

describe("Catalogo", () => {
  it("lista os livros com link para a ficha e a disponibilidade", async () => {
    render(<Catalogo />);
    expect(await screen.findByRole("link", { name: "Livro 1" })).toHaveAttribute("href", "/livro/1");
    expect(screen.getByText("2 disponíveis")).toBeInTheDocument();
    expect(screen.getByText("Indisponível, fila de 3")).toBeInTheDocument();
  });

  it("filtra por categoria e por só disponíveis", async () => {
    const u = userEvent.setup();
    render(<Catalogo />);
    await screen.findByRole("link", { name: "Livro 1" });
    await u.selectOptions(screen.getByLabelText("Categoria"), "poesia");
    await waitFor(() => expect(ultimaListagem()).toContain("categoria=poesia"));
    await u.click(screen.getByLabelText("Só disponíveis"));
    await waitFor(() => expect(ultimaListagem()).toContain("apenas_disponiveis=true"));
  });

  it("busca por texto usa /livros/busca", async () => {
    const u = userEvent.setup();
    render(<Catalogo />);
    await screen.findByRole("link", { name: "Livro 1" });
    await u.type(screen.getByLabelText("Buscar no acervo"), "memória");
    await u.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() => expect(ultimaListagem()).toMatch(/^\/livros\/busca\?.*q=mem/));
  });

  it("pagina quando há mais de uma página", async () => {
    const u = userEvent.setup();
    apiMock.mockImplementation((caminho: string) =>
      caminho === "/categorias" ? Promise.resolve([]) : Promise.resolve(listagem([livro(1)], 45)),
    );
    render(<Catalogo />);
    await screen.findByText("Página 1 de 3");
    await u.click(screen.getByRole("button", { name: "Próxima" }));
    await waitFor(() => expect(ultimaListagem()).toContain("pagina=2"));
  });

  it("sem resultados mostra mensagem", async () => {
    apiMock.mockImplementation((caminho: string) =>
      caminho === "/categorias" ? Promise.resolve([]) : Promise.resolve(listagem([])),
    );
    render(<Catalogo />);
    expect(await screen.findByText("Nenhum livro encontrado.")).toBeInTheDocument();
  });

  it("limite de buscas (429) vira alerta com a mensagem do servidor", async () => {
    const u = userEvent.setup();
    render(<Catalogo />);
    await screen.findByRole("link", { name: "Livro 1" });
    apiMock.mockRejectedValueOnce(
      new ErroApi(429, "muitas_buscas", "Muitas buscas seguidas. Aguarde um instante."),
    );
    await u.type(screen.getByLabelText("Buscar no acervo"), "x");
    await u.click(screen.getByRole("button", { name: "Buscar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Aguarde um instante");
  });
});

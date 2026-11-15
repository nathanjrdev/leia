import { act, render, screen, waitFor } from "@testing-library/react";
import { useSyncExternalStore } from "react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ErroApi } from "@/lib/api";
import type { ItemLivro } from "@/lib/tipos";
import { Catalogo } from "@/components/Catalogo";

// URL falsa: push muda a query e re-renderiza quem lê useSearchParams.
const url = {
  busca: "",
  ouvintes: new Set<() => void>(),
  ir(q: string) {
    url.busca = q;
    url.ouvintes.forEach((f) => f());
  },
};
const pushMock = vi.fn((destino: string) => url.ir(destino.split("?")[1] ?? ""));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/catalogo",
  useSearchParams: () =>
    new URLSearchParams(
      useSyncExternalStore(
        (f) => (url.ouvintes.add(f), () => url.ouvintes.delete(f)),
        () => url.busca,
      ),
    ),
}));

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
  url.busca = "";
  pushMock.mockClear();
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

  it("a busca vai para a URL e limpar volta ao catálogo completo", async () => {
    const u = userEvent.setup();
    render(<Catalogo />);
    await screen.findByRole("link", { name: "Livro 1" });
    await u.type(screen.getByLabelText("Buscar no acervo"), "memória");
    await u.click(screen.getByRole("button", { name: "Buscar" }));
    expect(pushMock).toHaveBeenLastCalledWith("/catalogo?q=mem%C3%B3ria");
    await screen.findByText("Resultados para “memória”");
    await u.click(screen.getByRole("button", { name: "Limpar busca" }));
    expect(pushMock).toHaveBeenLastCalledWith("/catalogo");
    await waitFor(() => expect(ultimaListagem()).toMatch(/^\/livros\?/));
    expect(screen.getByLabelText("Buscar no acervo")).toHaveValue("");
  });

  it("apagar o campo volta ao catálogo completo", async () => {
    const u = userEvent.setup();
    url.busca = "q=asfadfasfaf";
    render(<Catalogo />);
    await screen.findByText("Resultados para “asfadfasfaf”");
    expect(screen.getByLabelText("Buscar no acervo")).toHaveValue("asfadfasfaf");
    await u.clear(screen.getByLabelText("Buscar no acervo"));
    await waitFor(() => expect(ultimaListagem()).toMatch(/^\/livros\?/));
    expect(screen.queryByText(/Resultados para/)).not.toBeInTheDocument();
  });

  it("voltar para /catalogo sem q mostra o acervo, não a busca anterior", async () => {
    url.busca = "q=memória";
    render(<Catalogo />);
    await screen.findByText("Resultados para “memória”");
    act(() => url.ir(""));
    await waitFor(() => expect(ultimaListagem()).toMatch(/^\/livros\?/));
    expect(screen.getByLabelText("Buscar no acervo")).toHaveValue("");
  });
});

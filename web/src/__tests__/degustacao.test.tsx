import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Degustacao } from "@/components/Degustacao";
import { EstanteDaHome } from "@/components/EstanteDaHome";
import {
  carregarDegustacoes,
  chaveTitulo,
  rotuloVista,
  vistaDoItem,
  vistas,
  type Degustacao as DadosDegustacao,
} from "@/lib/degustacao";

const apiMock = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  api: (...a: unknown[]) => apiMock(...a),
}));

const paginas = (n: number) => Array.from({ length: n }, (_, i) => `/degustacao/dom-casmurro/${String(i + 1).padStart(2, "0")}.jpg`);
const dados = (n = 5): DadosDegustacao => ({ titulo: "Dom Casmurro", largura: 900, altura: 1278, paginas: paginas(n) });
const livro = { id: 7, titulo: "Dom Casmurro", autores: ["Machado de Assis"] };

/** Simula as consultas de mídia: largura de desktop e/ou movimento reduzido. */
function midia({ largo = false, reduzido = false } = {}) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((q: string) => ({
      matches: q.includes("min-width") ? largo : q.includes("reduced-motion") ? reduzido : false,
      media: q,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

/** O React escolhe o nome do evento (com ou sem prefixo) conforme o navegador; o jsdom não tem
 * AnimationEvent, então disparamos os dois. */
function fimDaAnimacao(el: Element) {
  act(() => {
    el.dispatchEvent(new Event("animationend", { bubbles: true }));
    el.dispatchEvent(new Event("webkitAnimationEnd", { bubbles: true }));
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("lib/degustacao", () => {
  it("em página dupla, a capa abre sozinha à direita e o fim fecha a última vista", () => {
    expect(vistas(5, true)).toEqual([
      [null, 0],
      [1, 2],
      [3, 4],
      [5, null],
    ]);
    expect(vistas(4, true)).toEqual([
      [null, 0],
      [1, 2],
      [3, 4],
    ]);
  });

  it("em página simples, uma por vez, com o fim no final", () => {
    expect(vistas(3, false)).toEqual([[0], [1], [2], [3]]);
  });

  it("acha a vista de um item nos dois modos", () => {
    expect([0, 1, 2, 3, 4, 5].map((i) => vistaDoItem(i, true))).toEqual([0, 1, 1, 2, 2, 3]);
    expect(vistaDoItem(4, false)).toBe(4);
  });

  it("o contador não conta a capa como página", () => {
    expect(rotuloVista([null, 0], 5)).toBe("Capa");
    expect(rotuloVista([1, 2], 5)).toBe("Páginas 1 e 2 de 4");
    expect(rotuloVista([3], 5)).toBe("Página 3 de 4");
    expect(rotuloVista([5, null], 5)).toBe("Fim da degustação");
  });

  it("compara títulos sem ligar para caixa nem forma de acento (NFD/NFC)", () => {
    expect(chaveTitulo("Memórias Póstumas".normalize("NFD"))).toBe(chaveTitulo("memórias póstumas"));
  });

  it("lê o índice e descarta entradas inválidas; sem índice, mapa vazio", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          versao: 1,
          livros: [dados(3), { titulo: "Ruim", largura: 1, altura: 1, paginas: ["https://fora.example/x.jpg"] }],
        }),
      }),
    );
    const m = await carregarDegustacoes();
    expect([...m.keys()]).toEqual(["dom casmurro"]);

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    expect((await carregarDegustacoes()).size).toBe(0);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("rede")));
    expect((await carregarDegustacoes()).size).toBe(0);
  });
});

describe("Degustacao (leitor)", () => {
  it("abre como diálogo nomeado pelo livro, na capa, com o foco em Fechar", () => {
    render(<Degustacao livro={livro} degustacao={dados()} onFechar={() => {}} />);
    const dialogo = screen.getByRole("dialog", { name: "Degustação: Dom Casmurro" });
    expect(dialogo).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("img", { name: "Capa de Dom Casmurro" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fechar" })).toHaveFocus();
    expect(screen.getByRole("button", { name: "Página anterior" })).toBeDisabled();
    expect(screen.getByText("Capa")).toBeInTheDocument();
    expect(document.body.style.overflow).toBe("hidden");
  });

  it("vira para a frente e para trás com os botões e com as setas do teclado", async () => {
    const u = userEvent.setup();
    render(<Degustacao livro={livro} degustacao={dados()} onFechar={() => {}} />);
    await u.click(screen.getByRole("button", { name: "Próxima página" }));
    expect(screen.getByRole("img", { name: "Página 1 de Dom Casmurro" })).toBeInTheDocument();
    expect(screen.getByText("Página 1 de 4")).toBeInTheDocument();

    await u.keyboard("{ArrowRight}{ArrowRight}");
    expect(screen.getByRole("img", { name: "Página 3 de Dom Casmurro" })).toBeInTheDocument();
    await u.keyboard("{ArrowLeft}");
    expect(screen.getByRole("img", { name: "Página 2 de Dom Casmurro" })).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Página anterior" }));
    expect(screen.getByRole("img", { name: "Página 1 de Dom Casmurro" })).toBeInTheDocument();
  });

  it("no fim, leva à ficha para locar e à conversa; não passa do fim", async () => {
    const u = userEvent.setup();
    render(<Degustacao livro={livro} degustacao={dados(3)} onFechar={() => {}} />);
    await u.keyboard("{ArrowRight}{ArrowRight}{ArrowRight}{ArrowRight}{ArrowRight}");
    expect(screen.getByRole("link", { name: "Ver ficha e locar" })).toHaveAttribute("href", "/livro/7");
    expect(screen.getByRole("link", { name: "Conversar com a Léia" })).toHaveAttribute("href", "/conversa");
    expect(screen.getByRole("button", { name: "Próxima página" })).toBeDisabled();
    expect(screen.getAllByText("Fim da degustação").length).toBeGreaterThan(0);
  });

  it("Esc e o botão Fechar fecham", async () => {
    const u = userEvent.setup();
    const onFechar = vi.fn();
    render(<Degustacao livro={livro} degustacao={dados()} onFechar={onFechar} />);
    await u.keyboard("{Escape}");
    await u.click(screen.getByRole("button", { name: "Fechar" }));
    expect(onFechar).toHaveBeenCalledTimes(2);
  });

  it("prende o foco no diálogo (Tab do último volta ao primeiro)", async () => {
    const u = userEvent.setup();
    render(<Degustacao livro={livro} degustacao={dados()} onFechar={() => {}} />);
    await u.tab(); // Próxima página (a anterior está desabilitada)
    expect(screen.getByRole("button", { name: "Próxima página" })).toHaveFocus();
    await u.tab();
    expect(screen.getByRole("button", { name: "Fechar" })).toHaveFocus();
    await u.tab({ shift: true });
    expect(screen.getByRole("button", { name: "Próxima página" })).toHaveFocus();
  });

  it("deslize no toque vira a página", () => {
    render(<Degustacao livro={livro} degustacao={dados()} onFechar={() => {}} />);
    const capa = screen.getByRole("img", { name: "Capa de Dom Casmurro" });
    const livroEl = capa.closest(".degustacao-livro")!;
    fireEvent.pointerDown(livroEl, { pointerType: "touch", clientX: 300, clientY: 100 });
    fireEvent.pointerUp(livroEl, { pointerType: "touch", clientX: 200, clientY: 110 });
    expect(screen.getByRole("img", { name: "Página 1 de Dom Casmurro" })).toBeInTheDocument();
  });

  it("em tela larga mostra páginas duplas e a folha vira por cima até a animação acabar", async () => {
    midia({ largo: true });
    vi.useFakeTimers();
    render(<Degustacao livro={livro} degustacao={dados()} onFechar={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Próxima página" }));
    const dialogo = screen.getByRole("dialog");
    expect(screen.getByText("Páginas 1 e 2 de 4")).toBeInTheDocument();
    // A folha (decorativa) leva a capa na frente e a página 1 no verso.
    const folha = dialogo.querySelector(".degustacao-folha")!;
    expect(folha).toHaveAttribute("data-dir", "avanca");
    expect(within(folha as HTMLElement).getAllByRole("img", { hidden: true })).toHaveLength(2);
    fimDaAnimacao(folha);
    expect(dialogo.querySelector(".degustacao-folha")).toBeNull();
    // Por baixo, a vista nova inteira.
    expect(screen.getByRole("img", { name: "Página 1 de Dom Casmurro" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Página 2 de Dom Casmurro" })).toBeInTheDocument();

    // Voltar também vira; se o animationend não vier, o prazo limpa a folha.
    fireEvent.click(screen.getByRole("button", { name: "Página anterior" }));
    expect(dialogo.querySelector(".degustacao-folha")).toHaveAttribute("data-dir", "volta");
    act(() => vi.advanceTimersByTime(1000));
    expect(dialogo.querySelector(".degustacao-folha")).toBeNull();
    expect(screen.getByText("Capa")).toBeInTheDocument();
  });

  it("clique no lado direito da página avança e no esquerdo volta", () => {
    midia({ largo: true, reduzido: true });
    render(<Degustacao livro={livro} degustacao={dados()} onFechar={() => {}} />);
    const dialogo = screen.getByRole("dialog");
    fireEvent.click(dialogo.querySelector(".degustacao-lado-dir")!);
    expect(screen.getByText("Páginas 1 e 2 de 4")).toBeInTheDocument();
    fireEvent.click(dialogo.querySelector(".degustacao-lado-esq")!);
    expect(screen.getByText("Capa")).toBeInTheDocument();
  });

  it("com movimento reduzido não há folha virando", () => {
    midia({ largo: true, reduzido: true });
    render(<Degustacao livro={livro} degustacao={dados()} onFechar={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Próxima página" }));
    expect(screen.getByRole("dialog").querySelector(".degustacao-folha")).toBeNull();
    expect(screen.getByText("Páginas 1 e 2 de 4")).toBeInTheDocument();
  });
});

describe("EstanteDaHome com degustação", () => {
  const item = (id: number, titulo: string) => ({
    id,
    titulo,
    autores: ["Autoria"],
    ano: 1900,
    capa_url: "https://covers.example/x.jpg",
    livres: 1,
    fila: 0,
  });

  beforeEach(() => {
    apiMock.mockReset();
    apiMock.mockResolvedValue({ itens: [item(1, "Dom Casmurro"), item(2, "Iracema")], total: 2, pagina: 1 });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ versao: 1, livros: [dados(4)] }) }),
    );
  });

  it("livro com degustação abre o leitor no clique; ao fechar, o foco volta para a capa", async () => {
    const u = userEvent.setup();
    render(<EstanteDaHome />);
    const link = await screen.findByRole("link", { name: "Dom Casmurro" });
    await waitFor(() => expect(link).toHaveAttribute("aria-haspopup", "dialog"));
    expect(link).toHaveAttribute("href", "/livro/1");
    expect(link).toHaveAccessibleDescription("Abra uma capa para folhear as primeiras páginas.");

    await u.click(link);
    expect(screen.getByRole("dialog", { name: "Degustação: Dom Casmurro" })).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Fechar" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(link).toHaveFocus();
  });

  it("livro sem degustação segue sendo só o link para a ficha", async () => {
    const u = userEvent.setup();
    render(<EstanteDaHome />);
    const link = await screen.findByRole("link", { name: "Iracema" });
    await screen.findByText("Abra uma capa para folhear as primeiras páginas.");
    expect(link).not.toHaveAttribute("aria-haspopup");
    // jsdom não navega; o que importa é não abrir o leitor.
    await u.click(link);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

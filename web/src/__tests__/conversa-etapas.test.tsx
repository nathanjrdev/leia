import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EventoSSE } from "@/lib/api";
import { Conversa } from "@/components/Conversa";

// Andamento do turno: a API manda `etapa` enquanto a resposta ainda não foi validada.
vi.mock("@/components/SessaoProvider", () => ({
  useSessao: () => ({
    conta: { nome: "Ana", email: "ana@leia.example" },
    carregando: false,
    definirConta: vi.fn(),
    sair: vi.fn(),
  }),
}));

const apiMock = vi.fn();
const postarMock = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  api: (...a: unknown[]) => apiMock(...a),
  postarSSE: (...a: unknown[]) => postarMock(...a),
}));

beforeEach(() => {
  sessionStorage.clear();
  apiMock.mockReset();
  postarMock.mockReset();
  apiMock.mockImplementation((caminho: string, o?: { metodo?: string }) => {
    if (caminho === "/conversas" && o?.metodo === "POST") return Promise.resolve({ id: 7 });
    return Promise.reject(new Error("inesperado " + caminho));
  });
});

function turnoPausado(eventos: EventoSSE[]): () => void {
  let liberar: () => void = () => {};
  postarMock.mockImplementationOnce(
    (_c: string, _b: unknown, aoEvento: (e: EventoSSE) => void) =>
      new Promise<void>((r) => {
        eventos.forEach(aoEvento);
        liberar = r;
      }),
  );
  return () => liberar();
}

async function enviar(texto: string) {
  const u = userEvent.setup();
  await u.type(await screen.findByLabelText("Mensagem para a Léia"), texto);
  await u.click(screen.getByRole("button", { name: "Enviar" }));
}

describe("Conversa: andamento do turno", () => {
  it("depois da busca, avisa que está escrevendo a resposta", async () => {
    const liberar = turnoPausado([
      { evento: "ferramenta", dados: { nome: "buscar_livros" } },
      { evento: "etapa", dados: { etapa: "escrevendo" } },
    ]);
    render(<Conversa />);
    await enviar("poesia");
    expect(await screen.findByText("Escrevendo a resposta…")).toBeInTheDocument();
    expect(screen.queryByText(/Buscando no acervo/)).not.toBeInTheDocument();
    liberar();
    await waitFor(() => expect(screen.getByRole("button", { name: "Enviar" })).toBeEnabled());
  });

  it("quando a resposta é refeita, avisa que está conferindo", async () => {
    const liberar = turnoPausado([
      { evento: "ferramenta", dados: { nome: "buscar_livros" } },
      { evento: "etapa", dados: { etapa: "escrevendo" } },
      { evento: "etapa", dados: { etapa: "revisando" } },
    ]);
    render(<Conversa />);
    await enviar("poesia");
    expect(await screen.findByText("Conferindo os livros no acervo…")).toBeInTheDocument();
    liberar();
    await waitFor(() => expect(screen.getByRole("button", { name: "Enviar" })).toBeEnabled());
  });

  it("etapa desconhecida não quebra a tela e mantém o aviso genérico", async () => {
    const liberar = turnoPausado([{ evento: "etapa", dados: { etapa: "outra-coisa" } }]);
    render(<Conversa />);
    await enviar("poesia");
    expect(await screen.findByText("Pensando…")).toBeInTheDocument();
    liberar();
    await waitFor(() => expect(screen.getByRole("button", { name: "Enviar" })).toBeEnabled());
  });

  it("descartar apaga o texto parcial e mostra o andamento até chegar o novo", async () => {
    let liberar: () => void = () => {};
    let emitir: (e: EventoSSE) => void = () => {};
    postarMock.mockImplementationOnce(
      (_c: string, _b: unknown, aoEvento: (e: EventoSSE) => void) =>
        new Promise<void>((r) => {
          emitir = aoEvento;
          aoEvento({ evento: "resposta", dados: { texto: "Leia " } });
          liberar = r;
        }),
    );
    render(<Conversa />);
    await enviar("poesia");
    expect(await screen.findByText("Leia")).toBeInTheDocument();

    emitir({ evento: "descartar", dados: {} });
    emitir({ evento: "etapa", dados: { etapa: "revisando" } });
    expect(await screen.findByText("Conferindo os livros no acervo…")).toBeInTheDocument();
    expect(screen.queryByText("Leia")).not.toBeInTheDocument();

    emitir({ evento: "resposta", dados: { texto: "Achei um livro." } });
    emitir({ evento: "fim", dados: { erro: null } });
    expect(await screen.findByText("Achei um livro.")).toBeInTheDocument();
    expect(screen.queryByText(/Leia Achei/)).not.toBeInTheDocument();
    liberar();
  });

  it("o texto da resposta substitui o aviso de andamento", async () => {
    const liberar = turnoPausado([
      { evento: "etapa", dados: { etapa: "escrevendo" } },
      { evento: "resposta", dados: { texto: "Achei três livros." } },
      { evento: "fim", dados: { erro: null } },
    ]);
    render(<Conversa />);
    await enviar("poesia");
    expect(await screen.findByText("Achei três livros.")).toBeInTheDocument();
    expect(screen.queryByText("Escrevendo a resposta…")).not.toBeInTheDocument();
    liberar();
  });
});

describe("Conversa: animação do aviso de andamento", () => {
  it("o aviso tem um indicador animado escondido do leitor de tela", async () => {
    const liberar = turnoPausado([{ evento: "ferramenta", dados: { nome: "buscar_livros" } }]);
    render(<Conversa />);
    await enviar("poesia");
    const rotulo = await screen.findByText("Buscando no acervo…");
    const aviso = rotulo.closest("p");
    const indicador = aviso?.querySelector('[aria-hidden="true"]');
    expect(indicador?.querySelectorAll(".andamento-ponto")).toHaveLength(3);
    // o rótulo continua sendo o único texto do aviso
    expect(aviso).toHaveTextContent(/^Buscando no acervo…$/);
    liberar();
    await waitFor(() => expect(screen.getByRole("button", { name: "Enviar" })).toBeEnabled());
  });

  it("o aviso não vira região viva: só o status da conversa anuncia", async () => {
    const liberar = turnoPausado([{ evento: "etapa", dados: { etapa: "escrevendo" } }]);
    render(<Conversa />);
    await enviar("poesia");
    const aviso = (await screen.findByText("Escrevendo a resposta…")).closest("p");
    expect(aviso).not.toHaveAttribute("role");
    expect(aviso).not.toHaveAttribute("aria-live");
    expect(screen.getByRole("list", { name: "Conversa" })).not.toHaveAttribute("aria-live");
    expect(screen.getAllByRole("status").map((s) => s.textContent)).toContain(
      "A Léia está respondendo…",
    );
    liberar();
    await waitFor(() => expect(screen.getByRole("button", { name: "Enviar" })).toBeEnabled());
  });

  it("antes de qualquer etapa, 'Pensando…' também tem o indicador", async () => {
    const liberar = turnoPausado([]);
    render(<Conversa />);
    await enviar("poesia");
    const aviso = (await screen.findByText("Pensando…")).closest("p");
    expect(aviso?.querySelectorAll(".andamento-ponto")).toHaveLength(3);
    liberar();
    await waitFor(() => expect(screen.getByRole("button", { name: "Enviar" })).toBeEnabled());
  });

  it("a animação só existe sem preferência por movimento reduzido", () => {
    const css = readFileSync(resolve(__dirname, "../app/globals.css"), "utf8");
    const semAnimacao = css.replace(
      /@media \(prefers-reduced-motion: no-preference\) \{[\s\S]*?\n\}/g,
      "",
    );
    expect(css).toMatch(/\.andamento-ponto[^{]*\{[^}]*animation:/);
    expect(semAnimacao).not.toMatch(/animation:/);
  });
});

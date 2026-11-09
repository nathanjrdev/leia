import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Cabecalho } from "@/components/Cabecalho";

vi.mock("@/components/SessaoProvider", () => ({
  useSessao: () => ({ conta: null, carregando: false, definirConta: vi.fn(), sair: vi.fn() }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

describe("Cabecalho", () => {
  it("o primeiro link da página pula direto para o conteúdo principal", () => {
    render(<Cabecalho />);
    const [primeiro] = screen.getAllByRole("link");
    expect(primeiro).toHaveTextContent("Pular para o conteúdo");
    expect(primeiro).toHaveAttribute("href", "#conteudo");
  });

  it("a navegação principal continua com os três destinos", () => {
    render(<Cabecalho />);
    const nav = screen.getByRole("navigation", { name: "Principal" });
    expect(nav.querySelectorAll("a")).toHaveLength(3);
  });
});

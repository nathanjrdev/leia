import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Cabecalho } from "@/components/Cabecalho";
import type { Conta } from "@/lib/tipos";

const sessao = vi.hoisted(() => ({
  conta: null as Conta | null,
  sair: vi.fn(),
}));
const push = vi.hoisted(() => vi.fn());

vi.mock("@/components/SessaoProvider", () => ({
  useSessao: () => ({
    conta: sessao.conta,
    carregando: false,
    definirConta: vi.fn(),
    sair: sessao.sair,
  }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

beforeEach(() => {
  sessao.conta = null;
  sessao.sair.mockReset().mockResolvedValue(undefined);
  push.mockReset();
});

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

  it("sem sessão mostra Entrar e nenhum menu da conta", () => {
    render(<Cabecalho />);
    expect(screen.getByRole("link", { name: "Entrar" })).toHaveAttribute("href", "/entrar");
    expect(screen.queryByRole("button", { name: "Menu da conta" })).toBeNull();
  });

  describe("com sessão", () => {
    beforeEach(() => {
      sessao.conta = { nome: "Ana Souza", email: "ana@leia.example" };
    });

    it("Sair fica atrás do botão de menu, fechado de início", () => {
      render(<Cabecalho />);
      const menu = screen.getByRole("button", { name: "Menu da conta" });
      expect(menu).toHaveAttribute("aria-expanded", "false");
      expect(menu).toHaveAttribute("aria-haspopup", "dialog");
      expect(screen.queryByRole("dialog")).toBeNull();
      expect(screen.queryByRole("button", { name: "Sair" })).toBeNull();
    });

    it("o ícone é o render dos livros de prata, decorativo, com o desenho de traço de reserva", () => {
      render(<Cabecalho />);
      const botao = screen.getByRole("button", { name: "Menu da conta" });
      const img = botao.querySelector("img");
      expect(img).toHaveAttribute("src", "/objetos/menu-livros.webp");
      expect(img).toHaveAttribute("alt", "");
      fireEvent.error(img!);
      expect(botao.querySelector("img")).toBeNull();
      expect(botao.querySelector("svg")).not.toBeNull();
    });

    it("o menu abre a gaveta com a conta e a opção Sair", async () => {
      const u = userEvent.setup();
      render(<Cabecalho />);
      const menu = screen.getByRole("button", { name: "Menu da conta" });
      await u.click(menu);
      const gaveta = screen.getByRole("dialog", { name: "Sua conta" });
      expect(gaveta).toHaveTextContent("Ana Souza");
      expect(gaveta).toHaveTextContent("ana@leia.example");
      expect(screen.getByRole("button", { name: "Sair" })).toBeVisible();
      expect(menu).toHaveAttribute("aria-expanded", "true");
    });

    it("Sair encerra a sessão, fecha a gaveta e volta ao início", async () => {
      const u = userEvent.setup();
      render(<Cabecalho />);
      await u.click(screen.getByRole("button", { name: "Menu da conta" }));
      await u.click(screen.getByRole("button", { name: "Sair" }));
      expect(sessao.sair).toHaveBeenCalledOnce();
      await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("o botão Fechar fecha a gaveta", async () => {
      const u = userEvent.setup();
      render(<Cabecalho />);
      await u.click(screen.getByRole("button", { name: "Menu da conta" }));
      await u.click(screen.getByRole("button", { name: "Fechar menu" }));
      expect(screen.queryByRole("dialog")).toBeNull();
      expect(screen.getByRole("button", { name: "Menu da conta" })).toHaveAttribute(
        "aria-expanded",
        "false",
      );
    });
  });
});

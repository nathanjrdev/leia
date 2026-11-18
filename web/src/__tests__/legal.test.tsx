import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Privacidade from "@/app/privacidade/page";
import Termos from "@/app/termos/page";
import { Rodape } from "@/components/Rodape";

describe("páginas legais", () => {
  it("a política diz o que guarda, com quem compartilha e como pedir exclusão", () => {
    render(<Privacidade />);
    expect(screen.getByRole("heading", { level: 1, name: "Política de Privacidade" })).toBeVisible();
    for (const secao of ["O que guardamos", "Com quem compartilhamos", "Cookies", "Seus direitos"]) {
      expect(screen.getByRole("heading", { level: 2, name: secao })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("link", { name: "njunioestudos@gmail.com" })[0]).toHaveAttribute(
      "href",
      "mailto:njunioestudos@gmail.com",
    );
    expect(screen.getByRole("link", { name: "Termos de Uso" })).toHaveAttribute("href", "/termos");
  });

  it("os termos apontam para a política", () => {
    render(<Termos />);
    expect(screen.getByRole("heading", { level: 1, name: "Termos de Uso" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Política de Privacidade" })).toHaveAttribute(
      "href",
      "/privacidade",
    );
  });

  it("o rodapé leva às duas páginas", () => {
    render(<Rodape />);
    const nav = screen.getByRole("navigation", { name: "Rodapé" });
    expect(nav.querySelector('a[href="/privacidade"]')).not.toBeNull();
    expect(nav.querySelector('a[href="/termos"]')).not.toBeNull();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Aviso } from "@/components/ui/Aviso";
import { Botao, classesBotao } from "@/components/ui/Botao";
import { Prateleira } from "@/components/ui/Prateleira";
import { Selo } from "@/components/ui/Selo";

describe("Botao", () => {
  it("é type=button por padrão: não envia formulário sem querer", () => {
    render(<Botao>Renovar</Botao>);
    expect(screen.getByRole("button", { name: "Renovar" })).toHaveAttribute("type", "button");
  });

  it("aceita type=submit e repassa clique e disabled", async () => {
    const u = userEvent.setup();
    const f = vi.fn();
    const { rerender } = render(
      <Botao type="submit" variante="primaria" onClick={f}>
        Enviar
      </Botao>,
    );
    const b = screen.getByRole("button", { name: "Enviar" });
    expect(b).toHaveAttribute("type", "submit");
    await u.click(b);
    expect(f).toHaveBeenCalledTimes(1);
    rerender(
      <Botao type="submit" variante="primaria" onClick={f} disabled>
        Enviar
      </Botao>,
    );
    await u.click(screen.getByRole("button", { name: "Enviar" }));
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("as classes de variante servem também para links", () => {
    expect(classesBotao("primaria")).toContain("botao-primaria");
    expect(classesBotao("secundaria")).toContain("botao-secundaria");
    expect(classesBotao("texto")).toContain("botao-texto");
  });
});

describe("Selo", () => {
  it("mostra o texto; o ponto é decorativo", () => {
    const { container } = render(<Selo tom="disponivel">2 disponíveis</Selo>);
    expect(screen.getByText("2 disponíveis")).toBeInTheDocument();
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });

  it("o atraso leva ícone e texto, nunca só cor", () => {
    render(<Selo tom="alerta">Atrasada</Selo>);
    expect(screen.getByText("Atrasada")).toBeInTheDocument();
  });
});

describe("Aviso", () => {
  it("erro é alerta; o texto fica dentro do papel", () => {
    render(<Aviso tipo="erro">Algo deu errado.</Aviso>);
    expect(screen.getByRole("alert")).toHaveTextContent("Algo deu errado.");
  });

  it("sucesso é status", () => {
    render(<Aviso tipo="sucesso">Locação feita.</Aviso>);
    expect(screen.getByRole("status")).toHaveTextContent("Locação feita.");
  });
});

describe("Prateleira", () => {
  it("a tábua de vidro é decorativa e não cobre os livros para o leitor de tela", () => {
    const { container } = render(
      <Prateleira>
        <button type="button">Dom Casmurro</button>
      </Prateleira>,
    );
    expect(screen.getByRole("button", { name: "Dom Casmurro" })).toBeInTheDocument();
    expect(container.querySelector(".prateleira-tabua")).toHaveAttribute("aria-hidden", "true");
  });
});

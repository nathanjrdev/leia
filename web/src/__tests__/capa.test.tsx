import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Capa } from "@/components/Capa";
import { autoriaDaCapa, TONS_DE_CAPA, tituloDaCapa, tomDaCapa } from "@/lib/capa";

describe("tituloDaCapa", () => {
  it("mantém o título curto como está", () => {
    expect(tituloDaCapa("Dom Casmurro")).toBe("Dom Casmurro");
  });

  it("corta o subtítulo entre parênteses, depois de dois-pontos ou de travessão", () => {
    expect(tituloDaCapa("O Pequeno Livro Vermelho (Citações do Presidente Mao Tsé-Tung)")).toBe(
      "O Pequeno Livro Vermelho",
    );
    expect(tituloDaCapa("Sapiens: Uma breve história da humanidade")).toBe("Sapiens");
    expect(tituloDaCapa("A Noite da Espera - Volume 1")).toBe("A Noite da Espera");
    expect(tituloDaCapa("Grande Sertão — Veredas")).toBe("Grande Sertão");
  });

  it("não corta hífen dentro de palavra nem deixa o título vazio", () => {
    expect(tituloDaCapa("Mao Tsé-Tung")).toBe("Mao Tsé-Tung");
    expect(tituloDaCapa("(Sem título)")).toBe("(Sem título)");
  });
});

describe("autoriaDaCapa", () => {
  it("um ou dois autores aparecem pelo nome; mais de dois viram 'e outros'", () => {
    expect(autoriaDaCapa([])).toBe("");
    expect(autoriaDaCapa(["Clarice Lispector"])).toBe("Clarice Lispector");
    expect(autoriaDaCapa(["A", "B"])).toBe("A e B");
    expect(autoriaDaCapa(["A", "B", "C"])).toBe("A e outros");
  });
});

describe("tomDaCapa", () => {
  it("é determinístico e fica entre 1 e o número de tons", () => {
    expect(tomDaCapa(42)).toBe(tomDaCapa(42));
    for (let id = -3; id < 20; id++) {
      const tom = tomDaCapa(id);
      expect(tom).toBeGreaterThanOrEqual(1);
      expect(tom).toBeLessThanOrEqual(TONS_DE_CAPA);
    }
  });

  it("livros vizinhos na lista ganham tons diferentes", () => {
    expect(tomDaCapa(1)).not.toBe(tomDaCapa(2));
    expect(new Set(Array.from({ length: TONS_DE_CAPA }, (_, i) => tomDaCapa(i))).size).toBe(
      TONS_DE_CAPA,
    );
  });
});

const props = { titulo: "Dom Casmurro", autores: ["Machado de Assis"], semente: 7 };

describe("Capa", () => {
  it("sem imagem, gera a capa com título e autor, escondida dos leitores de tela", () => {
    const { container } = render(<Capa url={null} {...props} />);
    const capa = container.querySelector("[data-capa='gerada']");
    expect(capa).not.toBeNull();
    expect(capa).toHaveAttribute("aria-hidden", "true");
    expect(capa).toHaveClass(`capa-tom-${tomDaCapa(7)}`);
    expect(screen.getByText("Dom Casmurro")).toBeInTheDocument();
    expect(screen.getByText("Machado de Assis")).toBeInTheDocument();
    expect(screen.queryByText("Sem capa")).not.toBeInTheDocument();
  });

  it("com imagem, mostra a capa real", () => {
    const { container } = render(<Capa url="https://covers.example/dc.jpg" {...props} />);
    expect(container.querySelector("img")).toHaveAttribute("src", "https://covers.example/dc.jpg");
    expect(container.querySelector("[data-capa='gerada']")).toBeNull();
  });

  it("imagem que falha vira capa gerada", () => {
    const { container } = render(<Capa url="https://covers.example/quebrada.jpg" {...props} />);
    fireEvent.error(container.querySelector("img")!);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("[data-capa='gerada']")).not.toBeNull();
  });

  it("imagem de 1 pixel (capa inexistente na Open Library) vira capa gerada", () => {
    const { container } = render(<Capa url="https://covers.example/vazia.jpg" {...props} />);
    const img = container.querySelector("img")!;
    Object.defineProperty(img, "naturalWidth", { value: 1 });
    fireEvent.load(img);
    expect(container.querySelector("[data-capa='gerada']")).not.toBeNull();
  });

  it("imagem que carrega de verdade continua na tela", () => {
    const { container } = render(<Capa url="https://covers.example/dc.jpg" {...props} />);
    const img = container.querySelector("img")!;
    Object.defineProperty(img, "naturalWidth", { value: 300 });
    fireEvent.load(img);
    expect(container.querySelector("img")).not.toBeNull();
  });

  it("trocar a URL depois de uma falha tenta a nova imagem", () => {
    const { container, rerender } = render(<Capa url="https://covers.example/a.jpg" {...props} />);
    fireEvent.error(container.querySelector("img")!);
    rerender(<Capa url="https://covers.example/b.jpg" {...props} />);
    expect(container.querySelector("img")).toHaveAttribute("src", "https://covers.example/b.jpg");
  });
});

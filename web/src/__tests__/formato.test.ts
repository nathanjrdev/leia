import { describe, expect, it } from "vitest";
import { ano, avisoLocacao } from "@/lib/formato";

describe("avisoLocacao", () => {
  it("agradece, deseja boa leitura e informa a data de devolução", () => {
    const aviso = avisoLocacao("2026-11-23T12:00:00Z");
    expect(aviso).toContain("Obrigada");
    expect(aviso).toContain("Boa leitura");
    expect(aviso).toContain("Devolver até 23/11/2026");
  });
});

describe("ano", () => {
  it("ano comum fica como está", () => {
    expect(ano(1899)).toBe("1899");
  });

  it("ano negativo vira a.C., nunca um número com sinal", () => {
    expect(ano(-500)).toBe("500 a.C.");
  });
});

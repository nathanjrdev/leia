import { describe, expect, it } from "vitest";
import { ano } from "@/lib/formato";

describe("ano", () => {
  it("ano comum fica como está", () => {
    expect(ano(1899)).toBe("1899");
  });

  it("ano negativo vira a.C., nunca um número com sinal", () => {
    expect(ano(-500)).toBe("500 a.C.");
  });
});

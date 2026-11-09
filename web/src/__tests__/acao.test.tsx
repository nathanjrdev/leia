import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ErroApi } from "@/lib/api";
import { AcaoComConfirmacao } from "@/components/AcaoComConfirmacao";

function montar(aoConfirmar = vi.fn().mockResolvedValue(undefined)) {
  render(
    <AcaoComConfirmacao
      rotulo="Devolver"
      pergunta="Devolver “Dom Casmurro” agora?"
      rotuloConfirmar="Confirmar devolução"
      aoConfirmar={aoConfirmar}
    />,
  );
  return aoConfirmar;
}

describe("AcaoComConfirmacao", () => {
  it("o primeiro clique só pergunta; nada é executado", async () => {
    const u = userEvent.setup();
    const f = montar();
    await u.click(screen.getByRole("button", { name: "Devolver" }));
    expect(screen.getByText("Devolver “Dom Casmurro” agora?")).toBeInTheDocument();
    expect(f).not.toHaveBeenCalled();
  });

  it("só executa no botão de confirmação", async () => {
    const u = userEvent.setup();
    const f = montar();
    await u.click(screen.getByRole("button", { name: "Devolver" }));
    await u.click(screen.getByRole("button", { name: "Confirmar devolução" }));
    expect(f).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.getByRole("button", { name: "Devolver" })).toBeInTheDocument());
  });

  it("Voltar desfaz a pergunta sem executar", async () => {
    const u = userEvent.setup();
    const f = montar();
    await u.click(screen.getByRole("button", { name: "Devolver" }));
    await u.click(screen.getByRole("button", { name: "Voltar" }));
    expect(f).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Devolver" })).toBeInTheDocument();
  });

  it("erro da regra aparece como alerta e a ação volta ao início", async () => {
    const u = userEvent.setup();
    const f = montar(
      vi.fn().mockRejectedValue(new ErroApi(409, "renovacao_negada", "Há fila para este livro.")),
    );
    await u.click(screen.getByRole("button", { name: "Devolver" }));
    await u.click(screen.getByRole("button", { name: "Confirmar devolução" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Há fila para este livro.");
    expect(f).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Devolver" })).toBeInTheDocument();
  });
});

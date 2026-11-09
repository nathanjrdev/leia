import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ErroApi } from "@/lib/api";
import { FormularioAuth } from "@/components/FormularioAuth";
import { SessaoProvider } from "@/components/SessaoProvider";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: push }),
}));

const apiMock = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  api: (...a: unknown[]) => apiMock(...a),
}));

function montar(modo: "entrar" | "cadastrar") {
  return render(
    <SessaoProvider>
      <FormularioAuth modo={modo} />
    </SessaoProvider>,
  );
}

beforeEach(() => {
  push.mockReset();
  apiMock.mockReset();
  // a sessão começa sem ninguém logado
  apiMock.mockImplementation((caminho: string) =>
    caminho === "/auth/eu"
      ? Promise.reject(new ErroApi(401, "nao_autenticado", ""))
      : Promise.resolve({ nome: "Ana", email: "ana@leia.example" }),
  );
});

describe("FormularioAuth", () => {
  it("entrar: campos com rótulo e envio para /auth/login", async () => {
    const u = userEvent.setup();
    montar("entrar");
    await u.type(screen.getByLabelText("E-mail"), "ana@leia.example");
    await u.type(screen.getByLabelText("Senha"), "senha-ficticia-123");
    await u.click(screen.getByRole("button", { name: "Entrar" }));
    await waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith("/auth/login", {
        metodo: "POST",
        corpo: { email: "ana@leia.example", senha: "senha-ficticia-123" },
      }),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/conversa"));
  });

  it("cadastrar: pede nome e envia para /auth/cadastro", async () => {
    const u = userEvent.setup();
    montar("cadastrar");
    await u.type(screen.getByLabelText("Nome"), "Ana");
    await u.type(screen.getByLabelText("E-mail"), "ana@leia.example");
    await u.type(screen.getByLabelText("Senha"), "senha-ficticia-123");
    await u.click(screen.getByRole("button", { name: "Criar conta" }));
    await waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith("/auth/cadastro", {
        metodo: "POST",
        corpo: { nome: "Ana", email: "ana@leia.example", senha: "senha-ficticia-123" },
      }),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/conversa"));
  });

  it("mostra o erro do servidor num alerta e não navega", async () => {
    const u = userEvent.setup();
    apiMock.mockImplementation((caminho: string) =>
      caminho === "/auth/eu"
        ? Promise.reject(new ErroApi(401, "nao_autenticado", ""))
        : Promise.reject(
            new ErroApi(429, "muitas_tentativas", "Muitas tentativas. Aguarde 15 minutos."),
          ),
    );
    montar("entrar");
    await u.type(screen.getByLabelText("E-mail"), "ana@leia.example");
    await u.type(screen.getByLabelText("Senha"), "errada");
    await u.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Aguarde 15 minutos");
    expect(push).not.toHaveBeenCalled();
  });

  it("desabilita o botão enquanto envia (sem envio duplo)", async () => {
    const u = userEvent.setup();
    let resolver: (v: unknown) => void = () => {};
    apiMock.mockImplementation((caminho: string) =>
      caminho === "/auth/eu"
        ? Promise.reject(new ErroApi(401, "nao_autenticado", ""))
        : new Promise((r) => (resolver = r)),
    );
    montar("entrar");
    await u.type(screen.getByLabelText("E-mail"), "ana@leia.example");
    await u.type(screen.getByLabelText("Senha"), "x");
    await u.click(screen.getByRole("button", { name: "Entrar" }));
    expect(screen.getByRole("button", { name: "Entrando…" })).toBeDisabled();
    resolver({ nome: "Ana", email: "ana@leia.example" });
    await waitFor(() => expect(push).toHaveBeenCalled());
  });

  it("oferece o link para a outra tela", () => {
    montar("entrar");
    expect(screen.getByRole("link", { name: "Criar conta" })).toHaveAttribute("href", "/cadastrar");
  });
});

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

let contador = 0;

/** Cada teste cria o próprio leitor fictício, então podem rodar em qualquer ordem. */
async function cadastrar(page: Page) {
  await page.goto("/cadastrar");
  // O cabeçalho só mostra "Entrar" depois que o React hidratou e a sessão foi consultada.
  await expect(page.getByRole("banner").getByRole("link", { name: "Entrar" })).toBeVisible();
  await page.getByLabel("Nome").fill("Leitor E2E");
  await page.getByLabel("E-mail").fill(`e2e-${Date.now()}-${++contador}@leia.example`);
  await page.getByLabel("Senha").fill("senha-ficticia-123");
  await page.getByRole("button", { name: "Criar conta" }).click();
  await expect(page.getByRole("button", { name: "Sair" })).toBeVisible();
}

async function falar(page: Page, texto: string) {
  await page.goto("/conversa");
  await page.getByLabel("Mensagem para a Léia").fill(texto);
  await page.getByRole("button", { name: "Enviar" }).click();
}

test("o andamento chega antes do texto (SSE sem compressão no proxy)", async ({ page }) => {
  await cadastrar(page);
  await page.goto("/conversa");
  // Grava cada estado da última mensagem: com o SSE acumulado (gzip no proxy), o aviso nunca aparece.
  await page.getByRole("list", { name: "Conversa" }).evaluate((lista) => {
    const w = window as unknown as { linhaDoTempo: string[] };
    w.linhaDoTempo = [];
    new MutationObserver(() => {
      const texto = lista.lastElementChild?.textContent ?? "";
      if (texto !== w.linhaDoTempo.at(-1)) w.linhaDoTempo.push(texto);
    }).observe(lista, { childList: true, subtree: true, characterData: true });
  });
  const resposta = page.waitForResponse((r) => /\/api\/conversas\/\d+\/mensagens$/.test(r.url()));
  await page.getByLabel("Mensagem para a Léia").fill("Quero Dom Casmurro");
  await page.getByRole("button", { name: "Enviar" }).click();

  const cabecalhos = await (await resposta).allHeaders();
  expect(cabecalhos["content-encoding"]).toBeUndefined();
  expect(cabecalhos["cache-control"]).toContain("no-transform");
  await expect(page.getByText(/Encontrei “Dom Casmurro”/)).toBeVisible();

  const linha = await page.evaluate(
    () => (window as unknown as { linhaDoTempo: string[] }).linhaDoTempo,
  );
  const aviso = linha.findIndex((t) => /Buscando no acervo|Escrevendo a resposta/.test(t));
  const final = linha.findIndex((t) => t.includes("Encontrei “Dom Casmurro”"));
  expect(aviso, linha.join(" | ")).toBeGreaterThanOrEqual(0);
  expect(aviso).toBeLessThan(final);
});

test("conversa → locar → minha estante → devolver", async ({ page }) => {
  await cadastrar(page);
  await falar(page, "Quero locar Dom Casmurro");

  await expect(page.getByText(/Preparei a ação/)).toBeVisible();
  await page.getByRole("button", { name: "Confirmar", exact: true }).click();
  await expect(page.getByText("Locação concluída. Boa leitura!")).toBeVisible();

  await page.getByRole("link", { name: "Minha estante" }).click();
  await expect(page.getByRole("link", { name: "Dom Casmurro" })).toBeVisible();
  await page.getByRole("button", { name: "Devolver" }).click();
  await page.getByRole("button", { name: "Confirmar devolução" }).click();
  await expect(page.getByText("Você não tem livros locados nem reservas.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Histórico" })).toContainText("Dom Casmurro");
});

test("cancelar a proposta não aloca nenhum livro", async ({ page }) => {
  await cadastrar(page);
  await falar(page, "Quero locar Dom Casmurro");

  await expect(page.getByText(/Preparei a ação/)).toBeVisible();
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(page.getByText(/cancelei/)).toBeVisible();

  await page.getByRole("link", { name: "Minha estante" }).click();
  await expect(page.getByText("Você não tem livros locados nem reservas.")).toBeVisible();
});

test("cartão do livro no chat: Locar em duas etapas e o livro vai para a estante", async ({
  page,
}) => {
  await cadastrar(page);
  await falar(page, "Quero Dom Casmurro");

  const cartao = page.getByRole("group", { name: "Livro: Dom Casmurro" });
  await expect(cartao).toBeVisible();
  await cartao.getByRole("button", { name: "Locar" }).click();
  // O primeiro clique só pergunta: nada foi locado ainda.
  await expect(cartao.getByText("Locar “Dom Casmurro”?")).toBeVisible();
  await cartao.getByRole("button", { name: "Confirmar locação" }).click();
  // A locação passa pelo chat: a resposta da Léia aparece na conversa, não no cartão.
  await expect(page.getByText("Locação concluída. Boa leitura!")).toBeVisible();

  await cartao.getByRole("link", { name: "Ver minha estante" }).click();
  await expect(page.getByRole("region", { name: "Locações ativas" })).toContainText("Dom Casmurro");
  // Devolve: sem isso cada rodada prende 1 dos 3 exemplares e a 3ª rodada já falha.
  await page.getByRole("button", { name: "Devolver" }).click();
  await page.getByRole("button", { name: "Confirmar devolução" }).click();
  await expect(page.getByText("Você não tem livros locados nem reservas.")).toBeVisible();
});

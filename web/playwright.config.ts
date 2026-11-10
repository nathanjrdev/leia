import { defineConfig } from "@playwright/test";

/**
 * E2E do fluxo conversa → locar → minha estante → devolver.
 * A API sobe em MODO_TESTE (LLM e encoder falsos: sem cota, sem rede, sem ML) e o web em produção
 * (`npm run build` antes). Pré-requisito: Postgres com o catálogo carregado
 * (`docker compose up -d db` + `uv run python -m leia_api.modo_teste` em api/).
 * A porta 8000 precisa estar livre: nunca reaproveitamos uma API com o LLM de verdade.
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.e2e\.ts/,
  timeout: 60_000,
  // O cadastro faz hash de senha (scrypt) e fica lento logo depois que a API sobe a frio.
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    // CI instala o Chromium do Playwright; localmente usa o Chrome já instalado.
    channel: process.env.CI ? undefined : "chrome",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run uvicorn leia_api.main:app --port 8000",
      cwd: "../api",
      url: "http://127.0.0.1:8000/health",
      // O atraso dá duração ao turno do LLM falso: sem ele o andamento nem chega a ser pintado.
      env: { MODO_TESTE: "true", MODO_TESTE_ATRASO_MS: "400", PYTHONUTF8: "1" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run start -- -p 3000",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});

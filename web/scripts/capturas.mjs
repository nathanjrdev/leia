// Capturas de tela de todas as rotas, em desktop e celular, claro e escuro. Servem para comparar
// o antes e o depois de uma mudança visual (conteúdo e estados, não pixel a pixel).
//
// Uso (em web/, com o app no ar em http://127.0.0.1:3000):
//   node scripts/capturas.mjs capturas/antes
//   BASE=http://127.0.0.1:3000 MOVIMENTO=reduzido node scripts/capturas.mjs capturas/depois
//
// Com a API falsa (scripts/api-falsa.mjs) todos os estados aparecem; com a API real, os da conta usada.
import { mkdir } from "node:fs/promises";
import { chromium } from "@playwright/test";

const BASE = process.env.BASE ?? "http://127.0.0.1:3000";
const SAIDA = process.argv[2] ?? "capturas/atual";
const MOVIMENTO = process.env.MOVIMENTO === "reduzido" ? "reduce" : "no-preference";

const TAMANHOS = [
  { nome: "1440", viewport: { width: 1440, height: 900 } },
  { nome: "390", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
];
const TEMAS = ["light", "dark"];

/** Cada cena: rota, nome do arquivo e o que fazer antes da foto. */
const CENAS = [
  { nome: "inicio", rota: "/" },
  { nome: "entrar", rota: "/entrar" },
  { nome: "cadastrar", rota: "/cadastrar" },
  { nome: "catalogo", rota: "/catalogo", espera: (p) => p.getByRole("link", { name: "Dom Casmurro" }).waitFor() },
  { nome: "ficha", rota: "/livro/1", espera: (p) => p.getByRole("heading", { name: "Dom Casmurro" }).waitFor() },
  { nome: "estante", rota: "/estante", espera: (p) => p.getByRole("region", { name: "Histórico" }).waitFor() },
  {
    nome: "conversa-vazia",
    rota: "/conversa",
    espera: (p) => p.getByRole("group", { name: "Sugestões para começar" }).waitFor(),
  },
  {
    nome: "conversa-cartoes",
    rota: "/conversa",
    espera: async (p) => {
      await p.getByLabel("Mensagem para a Léia").fill("Quero Dom Casmurro");
      await p.getByRole("button", { name: "Enviar" }).click();
      await p.getByRole("group", { name: "Livro: Quincas Borba" }).waitFor();
    },
  },
  {
    nome: "conversa-proposta",
    rota: "/conversa",
    espera: async (p) => {
      await p.getByLabel("Mensagem para a Léia").fill("Quero locar Dom Casmurro");
      await p.getByRole("button", { name: "Enviar" }).click();
      await p.getByRole("group", { name: "Confirmação" }).waitFor();
    },
  },
];

const navegador = await chromium.launch({ channel: process.env.CI ? undefined : "chrome" });
await mkdir(SAIDA, { recursive: true });
let feitas = 0;
for (const t of TAMANHOS) {
  for (const tema of TEMAS) {
    for (const c of CENAS) {
      const ctx = await navegador.newContext({
        viewport: t.viewport,
        isMobile: t.isMobile,
        hasTouch: t.hasTouch,
        colorScheme: tema,
        reducedMotion: MOVIMENTO,
        locale: "pt-BR",
        timezoneId: "America/Sao_Paulo",
      });
      const p = await ctx.newPage();
      try {
        await p.goto(`${BASE}${c.rota}`, { waitUntil: "networkidle" });
        if (c.espera) await c.espera(p);
        await p.waitForTimeout(400); // fontes e transições curtas assentarem
        await p.screenshot({ path: `${SAIDA}/${c.nome}-${t.nome}-${tema}.png`, fullPage: true });
        feitas++;
      } catch (e) {
        console.error(`falhou: ${c.nome} ${t.nome} ${tema}: ${e.message.split("\n")[0]}`);
      } finally {
        await ctx.close();
      }
    }
  }
}
await navegador.close();
console.log(`${feitas} capturas em ${SAIDA}`);

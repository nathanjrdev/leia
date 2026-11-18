"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import type { FormEvent } from "react";
import { api, mensagemDoErro } from "@/lib/api";
import type { Conta } from "@/lib/tipos";
import { useSessao } from "./SessaoProvider";
import { Aviso } from "./ui/Aviso";
import { Botao, classesBotao } from "./ui/Botao";

const SENHA_MIN = 8;

type Provedor = "google" | "microsoft";
const NOME_PROVEDOR: Record<Provedor, string> = { google: "Google", microsoft: "Microsoft" };

/** Códigos que a API põe em `/entrar?erro=…` quando o login com Google/Microsoft não dá certo. */
const ERRO_SOCIAL: Record<string, string> = {
  cancelado: "A entrada foi cancelada. Tente de novo quando quiser.",
  email_nao_verificado:
    "Essa conta não tem um e-mail verificado. Use outra conta ou entre com e-mail e senha.",
  provedor_indisponivel: "Essa forma de entrar não está disponível agora.",
  muitas_tentativas: "Muitas tentativas seguidas. Aguarde um instante.",
  oauth_falhou: "Não consegui entrar com essa conta. Tente de novo.",
};

export function FormularioAuth({ modo }: { modo: "entrar" | "cadastrar" }) {
  const router = useRouter();
  const { definirConta } = useSessao();
  const cadastro = modo === "cadastrar";
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [provedores, setProvedores] = useState<Provedor[]>([]);

  // Erro do login social vem na URL (?erro=…). Lido sem efeito: no servidor não há URL (null).
  const codigoUrl = useSyncExternalStore(
    semAssinatura,
    () => new URLSearchParams(window.location.search).get("erro"),
    () => null,
  );
  const [tentouDeNovo, setTentouDeNovo] = useState(false);
  const erroSocial =
    codigoUrl && !tentouDeNovo ? (ERRO_SOCIAL[codigoUrl] ?? ERRO_SOCIAL.oauth_falhou) : null;
  const erroVisivel = erro ?? erroSocial;

  useEffect(() => {
    let vivo = true;
    api<{ provedores?: unknown }>("/auth/provedores")
      .then((r) => {
        const lista = Array.isArray(r?.provedores) ? r.provedores : [];
        if (vivo) setProvedores(lista.filter((p): p is Provedor => p in NOME_PROVEDOR));
      })
      .catch(() => {}); // sem a lista, só some o login social; e-mail e senha seguem
    return () => {
      vivo = false;
    };
  }, []);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (enviando) return;
    setEnviando(true);
    setErro(null);
    setTentouDeNovo(true);
    try {
      const conta = await api<Conta>(cadastro ? "/auth/cadastro" : "/auth/login", {
        metodo: "POST",
        corpo: cadastro ? { nome, email, senha } : { email, senha },
      });
      definirConta(conta);
      router.push("/conversa");
    } catch (x) {
      setErro(mensagemDoErro(x));
      setEnviando(false);
    }
  }

  const rotuloBotao = cadastro ? "Criar conta" : "Entrar";
  return (
    // method="post": se o envio acontecer antes da hidratação, a senha não vai para a URL (GET).
    <form
      method="post"
      onSubmit={enviar}
      className="flex w-full flex-col gap-5"
      noValidate={false}
    >
      {cadastro && (
        <Campo id="nome" rotulo="Nome" valor={nome} aoMudar={setNome} autoComplete="name" />
      )}
      <Campo
        id="email"
        rotulo="E-mail"
        tipo="email"
        valor={email}
        aoMudar={setEmail}
        autoComplete="email"
      />
      <Campo
        id="senha"
        rotulo="Senha"
        tipo="password"
        valor={senha}
        aoMudar={setSenha}
        autoComplete={cadastro ? "new-password" : "current-password"}
        minLength={cadastro ? SENHA_MIN : undefined}
        ajuda={cadastro ? `Pelo menos ${SENHA_MIN} caracteres.` : undefined}
      />
      {erroVisivel && <Aviso tipo="erro">{erroVisivel}</Aviso>}
      <Botao type="submit" variante="primaria" disabled={enviando} className="w-full">
        {enviando ? (cadastro ? "Criando…" : "Entrando…") : rotuloBotao}
      </Botao>
      {provedores.length > 0 && <EntrarCom provedores={provedores} />}
      <p className="rodape-auth text-texto-suave">
        {cadastro ? "Já tem conta? " : "Ainda não tem conta? "}
        <Link href={cadastro ? "/entrar" : "/cadastrar"} className="font-semibold text-rosa underline">
          {cadastro ? "Entrar" : "Criar conta"}
        </Link>
      </p>
    </form>
  );
}

const semAssinatura = () => () => {};

/** Divisor "ou entre com" e um botão por provedor, como pílulas de vidro lado a lado (um só
 * provedor ocupa a largura toda). São links comuns (GET): a API redireciona para o provedor e,
 * na volta, abre a sessão e manda para /conversa. Ao clicar, o botão diz que está abrindo e os
 * outros travam, para não haver dois redirecionamentos disputando o mesmo cookie de tentativa. */
function EntrarCom({ provedores }: { provedores: Provedor[] }) {
  const [indo, setIndo] = useState<Provedor | null>(null);

  // Voltar do provedor pelo botão "voltar" restaura a página do cache (bfcache) com o estado
  // antigo: destrava os botões.
  useEffect(() => {
    const destravar = (e: PageTransitionEvent) => e.persisted && setIndo(null);
    window.addEventListener("pageshow", destravar);
    return () => window.removeEventListener("pageshow", destravar);
  }, []);

  const sozinho = provedores.length === 1;
  return (
    <div className="entra flex flex-col gap-4">
      <div className="divisor-ou" aria-hidden="true">
        ou entre com
      </div>
      <ul
        aria-label="Outras formas de entrar"
        className={`grid gap-3 ${sozinho ? "grid-cols-1" : "grid-cols-1 min-[380px]:grid-cols-2"}`}
      >
        {provedores.map((p) => {
          const nome = NOME_PROVEDOR[p];
          const abrindo = indo === p;
          const travado = indo !== null && !abrindo;
          return (
            <li key={p} className="flex">
              <a
                href={`/api/auth/oauth/${p}/iniciar`}
                className={classesBotao("secundaria", "botao-provedor w-full")}
                aria-label={`Entrar com ${nome}`}
                aria-busy={abrindo || undefined}
                aria-disabled={travado || undefined}
                tabIndex={travado ? -1 : undefined}
                onClick={(e) => {
                  if (indo) {
                    e.preventDefault();
                    return;
                  }
                  setIndo(p);
                }}
              >
                <MarcaProvedor provedor={p} />
                <span>
                  {abrindo
                    ? `Abrindo o ${nome}…`
                    : sozinho
                      ? `Continuar com ${nome}`
                      : nome}
                </span>
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Logo oficial do provedor, se estiver em `public/marcas/{google,microsoft}.svg`. As diretrizes
 * de marca do Google e da Microsoft pedem os arquivos deles, sem redesenho: baixe-os das páginas
 * de marca e coloque nessa pasta. Sem o arquivo, o botão fica só com o nome. */
function MarcaProvedor({ provedor }: { provedor: Provedor }) {
  const [falhou, setFalhou] = useState(false);
  if (falhou) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- SVG local de 18 px; next/image não ajuda
    <img
      src={`/marcas/${provedor}.svg`}
      alt=""
      width={18}
      height={18}
      className="botao-provedor-marca"
      onError={() => setFalhou(true)}
    />
  );
}

function Campo(p: {
  id: string;
  rotulo: string;
  valor: string;
  aoMudar: (v: string) => void;
  tipo?: string;
  autoComplete?: string;
  minLength?: number;
  ajuda?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={p.id} className="font-semibold">
        {p.rotulo}
      </label>
      <input
        id={p.id}
        name={p.id}
        type={p.tipo ?? "text"}
        required
        value={p.valor}
        onChange={(e) => p.aoMudar(e.target.value)}
        autoComplete={p.autoComplete}
        minLength={p.minLength}
        aria-describedby={p.ajuda ? `${p.id}-ajuda` : undefined}
        className="campo"
      />
      {p.ajuda && (
        <span id={`${p.id}-ajuda`} className="text-sm text-texto-suave">
          {p.ajuda}
        </span>
      )}
    </div>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { api, ErroApi, mensagemDoErro, postarSSE } from "@/lib/api";
import type { EventoSSE } from "@/lib/api";
import type { MensagemHistorico, Proposta } from "@/lib/tipos";
import { useSessao } from "./SessaoProvider";

const CHAVE = "leia:conversa";
const MAX_CARACTERES = 2000;

type Msg = {
  chave: string;
  papel: "usuario" | "assistente";
  texto: string;
  ferramenta: string | null;
  propostas: Proposta[];
  nota: string | null;
};

const ROTULO_FERRAMENTA: Record<string, string> = {
  buscar_livros: "Buscando no acervo…",
  detalhar_livro: "Lendo a ficha do livro…",
  verificar_disponibilidade: "Vendo a disponibilidade…",
  minhas_locacoes: "Consultando sua estante…",
  locar: "Preparando a locação…",
  renovar: "Preparando a renovação…",
  devolver: "Preparando a devolução…",
  reservar: "Preparando a reserva…",
};

function guardado(): number | null {
  try {
    const v = sessionStorage.getItem(CHAVE);
    return v ? Number(v) : null;
  } catch {
    return null;
  }
}

function guardar(id: number) {
  try {
    sessionStorage.setItem(CHAVE, String(id));
  } catch {
    // sem armazenamento: a conversa só não sobrevive ao recarregar
  }
}

let contador = 0;
const nova = (papel: Msg["papel"], texto = ""): Msg => ({
  chave: `m${++contador}`,
  papel,
  texto,
  ferramenta: null,
  propostas: [],
  nota: null,
});

export function Conversa() {
  const { conta, carregando } = useSessao();
  const logado = !!conta;
  const [conversaId, setConversaId] = useState<number | null>(null);
  const [mensagens, setMensagens] = useState<Msg[]>([]);
  const [texto, setTexto] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [pronto, setPronto] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const fim = useRef<HTMLDivElement>(null);
  const controle = useRef<AbortController | null>(null);

  const comecar = useCallback(async () => {
    const { id } = await api<{ id: number }>("/conversas", { metodo: "POST" });
    guardar(id);
    setConversaId(id);
    setMensagens([]);
  }, []);

  useEffect(() => {
    if (carregando || !logado) return;
    let vivo = true;
    (async () => {
      try {
        const anterior = guardado();
        if (anterior) {
          try {
            const h = await api<MensagemHistorico[]>(`/conversas/${anterior}/mensagens`);
            if (!vivo) return;
            setConversaId(anterior);
            setMensagens(
              h.map((m) => nova(m.papel === "usuario" ? "usuario" : "assistente", m.conteudo)),
            );
            return;
          } catch (e) {
            if (!(e instanceof ErroApi && e.status === 404)) throw e;
          }
        }
        await comecar();
      } catch (e) {
        if (vivo) setErro(mensagemDoErro(e));
      } finally {
        if (vivo) setPronto(true);
      }
    })();
    return () => {
      vivo = false;
      controle.current?.abort();
    };
  }, [carregando, logado, comecar]);

  useEffect(() => {
    fim.current?.scrollIntoView?.({ block: "end" });
  }, [mensagens]);

  function alterar(chave: string, f: (m: Msg) => Msg) {
    setMensagens((ms) => ms.map((m) => (m.chave === chave ? f(m) : m)));
  }

  function aplicar(chave: string, e: EventoSSE) {
    const d = (e.dados ?? {}) as Record<string, unknown>;
    switch (e.evento) {
      case "ferramenta":
        alterar(chave, (m) => ({
          ...m,
          ferramenta: ROTULO_FERRAMENTA[String(d.nome)] ?? "Consultando o acervo…",
        }));
        break;
      case "resposta":
        alterar(chave, (m) => ({ ...m, ferramenta: null, texto: m.texto + String(d.texto ?? "") }));
        break;
      case "propostas":
        alterar(chave, (m) => ({ ...m, propostas: (d.propostas as Proposta[]) ?? [] }));
        break;
      case "acao":
        if (d.ok === false) {
          alterar(chave, (m) => ({ ...m, nota: "Não foi possível concluir essa ação." }));
        }
        break;
      case "fim":
        alterar(chave, (m) => ({
          ...m,
          ferramenta: null,
          nota:
            d.erro && !m.texto
              ? "A Léia teve um problema para responder. Tente de novo."
              : m.nota,
        }));
        break;
    }
  }

  async function transmitir(caminho: string, corpo: unknown, aoFalhar?: () => void) {
    const resposta = nova("assistente");
    setMensagens((ms) => [...ms, resposta]);
    setOcupado(true);
    setErro(null);
    const ctl = new AbortController();
    controle.current = ctl;
    try {
      await postarSSE(caminho, corpo, (e) => aplicar(resposta.chave, e), ctl.signal);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setErro(mensagemDoErro(e));
      setMensagens((ms) => ms.filter((m) => m.chave !== resposta.chave || m.texto !== ""));
      aoFalhar?.();
    } finally {
      setOcupado(false);
    }
  }

  async function enviar(e?: FormEvent) {
    e?.preventDefault();
    const t = texto.trim();
    if (!t || ocupado || conversaId === null) return;
    setTexto("");
    // uma nova fala do leitor invalida as propostas abertas no servidor: tira os botões
    setMensagens((ms) => [...ms.map((m) => ({ ...m, propostas: [] })), nova("usuario", t)]);
    await transmitir(`/conversas/${conversaId}/mensagens`, { texto: t }, () => setTexto(t));
  }

  async function decidir(chaveMsg: string, p: Proposta, decisao: "confirmar" | "cancelar") {
    if (ocupado || conversaId === null) return;
    alterar(chaveMsg, (m) => ({
      ...m,
      propostas: m.propostas.filter((x) => x.confirmacao_id !== p.confirmacao_id),
    }));
    await transmitir(`/conversas/${conversaId}/confirmacoes/${p.confirmacao_id}`, { decisao });
  }

  async function reiniciar() {
    controle.current?.abort();
    setErro(null);
    try {
      await comecar();
    } catch (e) {
      setErro(mensagemDoErro(e));
    }
  }

  function aoTeclar(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void enviar();
    }
  }

  if (!carregando && !logado) {
    return (
      <section className="medida flex flex-col gap-4">
        <h1 className="text-3xl font-semibold">Converse com a Léia</h1>
        <p className="text-tinta-suave">Entre na sua conta para conversar e fazer locações.</p>
        <div className="flex gap-4">
          <Link href="/entrar" className="text-lombada underline">
            Entrar
          </Link>
          <Link href="/cadastrar" className="text-lombada underline">
            Criar conta
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="medida mx-auto flex w-full flex-col gap-4">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-3xl font-semibold">Converse com a Léia</h1>
        <button
          type="button"
          onClick={reiniciar}
          disabled={ocupado}
          className="text-lombada underline disabled:opacity-60"
        >
          Nova conversa
        </button>
      </div>

      <ol
        aria-label="Conversa"
        aria-live="polite"
        className="flex min-h-[40vh] flex-col gap-4 border-y border-linha py-4"
      >
        {pronto && mensagens.length === 0 && (
          <li className="text-tinta-suave">
            Conte o que você quer ler. Por exemplo: “um romance curto sobre memória” ou “poesia
            brasileira do século XX”.
          </li>
        )}
        {mensagens.map((m) => (
          <li
            key={m.chave}
            className={m.papel === "usuario" ? "flex justify-end" : "flex justify-start"}
          >
            <div
              className={
                m.papel === "usuario"
                  ? "max-w-[85%] rounded-lg bg-papel-2 px-4 py-2"
                  : "w-full max-w-[95%]"
              }
            >
              <span className="sr-only">{m.papel === "usuario" ? "Você: " : "Léia: "}</span>
              {m.texto && <p className="whitespace-pre-wrap">{m.texto}</p>}
              {!m.texto && m.papel === "assistente" && ocupado && !m.nota && (
                <p className="text-tinta-suave">{m.ferramenta ?? "Pensando…"}</p>
              )}
              {m.texto && m.ferramenta && <p className="text-tinta-suave">{m.ferramenta}</p>}
              {m.nota && <p className="mt-1 text-alerta">{m.nota}</p>}
              {m.propostas.map((p) => (
                <div
                  key={p.confirmacao_id}
                  role="group"
                  aria-label="Confirmação"
                  className="mt-3 flex flex-col gap-3 border-l-4 border-lombada pl-4"
                >
                  <p id={`prop-${p.confirmacao_id}`} className="font-medium">
                    {p.resumo}
                  </p>
                  <div className="flex gap-3">
                    <button
                      type="button"
                      disabled={ocupado}
                      aria-describedby={`prop-${p.confirmacao_id}`}
                      onClick={() => decidir(m.chave, p, "confirmar")}
                      className="transicao rounded-md bg-lombada px-4 py-2 font-medium text-lombada-texto hover:opacity-90 disabled:opacity-60"
                    >
                      Confirmar
                    </button>
                    <button
                      type="button"
                      disabled={ocupado}
                      aria-describedby={`prop-${p.confirmacao_id}`}
                      onClick={() => decidir(m.chave, p, "cancelar")}
                      className="transicao rounded-md border border-linha px-4 py-2 hover:bg-papel-2 disabled:opacity-60"
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </li>
        ))}
        <div ref={fim} />
      </ol>

      {erro && (
        <p role="alert" className="border-l-4 border-alerta pl-3 text-alerta">
          {erro}
        </p>
      )}

      <form onSubmit={enviar} className="flex flex-col gap-2">
        <label htmlFor="mensagem" className="font-medium">
          Mensagem para a Léia
        </label>
        <textarea
          id="mensagem"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={aoTeclar}
          rows={2}
          maxLength={MAX_CARACTERES}
          className="rounded-md border border-linha bg-papel-2 px-3 py-2.5"
        />
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm text-tinta-suave">Enter envia; Shift+Enter quebra a linha.</span>
          <button
            type="submit"
            disabled={ocupado || conversaId === null}
            className="transicao rounded-md bg-lombada px-5 py-2.5 font-medium text-lombada-texto hover:opacity-90 disabled:opacity-60"
          >
            Enviar
          </button>
        </div>
      </form>
    </section>
  );
}

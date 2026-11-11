"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { api, ErroApi, mensagemDoErro, postarSSE } from "@/lib/api";
import type { EventoSSE } from "@/lib/api";
import type { LivroDoChat, MensagemHistorico, Proposta } from "@/lib/tipos";
import { CartaoLivroChat } from "./CartaoLivroChat";
import { useSessao } from "./SessaoProvider";

const CHAVE = "leia:conversa";
const MAX_CARACTERES = 2000;

// Perguntas que o acervo sabe responder; cobrem busca, tema e dúvida sobre o que o leitor já tem.
const SUGESTOES = [
  "Quero um romance curto para o fim de semana",
  "Me indique um livro sobre o sentido da vida",
  "Tem poesia brasileira disponível agora?",
  "O que eu tenho locado e quando devolvo?",
];

type Msg = {
  chave: string;
  papel: "usuario" | "assistente";
  texto: string;
  ferramenta: string | null;
  propostas: Proposta[];
  livros: LivroDoChat[];
  // a Léia já propôs uma ação nesta mensagem: o cartão não oferece outro caminho de locação
  teveProposta: boolean;
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

// Andamento depois das ferramentas. O texto só chega validado pelo grounding, então o leitor vê
// a etapa em vez de uma resposta que ainda pode ser refeita.
const ROTULO_ETAPA: Record<string, string> = {
  escrevendo: "Escrevendo a resposta…",
  revisando: "Conferindo os livros no acervo…",
};

/** Aviso de andamento: os pontos são decorativos; quem anuncia é o `role="status"` da conversa. */
function Andamento({ rotulo }: { rotulo: string }) {
  return (
    <p className="flex items-center gap-2 text-tinta-suave">
      <span aria-hidden="true" className="inline-flex gap-1">
        <span className="andamento-ponto" />
        <span className="andamento-ponto" />
        <span className="andamento-ponto" />
      </span>
      <span>{rotulo}</span>
    </p>
  );
}

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
  livros: [],
  teveProposta: false,
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
  // Trava síncrona: `ocupado` é estado e só muda no próximo render, então dois envios no mesmo
  // quadro (Enter duplo, clique duplo) passariam os dois pela checagem.
  const enviando = useRef(false);
  // Abertura da conversa em andamento: o efeito pode rodar duas vezes (StrictMode) e não deve
  // criar duas conversas.
  const abertura = useRef<Promise<{ id: number; historico: MensagemHistorico[] }> | null>(null);
  // A abertura já foi aplicada na tela. Com `cacheComponents`, o Next guarda a rota num <Activity>:
  // ao voltar (ex.: da ficha do livro) o efeito roda de novo com o estado preservado, e reaplicar
  // o histórico de quando a conversa abriu apagaria o que foi conversado depois.
  const aberta = useRef(false);

  const comecar = useCallback(async () => {
    const { id } = await api<{ id: number }>("/conversas", { metodo: "POST" });
    guardar(id);
    setConversaId(id);
    setMensagens([]);
  }, []);

  useEffect(() => {
    if (carregando) return;
    if (!logado) {
      abertura.current = null; // outra conta não herda a conversa aberta
      aberta.current = false;
      return;
    }
    let vivo = true;
    abertura.current ??= (async () => {
      const anterior = guardado();
      if (anterior) {
        try {
          const historico = await api<MensagemHistorico[]>(`/conversas/${anterior}/mensagens`);
          return { id: anterior, historico };
        } catch (e) {
          if (!(e instanceof ErroApi && e.status === 404)) throw e;
        }
      }
      const { id } = await api<{ id: number }>("/conversas", { metodo: "POST" });
      guardar(id);
      return { id, historico: [] };
    })();
    abertura.current
      .then(({ id, historico }) => {
        if (!vivo || aberta.current) return;
        aberta.current = true;
        setConversaId(id);
        setMensagens(
          historico.map((m) => nova(m.papel === "usuario" ? "usuario" : "assistente", m.conteudo)),
        );
      })
      .catch((e) => {
        abertura.current = null; // deixa tentar de novo ao remontar
        if (vivo) setErro(mensagemDoErro(e));
      })
      .finally(() => {
        if (vivo) setPronto(true);
      });
    return () => {
      vivo = false;
      controle.current?.abort();
    };
  }, [carregando, logado]);

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
      case "descartar":
        // a resposta parcial vai ser refeita (grounding) ou trocada pela final: some da tela
        alterar(chave, (m) => ({ ...m, texto: "" }));
        break;
      case "etapa": {
        const rotulo = ROTULO_ETAPA[String(d.etapa)];
        if (rotulo) alterar(chave, (m) => ({ ...m, ferramenta: rotulo }));
        break;
      }
      case "resposta":
        alterar(chave, (m) => ({ ...m, ferramenta: null, texto: m.texto + String(d.texto ?? "") }));
        break;
      case "livros":
        alterar(chave, (m) => ({ ...m, livros: (d.livros as LivroDoChat[]) ?? [] }));
        break;
      case "propostas":
        alterar(chave, (m) => ({
          ...m,
          propostas: (d.propostas as Proposta[]) ?? [],
          teveProposta: true,
        }));
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

  /** Um turno por vez. Devolve se a ação do clique deu certo (evento `acao`), ou false. */
  async function transmitir(
    caminho: string,
    corpo: unknown,
    aoFalhar?: () => void,
  ): Promise<boolean> {
    const resposta = nova("assistente");
    let acaoOk = false;
    setMensagens((ms) => [...ms, resposta]);
    setOcupado(true);
    setErro(null);
    const ctl = new AbortController();
    controle.current = ctl;
    try {
      await postarSSE(
        caminho,
        corpo,
        (e) => {
          if (e.evento === "acao") acaoOk = (e.dados as { ok?: boolean } | undefined)?.ok === true;
          aplicar(resposta.chave, e);
        },
        ctl.signal,
      );
      return acaoOk;
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return acaoOk;
      setErro(mensagemDoErro(e));
      setMensagens((ms) => ms.filter((m) => m.chave !== resposta.chave || m.texto !== ""));
      aoFalhar?.();
      return false;
    } finally {
      enviando.current = false;
      setOcupado(false);
    }
  }

  /** Reserva a vez do turno de forma síncrona; false se já há um turno saindo. */
  function reservarVez(): boolean {
    if (enviando.current || ocupado || conversaId === null) return false;
    enviando.current = true;
    return true;
  }

  async function enviar(e?: FormEvent) {
    e?.preventDefault();
    await enviarTexto(texto);
  }

  async function enviarTexto(bruto: string) {
    const t = bruto.trim();
    if (!t || !reservarVez()) return;
    setTexto("");
    // uma nova fala do leitor invalida as propostas abertas no servidor: tira os botões
    setMensagens((ms) => [...ms.map((m) => ({ ...m, propostas: [] })), nova("usuario", t)]);
    await transmitir(`/conversas/${conversaId}/mensagens`, { texto: t }, () => setTexto(t));
  }

  async function decidir(chaveMsg: string, p: Proposta, decisao: "confirmar" | "cancelar") {
    if (!reservarVez()) return;
    alterar(chaveMsg, (m) => ({
      ...m,
      propostas: m.propostas.filter((x) => x.confirmacao_id !== p.confirmacao_id),
    }));
    await transmitir(`/conversas/${conversaId}/confirmacoes/${p.confirmacao_id}`, { decisao });
  }

  /** Locar/reservar pelo cartão: a ação passa pelo chat e a Léia responde na conversa. */
  async function agirNoCartao(acao: "locar" | "reservar", livroId: number): Promise<boolean> {
    if (!reservarVez()) return false;
    return transmitir(`/conversas/${conversaId}/acoes`, { acao, livro_id: livroId });
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

      <p role="status" className="sr-only">
        {ocupado
          ? "A Léia está respondendo…"
          : mensagens.at(-1)?.papel === "assistente"
            ? "A Léia respondeu."
            : ""}
      </p>

      <ol
        aria-label="Conversa"
        className="flex min-h-[40vh] flex-col gap-4 border-y border-linha py-4"
      >
        {pronto && mensagens.length === 0 && (
          <li className="flex flex-col gap-3 text-tinta-suave">
            <p>Conte o que você quer ler, ou comece por uma destas perguntas:</p>
            <div
              role="group"
              aria-label="Sugestões para começar"
              className="flex flex-col items-start gap-2"
            >
              {SUGESTOES.map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={ocupado || conversaId === null}
                  onClick={() => void enviarTexto(s)}
                  className="transicao rounded-md border border-controle px-3 py-1.5 text-left text-tinta hover:bg-papel-2 disabled:opacity-60"
                >
                  {s}
                </button>
              ))}
            </div>
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
                <Andamento rotulo={m.ferramenta ?? "Pensando…"} />
              )}
              {m.texto && m.ferramenta && <Andamento rotulo={m.ferramenta} />}
              {m.livros.map((l) => (
                <CartaoLivroChat
                  key={l.id}
                  livro={l}
                  comAcao={!m.teveProposta}
                  ocupado={ocupado}
                  aoAgir={agirNoCartao}
                />
              ))}
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
                      className="transicao rounded-md border border-controle px-4 py-2 hover:bg-papel-2 disabled:opacity-60"
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </li>
        ))}
      </ol>
      <div ref={fim} />

      {erro && (
        <p role="alert" className="border-l-4 border-alerta pl-3 text-alerta">
          {erro}
        </p>
      )}

      <form
        onSubmit={enviar}
        className="sticky bottom-0 flex flex-col gap-2 border-t border-linha bg-papel pb-4 pt-3"
      >
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
          className="rounded-md border border-controle bg-papel-2 px-3 py-2.5"
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

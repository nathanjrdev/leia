"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { MouseEvent } from "react";
import { useRouter } from "next/navigation";
import type { Conta } from "@/lib/tipos";
import { useSessao } from "./SessaoProvider";
import { Botao } from "./ui/Botao";
import { IconeFechar, IconeMenuLivros, IconeSair } from "./ui/Icones";

/** Menu da conta: o botão de três livros abre uma gaveta lateral com quem está logado e "Sair".
 *
 * É um `<dialog>` nativo aberto com `showModal()`: Esc fecha, o foco fica preso dentro e volta ao
 * botão ao fechar, e o resto da página fica inerte. Clicar no fundo escurecido também fecha. */
export function MenuConta({ conta }: { conta: Conta }) {
  const { sair } = useSessao();
  const router = useRouter();
  const gaveta = useRef<HTMLDialogElement>(null);
  const [aberta, setAberta] = useState(false);
  const [saindo, setSaindo] = useState(false);
  const idTitulo = useId();
  const idGaveta = useId();

  // O estado manda; o elemento acompanha. Sem `showModal` (navegador antigo, jsdom), cai no
  // atributo `open`, que mostra a gaveta sem o modo modal.
  useEffect(() => {
    const d = gaveta.current;
    if (!d) return;
    if (aberta && !d.open) {
      if (typeof d.showModal === "function") d.showModal();
      else d.setAttribute("open", "");
    } else if (!aberta && d.open) {
      if (typeof d.close === "function") d.close();
      else d.removeAttribute("open");
    }
  }, [aberta]);

  function fecharNoFundo(e: MouseEvent<HTMLDialogElement>) {
    // O próprio <dialog> só recebe o clique quando ele cai no ::backdrop, fora do painel.
    if (e.target === e.currentTarget) setAberta(false);
  }

  async function aoSair() {
    if (saindo) return;
    setSaindo(true);
    try {
      await sair();
      setAberta(false);
      router.push("/");
    } finally {
      setSaindo(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="botao-menu"
        aria-label="Menu da conta"
        aria-haspopup="dialog"
        aria-expanded={aberta}
        aria-controls={idGaveta}
        onClick={() => setAberta(true)}
      >
        <IconeMenu />
      </button>

      <dialog
        ref={gaveta}
        id={idGaveta}
        className="gaveta"
        aria-labelledby={idTitulo}
        onClose={() => setAberta(false)}
        onClick={fecharNoFundo}
      >
        <div className="gaveta-painel">
          <div className="flex items-center justify-between gap-3">
            <h2 id={idTitulo} className="text-xl font-bold tracking-[-0.02em]">
              Sua conta
            </h2>
            <button
              type="button"
              className="botao-menu"
              aria-label="Fechar menu"
              onClick={() => setAberta(false)}
            >
              <IconeFechar />
            </button>
          </div>

          <div className="gaveta-conta">
            <p className="truncate font-semibold">{conta.nome}</p>
            <p className="truncate text-sm text-texto-suave">{conta.email}</p>
          </div>

          <Botao
            variante="secundaria"
            className="mt-auto w-full"
            onClick={aoSair}
            disabled={saindo}
          >
            <IconeSair />
            {saindo ? "Saindo…" : "Sair"}
          </Botao>
        </div>
      </dialog>
    </>
  );
}

/** Os três livros de prata (render do FigCraft, `design/menu-livros.figcraft`, como o chaveiro),
 * em 1x, 2x e 3x. Se a imagem não carregar, volta o desenho de traço da casa. */
function IconeMenu() {
  const [falhou, setFalhou] = useState(false);
  if (falhou) return <IconeMenuLivros className="botao-menu-icone" />;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- ícone de 28 px com srcSet próprio
    <img
      src="/objetos/menu-livros.webp"
      srcSet="/objetos/menu-livros.webp 1x, /objetos/menu-livros@2x.webp 2x, /objetos/menu-livros@3x.webp 3x"
      alt=""
      aria-hidden="true"
      width={28}
      height={28}
      draggable={false}
      className="botao-menu-render"
      onError={() => setFalhou(true)}
    />
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { api, mensagemDoErro } from "@/lib/api";
import type { Conta } from "@/lib/tipos";
import { useSessao } from "./SessaoProvider";
import { Aviso } from "./ui/Aviso";
import { Botao } from "./ui/Botao";

const SENHA_MIN = 8;

export function FormularioAuth({ modo }: { modo: "entrar" | "cadastrar" }) {
  const router = useRouter();
  const { definirConta } = useSessao();
  const cadastro = modo === "cadastrar";
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (enviando) return;
    setEnviando(true);
    setErro(null);
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
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <Botao type="submit" variante="primaria" disabled={enviando} className="w-full">
        {enviando ? (cadastro ? "Criando…" : "Entrando…") : rotuloBotao}
      </Botao>
      <p className="text-texto-suave">
        {cadastro ? "Já tem conta? " : "Ainda não tem conta? "}
        <Link href={cadastro ? "/entrar" : "/cadastrar"} className="font-semibold text-rosa underline">
          {cadastro ? "Entrar" : "Criar conta"}
        </Link>
      </p>
    </form>
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

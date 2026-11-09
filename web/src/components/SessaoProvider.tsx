"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "@/lib/api";
import type { Conta } from "@/lib/tipos";

type Estado = {
  conta: Conta | null;
  carregando: boolean;
  definirConta: (c: Conta | null) => void;
  sair: () => Promise<void>;
};

const Contexto = createContext<Estado | null>(null);

/** Guarda quem está logado. Quem manda é o cookie de sessão; aqui só espelhamos `GET /auth/eu`. */
export function SessaoProvider({ children }: { children: ReactNode }) {
  const [conta, setConta] = useState<Conta | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    let vivo = true;
    api<Conta>("/auth/eu")
      .then((c) => vivo && setConta(c))
      .catch(() => vivo && setConta(null))
      .finally(() => vivo && setCarregando(false));
    return () => {
      vivo = false;
    };
  }, []);

  const sair = useCallback(async () => {
    try {
      await api("/auth/logout", { metodo: "POST" });
    } finally {
      setConta(null);
    }
  }, []);

  const valor = useMemo(
    () => ({ conta, carregando, definirConta: setConta, sair }),
    [conta, carregando, sair],
  );
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useSessao(): Estado {
  const v = useContext(Contexto);
  if (!v) throw new Error("useSessao fora do SessaoProvider");
  return v;
}

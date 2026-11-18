import type { Metadata } from "next";
import Link from "next/link";
import { Secao, TextoLegal } from "@/components/TextoLegal";

export const metadata: Metadata = { title: "Termos de Uso · Léia" };

const CONTATO = "njunioestudos@gmail.com";

export default function Termos() {
  return (
    <TextoLegal titulo="Termos de Uso" atualizadaEm="18 de novembro de 2026">
      <p>
        Ao usar a Léia (leiabiblioteca.tech), você concorda com estes termos. São curtos de
        propósito.
      </p>

      <Secao titulo="O serviço">
        <p>
          A Léia é um projeto pessoal, oferecido como está e sem garantia de disponibilidade. Ela
          pode ficar fora do ar, mudar ou deixar de existir.
        </p>
      </Secao>

      <Secao titulo="Respostas da inteligência artificial">
        <p>
          A Léia usa um modelo de linguagem para conversar. Ela só cita livros do acervo e só loca,
          renova, devolve ou reserva depois que você confirma, mas pode se enganar no resto. Confira
          o que for importante.
        </p>
      </Secao>

      <Secao titulo="Sua conta">
        <p>
          Use dados verdadeiros e cuide do acesso à sua conta. Você responde pelo que é feito com
          ela.
        </p>
      </Secao>

      <Secao titulo="O que não é permitido">
        <ul>
          <li>Tentar acessar dados de outras pessoas ou burlar as regras de locação.</li>
          <li>Sobrecarregar o serviço, automatizar acessos em massa ou tentar invadi-lo.</li>
          <li>Usar a conversa para conteúdo ilegal ou para assediar alguém.</li>
        </ul>
        <p>Contas que fizerem isso podem ser suspensas.</p>
      </Secao>

      <Secao titulo="Privacidade">
        <p>
          O que guardamos e por quê está na <Link href="/privacidade">Política de Privacidade</Link>.
        </p>
      </Secao>

      <Secao titulo="Lei e contato">
        <p>
          Valem as leis do Brasil. Dúvidas: <a href={`mailto:${CONTATO}`}>{CONTATO}</a>.
        </p>
      </Secao>
    </TextoLegal>
  );
}

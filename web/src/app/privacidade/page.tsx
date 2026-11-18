import type { Metadata } from "next";
import Link from "next/link";
import { Secao, TextoLegal } from "@/components/TextoLegal";

export const metadata: Metadata = { title: "Política de Privacidade · Léia" };

const CONTATO = "njunioestudos@gmail.com";

export default function Privacidade() {
  return (
    <TextoLegal titulo="Política de Privacidade" atualizadaEm="18 de novembro de 2026">
      <p>
        A Léia (leiabiblioteca.tech) é uma bibliotecária virtual: você conversa com ela para achar,
        reservar e locar livros do acervo. É um projeto pessoal mantido por Nathan Junio. Esta página
        explica quais dados a Léia guarda, para quê e o que você pode pedir sobre eles.
      </p>

      <Secao titulo="O que guardamos">
        <ul>
          <li>
            <strong>Sua conta:</strong> nome e e-mail. Se você cria a conta com senha, guardamos só
            uma versão embaralhada dela (hash scrypt), nunca a senha em si.
          </li>
          <li>
            <strong>Entrar com Google ou Microsoft:</strong> recebemos do provedor seu nome, seu
            e-mail e um identificador da sua conta lá. Pedimos só o básico (openid, email e profile):
            a Léia não recebe sua senha do Google ou da Microsoft nem acesso a e-mails, arquivos ou
            contatos.
          </li>
          <li>
            <strong>Sessão:</strong> um cookie mantém você logado por até 7 dias. No banco fica só
            uma versão embaralhada do código do cookie.
          </li>
          <li>
            <strong>Uso da biblioteca:</strong> suas locações, renovações, devoluções, reservas e as
            avaliações que você escreve sobre livros.
          </li>
          <li>
            <strong>Conversas:</strong> as mensagens que você troca com a Léia e as consultas que
            ela faz ao acervo para responder, para manter o contexto da conversa.
          </li>
        </ul>
      </Secao>

      <Secao titulo="Para que usamos">
        <p>
          Para manter sua conta, registrar locações e reservas e responder às suas conversas. Não
          vendemos seus dados, não os usamos para publicidade e não montamos perfis para terceiros.
        </p>
      </Secao>

      <Secao titulo="Com quem compartilhamos">
        <ul>
          <li>
            <strong>Provedor de inteligência artificial:</strong> para a Léia responder, o texto da
            conversa é enviado ao provedor do modelo de linguagem configurado no serviço. Evite
            escrever dados sensíveis (documentos, saúde, senhas) nas conversas.
          </li>
          <li>
            <strong>Hospedagem:</strong> o servidor onde a Léia roda guarda o banco de dados.
          </li>
          <li>
            <strong>Google e Microsoft:</strong> só quando você escolhe entrar com eles, e só para
            confirmar quem você é.
          </li>
        </ul>
      </Secao>

      <Secao titulo="Cookies">
        <p>
          Só os necessários para funcionar: o cookie da sessão e, durante a entrada com Google ou
          Microsoft, um cookie temporário de 10 minutos que protege o login. A aba do navegador também
          lembra qual conversa está aberta. Não usamos cookies de análise nem de publicidade.
        </p>
      </Secao>

      <Secao titulo="Por quanto tempo">
        <p>
          Os dados da conta ficam enquanto ela existir. Sessões expiram em até 7 dias ou quando você
          sai. Se você pedir a exclusão da conta, apagamos os dados ligados a ela.
        </p>
      </Secao>

      <Secao titulo="Seus direitos">
        <p>
          Pela Lei Geral de Proteção de Dados (LGPD), você pode pedir para ver, corrigir ou apagar
          seus dados, e saber com quem eles foram compartilhados. Escreva para{" "}
          <a href={`mailto:${CONTATO}`}>{CONTATO}</a> com o e-mail da sua conta.
        </p>
      </Secao>

      <Secao titulo="Segurança">
        <p>
          O acesso é sempre por HTTPS, senhas e códigos de sessão ficam só em versão embaralhada e
          cada pessoa só vê as próprias locações, reservas e conversas.
        </p>
      </Secao>

      <Secao titulo="Mudanças e contato">
        <p>
          Se esta política mudar, a data no topo muda junto. Dúvidas:{" "}
          <a href={`mailto:${CONTATO}`}>{CONTATO}</a>. Veja também os{" "}
          <Link href="/termos">Termos de Uso</Link>.
        </p>
      </Secao>
    </TextoLegal>
  );
}

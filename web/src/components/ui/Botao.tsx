import type { ButtonHTMLAttributes } from "react";

export type VarianteBotao = "primaria" | "secundaria" | "texto";

/** Classes do botão, para usar também em `<Link>` com cara de botão. Estilos em globals.css. */
export function classesBotao(variante: VarianteBotao = "secundaria", extra = ""): string {
  return `botao botao-${variante}${extra ? ` ${extra}` : ""}`;
}

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variante?: VarianteBotao };

/** Botão da casa: pílula rosa (primária), pílula de vidro (secundária) ou texto sublinhado. */
export function Botao({ variante = "secundaria", className = "", type = "button", ...resto }: Props) {
  return <button type={type} className={classesBotao(variante, className)} {...resto} />;
}

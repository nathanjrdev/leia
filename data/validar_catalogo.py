"""Valida data/catalogo.json antes de carregar no banco.

Uso: python data/validar_catalogo.py [caminho]
Sai com código 1 se houver erro; avisos não bloqueiam.
"""

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).parent
CAMPOS = {
    "titulo",
    "autores",
    "ano",
    "paginas",
    "editora",
    "isbn",
    "capa_url",
    "sinopse",
    "sinopse_fonte",
    "categorias",
}
SINOPSE_MIN = 150


def _exclusoes() -> set[str]:
    """Pares 'título | autor' de excluidos.txt (minúsculos), sem os comentários."""
    arquivo = RAIZ / "excluidos.txt"
    if not arquivo.exists():
        return set()
    linhas = [linha.split("#")[0].strip() for linha in arquivo.read_text("utf-8").splitlines()]
    return {linha.lower() for linha in linhas if linha}


def validar(livros: list[dict]) -> tuple[list[str], list[str]]:
    erros: list[str] = []
    avisos: list[str] = []
    excluidos = _exclusoes()
    chaves = Counter((livro.get("titulo"), (livro.get("autores") or [None])[0]) for livro in livros)
    isbns = Counter(livro["isbn"] for livro in livros if livro.get("isbn"))

    for livro in livros:
        nome = str(livro.get("titulo", "?"))
        faltam = CAMPOS - livro.keys()
        if faltam:
            erros.append(f"{nome}: faltam campos {sorted(faltam)}")
            continue
        if not livro["autores"]:
            erros.append(f"{nome}: sem autores")
            continue
        if chaves[(livro["titulo"], livro["autores"][0])] > 1:
            erros.append(f"{nome}: duplicado (mesmo título e primeiro autor)")
        if livro["isbn"]:
            if not re.fullmatch(r"\d{10}|\d{13}", livro["isbn"]):
                erros.append(f"{nome}: ISBN fora do formato ({livro['isbn']})")
            if isbns[livro["isbn"]] > 1:
                erros.append(f"{nome}: ISBN repetido ({livro['isbn']})")
        for texto in [livro["titulo"], *livro["autores"]]:
            if texto != unicodedata.normalize("NFC", texto):
                erros.append(f"{nome}: texto fora de NFC ({texto!r})")
        for campo in ("titulo", "editora", "sinopse"):
            valor = livro[campo]
            if valor and (valor != valor.strip() or "  " in valor):
                erros.append(f"{nome}: espaços sobrando em {campo}")
        if "�" in json.dumps(livro, ensure_ascii=False):
            erros.append(f"{nome}: caractere inválido U+FFFD (arquivo salvo em outra codificação?)")
        if not livro["sinopse"]:
            erros.append(f"{nome}: sinopse vazia")
        elif len(livro["sinopse"]) < SINOPSE_MIN:
            avisos.append(f"{nome}: sinopse curta ({len(livro['sinopse'])} caracteres)")
        if not livro["sinopse_fonte"]:
            erros.append(f"{nome}: sem sinopse_fonte (atribuição)")
        if not livro["categorias"]:
            erros.append(f"{nome}: sem categorias")
        if livro["ano"] is None:
            avisos.append(f"{nome}: sem ano")
        elif not isinstance(livro["ano"], int) or livro["ano"] > 2026:
            erros.append(f"{nome}: ano inválido ({livro['ano']!r})")
        if livro["paginas"] is not None and not 10 <= livro["paginas"] <= 3000:
            avisos.append(f"{nome}: páginas improváveis ({livro['paginas']})")
        if not livro["isbn"]:
            avisos.append(f"{nome}: sem ISBN (renomear o título criaria um livro duplicado)")
        if not livro["capa_url"]:
            avisos.append(f"{nome}: sem capa")
        if f"{livro['titulo']} | {livro['autores'][0]}".lower() in excluidos:
            erros.append(f"{nome}: está em data/excluidos.txt")
    return erros, avisos


def main() -> int:
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "catalogo.json"
    livros = json.loads(caminho.read_text(encoding="utf-8"))
    erros, avisos = validar(livros)
    categorias = Counter(c for livro in livros for c in livro.get("categorias", []))
    print(f"{len(livros)} livros, {len(categorias)} categorias.")
    print("Categorias:", ", ".join(f"{c} ({n})" for c, n in categorias.most_common()))
    for aviso in avisos:
        print(f"AVISO {aviso}")
    for erro in erros:
        print(f"ERRO  {erro}")
    print(f"{len(erros)} erro(s), {len(avisos)} aviso(s).")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())

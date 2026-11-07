"""Coleta o catálogo de semente e grava data/catalogo.json.

Fontes: Open Library (metadados e sinopse) e, como fallback de sinopse, a
Wikipedia em português (CC BY-SA; a atribuição fica em `sinopse_fonte`).
Livros sem sinopse validada são descartados: nada é inventado.

Uso: python data/fetch_catalog.py [--por-autor 8] [--max-tentativas 30]
As respostas HTTP ficam em data/.cache, então reexecutar é barato.
"""

import argparse
import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
CACHE = ROOT / ".cache"
UA = {"User-Agent": "leia-portfolio/0.1 (projeto de portfolio; github.com/nathanjrdev/leia)"}
PAUSA = 0.35
OL = "https://openlibrary.org"
WIKI = "https://pt.wikipedia.org"

CATEGORIAS = [
    (r"poetry|poesia|poems", "Poesia"),
    (r"short stories|contos|short story", "Contos"),
    (r"drama|plays|teatro", "Teatro"),
    (r"children|infantil|juvenile", "Infantojuvenil"),
    (r"history|histor", "História"),
    (r"essay|ensaio|criticism", "Ensaios"),
    (r"biograph|memoir|autobiograph", "Biografia e memórias"),
    (r"science fiction|fantasy|fantasia", "Ficção científica e fantasia"),
    (r"detective|mystery|crime|thriller", "Policial e suspense"),
    (r"romance|love", "Romance"),
    (r"fiction|ficção|novel|romance", "Ficção"),
]


def norm(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto)
    return re.sub(r"[^a-z0-9 ]", "", base.encode("ascii", "ignore").decode().lower()).strip()


def get_json(url: str) -> dict | None:
    CACHE.mkdir(exist_ok=True)
    arquivo = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".json")
    if arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    for tentativa in range(3):
        try:
            time.sleep(PAUSA)
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                dados = json.load(r)
            arquivo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            return dados
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (tentativa + 1))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(2 * (tentativa + 1))
    return None


PALAVRAS_EN = {"the", "of", "and", "in", "to", "with", "from", "his", "her", "for", "is", "was"}
PALAVRAS_PT = {"o", "a", "os", "as", "de", "do", "da", "e", "que", "em", "um", "uma", "com", "para"}
PALAVRAS_OBRA = re.compile(
    r"\b(romance|livro|obra|novela|conto|contos|poema|poemas|peça|coletânea|ensaio|crônica|"
    r"autobiografia|antologia|epopeia|tragédia|comédia|drama|poesia)\b"
)
BIOGRAFIA = re.compile(r"\b(foi um|foi uma|é um|é uma) (escritor|escritora|poeta|poetisa|autor|autora)")


def parece_ingles(texto: str) -> bool:
    palavras = re.findall(r"[a-zà-ú]+", texto.lower())
    en = sum(p in PALAVRAS_EN for p in palavras)
    pt = sum(p in PALAVRAS_PT for p in palavras)
    return en > pt


def titulo_em_ingles(titulo: str) -> bool:
    return any(p in PALAVRAS_EN for p in re.findall(r"[a-z]+", titulo.lower()))


def limpar_sinopse(texto: str) -> str:
    texto = texto.split("\n----------")[0]
    texto = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", texto)
    texto = re.sub(r"\[\d+\]:.*", "", texto)
    texto = re.sub(r"[*_]{1,3}", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


def sinopse_openlibrary(chave: str) -> str | None:
    obra = get_json(f"{OL}{chave}.json")
    if not obra:
        return None
    desc = obra.get("description")
    desc = desc.get("value") if isinstance(desc, dict) else desc
    desc = limpar_sinopse(desc) if isinstance(desc, str) else ""
    return desc if len(desc) >= 80 and not parece_ingles(desc) else None


def sinopse_wikipedia(titulo: str, autor: str) -> tuple[str, str] | None:
    consulta = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": f'"{titulo}" {autor} livro',
            "srlimit": 1,
            "format": "json",
        }
    )
    achados = (get_json(f"{WIKI}/w/api.php?{consulta}") or {}).get("query", {}).get("search", [])
    if not achados:
        return None
    pagina = achados[0]["title"]
    resumo = get_json(f"{WIKI}/api/rest_v1/page/summary/{urllib.parse.quote(pagina)}")
    if not resumo or resumo.get("type") == "disambiguation":
        return None
    extrato = limpar_sinopse(resumo.get("extract", ""))
    sobrenome = norm(autor).split()[-1]
    abertura = extrato[:300].lower()
    if (
        len(extrato) < 120
        or sobrenome not in norm(extrato)
        or norm(titulo)[:12] not in norm(pagina + extrato)
        or not PALAVRAS_OBRA.search(abertura)  # precisa descrever uma obra
        or BIOGRAFIA.search(abertura)  # a página é do autor, não do livro
        or norm(extrato).startswith(norm(autor))
        or parece_ingles(extrato)
    ):
        return None
    url = resumo.get("content_urls", {}).get("desktop", {}).get("page", f"{WIKI}/wiki/{pagina}")
    return extrato, f"Wikipedia (CC BY-SA): {url}"


def categorias(assuntos: list[str]) -> list[str]:
    achadas: list[str] = []
    junto = " | ".join(a.lower() for a in assuntos)
    for padrao, nome in CATEGORIAS:
        if re.search(padrao, junto) and nome not in achadas:
            achadas.append(nome)
    return achadas[:3] or ["Literatura"]


def isbn13(isbns: list[str]) -> str | None:
    return next((i for i in isbns if len(i) == 13 and i.startswith("978")), None)


def coletar_autor(autor: str, por_autor: int, max_tentativas: int, vistos: set[str]) -> list[dict]:
    consulta = urllib.parse.urlencode(
        {
            "author": autor,
            "language": "por",
            "limit": max_tentativas,
            "fields": "key,title,author_name,first_publish_year,cover_i,"
            "number_of_pages_median,subject,publisher,isbn",
        }
    )
    docs = (get_json(f"{OL}/search.json?{consulta}") or {}).get("docs", [])
    sobrenome = norm(autor).split()[-1]
    livros: list[dict] = []
    for doc in docs:
        if len(livros) >= por_autor:
            break
        nomes = norm(" ".join(doc.get("author_name", [])))
        titulo = doc["title"].strip()
        chave_titulo = f"{norm(autor)}:{norm(titulo)}"
        if (
            sobrenome not in nomes
            or chave_titulo in vistos
            or not doc.get("cover_i")
            or titulo_em_ingles(titulo)
        ):
            continue
        sinopse, fonte = sinopse_openlibrary(doc["key"]), f"Open Library: {OL}{doc['key']}"
        if not sinopse:
            wiki = sinopse_wikipedia(titulo, autor)
            if not wiki:
                continue
            sinopse, fonte = wiki
        vistos.add(chave_titulo)
        livros.append(
            {
                "titulo": titulo,
                "autores": [autor],
                "ano": doc.get("first_publish_year"),
                "paginas": doc.get("number_of_pages_median"),
                "editora": (doc.get("publisher") or [None])[0],
                "isbn": isbn13(doc.get("isbn", [])),
                "capa_url": f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg",
                "sinopse": sinopse,
                "sinopse_fonte": fonte,
                "categorias": categorias(doc.get("subject", [])),
            }
        )
    return livros


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--por-autor", type=int, default=8)
    ap.add_argument("--max-tentativas", type=int, default=30)
    ap.add_argument("--teto-minutos", type=float, default=None, help="para ao estourar o tempo")
    args = ap.parse_args()
    inicio = time.monotonic()

    autores = [
        linha.strip()
        for linha in (ROOT / "autores.txt").read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.startswith("#")
    ]
    vistos: set[str] = set()
    arquivo_exclusoes = ROOT / "excluidos.txt"
    if arquivo_exclusoes.exists():  # revisão manual: pré-marca como já vistos
        for linha in arquivo_exclusoes.read_text(encoding="utf-8").splitlines():
            if linha.strip() and not linha.startswith("#"):
                titulo, _, resto = linha.partition("|")
                autor = resto.split("#")[0].strip()
                vistos.add(f"{norm(autor)}:{norm(titulo)}")
    catalogo: list[dict] = []
    isbns: set[str] = set()
    for i, autor in enumerate(autores, 1):
        if args.teto_minutos and time.monotonic() - inicio > args.teto_minutos * 60:
            print("Teto de tempo atingido; encerrando com o que foi coletado.", flush=True)
            break
        novos = coletar_autor(autor, args.por_autor, args.max_tentativas, vistos)
        for livro in novos:
            if livro["isbn"] in isbns:
                livro["isbn"] = None
            elif livro["isbn"]:
                isbns.add(livro["isbn"])
        catalogo.extend(novos)
        print(f"[{i}/{len(autores)}] {autor}: {len(novos)} livros (total {len(catalogo)})", flush=True)
        (ROOT / "catalogo.json").write_text(
            json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()

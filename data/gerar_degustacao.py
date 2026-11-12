"""Gera as páginas da degustação (as primeiras ~10 páginas de cada livro da estante da home).

Lê `data/degustacao.json`, abre cada PDF de `data/livros_estante/` e grava só as páginas
escolhidas como JPEG em `web/public/degustacao/<slug>/NN.jpg`, mais o índice
`web/public/degustacao/indice.json` que a web lê. O PDF inteiro nunca vai para o navegador:
o leitor só tem as páginas da degustação.

Uso (na raiz do repositório):
    uv run --with pymupdf python data/gerar_degustacao.py

Idempotente: sobrescreve as páginas de cada livro. Livro cujo PDF não existe é pulado com aviso.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "data" / "degustacao.json"
PDFS = RAIZ / "data" / "livros_estante"
SAIDA = RAIZ / "web" / "public" / "degustacao"
MAX_PAGINAS = 12  # a degustação é curta: capa + ~10 páginas


def slug(titulo: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def gerar_livro(cfg: dict, largura_px: int, qualidade: int) -> dict | None:
    pdf = PDFS / cfg["arquivo"]
    if not pdf.exists():
        print(f"  ! PDF não encontrado, pulando: {pdf.name}", file=sys.stderr)
        return None
    paginas: list[int] = cfg["paginas"]
    if not 1 <= len(paginas) <= MAX_PAGINAS:
        raise SystemExit(f"{cfg['titulo']}: escolha de 1 a {MAX_PAGINAS} páginas")

    destino = SAIDA / slug(cfg["titulo"])
    destino.mkdir(parents=True, exist_ok=True)
    # Sobrescreve as páginas; as que sobraram de uma escolha anterior mais longa saem.
    for velha in destino.glob("*.jpg"):
        if not velha.stem.isdigit() or int(velha.stem) > len(paginas):
            velha.unlink()

    urls: list[str] = []
    largura = altura = 0
    with pymupdf.open(pdf) as doc:
        for n, numero in enumerate(paginas, start=1):
            if not 1 <= numero <= doc.page_count:
                raise SystemExit(f"{cfg['titulo']}: página {numero} fora do PDF ({doc.page_count})")
            pagina = doc[numero - 1]
            escala = largura_px / pagina.rect.width
            pix = pagina.get_pixmap(matrix=pymupdf.Matrix(escala, escala), alpha=False)
            nome = f"{n:02d}.jpg"
            (destino / nome).write_bytes(pix.tobytes("jpeg", jpg_quality=qualidade))
            urls.append(f"/degustacao/{destino.name}/{nome}")
            if n == 2 or (n == 1 and len(paginas) == 1):
                # Proporção do miolo (a capa às vezes tem outro corte).
                largura, altura = pix.width, pix.height
    print(f"  ok {cfg['titulo']}: {len(urls)} páginas")
    return {"titulo": cfg["titulo"], "largura": largura, "altura": altura, "paginas": urls}


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    SAIDA.mkdir(parents=True, exist_ok=True)
    livros = [
        gerado
        for cfg in config["livros"]
        if (gerado := gerar_livro(cfg, config["largura_px"], config["qualidade_jpeg"]))
    ]
    indice = {"versao": 1, "livros": livros}
    (SAIDA / "indice.json").write_text(
        json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{len(livros)} livros em {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()

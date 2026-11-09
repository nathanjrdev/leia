"""Modelos SQLAlchemy do Léia.

Disponibilidade NÃO é coluna: é calculada pela view `disponibilidade_livro`
(ver migração). `exemplares.estado` só diz se o exemplar está em circulação.
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Column as SAColumn
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 768


class Base(DeclarativeBase):
    pass


def _now() -> Any:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


livro_autor = Table(
    "livro_autor",
    Base.metadata,
    SAColumn("livro_id", ForeignKey("livros.id", ondelete="CASCADE"), primary_key=True),
    SAColumn("autor_id", ForeignKey("autores.id", ondelete="CASCADE"), primary_key=True),
)

livro_categoria = Table(
    "livro_categoria",
    Base.metadata,
    SAColumn("livro_id", ForeignKey("livros.id", ondelete="CASCADE"), primary_key=True),
    SAColumn("categoria_id", ForeignKey("categorias.id", ondelete="CASCADE"), primary_key=True),
)


class Autor(Base):
    __tablename__ = "autores"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    biografia: Mapped[str | None] = mapped_column(Text)
    nacionalidade: Mapped[str | None] = mapped_column(String(80))


class Categoria(Base):
    __tablename__ = "categorias"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    categoria_pai_id: Mapped[int | None] = mapped_column(ForeignKey("categorias.id"))


class Livro(Base):
    __tablename__ = "livros"
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(300))
    isbn: Mapped[str | None] = mapped_column(String(20), unique=True)
    sinopse: Mapped[str | None] = mapped_column(Text)
    sinopse_fonte: Mapped[str | None] = mapped_column(Text)  # atribuição (licença da fonte)
    ano: Mapped[int | None]
    editora: Mapped[str | None] = mapped_column(String(160))
    paginas: Mapped[int | None]
    idioma: Mapped[str] = mapped_column(String(10), server_default="pt")
    capa_url: Mapped[str | None] = mapped_column(Text)

    autores: Mapped[list[Autor]] = relationship(secondary=livro_autor)
    categorias: Mapped[list[Categoria]] = relationship(secondary=livro_categoria)


class Exemplar(Base):
    __tablename__ = "exemplares"
    __table_args__ = (
        CheckConstraint("estado IN ('ativo', 'manutencao')", name="ck_exemplares_estado"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    livro_id: Mapped[int] = mapped_column(ForeignKey("livros.id", ondelete="CASCADE"), index=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    estado: Mapped[str] = mapped_column(String(20), server_default="ativo")


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint("papel IN ('leitor', 'admin')", name="ck_usuarios_papel"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    papel: Mapped[str] = mapped_column(String(20), server_default="leitor")
    preferencias: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class Sessao(Base):
    """Sessão de login. O token vai ao navegador em cookie; aqui fica só o SHA-256 dele."""

    __tablename__ = "sessoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    criada_em: Mapped[datetime] = _now()
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Locacao(Base):
    __tablename__ = "locacoes"
    __table_args__ = (
        # Um exemplar tem no máximo uma locação ativa.
        Index(
            "uq_locacao_ativa_por_exemplar",
            "exemplar_id",
            unique=True,
            postgresql_where=text("devolvida_em IS NULL"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    exemplar_id: Mapped[int] = mapped_column(ForeignKey("exemplares.id"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    retirada_em: Mapped[datetime] = _now()
    prevista_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    devolvida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    renovacoes: Mapped[int] = mapped_column(Integer, server_default="0")


class Reserva(Base):
    __tablename__ = "reservas"
    __table_args__ = (
        CheckConstraint("status IN ('ativa', 'atendida', 'cancelada')", name="ck_reservas_status"),
        # Um usuário só entra uma vez na fila de um livro.
        Index(
            "uq_reserva_ativa_por_usuario_livro",
            "livro_id",
            "usuario_id",
            unique=True,
            postgresql_where=text("status = 'ativa'"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    livro_id: Mapped[int] = mapped_column(ForeignKey("livros.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    posicao: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), server_default="ativa")
    criada_em: Mapped[datetime] = _now()


class LivroEmbedding(Base):
    __tablename__ = "livro_embeddings"
    __table_args__ = (
        Index(
            "ix_livro_embeddings_vetor_hnsw",
            "vetor",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"vetor": "vector_cosine_ops"},
        ),
    )
    livro_id: Mapped[int] = mapped_column(
        ForeignKey("livros.id", ondelete="CASCADE"), primary_key=True
    )
    modelo: Mapped[str] = mapped_column(String(160))
    vetor: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM))
    atualizado_em: Mapped[datetime] = _now()


class Avaliacao(Base):
    __tablename__ = "avaliacoes"
    __table_args__ = (
        CheckConstraint("nota BETWEEN 1 AND 5", name="ck_avaliacoes_nota"),
        UniqueConstraint("livro_id", "usuario_id", name="uq_avaliacao_livro_usuario"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    livro_id: Mapped[int] = mapped_column(ForeignKey("livros.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    nota: Mapped[int]
    comentario: Mapped[str | None] = mapped_column(Text)


class Conversa(Base):
    __tablename__ = "conversas"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), index=True)
    criada_em: Mapped[datetime] = _now()
    # ids dos livros que ferramentas devolveram na conversa (grounding vale entre turnos)
    livros_vistos: Mapped[list[int]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))


class AcaoPendente(Base):
    """Ação de escrita proposta pelo agente, aguardando o clique. Pertence a uma conversa."""

    __tablename__ = "acoes_pendentes"
    __table_args__ = (
        CheckConstraint(
            "ferramenta IN ('locar', 'renovar', 'devolver', 'reservar')",
            name="ck_acoes_pendentes_ferramenta",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(
        ForeignKey("conversas.id", ondelete="CASCADE"), index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True)
    ferramenta: Mapped[str] = mapped_column(String(20))
    argumentos: Mapped[dict[str, Any]] = mapped_column(JSONB)
    resumo: Mapped[str] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Mensagem(Base):
    __tablename__ = "mensagens"
    __table_args__ = (
        CheckConstraint("papel IN ('usuario', 'assistente', 'sistema')", name="ck_mensagens_papel"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(
        ForeignKey("conversas.id", ondelete="CASCADE"), index=True
    )
    papel: Mapped[str] = mapped_column(String(20))
    conteudo: Mapped[str] = mapped_column(Text)
    criada_em: Mapped[datetime] = _now()


class ChamadaFerramenta(Base):
    __tablename__ = "chamadas_ferramenta"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(
        ForeignKey("conversas.id", ondelete="CASCADE"), index=True
    )
    ferramenta: Mapped[str] = mapped_column(String(80))
    argumentos: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    resultado: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    latencia_ms: Mapped[int | None]
    tokens_entrada: Mapped[int | None]
    tokens_saida: Mapped[int | None]
    criada_em: Mapped[datetime] = _now()

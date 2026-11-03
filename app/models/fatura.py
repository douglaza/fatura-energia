"""Modelo da tabela faturas — espelha app/schemas/fatura.py."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Integer, Numeric, String, Date, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Fatura(Base):
    """Uma fatura de energia da CEMIG."""

    __tablename__ = "faturas"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_fatura: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    instalacao: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    titular: Mapped[str] = mapped_column(String(120), nullable=False)
    mes_referencia: Mapped[str] = mapped_column(String(7), nullable=False)  # "2025-01"
    data_emissao: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    vencimento: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    consumo_kwh: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    texto_extraido: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    consumos = relationship(
        "Consumo",
        back_populates="fatura",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Fatura {self.codigo_fatura} {self.mes_referencia}>"

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.consumo import ConsumoRead


class FaturaBase(BaseModel):
    codigo_fatura: str = Field(max_length=50)
    instalacao: str = Field(max_length=30)
    titular: str = Field(max_length=100)
    mes_referencia: str = Field(pattern=r"^\d{4}-\d{2}$")   # formato "2025-01"
    data_emissao: date
    vencimento: date
    valor_total: Decimal = Field(gt=0)
    consumo_kwh: Decimal = Field(ge=0)
    texto_extraido: str | None = None


class FaturaCreate(FaturaBase):
    """Payload de criação: todos os campos obrigatórios (exceto texto_extraido)."""
    pass


class FaturaUpdate(BaseModel):
    """Payload de atualização parcial (PATCH): tudo opcional."""
    codigo_fatura: str | None = Field(default=None, max_length=50)
    instalacao: str | None = Field(default=None, max_length=30)
    titular: str | None = Field(default=None, max_length=100)
    mes_referencia: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    data_emissao: date | None = None
    vencimento: date | None = None
    valor_total: Decimal | None = Field(default=None, gt=0)
    consumo_kwh: Decimal | None = Field(default=None, ge=0)
    texto_extraido: str | None = None


class FaturaRead(FaturaBase):
    """Resposta da API: inclui id e consumos aninhados."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    consumos: list[ConsumoRead] = []

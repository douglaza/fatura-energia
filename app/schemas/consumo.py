from datetime import date
from pydantic import BaseModel, ConfigDict


class ConsumoBase(BaseModel):
    data_leitura: date
    kwh: float


class ConsumoCreate(ConsumoBase):
    # fatura_id vem da URL (path), não do body — por isso não está aqui
    pass


class ConsumoRead(ConsumoBase):
    model_config = ConfigDict(from_attributes=True)  # converte direto do model ORM

    id: int
    fatura_id: int

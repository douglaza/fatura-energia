from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.consumo import Consumo
from app.schemas.consumo import ConsumoCreate


def criar_consumo(db: Session, dados: ConsumoCreate, fatura_id: int) -> Consumo:
    consumo = Consumo(**dados.model_dump(), fatura_id=fatura_id)
    db.add(consumo)
    db.commit()
    db.refresh(consumo)
    return consumo


def listar_consumos(db: Session, fatura_id: int) -> list[Consumo]:
    stmt = select(Consumo).where(Consumo.fatura_id == fatura_id).order_by(Consumo.data_leitura)
    return list(db.scalars(stmt))

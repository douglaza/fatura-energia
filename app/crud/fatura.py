from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.fatura import Fatura
from app.schemas.fatura import FaturaCreate, FaturaUpdate


def criar_fatura(db: Session, dados: FaturaCreate) -> Fatura:
    fatura = Fatura(**dados.model_dump())
    db.add(fatura)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # devolve a sessão ao estado limpo antes de propagar
        raise
    db.refresh(fatura)  # traz id e defaults do banco
    return fatura


def obter_fatura_por_codigo(db: Session, codigo_fatura: str) -> Fatura | None:
    stmt = select(Fatura).where(Fatura.codigo_fatura == codigo_fatura)
    return db.scalars(stmt).first()


def listar_faturas(db: Session, skip: int = 0, limit: int = 100) -> list[Fatura]:
    stmt = select(Fatura).offset(skip).limit(limit).order_by(Fatura.mes_referencia)
    return list(db.scalars(stmt))


def obter_fatura(db: Session, fatura_id: int) -> Fatura | None:
    return db.get(Fatura, fatura_id)


def atualizar_fatura(db: Session, fatura: Fatura, dados: FaturaUpdate) -> Fatura:
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(fatura, campo, valor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # devolve a sessão ao estado limpo antes de propagar
        raise
    db.refresh(fatura)
    return fatura


def deletar_fatura(db: Session, fatura: Fatura) -> None:
    db.delete(fatura)
    db.commit()

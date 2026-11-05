from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import fatura as crud
from app.models import Fatura, Consumo
from app.schemas.fatura import FaturaCreate, FaturaRead, FaturaUpdate
from app.schemas.consumo import ConsumoCreate, ConsumoRead

from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/faturas", tags=["Faturas"])


@router.post("", response_model=FaturaRead, status_code=status.HTTP_201_CREATED)
def criar_fatura(dados: FaturaCreate, db: Session = Depends(get_db)):
    if crud.obter_fatura_por_codigo(db, dados.codigo_fatura):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Já existe uma fatura com o código {dados.codigo_fatura!r}",
        )
    try:
        return crud.criar_fatura(db, dados)
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Já existe uma fatura com o código {dados.codigo_fatura!r}",
        )


@router.get("", response_model=list[FaturaRead])
def listar_faturas(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.listar_faturas(db, skip=skip, limit=limit)


@router.get("/{fatura_id}", response_model=FaturaRead)
def obter_fatura(fatura_id: int, db: Session = Depends(get_db)):
    fatura = crud.obter_fatura(db, fatura_id)
    if not fatura:
        raise HTTPException(404, "Fatura não encontrada")
    return fatura


@router.patch("/{fatura_id}", response_model=FaturaRead)
def atualizar_fatura(fatura_id: int, dados: FaturaUpdate, db: Session = Depends(get_db)):
    fatura = crud.obter_fatura(db, fatura_id)
    if not fatura:
        raise HTTPException(404, "Fatura não encontrada")
    if dados.codigo_fatura is not None:
        existente = crud.obter_fatura_por_codigo(db, dados.codigo_fatura)
        if existente and existente.id != fatura.id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Já existe uma fatura com o código {dados.codigo_fatura!r}",
            )
    try:
        return crud.atualizar_fatura(db, fatura, dados)
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Já existe uma fatura com o código {dados.codigo_fatura!r}",
        )


@router.delete("/{fatura_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_fatura(fatura_id: int, db: Session = Depends(get_db)):
    fatura = crud.obter_fatura(db, fatura_id)
    if not fatura:
        raise HTTPException(404, "Fatura não encontrada")
    crud.deletar_fatura(db, fatura)


# --- Consumos aninhados (novo — não existia na versão antiga) ---

@router.post("/{fatura_id}/consumos", response_model=ConsumoRead,
             status_code=status.HTTP_201_CREATED)
def criar_consumo(fatura_id: int, dados: ConsumoCreate, db: Session = Depends(get_db)):
    if not crud.obter_fatura(db, fatura_id):
        raise HTTPException(404, "Fatura não encontrada")
    consumo = Consumo(**dados.model_dump(), fatura_id=fatura_id)
    db.add(consumo)
    db.commit()
    db.refresh(consumo)
    return consumo


@router.get("/{fatura_id}/consumos", response_model=list[ConsumoRead])
def listar_consumos(fatura_id: int, db: Session = Depends(get_db)):
    fatura = crud.obter_fatura(db, fatura_id)
    if not fatura:
        raise HTTPException(404, "Fatura não encontrada")
    return fatura.consumos

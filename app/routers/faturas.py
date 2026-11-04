from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import fatura as crud
from app.models import Fatura, Consumo
from app.schemas.fatura import FaturaCreate, FaturaRead, FaturaUpdate
from app.schemas.consumo import ConsumoCreate, ConsumoRead

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from app.parser.cemig import parse_fatura
from app.parser.pdf import extrair_texto

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


@router.post("/upload", response_model=FaturaRead,
             status_code=status.HTTP_201_CREATED)
def upload_fatura(pdf: UploadFile = File(...), db: Session = Depends(get_db)):
    if pdf.filename and not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "O arquivo deve ser um PDF")

    conteudo = pdf.file.read()

    try:
        texto = extrair_texto(conteudo)
    except Exception:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Não foi possível ler o PDF")

    dados = parse_fatura(texto)

    if not dados["codigo_fatura"] or not dados["valor_total"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PDF não parece ser uma fatura Cemig válida "
            "(campos obrigatórios não encontrados)",
        )

    if crud.obter_fatura_por_codigo(db, dados["codigo_fatura"]):
        raise HTTPException(
            # status.HTTP_409_CONFLICT,
            # f"Já existe uma fatura com o código {dados['codigo_fatura']!r}",
            status_code=409,
            detail=f"Fatura duplicada: já existe uma fatura com o código '{dados['codigo_fatura']}'",
        )

    # Separar consumos do payload da fatura
    consumos_data = dados.pop("consumos", [])
    consumo_kwh = dados.pop("consumo_kwh", None)

    fatura = Fatura(**dados)

    # Consumo vindo do parser antigo (consumo_kwh solto)
    if consumo_kwh is not None and "mes_referencia" in dados:
        ano, mes = dados["mes_referencia"].split("-")
        fatura.consumos.append(Consumo(
            data_leitura=date(int(ano), int(mes), 15),
            kwh=float(consumo_kwh),
        ))

    # Consumos vindos do parser novo
    campos_validos = {"data_leitura", "kwh"}
    for c in consumos_data:
        fatura.consumos.append(Consumo(
            **{k: v for k, v in c.items() if k in campos_validos}
        ))

    # ✅ Validar se conseguimos pelo menos UM consumo
    if not fatura.consumos:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="Não foi possível extrair o consumo (kWh) do PDF",
        )

    # Se quiser manter o campo na fatura também:
    # fatura.consumo_kwh = fatura.consumos[0].kwh  # opcional

    db.add(fatura)
    db.commit()
    db.refresh(fatura)
    return fatura

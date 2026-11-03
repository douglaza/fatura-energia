import io

import pdfplumber
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.core.database import get_db
from app.parser.cemig import parse_fatura

from app.schemas import fatura as fatura_schemas

router = APIRouter(prefix="/faturas", tags=["upload"])
# Campos que o parser pode não conseguir extrair do PDF.
CAMPOS_OBRIGATORIOS = (
    "codigo_fatura",
    "instalacao",
    "titular",
    "mes_referencia",
    "data_emissao",
    "vencimento",
    "valor_total",
    "consumo_kwh",
)


@router.post("/upload", response_model=fatura_schemas.FaturaRead, status_code=status.HTTP_201_CREATED)
async def upload_fatura(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arquivo deve ser um PDF")

    conteudo = await file.read()
    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Erro ao ler PDF: {e}")

    dados = parse_fatura(texto)
    faltando = [campo for campo in CAMPOS_OBRIGATORIOS if dados.get(campo) in (None, "")]
    if faltando:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Não foi possível extrair os dados da fatura: {', '.join(faltando)}",
        )

    consumos_data = dados.pop("consumos", [])
    try:
        fatura = crud.criar_fatura(db, schemas.FaturaCreate(**dados))
    except ValidationError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Dados inválidos: {e}")
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Já existe uma fatura com o código {dados['codigo_fatura']!r}",
        )

    for c in consumos_data:
        # o parser devolve "descricao" (informativo); o schema só aceita data_leitura/kwh
        crud.criar_consumo(
            db,
            schemas.ConsumoCreate(data_leitura=c["data_leitura"], kwh=c["kwh"]),
            fatura.id,
        )

    db.refresh(fatura)
    return fatura


# import pdfplumber
# from fastapi import APIRouter, File, UploadFile, HTTPException

# router = APIRouter(prefix="/faturas", tags=["upload"])

# @router.post("/upload")
# async def upload_fatura(file: UploadFile = File(...)):
#     if not file.filename.lower().endswith(".pdf"):
#         raise HTTPException(status_code=400, detail="Arquivo deve ser um PDF")

#     conteudo = await file.read()

#     try:
#         with pdfplumber.open(__import__("io").BytesIO(conteudo)) as pdf:
#             texto = "\n".join(page.extract_text() or "" for page in pdf.pages)
#     except Exception as e:
#         raise HTTPException(status_code=422, detail=f"Erro ao ler PDF: {e}")

#     return {
#         "arquivo": file.filename,
#         "paginas": texto.count("\n") + 1,
#         "primeiros_500_chars": texto[:500],
#         "texto_extraido": texto,
#     }

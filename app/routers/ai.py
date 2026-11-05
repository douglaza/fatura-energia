from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.ai.assistant import explicar_fatura, recomendar_economia, responder_pergunta
from app.core.database import get_db
from app.schemas.ai import ExplicacaoFatura, PerguntaAI, RecomendacaoEnergetica, RespostaAI

router = APIRouter(prefix="/ai", tags=["Assistente"])


@router.get("/faturas/{mes_referencia}/explicar", response_model=ExplicacaoFatura)
def explicar_fatura_por_mes(
    mes_referencia: Annotated[str, Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
    db: Session = Depends(get_db),
):
    explicacao = explicar_fatura(db, mes_referencia)
    if explicacao is None:
        raise HTTPException(status_code=404, detail="Fatura não encontrada para o mês informado.")
    return ExplicacaoFatura(explicacao=explicacao)


@router.post("/chat", response_model=RespostaAI)
def chat_faturas(pergunta: PerguntaAI, db: Session = Depends(get_db)):
    return RespostaAI(resposta=responder_pergunta(db, pergunta.pergunta))


@router.post("/consultor", response_model=RecomendacaoEnergetica)
def consultor_energetico(db: Session = Depends(get_db)):
    return RecomendacaoEnergetica(recomendacao=recomendar_economia(db))
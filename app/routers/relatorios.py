"""Endpoint de geração do dashboard Excel de consumo."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.analytics.dashboard_excel import gerar_dashboard_excel
from app.core.database import get_db

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


@router.get("/dashboard.xlsx")
def gerar_dashboard(db: Session = Depends(get_db)):
    """Gera e retorna o dashboard em Excel (dashboard_consumo.xlsx).

    O arquivo contém quatro abas:
        - Resumo Executivo: KPIs de consumo
        - Histórico: consumo mensal
        - Faturas: detalhamento das faturas
        - Gráficos: consumo, valor e variação %
    """
    conteudo = gerar_dashboard_excel(db)
    return StreamingResponse(
        iter([conteudo]),
        media_type=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": 'attachment; filename="dashboard_consumo.xlsx"'
        },
    )
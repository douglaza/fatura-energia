"""Acesso aos dados de faturas e consumos usados pelo assistente."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics.relatorios import df_consumo_mensal, df_faturas


def listar_consumos_mensais(db: Session) -> list[dict]:
    """Retorna a série mensal consolidada usada também pelo dashboard."""
    return df_consumo_mensal(db).to_dict(orient="records")


def listar_faturas(db: Session) -> list[dict]:
    """Retorna faturas sem incluir texto extraído ou identificadores pessoais."""
    dados = df_faturas(db)
    if dados.empty:
        return []
    return dados[["mes_referencia", "valor_total", "consumo_kwh"]].to_dict(
        orient="records"
    )


def obter_fatura_mes(db: Session, mes_referencia: str) -> dict | None:
    """Retorna valores de uma fatura, excluindo dados identificáveis."""
    faturas = listar_faturas(db)
    correspondentes = [
        fatura
        for fatura in faturas
        if fatura["mes_referencia"] == mes_referencia
    ]
    if not correspondentes:
        return None
    return correspondentes[-1]
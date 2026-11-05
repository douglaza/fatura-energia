"""Transforma dados do banco em DataFrames pandas para relatórios."""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy.orm import Session, joinedload

from app.models.consumo import Consumo
from app.models.fatura import Fatura


def df_faturas(db: Session) -> pd.DataFrame:
    """DataFrame com os dados das faturas, ordenado por mês de referência."""
    stmt = select(Fatura).order_by(Fatura.mes_referencia)
    faturas = list(db.scalars(stmt))
    if not faturas:
        return pd.DataFrame(
            columns=[
                "id",
                "codigo_fatura",
                "instalacao",
                "titular",
                "mes_referencia",
                "data_emissao",
                "vencimento",
                "valor_total",
                "consumo_kwh",
            ]
        )
    rows = [
        {
            "id": f.id,
            "codigo_fatura": f.codigo_fatura,
            "instalacao": f.instalacao,
            "titular": f.titular,
            "mes_referencia": f.mes_referencia,
            "data_emissao": f.data_emissao,
            "vencimento": f.vencimento,
            "valor_total": float(f.valor_total),
            "consumo_kwh": float(f.consumo_kwh) if f.consumo_kwh is not None else None,
        }
        for f in faturas
    ]
    return pd.DataFrame(rows)


def df_consumos(db: Session) -> pd.DataFrame:
    """DataFrame com os registros individuais de consumo (tabela consumos)."""
    stmt = select(Consumo).order_by(Consumo.data_leitura)
    consumos = list(db.scalars(stmt))
    if not consumos:
        return pd.DataFrame(columns=["id", "fatura_id", "data_leitura", "kwh"])
    rows = [
        {
            "id": c.id,
            "fatura_id": c.fatura_id,
            "data_leitura": c.data_leitura,
            "kwh": c.kwh,
        }
        for c in consumos
    ]
    return pd.DataFrame(rows)


def df_consumo_mensal(db: Session) -> pd.DataFrame:
    """DataFrame consolidado: uma leitura de consumo por mês.

    Leituras repetidas em históricos de faturas diferentes são consolidadas
    pelo mês. O valor da fatura só é preenchido nos meses com conta cadastrada.
    """
    from app.analytics.indicadores import _dados_consumo_mensal  # noqa: PLC0415

    dados = _dados_consumo_mensal(db)
    if not dados:
        return pd.DataFrame(columns=["mes_referencia", "consumo_kwh", "valor_total"])
    df = pd.DataFrame(dados)
    df = df.rename(
        columns={
            "mes": "mes_referencia",
            "kwh": "consumo_kwh",
            "valor": "valor_total",
        }
    )
    df = df.dropna(subset=["consumo_kwh"])
    return df[["mes_referencia", "consumo_kwh", "valor_total"]]


def df_indicadores(db: Session) -> pd.DataFrame:
    """DataFrame de uma única linha com os indicadores principais."""
    from app.analytics.indicadores import calcular_indicadores  # noqa: PLC0415

    ind = calcular_indicadores(db)
    return pd.DataFrame([ind])


# Necessário pelo select usado em df_faturas / df_consumos
from sqlalchemy import select  # noqa: E402
"""Indicadores de consumo calculados a partir do banco de dados."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.fatura import Fatura


def _consumo_por_fatura(db: Session) -> list[dict[str, Any]]:
    """Retorna lista de faturas com consumo (kwh), valor e metadados."""
    stmt = (
        select(Fatura)
        .options(joinedload(Fatura.consumos))
        .order_by(Fatura.mes_referencia)
    )
    # faturas = list(db.scalars(stmt))
    faturas = list(db.scalars(stmt).unique())


    resultado = []
    for f in faturas:
        if f.consumos:
            kwh = sum(c.kwh for c in f.consumos)
        else:
            kwh = float(f.consumo_kwh) if f.consumo_kwh is not None else None
        resultado.append(
            {
                "mes": f.mes_referencia,
                "kwh": kwh,
                "valor": float(f.valor_total),
                "codigo": f.codigo_fatura,
                "titular": f.titular,
                "vencimento": f.vencimento,
            }
        )
    return resultado


def calcular_indicadores(db: Session) -> dict[str, Any]:
    """Calcula os principais indicadores de consumo.

    Retorna um dicionário com:
        consumo_medio, maior_consumo, menor_consumo,
        mes_maior_consumo, mes_menor_consumo, valor_medio,
        gasto_anual, ultima_fatura, tendencia, total_faturas,
        projecao_consumo (média dos até três meses mais recentes).
    """
    dados = [d for d in _consumo_por_fatura(db) if d["kwh"] is not None]

    if not dados:
        return {
            "consumo_medio": 0.0,
            "maior_consumo": 0.0,
            "menor_consumo": 0.0,
            "mes_maior_consumo": None,
            "mes_menor_consumo": None,
            "valor_medio": 0.0,
            "gasto_anual": 0.0,
            "ultima_fatura": None,
            "tendencia": "indisponível",
            "total_faturas": 0,
            "projecao_consumo": None,
        }

    consumo_medio = sum(d["kwh"] for d in dados) / len(dados)
    maior = max(dados, key=lambda d: d["kwh"])
    menor = min(dados, key=lambda d: d["kwh"])
    valor_medio = sum(d["valor"] for d in dados) / len(dados)
    gasto_anual = sum(d["valor"] for d in dados)

    tendencia = _calcular_tendencia(dados)
    ultima = dados[-1] if dados else None
    consumos_recentes = [d["kwh"] for d in dados[-3:]]
    projecao_consumo = sum(consumos_recentes) / len(consumos_recentes)

    return {
        "consumo_medio": round(consumo_medio, 2),
        "maior_consumo": round(maior["kwh"], 2),
        "menor_consumo": round(menor["kwh"], 2),
        "mes_maior_consumo": maior["mes"],
        "mes_menor_consumo": menor["mes"],
        "valor_medio": round(valor_medio, 2),
        "gasto_anual": round(gasto_anual, 2),
        "ultima_fatura": ultima,
        "tendencia": tendencia,
        "total_faturas": len(dados),
        "projecao_consumo": round(projecao_consumo, 2),
    }


def _calcular_tendencia(dados: list[dict[str, Any]]) -> str:
    """Compara a média dos últimos 3 meses com a dos 3 anteriores."""
    if len(dados) < 4:
        return "insuficiente"
    ultimos = dados[-3:]
    anteriores = dados[-6:-3] if len(dados) >= 6 else dados[:-3]
    if not anteriores:
        return "insuficiente"
    media_ultimos = sum(d["kwh"] for d in ultimos) / len(ultimos)
    media_anteriores = sum(d["kwh"] for d in anteriores) / len(anteriores)
    diff = media_ultimos - media_anteriores
    if diff > 0:
        return "alta"
    if diff < 0:
        return "baixa"
    return "estável"
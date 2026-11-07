"""Ferramentas de leitura permitidas ao assistente sobre o banco do app."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics.indicadores import _consumo_por_fatura, _dados_consumo_mensal

FERRAMENTAS_OLLAMA = [
    {
        "type": "function",
        "function": {
            "name": "resumir_consumo",
            "description": "Resume o consumo mensal, incluindo a série por mês; opcionalmente filtrada por ano. Use a série para perguntas sobre tendência e meses recentes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ano": {"type": "integer", "minimum": 2000, "maximum": 2100},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resumir_faturas",
            "description": "Resume quantidade e valores das faturas, opcionalmente filtradas por ano.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ano": {"type": "integer", "minimum": 2000, "maximum": 2100},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_historico_consumo",
            "description": "Lista leituras mensais de consumo, limitadas a no máximo 36 meses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ano": {"type": "integer", "minimum": 2000, "maximum": 2100},
                    "limite": {"type": "integer", "minimum": 1, "maximum": 36},
                },
                "additionalProperties": False,
            },
        },
    },
]


def _ano_argumento(argumentos: dict) -> int | None:
    ano = argumentos.get("ano")
    if ano is None:
        return None
    if isinstance(ano, bool) or not isinstance(ano, int) or not 2000 <= ano <= 2100:
        raise ValueError("O ano deve ser um inteiro entre 2000 e 2100.")
    return ano


def _filtrar_ano(registros: list[dict], ano: int | None) -> list[dict]:
    if ano is None:
        return registros
    return [registro for registro in registros if registro["mes"].startswith(f"{ano}-")]


def resumir_consumo(db: Session, argumentos: dict) -> dict:
    ano = _ano_argumento(argumentos)
    registros = _filtrar_ano(_dados_consumo_mensal(db), ano)
    consumos = [registro for registro in registros if registro["kwh"] is not None]
    if not consumos:
        return {"ano": ano, "meses_com_consumo": 0, "mensagem": "Sem consumo no período."}

    maior = max(consumos, key=lambda registro: registro["kwh"])
    menor = min(consumos, key=lambda registro: registro["kwh"])
    return {
        "ano": ano,
        "meses_com_consumo": len(consumos),
        "consumo_total_kwh": round(sum(registro["kwh"] for registro in consumos), 2),
        "consumo_medio_kwh": round(
            sum(registro["kwh"] for registro in consumos) / len(consumos), 2
        ),
        "consumo_mensal": [
            {"mes": registro["mes"], "kwh": registro["kwh"]}
            for registro in consumos
        ],
        "maior_consumo": {"mes": maior["mes"], "kwh": maior["kwh"]},
        "menor_consumo": {"mes": menor["mes"], "kwh": menor["kwh"]},
    }


def resumir_faturas(db: Session, argumentos: dict) -> dict:
    ano = _ano_argumento(argumentos)
    faturas = _filtrar_ano(_consumo_por_fatura(db), ano)
    if not faturas:
        return {"ano": ano, "quantidade": 0, "mensagem": "Sem faturas no período."}

    valores = [fatura["valor"] for fatura in faturas]
    mais_cara = max(faturas, key=lambda fatura: fatura["valor"])
    return {
        "ano": ano,
        "quantidade": len(faturas),
        "valor_total_brl": round(sum(valores), 2),
        "valor_medio_brl": round(sum(valores) / len(valores), 2),
        "fatura_mais_cara": {
            "mes": mais_cara["mes"],
            "valor_total_brl": mais_cara["valor"],
        },
        "faturas_recentes": [
            {"mes": fatura["mes"], "valor_total_brl": fatura["valor"]}
            for fatura in faturas[-6:]
        ],
    }


def listar_historico_consumo(db: Session, argumentos: dict) -> dict:
    ano = _ano_argumento(argumentos)
    limite = argumentos.get("limite", 12)
    if isinstance(limite, bool) or not isinstance(limite, int) or not 1 <= limite <= 36:
        raise ValueError("O limite deve ser um inteiro entre 1 e 36.")
    registros = _filtrar_ano(_dados_consumo_mensal(db), ano)
    return {
        "ano": ano,
        "meses": [
            {"mes": registro["mes"], "consumo_kwh": registro["kwh"]}
            for registro in registros[-limite:]
        ],
    }


def executar_ferramenta(db: Session, nome: str, argumentos: dict) -> dict:
    ferramentas = {
        "resumir_consumo": resumir_consumo,
        "resumir_faturas": resumir_faturas,
        "listar_historico_consumo": listar_historico_consumo,
    }
    if nome not in ferramentas:
        raise ValueError("Ferramenta não permitida.")
    if not isinstance(argumentos, dict):
        raise ValueError("Argumentos da ferramenta devem ser um objeto JSON.")
    return ferramentas[nome](db, argumentos)
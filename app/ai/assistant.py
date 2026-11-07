"""Respostas em linguagem natural sem chamadas externas a modelos."""

from __future__ import annotations

import json
import re
import unicodedata

from sqlalchemy.orm import Session

from app.ai.ollama import gerar_resposta, responder_com_ferramentas
from app.ai.prompts import PROMPT_CHAT_FATURAS, PROMPT_CONSULTOR, PROMPT_EXPLICAR_FATURA
from app.ai.services import (
    contexto_agregado,
    listar_consumos_mensais,
    listar_faturas,
    obter_fatura_mes,
)

MESES = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)


def _normalizar(texto: str) -> str:
    decomposicao = unicodedata.normalize("NFD", texto.casefold())
    return "".join(caractere for caractere in decomposicao if not unicodedata.combining(caractere))


def _formatar_numero(valor: float, casas: int = 2) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _nome_mes(mes_referencia: str) -> str:
    ano, mes = mes_referencia.split("-")
    return f"{MESES[int(mes) - 1]}/{ano}"


def _perguntar_llm(system_prompt: str, pergunta: str, contexto: dict) -> str:
    user_prompt = (
        f"Pergunta ou tarefa: {pergunta}\n\n"
        "Use exclusivamente este contexto factual em JSON:\n"
        f"{json.dumps(contexto, ensure_ascii=False, allow_nan=False)}"
    )
    return gerar_resposta(system_prompt, user_prompt)


def explicar_fatura(db: Session, mes_referencia: str) -> str | None:
    fatura = obter_fatura_mes(db, mes_referencia)
    if fatura is None:
        return None

    consumos = listar_consumos_mensais(db)
    consumo_atual = next(
        (item for item in consumos if item["mes_referencia"] == mes_referencia),
        None,
    )
    ano, mes = map(int, mes_referencia.split("-"))
    ano_anterior, mes_anterior = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    referencia_anterior = f"{ano_anterior:04d}-{mes_anterior:02d}"
    anterior = next(
        (item for item in consumos if item["mes_referencia"] == referencia_anterior),
        None,
    )
    contexto = {
        "fatura": {
            "mes_referencia": mes_referencia,
            "valor_total_brl": fatura["valor_total"],
            "consumo_fatura_kwh": fatura["consumo_kwh"],
        },
        "consumo_mensal": consumo_atual,
        "consumo_mes_anterior": anterior,
    }
    return _perguntar_llm(
        PROMPT_EXPLICAR_FATURA,
        f"Explique a fatura de {_nome_mes(mes_referencia)}.",
        contexto,
    )


def responder_pergunta(db: Session, pergunta: str) -> str:
    pergunta_normalizada = _normalizar(pergunta)
    consumos = listar_consumos_mensais(db)
    faturas = listar_faturas(db)

    if any(termo in pergunta_normalizada for termo in ("reduzir", "economizar", "economia")):
        return recomendar_economia(db, pergunta)

    if "fatura" in pergunta_normalizada and any(
        termo in pergunta_normalizada for termo in ("quantas", "quantidade", "numero")
    ):
        if any(
            termo in pergunta_normalizada
            for termo in ("valor total", "gasto total", "total gasto")
        ):
            total = sum(item["valor_total"] for item in faturas)
            return (
                f"Há {len(faturas)} fatura(s) cadastrada(s), com valor total de "
                f"R$ {_formatar_numero(total)}."
            )
        return f"Há {len(faturas)} fatura(s) cadastrada(s) neste banco."

    if any(
        termo in pergunta_normalizada
        for termo in ("valor total", "gasto total", "total gasto")
    ):
        if not faturas:
            return "Ainda não há faturas cadastradas para somar."
        total = sum(item["valor_total"] for item in faturas)
        return f"O valor total das {len(faturas)} fatura(s) cadastradas é R$ {_formatar_numero(total)}."

    if "consumo" in pergunta_normalizada and any(
        termo in pergunta_normalizada
        for termo in ("maior", "maximo", "mais alto", "pico")
    ):
        if not consumos:
            return "Ainda não há histórico de consumo cadastrado."
        maior = max(consumos, key=lambda item: item["consumo_kwh"])
        return f"{_nome_mes(maior['mes_referencia'])}\n{_formatar_numero(maior['consumo_kwh'])} kWh"

    if "consumo" in pergunta_normalizada and any(
        termo in pergunta_normalizada
        for termo in ("mais recente", "ultimos meses", "historico recente")
    ):
        if not consumos:
            return "Ainda não há histórico de consumo cadastrado."
        quantidade = 3
        palavras_quantidade = {
            "um": 1,
            "dois": 2,
            "tres": 3,
            "quatro": 4,
            "cinco": 5,
            "seis": 6,
            "sete": 7,
            "oito": 8,
            "nove": 9,
            "dez": 10,
        }
        for palavra, valor in palavras_quantidade.items():
            if palavra in pergunta_normalizada:
                quantidade = valor
                break
        ultimos = consumos[-quantidade:]
        return "\n".join(
            f"{_nome_mes(item['mes_referencia'])}: "
            f"{_formatar_numero(item['consumo_kwh'])} kWh"
            for item in ultimos
        )

    if any(termo in pergunta_normalizada for termo in ("mais cara", "maior valor", "mais alto valor")):
        if not faturas:
            return "Ainda não há faturas cadastradas."
        maior = max(faturas, key=lambda item: item["valor_total"])
        return f"{_nome_mes(maior['mes_referencia'])}\nR$ {_formatar_numero(maior['valor_total'])}"

    if "consum" in pergunta_normalizada and any(
        termo in pergunta_normalizada for termo in ("quanto", "total", "soma")
    ):
        ano = re.search(r"\b(20\d{2})\b", pergunta_normalizada)
        selecionados = [
            item
            for item in consumos
            if ano is None or item["mes_referencia"].startswith(ano.group(1))
        ]
        if not selecionados:
            return "Não há consumos registrados para o período solicitado."
        total = sum(item["consumo_kwh"] for item in selecionados)
        periodo = f"em {ano.group(1)}" if ano else "no histórico disponível"
        return f"O consumo registrado {periodo} foi de {_formatar_numero(total)} kWh."

    if "media" in pergunta_normalizada and any(
        termo in pergunta_normalizada for termo in ("gasto", "conta", "valor")
    ):
        if not faturas:
            return "Ainda não há faturas cadastradas para calcular a média."
        media = sum(item["valor_total"] for item in faturas) / len(faturas)
        return f"O gasto médio por fatura cadastrada é R$ {_formatar_numero(media)}."

    return responder_com_ferramentas(db, PROMPT_CHAT_FATURAS, pergunta)


def recomendar_economia(db: Session, pergunta: str = "Como posso reduzir minha conta?") -> str:
    consumos = listar_consumos_mensais(db)
    if not consumos:
        return "Ainda não há histórico de consumo para personalizar recomendações."

    return _perguntar_llm(PROMPT_CONSULTOR, pergunta, contexto_agregado(db))
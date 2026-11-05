"""Respostas em linguagem natural sem chamadas externas a modelos."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy.orm import Session

from app.ai.services import listar_consumos_mensais, listar_faturas, obter_fatura_mes

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


def explicar_fatura(db: Session, mes_referencia: str) -> str | None:
    fatura = obter_fatura_mes(db, mes_referencia)
    if fatura is None:
        return None

    linhas = [f"Fatura de {_nome_mes(mes_referencia)}."]
    consumos = listar_consumos_mensais(db)
    consumo_atual = next(
        (item for item in consumos if item["mes_referencia"] == mes_referencia),
        None,
    )
    if consumo_atual is not None:
        linhas.append(f"O consumo foi de {_formatar_numero(consumo_atual['consumo_kwh'])} kWh.")
        ano, mes = map(int, mes_referencia.split("-"))
        ano_anterior, mes_anterior = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
        referencia_anterior = f"{ano_anterior:04d}-{mes_anterior:02d}"
        anterior = next(
            (item for item in consumos if item["mes_referencia"] == referencia_anterior),
            None,
        )
        if anterior and anterior["consumo_kwh"]:
            variacao = (
                (consumo_atual["consumo_kwh"] - anterior["consumo_kwh"])
                / anterior["consumo_kwh"]
                * 100
            )
            sentido = "aumento" if variacao > 0 else "redução"
            linhas.append(
                f"Em relação a {_nome_mes(referencia_anterior)}, houve {sentido} "
                f"de {_formatar_numero(abs(variacao), 1)}%."
            )
        else:
            linhas.append("Não há consumo do mês anterior disponível para comparação.")
    elif fatura["consumo_kwh"] is not None:
        linhas.append(f"O consumo informado na fatura foi de {_formatar_numero(fatura['consumo_kwh'])} kWh.")
    else:
        linhas.append("O consumo desta fatura não está disponível no histórico.")

    linhas.append(f"O valor total foi de R$ {_formatar_numero(fatura['valor_total'])}.")
    linhas.append(
        "A composição detalhada dos encargos ainda não está estruturada; "
        "não é possível listar os componentes com segurança."
    )
    return "\n\n".join(linhas)


def responder_pergunta(db: Session, pergunta: str) -> str:
    pergunta_normalizada = _normalizar(pergunta)
    consumos = listar_consumos_mensais(db)
    faturas = listar_faturas(db)

    if any(termo in pergunta_normalizada for termo in ("reduzir", "economizar", "economia")):
        return recomendar_economia(db)

    if "consumo" in pergunta_normalizada and any(
        termo in pergunta_normalizada
        for termo in ("maior", "maximo", "mais alto", "pico")
    ):
        if not consumos:
            return "Ainda não há histórico de consumo cadastrado."
        maior = max(consumos, key=lambda item: item["consumo_kwh"])
        return f"{_nome_mes(maior['mes_referencia'])}\n{_formatar_numero(maior['consumo_kwh'])} kWh"

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

    return (
        "Ainda não reconheço essa pergunta. Posso informar maior consumo, "
        "conta mais cara, consumo total por ano, gasto médio ou sugerir formas de economizar."
    )


def recomendar_economia(db: Session) -> str:
    consumos = listar_consumos_mensais(db)
    if not consumos:
        return "Ainda não há histórico de consumo para personalizar recomendações."

    media = sum(item["consumo_kwh"] for item in consumos) / len(consumos)
    ultimo = consumos[-1]
    resposta = (
        f"A média do histórico é {_formatar_numero(media)} kWh por mês. "
        f"O mês mais recente registrado foi {_nome_mes(ultimo['mes_referencia'])}, "
        f"com {_formatar_numero(ultimo['consumo_kwh'])} kWh."
    )
    if len(consumos) < 3:
        resposta += " O histórico ainda é curto para identificar uma tendência confiável."
    elif ultimo["consumo_kwh"] > media:
        resposta += " Esse mês ficou acima da média; vale revisar o uso de chuveiro elétrico, climatização e equipamentos em espera."
    else:
        resposta += " Esse mês ficou dentro ou abaixo da média; mantenha o acompanhamento e observe quais hábitos coincidem com os meses de maior consumo."
    resposta += (
        " As recomendações são gerais: o banco ainda não contém medições por aparelho "
        "nem a composição detalhada da tarifa."
    )
    return resposta
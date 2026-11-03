import re
from datetime import date

MESES = {"JAN":1,"FEV":2,"MAR":3,"ABR":4,"MAI":5,"JUN":6,
         "JUL":7,"AGO":8,"SET":9,"OUT":10,"NOV":11,"DEZ":12}

def _num_br(s: str) -> str:
    """'344,83' -> '344.83' | '1.234,56' -> '1234.56'"""
    return s.replace(".", "").replace(",", ".")

def _to_date(s: str) -> date:
    d, m, y = s.split("/")
    return date(int(y), int(m), int(d))

def parse_fatura(texto: str) -> dict:
    """Extrai os campos da fatura Cemig a partir do texto do PDF."""

    # Titular: linha imediatamente antes de "Referente a"
    m = re.search(r"\n([A-ZÀ-Ü][A-ZÀ-Ü\s]+)\s+Referente a", texto)
    titular = m.group(1).strip() if m else None

    # Número da nota fiscal
    m = re.search(r"NOTA FISCAL Nº\s*(\d+)", texto)
    codigo_fatura = m.group(1) if m else None

    # Unidade consumidora (número após o cabeçalho "N.º DA UNIDADE CONSUMIDORA")
    m = re.search(r"UNIDADE CONSUMIDORA.*?\n([\d.\-]+)", texto, re.DOTALL)
    instalacao = m.group(1).strip() if m else None

    # Mês de referência (ex.: OUT/2026)
    m = re.search(r"\b([A-Z]{3})/(\d{4})\s+[\d/]+\s+[\d,]+\b", texto)
    mes_referencia = f"{m.group(2)}-{MESES[m.group(1)]:02d}" if m else None

    # Data de emissão
    m = re.search(r"Data de emissão:\s*(\d{2}/\d{2}/\d{4})", texto)
    data_emissao = _to_date(m.group(1)) if m else None

    # Vencimento (primeira data no cabeçalho "Referente a Vencimento Valor")
    m = re.search(r"Referente a Vencimento Valor a pagar \(R\$\)\s*\n.*?\b(\d{2}/\d{2}/\d{4})\b", texto)
    vencimento = _to_date(m.group(1)) if m else None

    # Valor total (linha TOTAL da tabela "Valores Faturados")
    m = re.search(r"^TOTAL\s+([\d.,]+)", texto, re.MULTILINE)
    valor_total = _num_br(m.group(1)) if m else None

    # Consumo do mês: linha "MÊS/ANO Cons. kWh" -> primeira linha do histórico
    m = re.search(r"MÊS/ANO\s+Cons\. kWh.*?\n([A-Z]{3})/\d{2}\s+(\d+)\s", texto)
    consumo_kwh = m.group(2) if m else None

    # Histórico de consumos: todas as linhas "OUT/26 268 8,93 30"
    consumos = []
    for m in re.finditer(
        r"^([A-Z]{3})/(\d{2})\s+(\d+)\s+([\d,]+)\s+(\d+)\s*$", texto, re.MULTILINE
    ):
        mes_abbr, ano2, kwh, media, dias = m.groups()
        ano = int("20" + ano2)
        data_leitura = date(ano, MESES[mes_abbr], 15)  # dia 15 como aproximação
        consumos.append({
            "data_leitura": data_leitura,
            "kwh": float(kwh),
            "descricao": f"{mes_abbr}/{ano} — média {media} kWh/dia, {dias} dias",
        })

    return {
        "codigo_fatura": codigo_fatura,
        "instalacao": instalacao,
        "titular": titular,
        "mes_referencia": mes_referencia,
        "data_emissao": data_emissao,
        "vencimento": vencimento,
        "valor_total": valor_total,
        "consumo_kwh": consumo_kwh,
        "consumos": consumos,
    }

import re
from datetime import date

MESES = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}

def _num_br(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))

def _to_date(s: str) -> date:
    d, m, y = s.split("/")
    return date(int(y), int(m), int(d))

def parse_fatura(texto: str) -> dict:
    # Normaliza: remove espaços múltiplos, unifica acentuação opcional
    t = re.sub(r"[ \t]+", " ", texto)

    # --- Nota fiscal: "NOTA FISCAL Nº 409472101 - SERIE 000"
    m = re.search(r"NOTA\s*FISCAL\s*N[ºo°.]?\s*(\d+)", t, re.IGNORECASE)
    codigo_fatura = m.group(1) if m else None

    # --- Instalação: número depois de "DA UNIDADE CONSUMIDORA"
    #     (na fatura real pode vir na mesma linha ou na seguinte)
    m = re.search(r"UNIDADE\s*CONSUMIDORA\s*:?\s*([\d.\-]{10,})",
                  t, re.IGNORECASE)
    instalacao = m.group(1).strip(".") if m else None

    # O mês aparece como "Referente a JUL/2026" ou na coluna "MÊS/ANO".
    m = re.search(r"\b([A-Z]{3})/(\d{4})\b", t, re.IGNORECASE)
    mes_referencia = (
        f"{m.group(2)}-{MESES[m.group(1).upper()]:02d}" if m else None
    )

    # --- Data de emissão
    m = re.search(r"Data\s*de\s*emiss[aã]o:\s*(\d{2}/\d{2}/\d{4})", t)
    data_emissao = _to_date(m.group(1)) if m else None

    # # --- Vencimento e valor: no cabeçalho
    # #     "Referente a   Vencimento   Valor a pagar (R$)"
    # #     "JUL/2026      22/08/2026   306,01"
    # m = re.search(
    #     r"Vencimento\s+Valor\s*a\s*pagar\s*\(R\$\)\s*\n?"
    #     r".*?(\d{2}/\d{2}/\d{4})\s+([\d.,]+)",
    #     t, re.DOTALL)
    # vencimento = _to_date(m.group(1)) if m else None
    # valor_total = _num_br(m.group(2)) if m else None

    # A data pode ficar na linha seguinte ao cabeçalho das colunas da fatura.
    m = re.search(
        r"Vencimento\s*[\s\S]{0,200}?(\d{2}/\d{2}/\d{4})",
        t,
        re.IGNORECASE,
    )
    vencimento = _to_date(m.group(1)) if m else None

    valor_total = None

    # --- Fallback para valor: linha "TOTAL 306,01"
    if valor_total is None:
        m = re.search(r"^TOTAL\s+([\d.,]+)", t, re.MULTILINE)
        valor_total = _num_br(m.group(1)) if m else None

    # O nome do cliente pode compartilhar a linha com o cabeçalho das colunas.
    BOILERPLATE = re.compile(
        r"CEMIG|DOCUMENTO AUXILIAR|NOTA FISCAL", re.IGNORECASE
    )
    titular = None
    for linha in t.splitlines():
        marcador_referencia = re.search(r"\bReferente\s+a\b", linha, re.IGNORECASE)
        if marcador_referencia:
            candidato = linha[:marcador_referencia.start()].strip()
            if candidato and not BOILERPLATE.search(candidato):
                titular = candidato
                break

    if titular is None:
        endereco = re.compile(
            r"^(?:RUA|R\.|AV\.?|AVENIDA|ALAMEDA|ROD\.?|RODOVIA|"
            r"TRAVESSA|ESTRADA|CEP\b|CPF\b)",
            re.IGNORECASE,
        )
        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha or BOILERPLATE.search(linha) or endereco.search(linha):
                continue
            titular = linha
            break

    # # --- Consumo do mês: coluna "Consumo kWh" (Informações Técnicas)
    # #     "Energia kWh   PPC257033321   3.056   3.284   1   228"
    # m = re.search(
    #     r"Consumo\s*kWh\s*\n?.*?\n.*?Energia\s*kWh\s+\S+\s+[\d.,]+\s+"
    #     r"[\d.,]+\s+[\d.,]+\s+(\d+)",
    #     t, re.DOTALL)
    # consumo_kwh = int(m.group(1)) if m else None
    # --- Consumo: linha "Energia KWh PPC... 3.056 3.284 1 228"
    #     pegar o ÚLTIMO número da linha (leitura anterior, atual, constante, consumo)
    # m = re.search(
    #     r"Informacoes?\s*Tecnicas?[\s\S]*?Energia\s+K?wh\s+\S+\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+(\d+)",
    #     t)
    # consumo_kwh = int(m.group(4)) if m else None

    consumo_kwh = None

    for linha in t.splitlines():
        m = re.search(
            r"Energia\s+KWh\s+\S+\s+\d[\d.,]*\s+\d[\d.,]*\s+\d+\s+(\d+)",
            linha,
            re.IGNORECASE,
        )
        if m:
            consumo_kwh = int(m.group(1))
            break

    # --- Histórico: "JUL/26 228 7,12 32"
    consumos = []
    for mm in re.finditer(
        r"^[ \t]*([A-Z]{3})/(\d{2})[ \t]+(\d+)[ \t]+([\d.,]+)[ \t]+(\d+)\b",
        t, re.MULTILINE):
        mes_abbr, ano2, kwh, media, dias = mm.groups()
        consumos.append({
            "data_leitura": date(2000 + int(ano2), MESES[mes_abbr], 15),
            "kwh": float(kwh),
            "descricao": f"{mes_abbr}/20{ano2} — média {media} kWh/dia, {dias} dias",
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

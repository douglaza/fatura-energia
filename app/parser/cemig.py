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

    # --- Mês de referência: "Referente a JUL/2026"
    m = re.search(r"Referente\s+a\s+([A-Z]{3})/(\d{4})", t)
    mes_referencia = f"{m.group(2)}-{MESES[m.group(1)]:02d}" if m else None

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

    # --- Vencimento: data após o rótulo, tolerante a quebras de linha
    m = re.search(r"Vencimento\s*[\s\S]{0,40}?(\d{2}/\d{2}/\d{4})", t)
    vencimento = _to_date(m.group(1)) if m else None

    valor_total = None

    # --- Fallback para valor: linha "TOTAL 306,01"
    if valor_total is None:
        m = re.search(r"^TOTAL\s+([\d.,]+)", t, re.MULTILINE)
        valor_total = _num_br(m.group(1)) if m else None

    # --- Titular: primeira linha em CAIXA ALTA que NÃO é cabeçalho CEMIG
    BOILERPLATE = re.compile(
        r"CEMIG|DOCUMENTO AUXILIAR|NOTA FISCAL", re.IGNORECASE
    )
    titular = None
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or BOILERPLATE.search(linha):
            continue
        titular = linha          # primeira linha "de conteúdo" após o cabeçalho
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

    if "Energia" in t:
        print("ACHOU ENERGIA")

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

    for linha in t.splitlines():
        if "Energia" in linha:
            print(linha)

    for linha in t.splitlines():
        if "Energia KWh" in linha:
            print(repr(linha))

    # --- Histórico: "JUL/26 228 7,12 32"
    consumos = []
    for mm in re.finditer(
        r"^([A-Z]{3})/(\d{2})\s+(\d+)\s+([\d,]+)\s+(\d+)\s*$",
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

# scripts/gerar_fixture_pdf.py
from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=10)

linhas = [
    "CEMIG DISTRIBUICAO S.A.",
    "DOCUMENTO AUXILIAR DA NOTA FISCAL DE ENERGIA ELETRICA ELETRONICA",
    "",
    "RENATO DOS SANTOS PIMENTEL",
    "RUA LORENA 6 AP103",
    "CARAVELAS 355164-268 IPATINGA, MG",
    "",
    "Referente a",
    "JUL/2026",
    "Vencimento",
    "22/08/2026",
    "Valor a pagar (R$)",
    "306,01",
    "",
    "NOTA FISCAL Nº 043171166 - SERIE 000",
    "Data de emissão: 15/07/2026",
    "",
    "Nº. DA UNIDADE CONSUMIDORA",
    "00.000.000.018-17",
    "",
    "Itens da Fatura",
    "Energia Eletrica        KWh        228        1,29075334        275,64        30,37",
    "Ilum. Publica Municipal                                        5,62",
    "TOTAL                                                          306,01",
    "",
    "Informacoes Tecnicas",
    "Tipo de Medicao     Medicao     Leitura Anterior     Leitura Atual     "
    "Constante de Multiplicacao     Consumo kWh",
    "Energia KWh     PPC257033321     3.056     3.284     1     228",
    "",
    "Historico de Consumo",
    "MES/ANO     Cons. kWh     Media kWh/Dia     Dias",
    "JUL/26     228     7,12     32",
    "JUN/26     213     6,87     31",
    "MAI/26     224     7,00     32",
    "ABR/26     205     7,06     29",
    "MAR/26     198     6,63     30",
    "FEV/26     198     7,17     28",
    "JAN/26     292     9,17     32",
    "DEZ/25     231     7,45     31",
]

for linha in linhas:
    pdf.multi_cell(0, 5, txt=linha, new_x="LMARGIN", new_y="NEXT")

pdf.output("tests/fixtures/fatura.pdf")


# scripts/gerar_fixture_pdf.py (roda uma vez, não precisa ir ao repo — mas pode ir)
from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=12)

# linhas = [
#     "Distribuidora: CEMIG Distribuicao S.A.",
#     "Nota Fiscal / Fatura: 0000000000",
#     "Numero do Cliente: 00000000  /  Instalacao: 0000000000",
#     "Mes de referencia: JANEIRO/2025",
#     "Vencimento: 20/02/2025",
#     "Valor a pagar (R$): 123,45",
#     "Total de consumo (kWh): 150",
#     "Bandeira tarifaria: VERDE",
# ]



for linha in linhas:
    pdf.cell(200, 8, txt=linha, new_x="LMARGIN", new_y="NEXT")

pdf.output("tests/fixtures/fatura.pdf")

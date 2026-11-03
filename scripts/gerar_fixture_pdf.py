# scripts/gerar_fixture_pdf.py (roda uma vez, não precisa ir ao repo — mas pode ir)
from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=12)

linhas = [
    "Distribuidora: CEMIG Distribuicao S.A.",
    "Nota Fiscal / Fatura: 0000000000",
    "Numero do Cliente: 00000000  /  Instalacao: 0000000000",
    "Mes de referencia: JANEIRO/2025",
    "Vencimento: 20/02/2025",
    "Valor a pagar (R$): 123,45",
    "Total de consumo (kWh): 150",
    "Bandeira tarifaria: VERDE",
]
for linha in linhas:
    pdf.cell(200, 8, txt=linha, new_x="LMARGIN", new_y="NEXT")

pdf.output("tests/fixtures/fatura.pdf")

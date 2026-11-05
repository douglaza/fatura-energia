"""Gera o arquivo Excel do dashboard de consumo com OpenPyXL.

Quatro abas:
1. Resumo Executivo — KPIs (consumo médio, maior/menor mês, valor médio, tendência).
2. Histórico — tabela de consumo mensal (vinda do banco).
3. Faturas — detalhamento das faturas (código, titular, valor, vencimento).
4. Gráficos — LineChart (consumo), BarChart (valor da conta), barras de variação %.
"""

from __future__ import annotations

from io import BytesIO
import pandas as pd

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from app.analytics.indicadores import calcular_indicadores
from app.analytics.relatorios import df_consumo_mensal, df_faturas
from app.core.database import SessionLocal

# Cores da identidade visual (tons de azul CEMIG)
AZUL_ESCURO = "1F4E79"
AZUL_MEDIO = "2E75B6"
AZUL_CLARO = "DDEBF7"
CINZA = "F2F2F2"


def gerar_dashboard_excel(db=None) -> bytes:
    """Gera o conteúdo do arquivo dashboard_consumo.xlsx em bytes.

    Se ``db`` for None, abre uma sessão própria do banco (útil para uso
    standalone fora do FastAPI).
    """
    if db is None:
        db = SessionLocal()
        dono = True
    else:
        dono = False
    try:
        return _montar_workbook(db)
    finally:
        if dono:
            db.close()


def _estilo_cabecalho(ws, row, n_cols):
    """Aplica estilo de cabeçalho de tabela em uma linha da planilha."""
    fill = PatternFill("solid", fgColor=AZUL_ESCURO)
    font = Font(color="FFFFFF", bold=True, size=11)
    alinhamento = Alignment(horizontal="center", vertical="center", wrap_text=True)
    fina = Side(style="thin", color="BFBFBF")
    borda = Border(left=fina, right=fina, top=fina, bottom=fina)
    for col in range(1, n_cols + 1):
        celula = ws.cell(row=row, column=col)
        celula.fill = fill
        celula.font = font
        celula.alignment = alinhamento
        celula.border = borda


def _montar_workbook(db) -> bytes:
    indicadores = calcular_indicadores(db)
    df_mensal = df_consumo_mensal(db)
    df_faturas_df = df_faturas(db)

    wb = Workbook()

    # =====================================================================
    # Aba 1: Resumo Executivo
    # =====================================================================
    ws_resumo = wb.active
    ws_resumo.title = "Resumo Executivo"

    ws_resumo["A1"] = "Dashboard de Consumo de Energia — CEMIG"
    ws_resumo["A1"].font = Font(bold=True, size=16, color=AZUL_ESCURO)

    ws_resumo["A3"] = "Indicador"
    ws_resumo["B3"] = "Valor"
    _estilo_cabecalho(ws_resumo, 3, 2)

    resumo = [
        ("Consumo médio (kWh)", indicadores["consumo_medio"], "0.00"),
        (
            "Projeção próximo mês (kWh)",
            indicadores["projecao_consumo"],
            "0.00",
        ),
        ("Maior consumo (kWh)", indicadores["maior_consumo"], "0.00"),
        ("Mês do maior consumo", indicadores["mes_maior_consumo"], "@"),
        ("Menor consumo (kWh)", indicadores["menor_consumo"], "0.00"),
        ("Mês do menor consumo", indicadores["mes_menor_consumo"], "@"),
        ("Valor médio (R$)", indicadores["valor_medio"], '"R$ "#,##0.00'),
        ("Gasto total (R$)", indicadores["gasto_anual"], '"R$ "#,##0.00'),
        ("Total de faturas", indicadores["total_faturas"], "0"),
        ("Tendência", indicadores["tendencia"], "@"),
    ]

    linha = 4
    for nome, valor, formato in resumo:
        ws_resumo.cell(row=linha, column=1, value=nome)
        celula = ws_resumo.cell(row=linha, column=2, value=valor)
        celula.number_format = formato
        linha += 1

    ultima = indicadores.get("ultima_fatura")
    if ultima:
        ws_resumo.cell(row=linha + 1, column=1, value="Última fatura")
        ws_resumo.cell(
            row=linha + 1,
            column=2,
            value=f"{ultima['mes']} — R$ {ultima['valor']:,.2f}",
        )

    ws_resumo.column_dimensions["A"].width = 30
    ws_resumo.column_dimensions["B"].width = 22

    # =====================================================================
    # Aba 2: Histórico
    # =====================================================================
    ws_historico = wb.create_sheet("Histórico")
    ws_historico["A1"] = "Histórico de Consumo Mensal (kWh)"
    ws_historico["A1"].font = Font(bold=True, size=14, color=AZUL_ESCURO)

    if not df_mensal.empty:
        cabecalho = ["Mês", "Consumo (kWh)", "Valor (R$)"]
        ws_historico.append(cabecalho)
        _estilo_cabecalho(ws_historico, 2, 3)

        linha = 3
        for _, row in df_mensal.iterrows():
            ws_historico.cell(row=linha, column=1, value=row["mes_referencia"])
            c2 = ws_historico.cell(row=linha, column=2, value=round(float(row["consumo_kwh"]), 2))
            c2.number_format = "0.00"
            if pd.notna(row["valor_total"]):
                c3 = ws_historico.cell(
                    row=linha,
                    column=3,
                    value=round(float(row["valor_total"]), 2),
                )
                c3.number_format = '"R$ "#,##0.00'
            linha += 1

        ultimo = linha - 1
        ref = f"A2:C{ultimo}"
        tabela = Table(displayName="TabelaHistorico", ref=ref)
        estilo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        tabela.tableStyleInfo = estilo
        ws_historico.add_table(tabela)

        ws_historico.column_dimensions["A"].width = 15
        ws_historico.column_dimensions["B"].width = 20
        ws_historico.column_dimensions["C"].width = 18
    else:
        ws_historico["A3"] = "Não há dados de consumo disponíveis."

    # =====================================================================
    # Aba 3: Faturas
    # =====================================================================
    ws_faturas = wb.create_sheet("Faturas")
    ws_faturas["A1"] = "Detalhamento de Faturas"
    ws_faturas["A1"].font = Font(bold=True, size=14, color=AZUL_ESCURO)

    if not df_faturas_df.empty:
        colunas = [
            "Código",
            "Titular",
            "Mês Ref.",
            "Valor Total",
            "Consumo kWh",
            "Vencimento",
        ]
        ws_faturas.append(colunas)
        _estilo_cabecalho(ws_faturas, 2, len(colunas))

        linha = 3
        for _, row in df_faturas_df.iterrows():
            ws_faturas.cell(row=linha, column=1, value=row["codigo_fatura"])
            ws_faturas.cell(row=linha, column=2, value=row["titular"])
            ws_faturas.cell(row=linha, column=3, value=row["mes_referencia"])
            c = ws_faturas.cell(row=linha, column=4, value=round(float(row["valor_total"]), 2))
            c.number_format = '"R$ "#,##0.00'
            c = ws_faturas.cell(
                row=linha, column=5, value=round(float(row["consumo_kwh"] or 0), 2)
            )
            c.number_format = "0.00"
            v = row["vencimento"]
            texto_venc = v.strftime("%d/%m/%Y") if hasattr(v, "strftime") else str(v)
            ws_faturas.cell(row=linha, column=6, value=texto_venc)
            linha += 1

        ultimo = linha - 1
        ref = f"A2:{get_column_letter(len(colunas))}{ultimo}"
        tabela = Table(displayName="TabelaFaturas", ref=ref)
        estilo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        tabela.tableStyleInfo = estilo
        ws_faturas.add_table(tabela)

        larguras = [22, 30, 12, 14, 14, 14]
        for i, largura in enumerate(larguras, start=1):
            ws_faturas.column_dimensions[get_column_letter(i)].width = largura
    else:
        ws_faturas["A3"] = "Não há faturas cadastradas."

    # =====================================================================
    # Aba 4: Gráficos
    # =====================================================================
    ws_graficos = wb.create_sheet("Gráficos")
    ws_graficos["A1"] = "Gráficos de Consumo"
    ws_graficos["A1"].font = Font(bold=True, size=14, color=AZUL_ESCURO)

    if not df_mensal.empty:
        # Tabela auxiliar (coluna A-C) que alimenta os gráficos
        linha_dados = 3
        for col, nome in enumerate(["Mês", "Consumo (kWh)", "Valor (R$)"], start=1):
            celula = ws_graficos.cell(row=linha_dados, column=col, value=nome)
            celula.fill = PatternFill("solid", fgColor=AZUL_ESCURO)
            celula.font = Font(color="FFFFFF", bold=True)
            celula.alignment = Alignment(horizontal="center")

        r = linha_dados + 1
        for _, row in df_mensal.iterrows():
            ws_graficos.cell(row=r, column=1, value=row["mes_referencia"])
            ws_graficos.cell(row=r, column=2, value=round(float(row["consumo_kwh"]), 2))
            if pd.notna(row["valor_total"]):
                c = ws_graficos.cell(
                    row=r,
                    column=3,
                    value=round(float(row["valor_total"]), 2),
                )
                c.number_format = '"R$ "#,##0.00'
            r += 1
        ultima_linha = r - 1

        categorias = Reference(
            ws_graficos, min_col=1, min_row=linha_dados + 1, max_row=ultima_linha
        )

        # Gráfico de linha: consumo mensal
        grafico_linha = LineChart()
        grafico_linha.title = "Consumo Mensal (kWh)"
        grafico_linha.style = 12
        grafico_linha.y_axis.title = "kWh"
        grafico_linha.x_axis.title = "Mês"
        dados = Reference(ws_graficos, min_col=2, min_row=linha_dados, max_row=ultima_linha)
        grafico_linha.add_data(dados, titles_from_data=True)
        grafico_linha.set_categories(categorias)
        grafico_linha.height = 9
        grafico_linha.width = 26
        ws_graficos.add_chart(grafico_linha, "A4")

        # Gráfico de colunas: valor da conta
        grafico_coluna = BarChart()
        grafico_coluna.type = "col"
        grafico_coluna.title = "Valor da Conta (R$)"
        grafico_coluna.style = 10
        grafico_coluna.y_axis.title = "R$"
        grafico_coluna.x_axis.title = "Mês"
        dados2 = Reference(ws_graficos, min_col=3, min_row=linha_dados, max_row=ultima_linha)
        grafico_coluna.add_data(dados2, titles_from_data=True)
        grafico_coluna.set_categories(categorias)
        grafico_coluna.height = 9
        grafico_coluna.width = 26
        ws_graficos.add_chart(grafico_coluna, "A22")

        # Variação % (gráfico de barras)
        ws_graficos.cell(row=linha_dados, column=5, value="Variação %")
        celula = ws_graficos.cell(row=linha_dados, column=5)
        celula.fill = PatternFill("solid", fgColor=AZUL_ESCURO)
        celula.font = Font(color="FFFFFF", bold=True)
        celula.alignment = Alignment(horizontal="center")

        consumos = df_mensal["consumo_kwh"].tolist()
        variacoes = [None]
        for i in range(1, len(consumos)):
            if consumos[i - 1]:
                variacoes.append(round((consumos[i] - consumos[i - 1]) / consumos[i - 1] * 100, 1))
            else:
                variacoes.append(None)

        r = linha_dados + 1
        for v in variacoes[1:]:
            ws_graficos.cell(row=r, column=5, value=v)
            r += 1

        grafico_barra = BarChart()
        grafico_barra.type = "bar"
        grafico_barra.title = "Variação % do Consumo Mensal"
        grafico_barra.style = 11
        dados3 = Reference(ws_graficos, min_col=5, min_row=linha_dados, max_row=ultima_linha)
        grafico_barra.add_data(dados3, titles_from_data=True)
        grafico_barra.set_categories(categorias)
        grafico_barra.height = 9
        grafico_barra.width = 26
        ws_graficos.add_chart(grafico_barra, "A40")

    else:
        ws_graficos["A4"] = "Não há dados suficientes para gerar gráficos."

    # Salva em buffer de bytes
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.read()
from io import BytesIO

import pandas as pd
from openpyxl import load_workbook

from app.analytics import dashboard_excel, indicadores


def test_dashboard_excel_inclui_projecao_dos_tres_meses_mais_recentes(monkeypatch):
    dados = [
        {"mes": "2026-01", "kwh": 100, "valor": 100, "codigo": "1", "titular": "A", "vencimento": None},
        {"mes": "2026-02", "kwh": 200, "valor": 100, "codigo": "2", "titular": "A", "vencimento": None},
        {"mes": "2026-03", "kwh": 300, "valor": 100, "codigo": "3", "titular": "A", "vencimento": None},
        {"mes": "2026-04", "kwh": 400, "valor": 100, "codigo": "4", "titular": "A", "vencimento": None},
    ]
    monkeypatch.setattr(indicadores, "_consumo_por_fatura", lambda _db: dados)
    monkeypatch.setattr(
        dashboard_excel,
        "df_consumo_mensal",
        lambda _db: pd.DataFrame(columns=["mes_referencia", "consumo_kwh", "valor_total"]),
    )
    monkeypatch.setattr(
        dashboard_excel,
        "df_faturas",
        lambda _db: pd.DataFrame(columns=["codigo_fatura"]),
    )

    arquivo = dashboard_excel.gerar_dashboard_excel(db=object())
    planilha = load_workbook(BytesIO(arquivo), data_only=True)["Resumo Executivo"]

    assert indicadores.calcular_indicadores(None)["projecao_consumo"] == 300
    assert planilha["A5"].value == "Projeção próximo mês (kWh)"
    assert planilha["B5"].value == 300


def test_projecao_sem_historico_e_indisponivel(monkeypatch):
    monkeypatch.setattr(indicadores, "_consumo_por_fatura", lambda _db: [])

    assert indicadores.calcular_indicadores(None)["projecao_consumo"] is None
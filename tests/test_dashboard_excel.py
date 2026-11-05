from io import BytesIO
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
from openpyxl import load_workbook

from app.analytics import dashboard_excel, indicadores
from app.models.consumo import Consumo
from app.models.fatura import Fatura


def test_dashboard_excel_inclui_projecao_dos_tres_meses_mais_recentes(monkeypatch):
    dados = [
        {"mes": "2026-01", "kwh": 100, "valor": 100, "codigo": "1", "titular": "A", "vencimento": None},
        {"mes": "2026-02", "kwh": 200, "valor": 100, "codigo": "2", "titular": "A", "vencimento": None},
        {"mes": "2026-03", "kwh": 300, "valor": 100, "codigo": "3", "titular": "A", "vencimento": None},
        {"mes": "2026-04", "kwh": 400, "valor": 100, "codigo": "4", "titular": "A", "vencimento": None},
    ]
    monkeypatch.setattr(indicadores, "_consumo_por_fatura", lambda _db: dados)
    monkeypatch.setattr(indicadores, "_dados_consumo_mensal", lambda _db: dados)
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
    monkeypatch.setattr(indicadores, "_dados_consumo_mensal", lambda _db: [])

    assert indicadores.calcular_indicadores(None)["projecao_consumo"] is None


def test_dashboard_usa_leituras_mensais_sem_somar_todo_o_historico(db):
    fatura = Fatura(
        codigo_fatura="FATURA-TESTE-DASH",
        instalacao="1234567890",
        titular="CLIENTE DE TESTE",
        mes_referencia="2026-10",
        data_emissao=datetime(2026, 10, 15),
        vencimento=datetime(2026, 11, 22),
        valor_total=Decimal("344.83"),
        consumo_kwh=Decimal("80"),
        consumos=[
            Consumo(data_leitura=date(2026, 7, 15), kwh=50),
            Consumo(data_leitura=date(2026, 8, 15), kwh=60),
            Consumo(data_leitura=date(2026, 9, 15), kwh=70),
            Consumo(data_leitura=date(2026, 10, 15), kwh=80),
        ],
    )
    db.add(fatura)
    db.commit()

    indicadores_calculados = indicadores.calcular_indicadores(db)
    arquivo = dashboard_excel.gerar_dashboard_excel(db)
    workbook = load_workbook(BytesIO(arquivo), data_only=True)
    historico = workbook["Histórico"]
    graficos = workbook["Gráficos"]

    assert indicadores_calculados["consumo_medio"] == 65
    assert indicadores_calculados["maior_consumo"] == 80
    assert indicadores_calculados["menor_consumo"] == 50
    assert indicadores_calculados["projecao_consumo"] == 70
    assert indicadores_calculados["valor_medio"] == 344.83
    assert indicadores_calculados["gasto_anual"] == 344.83
    assert [historico.cell(row, 2).value for row in range(3, 7)] == [50, 60, 70, 80]
    assert len(graficos._charts) == 3
    assert [graficos.cell(row, 5).value for row in range(5, 7)] == [16.7, 14.3]
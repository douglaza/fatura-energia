from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.consumo import Consumo
from app.models.fatura import Fatura


def criar_fatura(db, mes, kwh, valor):
    fatura = Fatura(
        codigo_fatura=f"AI-{mes}",
        instalacao="1234567890",
        titular="CLIENTE DE TESTE",
        mes_referencia=mes,
        data_emissao=datetime.fromisoformat(f"{mes}-10"),
        vencimento=datetime.fromisoformat(f"{mes}-25"),
        valor_total=Decimal(str(valor)),
        consumo_kwh=Decimal(str(kwh)),
        consumos=[Consumo(data_leitura=date.fromisoformat(f"{mes}-15"), kwh=kwh)],
    )
    db.add(fatura)
    db.commit()
    return fatura


def test_explicar_fatura_compara_com_mes_anterior(client, db):
    criar_fatura(db, "2026-09", 100, 120)
    criar_fatura(db, "2026-10", 120, 150)

    response = client.get("/ai/faturas/2026-10/explicar")

    assert response.status_code == 200
    assert "Outubro/2026" in response.json()["explicacao"]
    assert "aumento de 20,0%" in response.json()["explicacao"]
    assert "R$ 150,00" in response.json()["explicacao"]


def test_explicar_fatura_inexistente_retorna_404(client):
    assert client.get("/ai/faturas/2026-10/explicar").status_code == 404


@pytest.mark.parametrize(
    ("pergunta", "esperado"),
    [
        ("Qual foi meu maior consumo?", "Março/2026\n389,00 kWh"),
        ("Qual foi minha conta mais cara?", "Fevereiro/2026\nR$ 200,00"),
        ("Quanto consumi em 2026?", "O consumo registrado em 2026 foi de 639,00 kWh."),
        ("Quanto gasto em média?", "O gasto médio por fatura cadastrada é R$ 150,00."),
    ],
)
def test_chat_responde_perguntas_com_dados_do_banco(client, db, pergunta, esperado):
    criar_fatura(db, "2026-01", 100, 100)
    criar_fatura(db, "2026-02", 150, 200)
    criar_fatura(db, "2026-03", 389, 150)

    response = client.post("/ai/chat", json={"pergunta": pergunta})

    assert response.status_code == 200
    assert response.json()["resposta"] == esperado


def test_consultor_energetico_sem_historico_responde_com_limite_claro(client):
    response = client.post("/ai/consultor")

    assert response.status_code == 200
    assert "não há histórico" in response.json()["recomendacao"].lower()


def test_chat_rejeita_pergunta_vazia(client):
    response = client.post("/ai/chat", json={"pergunta": "   "})

    assert response.status_code == 422
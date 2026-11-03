from datetime import date
from decimal import Decimal

import pytest

FAATURA_BASE = {
    "codigo_fatura": "API-001",
    "instalacao": "1234567",
    "titular": "Douglas Laza",
    "mes_referencia": "2025-01",
    "data_emissao": "2025-01-10",
    "vencimento": "2025-01-25",
    "valor_total": 250.00,
    "consumo_kwh": 450,
}


def test_criar_fatura_201(client):
    response = client.post("/faturas", json=FAATURA_BASE)
    assert response.status_code == 201
    body = response.json()
    assert body["codigo_fatura"] == "API-001"
    assert body["id"] > 0
    assert body["consumos"] == []


def test_criar_fatura_codigo_duplicado_409(client):
    client.post("/faturas", json=FAATURA_BASE)
    response = client.post("/faturas", json=FAATURA_BASE)
    assert response.status_code == 409
    assert "API-001" in response.json()["detail"]


def test_listar_faturas(client):
    client.post("/faturas", json=FAATURA_BASE)
    client.post("/faturas", json={**FAATURA_BASE, "codigo_fatura": "API-002"})
    response = client.get("/faturas")
    assert response.status_code == 200
    codigos = [f["codigo_fatura"] for f in response.json()]
    assert codigos == ["API-001", "API-002"]


def test_obter_fatura_por_id(client):
    fatura_id = client.post("/faturas", json=FAATURA_BASE).json()["id"]
    response = client.get(f"/faturas/{fatura_id}")
    assert response.status_code == 200
    assert response.json()["codigo_fatura"] == "API-001"


def test_obter_fatura_inexistente_404(client):
    assert client.get("/faturas/9999").status_code == 404


def test_patch_atualiza_valor_total(client):
    fatura_id = client.post("/faturas", json=FAATURA_BASE).json()["id"]
    response = client.patch(f"/faturas/{fatura_id}", json={"valor_total": 300.00})
    assert response.status_code == 200
    assert Decimal(response.json()["valor_total"]) == Decimal("300.00")
    assert response.json()["titular"] == "Douglas Laza"



def test_patch_codigo_duplicado_409(client):
    client.post("/faturas", json=FAATURA_BASE)
    fatura2_id = client.post(
        "/faturas", json={**FAATURA_BASE, "codigo_fatura": "API-002"}
    ).json()["id"]
    response = client.patch(
        f"/faturas/{fatura2_id}", json={"codigo_fatura": "API-001"}
    )
    assert response.status_code == 409


def test_delete_retorna_204_e_remove(client):
    fatura_id = client.post("/faturas", json=FAATURA_BASE).json()["id"]
    assert client.delete(f"/faturas/{fatura_id}").status_code == 204
    assert client.get(f"/faturas/{fatura_id}").status_code == 404


def test_delete_inexistente_404(client):
    assert client.delete("/faturas/9999").status_code == 404


def test_validacao_mes_referencia_422(client):
    response = client.post("/faturas", json={**FAATURA_BASE, "mes_referencia": "01/2025"})
    assert response.status_code == 422


def test_validacao_valor_total_positivo_422(client):
    response = client.post("/faturas", json={**FAATURA_BASE, "valor_total": -1})
    assert response.status_code == 422


# --- Consumos aninhados ---


def test_criar_consumo_na_fatura(client):
    fatura_id = client.post("/faturas", json=FAATURA_BASE).json()["id"]
    payload = {"data_leitura": "2025-01-10", "kwh": 220}
    response = client.post(f"/faturas/{fatura_id}/consumos", json=payload)
    assert response.status_code == 201
    assert response.json()["kwh"] == 220
    assert response.json()["fatura_id"] == fatura_id


def test_consumos_aparecem_no_read_da_fatura(client):
    fatura_id = client.post("/faturas", json=FAATURA_BASE).json()["id"]
    client.post(
        f"/faturas/{fatura_id}/consumos",
        json={"data_leitura": "2025-01-10", "kwh": 220},
    )
    client.post(
        f"/faturas/{fatura_id}/consumos",
        json={"data_leitura": "2025-01-20", "kwh": 230},
    )
    response = client.get(f"/faturas/{fatura_id}")
    consumos = response.json()["consumos"]
    assert len(consumos) == 2
    assert {c["kwh"] for c in consumos} == {220, 230}


def test_criar_consumo_fatura_inexistente_404(client):
    response = client.post(
        "/faturas/9999/consumos",
        json={"data_leitura": "2025-01-10", "kwh": 100},
    )
    assert response.status_code == 404


def test_listar_consumos_fatura_inexistente_404(client):
    assert client.get("/faturas/9999/consumos").status_code == 404

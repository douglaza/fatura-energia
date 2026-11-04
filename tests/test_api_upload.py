from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
PDF = FIXTURES / "fatura.pdf"

CODIGO_FATURA = "043171166"
TITULAR = "RENAT DOS SANTOS PIMENTEL"
MES_REFERENCIA = "2026-07"


def test_upload_fatura_pdf(client: TestClient):
    with open(PDF, "rb") as f:
        response = client.post(
            "/faturas/upload",
            files={"pdf": ("fatura.pdf", f, "application/pdf")},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["codigo_fatura"] == CODIGO_FATURA
    assert body["titular"] == TITULAR
    assert body["mes_referencia"] == MES_REFERENCIA
    assert float(body["valor_total"]) > 0
    assert len(body["consumos"]) >= 1


def test_upload_pdf_duplicado_409(client, fixture_pdf):
    resp1 = client.post("/faturas/upload", files=fixture_pdf)
    assert resp1.status_code == 201
    id_criado = resp1.json()["id"]

    resp2 = client.post("/faturas/upload", files=fixture_pdf)
    assert resp2.status_code == 409
    assert "duplicad" in resp2.json()["detail"].lower()


def test_upload_arquivo_invalido_422(client: TestClient):
    response = client.post(
        "/faturas/upload",
        files={"pdf": ("fake.pdf", b"isto nao e um pdf", "application/pdf")},
    )
    assert response.status_code == 422


def test_upload_pdf_sucesso(client, fixture_pdf):
    resp = client.post("/faturas/upload", files=fixture_pdf)

    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data, f"Resposta sem 'id': {data}"
    assert isinstance(data["id"], int)

    get = client.get(f"/faturas/{data['id']}")
    assert get.status_code == 200
    assert get.json()["id"] == data["id"]

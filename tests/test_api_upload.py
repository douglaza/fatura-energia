from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
PDF = FIXTURES / "fatura.pdf"


def test_upload_fatura_pdf(client: TestClient):
    with open(PDF, "rb") as f:
        response = client.post(
            "/faturas/upload",
            files={"pdf": ("fatura.pdf", f, "application/pdf")},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["codigo_fatura"] == "439886813"
    assert body["titular"] == "ANNA PAULA VIEIRA ROCHA CASTRO"
    assert body["mes_referencia"] == "2026-10"
    assert float(body["valor_total"]) > 0
    assert len(body["consumos"]) >= 1


def test_upload_pdf_duplicado_409(client: TestClient):
    with open(PDF, "rb") as f:
        r1 = client.post("/faturas/upload",
                         files={"pdf": ("fatura.pdf", f, "application/pdf")})
    assert r1.status_code == 201

    with open(PDF, "rb") as f:
        r2 = client.post("/faturas/upload",
                         files={"pdf": ("fatura.pdf", f, "application/pdf")})
    assert r2.status_code == 409


def test_upload_arquivo_invalido_422(client: TestClient):
    response = client.post(
        "/faturas/upload",
        files={"pdf": ("fake.pdf", b"isto nao e um pdf", "application/pdf")},
    )
    assert response.status_code == 422

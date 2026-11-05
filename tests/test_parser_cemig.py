from datetime import date
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
PDF = FIXTURES / "fatura.pdf"


# ---------- fixture: texto extraído do PDF ----------

def _extrair_texto(pdf_path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(str(pdf_path)).pages)
    except ImportError:
        pass
    try:
        from PyPDF2 import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(str(pdf_path)).pages)
    except ImportError:
        pytest.skip("Nenhuma lib de PDF instalada (pdfplumber/pypdf/PyPDF2)")


@pytest.fixture(scope="module")
def texto_fatura() -> str:
    assert PDF.exists(), f"Fixture não encontrada: {PDF}"
    return _extrair_texto(PDF)


@pytest.fixture(scope="module")
def resultado(texto_fatura):
    from app.parser.cemig import parse_fatura
    return parse_fatura(texto_fatura)


# ---------- helpers ----------

def _num_br(s: str) -> str:
    return s.replace(".", "").replace(",", ".")


# ---------- testes ----------

def test_parse_extrai_codigo_fatura(resultado):
    assert resultado["codigo_fatura"] is not None
    assert resultado["codigo_fatura"].isdigit()


def test_parse_extrai_instalacao(resultado):
    assert resultado["instalacao"] is not None
    assert resultado["instalacao"] != ""


def test_parse_extrai_titular(resultado):
    assert resultado["titular"] is not None
    assert resultado["titular"].isupper() or " " in resultado["titular"]


def test_parse_extrai_mes_referencia(resultado):
    import re
    assert resultado["mes_referencia"] is not None
    assert re.fullmatch(r"\d{4}-\d{2}", resultado["mes_referencia"])
    ano, mes = resultado["mes_referencia"].split("-")
    assert 1 <= int(mes) <= 12


def test_parse_extrai_datas(resultado):
    assert isinstance(resultado["data_emissao"], date)
    assert isinstance(resultado["vencimento"], date)
    assert resultado["vencimento"] >= resultado["data_emissao"]


def test_parse_extrai_valor_total(resultado):
    valor = resultado["valor_total"]
    assert valor is not None
    # conversível para Decimal (formato numérico brasileiro normalizado)
    from decimal import Decimal
    assert Decimal(str(valor)) > 0


def test_parse_extrai_consumo_kwh(resultado):
    consumo = resultado["consumo_kwh"]
    assert consumo is not None
    assert float(consumo) > 0


def test_parse_extrai_historico_consumos(resultado):
    consumos = resultado["consumos"]
    assert len(consumos) >= 1
    for c in consumos:
        assert isinstance(c["data_leitura"], date)
        assert c["kwh"] > 0
        assert c["descricao"]  # texto com média/dias


def test_consumo_mes_corresponde_ao_historico(resultado):
    """consumo_kwh deve bater com a linha do histórico do mês de referência."""
    consumos = resultado["consumos"]
    if not consumos:
        pytest.skip("sem histórico extraído")

    ano_ref, mes_ref = resultado["mes_referencia"].split("-")
    candidatos = [c for c in consumos
                  if c["data_leitura"].year == int(ano_ref)
                  and c["data_leitura"].month == int(mes_ref)]

    assert candidatos, "histórico não contém linha do mês de referência"
    assert float(resultado["consumo_kwh"]) == float(candidatos[-1]["kwh"])


def test_parse_texto_vazio():
    from app.parser.cemig import parse_fatura
    r = parse_fatura("")
    assert all(v in (None, []) for v in r.values())


def test_parse_titular_e_historico_com_texto_de_outra_coluna():
    from app.parser.cemig import parse_fatura

    texto = """DOCUMENTO AUXILIAR DA NOTA FISCAL DE ENERGIA ELÉTRICA
CEMIG DISTRIBUIÇÃO S.A.
AV. BARBACENA, 1200 - BELO HORIZONTE - MG
CLIENTE DE TESTE Referente a Vencimento Valor a pagar (R$)
OUT/2026 22/11/2026 344,83
Histórico de Consumo
OUT/26 268 8,93 30
ABR/26 205 7,06 29 Reservado ao Fisco
"""

    resultado = parse_fatura(texto)

    assert resultado["titular"] == "CLIENTE DE TESTE"
    assert resultado["mes_referencia"] == "2026-10"
    assert [consumo["data_leitura"].strftime("%Y-%m") for consumo in resultado["consumos"]] == [
        "2026-10",
        "2026-04",
    ]


def test_parse_mes_referencia_e_vencimento_no_layout_tabular():
    from app.parser.cemig import parse_fatura

    texto = """DOCUMENTO AUXILIAR DA NOTA FISCAL DE ENERGIA ELÉTRICA
NOTA FISCAL Nº 123456 - SÉRIE 000
TITULAR EXEMPLO
UNIDADE CONSUMIDORA 1234567890
Referente a Vencimento Valor a pagar (R$)
RUA EXEMPLO 10 AP 1 JUL/2026 22/08/2026 306,01
Data de emissão: 01/08/2026
TOTAL 306,01
Energia kWh PPC123456789 3.056 3.284 1 228
JUL/26 228 7,12 32
"""

    resultado = parse_fatura(texto)

    assert resultado["mes_referencia"] == "2026-07"
    assert resultado["vencimento"] == date(2026, 8, 22)

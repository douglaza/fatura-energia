from app.pipeline import processar_pdf

from app.parser.pdf import extrair_texto
from app.parser.cemig import parse_fatura

def test_persiste_e_e_idempotente(db, fixture_pdf):
    id1 = processar_pdf(fixture_pdf["pdf"][1], db)
    # print(parse_fatura(extrair_texto(open("tests/fixtures/fatura_exemplo.pdf","rb").read())))
    assert id1 is not None
    assert processar_pdf(fixture_pdf["pdf"][1], db) is None  # 2ª vez: já existe

from app.pipeline import processar_pdf

def test_persiste_e_e_idempotente(db, fixture_pdf):
    id1 = processar_pdf(fixture_pdf, db)
    assert id1 is not None
    assert processar_pdf(fixture_pdf, db) is None  # 2ª vez: já existe

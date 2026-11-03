from datetime import date

from app.models.consumo import Consumo
from app.models.fatura import Fatura


def test_criar_fatura_com_consumos(db_session):
    fatura = Fatura(
        codigo_fatura="REL-001",
        instalacao="1234567",
        titular="Douglas Laza",
        mes_referencia="2025-01",
        data_emissao=date(2025, 1, 10),
        vencimento=date(2025, 1, 25),
        valor_total=250.00,
        consumo_kwh=450,
    )
    db_session.add(fatura)
    db_session.flush()  # gera o id sem commitar

    c1 = Consumo(fatura_id=fatura.id, data_leitura=date(2025, 1, 10), kwh=220)
    c2 = Consumo(fatura_id=fatura.id, data_leitura=date(2025, 2, 10), kwh=230)
    db_session.add_all([c1, c2])
    db_session.flush()

    # Testa o relacionamento
    assert len(fatura.consumos) == 2
    assert {c.kwh for c in fatura.consumos} == {220, 230}
    assert c1.fatura.codigo_fatura == "REL-001"
    # O rollback do fixture desfaz tudo — nada vai pro banco real


def test_exclusao_cascade(db_session):
    fatura = Fatura(
        codigo_fatura="REL-002",
        instalacao="1234567",
        titular="Douglas Laza",
        mes_referencia="2025-02",
        data_emissao=date(2025, 2, 10),
        vencimento=date(2025, 2, 25),
        valor_total=180.00,
        consumo_kwh=300,
    )
    db_session.add(fatura)
    db_session.flush()

    db_session.add(Consumo(fatura_id=fatura.id, data_leitura=date(2025, 2, 10), kwh=300))
    db_session.flush()

    db_session.delete(fatura)
    db_session.flush()

    sobrou = db_session.query(Consumo).filter_by(fatura_id=fatura.id).count()
    assert sobrou == 0  # depende do cascade="all, delete-orphan" no relationship


# from decimal import Decimal
# from datetime import date

# from sqlalchemy.orm import Session
# from app.core.database import engine
# from app.models import Fatura, Consumo

# from sqlalchemy import select

# # session = Session(engine)

# with Session(engine) as session:
#     # 1. Cria uma fatura com dois consumos pendurados
#     fatura = Fatura(
#         codigo_fatura="TESTE-001",
#         instalacao="1234567",
#         titular="Douglas Laza",
#         mes_referencia="2025-01",
#         data_emissao=date(2025, 1, 10),
#         vencimento=date(2025, 1, 25),
#         valor_total=Decimal("250.00"),
#         consumo_kwh=Decimal("450.00"),
#         consumos=[
#             Consumo(data_leitura=date(2025, 1, 10), kwh=150.0),
#             Consumo(data_leitura=date(2025, 1, 20), kwh=300.0),
#         ],
#     )
#     session.add(fatura)
#     session.commit()
#     print(f"Fatura criada com id={fatura.id}")

#     # 2. Limpa a sessão e recarrega TUDO do banco
#     session.expunge_all()

#     # 3. Navega Fatura → Consumos
#     # fatura_db = session.exec(
#     #     select(Fatura).where(Fatura.codigo_fatura == "TESTE-001")
#     # ).one()
#     fatura_db = session.execute(
#         select(Fatura).where(Fatura.codigo_fatura == "TESTE-001")
#     ).scalar_one()
#     print(f"\nFatura {fatura_db.codigo_fatura} tem {len(fatura_db.consumos)} consumos:")
#     for c in fatura_db.consumos:
#         print(f"  - {c.data_leitura}: {c.kwh} kWh")

#     # 4. Navega Consumo → Fatura (o outro sentido!)
#     primeiro = fatura_db.consumos[0]
#     print(f"\nO consumo de {primeiro.kwh} kWh pertence à fatura "
#           f"{primeiro.fatura.codigo_fatura}")

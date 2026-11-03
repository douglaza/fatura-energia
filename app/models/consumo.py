# app/models/consumo.py
from sqlalchemy import Column, Integer, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Consumo(Base):
    __tablename__ = "consumos"

    id = Column(Integer, primary_key=True)
    fatura_id = Column(Integer, ForeignKey("faturas.id"), nullable=False)
    data_leitura = Column(Date, nullable=False)
    kwh = Column(Float, nullable=False)

    fatura = relationship("Fatura", back_populates="consumos")

"""Orquestra parser → persistência (e o download, quando disparado via CLI)."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.crud.fatura import criar_fatura, obter_fatura_por_codigo
from app.models.fatura import Fatura
from app.parser.pdf import extrair_texto
from app.parser.cemig import parse_fatura
from app.schemas.fatura import FaturaCreate
from app.core.config import settings



logger = logging.getLogger(__name__)

# RAW_DIR = Path("data/raw")
RAW_DIR = settings.download_dir


def processar_pdf(pdf_path: Path | bytes, db: Session) -> int | None:
    # texto = extrair_texto(pdf_path.read_bytes())
    if isinstance(pdf_path, Path):
        pdf_data = pdf_path.read_bytes()
    else:
        pdf_data = pdf_path
    texto = extrair_texto(pdf_data)

    dados = parse_fatura(texto)

    if not dados["codigo_fatura"]:
        raise ValueError(f"PDF sem nº de nota fiscal identificável: {pdf_path}")

    if obter_fatura_por_codigo(db, dados["codigo_fatura"]):
        logger.info("Fatura %s já registrada — ignorando.", dados["codigo_fatura"])
        return None

    consumos = dados.pop("consumos")
    fatura = criar_fatura(db, FaturaCreate(**dados, texto_extraido=texto))

    # persistir consumos — pelo crud, quando existir:
    # from app.crud.consumo import criar_consumos
    # criar_consumos(db, fatura.id, consumos)

    _renomear_com_referencia(pdf_path, fatura)
    return fatura.id


def _renomear_com_referencia(pdf_path: Path, fatura: Fatura) -> None:
    """Renomeia o PDF (timestamp) para um nome estável e identificável."""

    if not isinstance(pdf_path, Path):
        return
        
    destino = RAW_DIR / f"fatura_{fatura.codigo_fatura}.pdf"
    if destino != pdf_path:
        shutil.move(str(pdf_path), destino)
        logger.info("PDF renomeado: %s -> %s", pdf_path.name, destino.name)

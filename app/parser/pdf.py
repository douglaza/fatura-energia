from pathlib import Path

import pdfplumber


def extrair_texto(pdf_bytes: bytes) -> str:
    """Extrai o texto de um PDF (bytes) usando pdfplumber."""
    import io
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)

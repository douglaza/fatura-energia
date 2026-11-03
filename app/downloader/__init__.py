"""Automação de download de faturas no portal CEMIG.

Uso rápido::

    python -m app.downloader                    # baixa a fatura em aberto
    python -m app.downloader --mes 10/2026      # baixa um mês específico

⚠️ v1: o **login é manual em toda execução** — a persistência da sessão
(``storage_state.json``) está desativada de propósito. O browser abre na tela
de login, você resolve o reCAPTCHA e o robô segue para as faturas.

O PDF cai em ``CEMIG_DOWNLOAD_DIR`` (padrão ``data/raw/``).
"""

from app.downloader.auth import SessionExpired, SessionManager
from app.downloader.navegador import (
    FaturaNaoEncontrada,
    baixar_fatura,
    mes_por_extenso,
    normalizar_mes_referencia,
)

__all__ = [
    "FaturaNaoEncontrada",
    "SessionExpired",
    "SessionManager",
    "baixar_fatura",
    "mes_por_extenso",
    "normalizar_mes_referencia",
]

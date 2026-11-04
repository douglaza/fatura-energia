"""Configuração do portal CEMIG, usada pela automação de download.

Os valores vêm do `.env` com o prefixo ``CEMIG_`` (ex.: ``CEMIG_USER``).
Importar este módulo **nunca falha** por falta de credencial: a validação
acontece no momento do login (ver ``app/downloader/auth.py``), para que a
API continue subindo em ambientes onde a automação não é usada.

⚠️ v1: a persistência da sessão está desativada, então ``state_file``,
``token_refresh_margin_minutes`` e ``auth_mode`` estão comentados. Eles
voltam junto com o bloco ``[PERSISTÊNCIA]`` de ``app/downloader/auth.py``.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from typing import Literal

# from app.core.config import settings



class Settings(BaseSettings):
    """Parâmetros da navegação no portal CEMIG."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CEMIG_",
        extra="ignore",  # tolera variáveis do .env que não declaramos (DATABASE_URL…)
    )

    # --- Credenciais (opcionais: sem elas o login é 100% manual) ---
    user: str = ""          # e-mail ou CPF, igual ao digitado no site
    password: str = ""
    instalacao: str | None = None

    # ⚠️ Com login manual a cada execução, o browser precisa de tela:
    # mantenha ``False`` (o reCAPTCHA é resolvido pelo humano).
    headless: bool = False

    # --- URLs do portal ---
    base_url: str = "https://atende.cemig.com.br"
    login_url: str = "https://atende.cemig.com.br/Login"
    faturas_url: str = "https://atende.cemig.com.br/Login"

    # --- Arquivos ---
    download_dir: Path = Path("data/raw")

    # --- [PERSISTÊNCIA] reativar junto com o storage_state.py (ver auth.py) ---
    auth_mode: Literal["interactive", "reuse"] = "interactive"
    state_file: Path = Path("data/state/storage_state.json")
    token_refresh_margin_minutes: int = 15

    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )


settings = Settings()

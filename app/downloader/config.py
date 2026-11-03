from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class CemigSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CEMIG_",
        extra="ignore",
    )
    user: str = ""
    password: str = ""
    instalacao: str | None = None
    headless: bool = False
    base_url: str = "https://atende.cemig.com.br"
    login_url: str = "https://atende.cemig.com.br/Login"
    faturas_url: str = "https://atende.cemig.com.br/Login"
    download_dir: Path = Path("data/raw")
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

cemig_settings = CemigSettings()

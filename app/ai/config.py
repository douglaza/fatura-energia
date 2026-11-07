"""Configuração do servidor local Ollama (API compatível com OpenAI)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class OllamaSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OLLAMA_",
        extra="ignore",
    )

    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    model: str = "llama3.2:3b"
    timeout_seconds: float = 90


ollama_settings = OllamaSettings()
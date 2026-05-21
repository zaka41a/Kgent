from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _load_dotenv_once() -> None:
    if load_dotenv is None:
        return
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)
            break


_load_dotenv_once()


class Settings(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv("KGENT_HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(os.getenv("KGENT_PORT", "8088")))
    store_kind: Literal["json", "chroma", "auto"] = Field(
        default_factory=lambda: os.getenv("KGENT_STORE", "auto").lower()
    )
    store_path: Path = Field(
        default_factory=lambda: Path(os.getenv("KGENT_STORE_PATH", ".kgent_store/index.json"))
    )
    db_url: str = Field(
        default_factory=lambda: os.getenv("KGENT_DB_URL", "sqlite:///.kgent_store/chat.db")
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: _split_csv(
            os.getenv("KGENT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        )
    )
    log_level: str = Field(default_factory=lambda: os.getenv("KGENT_LOG_LEVEL", "INFO").upper())
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = Field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "mistral"))
    graph_mode: Literal["cooccurrence", "entity", "off"] = Field(
        default_factory=lambda: os.getenv("KGENT_GRAPH_MODE", "cooccurrence").lower()
    )
    graph_model: str = Field(
        default_factory=lambda: os.getenv("KGENT_GRAPH_MODEL", "")
    )


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def get_settings() -> Settings:
    return Settings()

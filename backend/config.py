from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = "gemini-2.5-flash"

    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openrouter_model: str = "deepseek/deepseek-chat"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    deepseek_model: str = "deepseek-chat"

    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")

    raptor_dir: Path = Field(
        default=Path("/home/dani/Documentos/Raptor/raptor"),
        validation_alias="RAPTOR_DIR",
    )
    raptor_bin: Path = Field(
        default=Path("/home/dani/Documentos/Raptor/raptor/bin/raptor"),
        validation_alias="RAPTOR_BIN",
    )

    raptor_default_target: str = Field(
        default="/tmp/test-repo",
        validation_alias="RAPTOR_DEFAULT_TARGET",
    )

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    max_prompt_length: int = 100_000
    max_concurrent_audits: int = 4

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

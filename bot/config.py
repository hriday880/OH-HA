"""
Configuration and Environment Variable Management.

Provides fail-fast environment validation, typed settings loading with Pydantic,
default values for cloud container environments, and secret masking.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, AliasChoices
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    _SETTINGS_BASE = BaseSettings
except ImportError:
    # Fallback to BaseModel if pydantic_settings is not yet installed
    _SETTINGS_BASE = BaseModel
    SettingsConfigDict = None  # type: ignore

logger = logging.getLogger(__name__)


def mask_secret(value: Optional[str], show_prefix: int = 3, show_suffix: int = 3) -> str:
    """Safely mask sensitive strings for logs and diagnostics."""
    if not value:
        return "[NOT SET]"
    val_str = str(value)
    if len(val_str) <= (show_prefix + show_suffix + 2):
        return "***"
    return f"{val_str[:show_prefix]}***{val_str[-show_suffix:]}"


class Config(_SETTINGS_BASE):
    """
    Unified Application Configuration.
    Loads from environment variables or .env file with validation and secret masking.
    """

    # Telegram Bot Settings
    telegram_bot_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN"),
        description="Telegram Bot API Token (from @BotFather)",
    )
    allowed_telegram_user_ids: List[int] = Field(
        default_factory=list,
        description="List of authorized Telegram user IDs for whitelist security",
    )

    # Primary LLM Provider Settings
    llm_provider: str = Field(
        default="openrouter",
        description="LLM provider: 'openrouter', 'groq', 'together', 'ollama', 'openai', or 'mock'",
    )
    llm_model: str = Field(
        default="nousresearch/hermes-3-llama-3.1-8b",
        description="Model identifier for the primary LLM provider",
    )
    llm_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "HERMES_API_KEY", "GROQ_API_KEY", "OPENHUMAN_API_KEY"),
        description="API key for the primary LLM provider",
    )
    llm_base_url: Optional[str] = Field(
        default=None,
        description="Custom base URL for OpenAI-compatible or local LLM endpoints",
    )
    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for LLM responses",
    )
    llm_max_tokens: int = Field(
        default=1024,
        gt=0,
        description="Maximum tokens per LLM completion",
    )
    llm_max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts on transient LLM rate limits/errors",
    )
    llm_retry_backoff: float = Field(
        default=1.0,
        ge=0.1,
        description="Base backoff multiplier in seconds for retries",
    )

    # Fallback LLM Provider Settings
    fallback_llm_provider: Optional[str] = Field(
        default=None,
        description="Secondary fallback LLM provider if primary fails",
    )
    fallback_llm_model: Optional[str] = Field(
        default=None,
        description="Model identifier for the secondary LLM provider",
    )
    fallback_llm_api_key: Optional[str] = Field(
        default=None,
        description="API key for the fallback LLM provider",
    )
    fallback_llm_base_url: Optional[str] = Field(
        default=None,
        description="Custom base URL for fallback provider",
    )

    # Obsidian Vault Settings
    vault_path: Path = Field(
        default=Path("./vault"),
        description="Local directory path to the Obsidian Markdown Vault",
    )
    auto_sync_interval_seconds: int = Field(
        default=1800,
        ge=0,
        description="Interval in seconds for periodic background Git sync (0 to disable)",
    )

    # Git Remote & Sync Settings
    git_remote_url: Optional[str] = Field(
        default=None,
        description="Remote Git repository URL (HTTPS or SSH) for Obsidian vault sync",
    )
    git_branch: str = Field(
        default="main",
        description="Git branch name to synchronize with",
    )
    git_auth_token: Optional[str] = Field(
        default=None,
        description="HTTPS Personal Access Token (PAT) for Git authentication",
    )
    git_ssh_key: Optional[str] = Field(
        default=None,
        description="Raw SSH private key or path to SSH key for Git authentication",
    )
    git_author_name: str = Field(
        default="OpenHuman Hermes Bot",
        description="Author name for automated Git commits",
    )
    git_author_email: str = Field(
        default="bot@openhuman.local",
        description="Author email for automated Git commits",
    )

    # Runtime & Container Infrastructure Settings
    port: int = Field(
        default=8080,
        gt=0,
        lt=65536,
        description="HTTP Port for the keepalive and health check server ($PORT)",
    )
    host: str = Field(
        default="0.0.0.0",
        description="Host address to bind the HTTP health server to",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    environment: str = Field(
        default="development",
        description="Execution environment ('development', 'production', 'test')",
    )
    max_reasoning_steps: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum multi-step reasoning/tool loop iterations for Hermes",
    )

    model_config = ConfigDict(
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("allowed_telegram_user_ids", mode="before")
    @classmethod
    def parse_allowed_user_ids(cls, v: Any) -> List[int]:
        """Parse comma-separated string, JSON list, int, or list of ints into List[int]."""
        if v is None or v == "":
            return []
        if isinstance(v, (int, float)):
            return [int(v)]
        if isinstance(v, str):
            v_str = v.strip()
            if not v_str:
                return []
            if v_str.startswith("[") and v_str.endswith("]"):
                try:
                    parsed = json.loads(v_str)
                    return [int(x) for x in parsed if str(x).strip()]
                except Exception:
                    pass
            # Comma-separated or whitespace separated
            ids: List[int] = []
            for part in v_str.replace(";", ",").split(","):
                part_clean = part.strip()
                if part_clean:
                    try:
                        ids.append(int(part_clean))
                    except ValueError:
                        logger.warning(f"Invalid user ID in allowed_telegram_user_ids: {part_clean}")
            return ids
        if isinstance(v, (list, tuple, set)):
            result: List[int] = []
            for item in v:
                try:
                    result.append(int(item))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid user ID in allowed_telegram_user_ids list: {item}")
            return result
        return []

    @field_validator("vault_path", mode="before")
    @classmethod
    def parse_vault_path(cls, v: Any) -> Path:
        """Convert str or Path to resolved/normalized Path."""
        if isinstance(v, Path):
            return v
        if isinstance(v, str):
            return Path(v)
        return Path("./vault")

    @field_validator("log_level", mode="before")
    @classmethod
    def parse_log_level(cls, v: Any) -> str:
        """Normalize log level string."""
        if isinstance(v, str):
            return v.upper()
        return "INFO"

    @field_validator("llm_provider", mode="before")
    @classmethod
    def parse_llm_provider(cls, v: Any) -> str:
        """Normalize LLM provider string."""
        if isinstance(v, str):
            return v.lower().strip()
        return "openrouter"

    def is_user_allowed(self, user_id: int) -> bool:
        """
        Check if a given Telegram user ID is authorized.
        If allowed_telegram_user_ids is empty:
          - in 'test' environment: allows all for fixture flexibility
          - in other environments: blocks access to protect private vault unless explicitly configured
        """
        if not self.allowed_telegram_user_ids:
            return self.environment.lower() == "test"
        return int(user_id) in self.allowed_telegram_user_ids

    def mask_secrets(self) -> Dict[str, Any]:
        """Return a dictionary of configuration with sensitive credentials masked."""
        raw = self.model_dump() if hasattr(self, "model_dump") else self.__dict__.copy()
        secret_keys = {
            "telegram_bot_token",
            "llm_api_key",
            "fallback_llm_api_key",
            "git_auth_token",
            "git_ssh_key",
        }
        masked = {}
        for k, v in raw.items():
            if k in secret_keys:
                masked[k] = mask_secret(v)
            elif isinstance(v, Path):
                masked[k] = str(v)
            else:
                masked[k] = v
        return masked

    def get_masked_dict(self) -> Dict[str, Any]:
        """Alias for mask_secrets() to return masked configuration dictionary."""
        return self.mask_secrets()

    def validate_for_production(self) -> List[str]:
        """
        Perform fail-fast validation for production deployment.
        Returns a list of configuration error messages (empty if valid).
        """
        errors: List[str] = []
        if not self.telegram_bot_token and self.environment.lower() == "production":
            errors.append("TELEGRAM_BOT_TOKEN is required in production environment.")
        if not self.allowed_telegram_user_ids and self.environment.lower() == "production":
            errors.append("ALLOWED_TELEGRAM_USER_IDS must contain at least one user ID in production.")
        if self.llm_provider != "mock" and not self.llm_api_key and self.llm_provider not in ("ollama", "local"):
            if self.environment.lower() == "production":
                errors.append(f"LLM_API_KEY is required for provider '{self.llm_provider}' in production.")
        return errors

    def __repr__(self) -> str:
        safe_data = self.mask_secrets()
        items = ", ".join(f"{k}={v!r}" for k, v in safe_data.items())
        return f"Config({items})"


def load_config(**overrides: Any) -> Config:
    """
    Load configuration from environment variables with optional overrides.
    """
    return Config(**overrides)

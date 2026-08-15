"""
Telegram Integration Module for OpenHuman & Hermes Personal Companion.
"""

from bot.telegram.bot import TelegramBot, TelegramBotService
from bot.telegram.commands import CommandRouter
from bot.telegram.formatters import (
    chunk_message,
    escape_html,
    escape_markdown_v2,
    sanitize_telegram_html,
)
from bot.telegram.security import (
    is_user_authorized,
    log_unauthorized_access,
    require_authorized_user,
)

__all__ = [
    "TelegramBotService",
    "TelegramBot",
    "CommandRouter",
    "chunk_message",
    "escape_markdown_v2",
    "escape_html",
    "sanitize_telegram_html",
    "is_user_authorized",
    "require_authorized_user",
    "log_unauthorized_access",
]

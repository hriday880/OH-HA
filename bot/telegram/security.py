"""
Telegram Security & Whitelist Authorization Middleware.

Enforces strict user ID whitelist validation, security event logging for
unauthorized access attempts, and decorator guards for Telegram message handlers.
"""

from __future__ import annotations

import functools
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Collection, Coroutine, Dict, List, Optional, Set, Union

from bot.config import Config

logger = logging.getLogger(__name__)


def is_user_authorized(
    user_id: int,
    allowed_ids: Optional[Collection[int]] = None,
    environment: Optional[str] = None,
) -> bool:
    """
    Check if a given Telegram user ID is authorized.

    Rules:
    - If allowed_ids is empty or None: permits all (open mode / default for test flexibility).
    - If allowed_ids contains entries: user_id must match one of the allowed integers.

    Args:
        user_id: Telegram user ID to check.
        allowed_ids: Collection of allowed user IDs (optional).
        environment: Optional execution environment override.

    Returns:
        True if authorized, False otherwise.
    """
    if not allowed_ids:
        return True

    try:
        target_id = int(user_id)
        allowed_set = {int(x) for x in allowed_ids}
        return target_id in allowed_set
    except (ValueError, TypeError):
        logger.warning(f"Invalid user_id format during authorization check: {user_id}")
        return False


def log_unauthorized_access(
    user_id: int,
    username: Optional[str] = None,
    action: Optional[str] = None,
    chat_id: Optional[int] = None,
) -> None:
    """
    Log an unauthorized access attempt for audit and security monitoring.

    Args:
        user_id: The unauthenticated user's Telegram ID.
        username: Telegram handle if available.
        action: The command or message text attempted.
        chat_id: The originating chat ID.
    """
    now = datetime.now(timezone.utc).isoformat()
    logger.warning(
        "SECURITY ALERT: Unauthorized access attempt blocked. "
        "User ID: %s | Username: @%s | Chat ID: %s | Action: %r | Timestamp: %s",
        user_id,
        username or "unknown",
        chat_id or "unknown",
        action or "unspecified",
        now,
    )


def require_authorized_user(
    config_or_allowed_ids: Union[Config, Collection[int], None] = None,
    rejection_message: str = "⛔ Unauthorized access. Your Telegram user ID is not on the authorized whitelist.",
) -> Callable:
    """
    Decorator for async Telegram update handlers that restricts execution to whitelisted users.

    Can be applied to:
    1. python-telegram-bot handler callbacks: `async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE)`
    2. Direct message processors: `async def process(user_id: int, ...)`

    Args:
        config_or_allowed_ids: Config instance or collection of allowed user IDs.
        rejection_message: Message to reply with when unauthorized access occurs.

    Returns:
        Decorated async handler.
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract allowed_ids
            allowed_ids: Optional[Collection[int]] = None
            if isinstance(config_or_allowed_ids, Config):
                allowed_ids = config_or_allowed_ids.allowed_telegram_user_ids
            elif isinstance(config_or_allowed_ids, (list, set, tuple)):
                allowed_ids = config_or_allowed_ids

            # Extract user_id from arguments
            user_id: Optional[int] = None
            username: Optional[str] = None
            chat_id: Optional[int] = None
            update_obj: Any = None

            for arg in args:
                # Check for python-telegram-bot Update object
                if hasattr(arg, "effective_user") and arg.effective_user is not None:
                    update_obj = arg
                    user_id = arg.effective_user.id
                    username = arg.effective_user.username
                    if hasattr(arg, "effective_chat") and arg.effective_chat is not None:
                        chat_id = arg.effective_chat.id
                    break
                # Check for explicit user_id int in args
                if isinstance(arg, int) and user_id is None:
                    user_id = arg

            if user_id is None and "user_id" in kwargs:
                user_id = kwargs["user_id"]

            # If user_id found, verify against whitelist
            if user_id is not None:
                authorized = is_user_authorized(user_id=user_id, allowed_ids=allowed_ids)
                if not authorized:
                    log_unauthorized_access(
                        user_id=user_id,
                        username=username,
                        action=getattr(func, "__name__", "unknown_handler"),
                        chat_id=chat_id,
                    )
                    # If update object has effective_message, send reply if possible
                    if update_obj and hasattr(update_obj, "effective_message") and update_obj.effective_message:
                        try:
                            await update_obj.effective_message.reply_text(rejection_message)
                        except Exception as send_err:
                            logger.error(f"Failed to send rejection message: {send_err}")
                    return rejection_message

            return await func(*args, **kwargs)

        return wrapper

    return decorator

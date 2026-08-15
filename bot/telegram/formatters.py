"""
Telegram Message Formatting, Chunking & Sanitization Engine.

Provides message chunking within Telegram's 4096-character limit, paragraph and
code block boundary preservation, and entity escaping for MarkdownV2 and HTML modes.
"""

from __future__ import annotations

import html
import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Telegram standard maximum message length in characters
MAX_TELEGRAM_MESSAGE_LENGTH = 4096

# MarkdownV2 reserved meta-characters that require backslash escaping
MARKDOWN_V2_RESERVED_CHARS = r"_*[]()~`>#+-=|{}.!"


def escape_markdown_v2(text: str) -> str:
    """
    Escape all Telegram MarkdownV2 reserved meta-characters.

    Characters escaped: `_*[]()~`>#+-=|{}.!`

    Args:
        text: Raw text to escape.

    Returns:
        Escaped string safe for ParseMode.MARKDOWN_V2.
    """
    if not text:
        return ""
    pattern = f"([{re.escape(MARKDOWN_V2_RESERVED_CHARS)}])"
    return re.sub(pattern, r"\\\1", text)


def escape_html(text: str) -> str:
    """
    Escape standard HTML entities (&, <, >, ", ').

    Args:
        text: Raw text to escape.

    Returns:
        HTML-safe escaped string.
    """
    if not text:
        return ""
    return html.escape(text, quote=True)


def sanitize_telegram_html(text: str) -> str:
    """
    Sanitize HTML string to ensure only supported Telegram HTML tags remain.
    Supported tags: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <strike>, <del>,
                    <span>, <tg-spoiler>, <a>, <code>, <pre>, <blockquote>.
    All other angle brackets are safely escaped.
    """
    if not text:
        return ""

    allowed_tag_pattern = re.compile(
        r"<\/?(b|strong|i|em|u|ins|s|strike|del|span|tg-spoiler|a|code|pre|blockquote)(\s+[^>]*)?>",
        re.IGNORECASE,
    )

    parts: List[str] = []
    last_idx = 0

    for match in allowed_tag_pattern.finditer(text):
        # Escape any text before the matched tag
        prefix = text[last_idx:match.start()]
        if prefix:
            parts.append(escape_html(prefix))
        # Keep the valid tag as-is
        parts.append(match.group(0))
        last_idx = match.end()

    # Escape remaining text after last tag
    if last_idx < len(text):
        parts.append(escape_html(text[last_idx:]))

    return "".join(parts)


def chunk_message(text: str, max_chars: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> List[str]:
    """
    Split a long text string into message chunks of at most `max_chars`.

    Prioritizes splitting on natural boundaries:
    1. Paragraph boundaries (`\\n\\n`)
    2. Line breaks (`\\n`)
    3. Word boundaries (` `)
    4. Hard character boundary if no separator is found within `max_chars`

    Preserves code block fences across chunk boundaries if a split occurs
    within a Markdown fenced code block.

    Args:
        text: Message string to partition.
        max_chars: Maximum character limit per chunk (default 4096).

    Returns:
        List of message chunks, each <= max_chars.
    """
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    remaining = text
    current_code_lang: Optional[str] = None

    while len(remaining) > max_chars:
        # Search for optimal split boundary within max_chars
        split_idx = -1
        delimiter_len = 0

        # Check paragraph boundary
        p_idx = remaining.rfind("\n\n", 0, max_chars)
        if p_idx > 0:
            split_idx = p_idx
            delimiter_len = 2
        else:
            # Check newline boundary
            nl_idx = remaining.rfind("\n", 0, max_chars)
            if nl_idx > 0:
                split_idx = nl_idx
                delimiter_len = 1
            else:
                # Check space boundary
                sp_idx = remaining.rfind(" ", 0, max_chars)
                if sp_idx > 0:
                    split_idx = sp_idx
                    delimiter_len = 1
                else:
                    # Hard slice at max_chars
                    split_idx = max_chars
                    delimiter_len = 0

        chunk_candidate = remaining[:split_idx]
        next_remaining = remaining[split_idx + delimiter_len:] if delimiter_len > 0 else remaining[split_idx:]

        # Check code block fences in chunk_candidate to maintain block integrity
        code_fence_pattern = re.compile(r"^```([a-zA-Z0-9_\-]*)", re.MULTILINE)
        fences = list(code_fence_pattern.finditer(chunk_candidate))

        # Check if fence count is odd (meaning chunk cuts across an open code block)
        if len(fences) % 2 != 0:
            last_fence = fences[-1]
            fence_lang = last_fence.group(1) or ""
            closing_fence = "\n```"
            opening_fence = f"```{fence_lang}\n" if fence_lang else "```\n"

            # If appending closing fence would exceed max_chars, adjust split
            if len(chunk_candidate) + len(closing_fence) > max_chars:
                trim_len = (len(chunk_candidate) + len(closing_fence)) - max_chars
                chunk_candidate = chunk_candidate[:-trim_len]
                next_remaining = remaining[len(chunk_candidate):]

            chunk_candidate = f"{chunk_candidate}{closing_fence}"
            next_remaining = f"{opening_fence}{next_remaining}"

        chunks.append(chunk_candidate)
        remaining = next_remaining

    if remaining:
        chunks.append(remaining)

    return chunks

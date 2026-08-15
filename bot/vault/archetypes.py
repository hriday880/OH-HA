"""
Obsidian Note Archetypes, Daily Log Appender, and Template Engine.

Implements structured note archetypes for Obsidian knowledge bases:
- Daily Notes (`10-daily/YYYY-MM-DD.md`) with section-targeted logging
- Conversation Logs (`20-conversations/`) capturing multi-turn dialogue history
- Evergreen / Concept Notes (`30-topics/` / `50-knowledge/`)
- Dynamic template rendering engine with variable interpolation
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from bot.vault.frontmatter import FrontmatterEngine, NoteMetadata

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Sanitize string for use as a safe filename in vault."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = re.sub(r"\s+", "_", clean.strip())
    return clean or "untitled"


def render_template(template_str: str, context: Dict[str, Any]) -> str:
    """
    Render a markdown template string by replacing `{{key}}` placeholders with context values.
    """
    rendered = template_str
    for key, val in context.items():
        placeholder = f"{{{{{key}}}}}"
        if isinstance(val, (list, tuple)):
            val_str = "\n".join(f"- {item}" for item in val)
        else:
            val_str = str(val)
        rendered = rendered.replace(placeholder, val_str)

    # Clean any remaining unmatched {{...}} placeholders with empty string
    rendered = re.sub(r"\{\{[a-zA-Z0-9_\-]+\}\}", "", rendered)
    return rendered


DAILY_NOTE_TEMPLATE = """---
title: "{{date}}"
type: "daily"
date: "{{date}}"
tags:
  - daily-note
---
# {{date}}

## Log
{{log_entries}}
"""

CONVERSATION_NOTE_TEMPLATE = """---
title: "Conversation: {{topic}}"
type: "conversation"
created: "{{created}}"
topic: "{{topic}}"
tags:
  - conversation
---
# Conversation: {{topic}}

## Summary
{{summary}}

## Dialogue
{{dialogue}}
"""

EVERGREEN_NOTE_TEMPLATE = """---
title: "{{title}}"
type: "evergreen"
created: "{{created}}"
updated: "{{updated}}"
tags:
  - concept
{{extra_tags}}
---
# {{title}}

## Summary
{{summary}}

## Content
{{content}}

## Related Notes
{{related_links}}
"""


class DailyNoteHandler:
    """
    Handles generation, section parsing, and append operations for Daily Notes.
    """

    DEFAULT_FOLDER = "10-daily"
    DEFAULT_SECTION = "Log"

    @classmethod
    def get_daily_path(
        cls,
        date_str: Optional[str] = None,
        folder: Optional[str] = None,
    ) -> str:
        """Get relative path for daily note e.g. '10-daily/2026-08-15.md'."""
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_folder = folder or cls.DEFAULT_FOLDER
        return f"{daily_folder}/{date_str}.md"

    @classmethod
    def format_log_entry(cls, content: str, include_timestamp: bool = False) -> str:
        """Format a single log entry line."""
        clean_content = content.strip()
        if include_timestamp:
            time_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
            return f"- [{time_str}] {clean_content}"
        # If content doesn't start with a bullet or dash, add one
        if not clean_content.startswith(("-", "*", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
            return f"- {clean_content}"
        return clean_content

    @classmethod
    def append_entry_to_content(
        cls,
        existing_content: Optional[str],
        entry: str,
        date_str: str,
        section_heading: str = "Log",
    ) -> str:
        """
        Append a log entry under the specified section in a daily note.
        If existing_content is empty or None, generates a fresh daily note.
        """
        formatted_entry = cls.format_log_entry(entry)

        if not existing_content or not existing_content.strip():
            # Create fresh daily note
            return render_template(
                DAILY_NOTE_TEMPLATE,
                {
                    "date": date_str,
                    "log_entries": formatted_entry,
                },
            )

        # Parse existing content
        meta, body = FrontmatterEngine.parse(existing_content)
        sec_header = f"## {section_heading}"

        if sec_header in body:
            # Locate section and insert entry under it
            header_idx = body.find(sec_header)
            after_header = header_idx + len(sec_header)

            # Find next section starting with ## or end of body
            next_sec_match = re.search(r"\n##\s+", body[after_header:])
            if next_sec_match:
                insert_idx = after_header + next_sec_match.start()
                sec_content = body[after_header:insert_idx].rstrip()
                new_sec_content = f"{sec_content}\n{formatted_entry}" if sec_content.strip() else f"\n{formatted_entry}"
                new_body = body[:after_header] + new_sec_content + "\n\n" + body[insert_idx:].lstrip("\n")
            else:
                sec_content = body[after_header:].rstrip()
                new_sec_content = f"{sec_content}\n{formatted_entry}" if sec_content.strip() else f"\n{formatted_entry}\n"
                new_body = body[:after_header] + new_sec_content
        else:
            # Section header not found - append section to bottom
            new_body = f"{body.rstrip()}\n\n{sec_header}\n{formatted_entry}\n"

        return FrontmatterEngine.serialize(meta, new_body)


class ConversationLogger:
    """
    Handles structuring and formatting conversation transcripts into Obsidian notes.
    """

    DEFAULT_FOLDER = "20-conversations"

    @classmethod
    def create_conversation_note(
        cls,
        topic: str,
        messages: List[Dict[str, str]],
        summary: str = "",
        timestamp: Optional[str] = None,
        folder: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Format dialogue messages and summary into a conversation note.
        Returns:
            Tuple of (relative_path, note_content)
        """
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M%S")
        iso_str = timestamp or now.isoformat()

        clean_topic = topic.strip() or "General Dialogue"
        safe_topic_slug = sanitize_filename(clean_topic)[:40]
        filename = f"{date_str}_{time_str}_{safe_topic_slug}.md"
        conv_folder = folder or cls.DEFAULT_FOLDER
        rel_path = f"{conv_folder}/{filename}"

        # Format dialogue lines
        dialogue_lines: List[str] = []
        for msg in messages:
            role = msg.get("role", "User").capitalize()
            content = msg.get("content", "").strip()
            dialogue_lines.append(f"- **{role}**: {content}")

        dialogue_text = "\n".join(dialogue_lines) if dialogue_lines else "No messages recorded."
        summary_text = summary.strip() or "No conversation summary generated."

        content = render_template(
            CONVERSATION_NOTE_TEMPLATE,
            {
                "topic": clean_topic,
                "created": iso_str,
                "summary": summary_text,
                "dialogue": dialogue_text,
            },
        )
        return rel_path, content


class EvergreenNoteHandler:
    """
    Handles creating and structuring Evergreen / Concept notes in the vault.
    """

    DEFAULT_FOLDER = "30-topics"

    @classmethod
    def create_evergreen_note(
        cls,
        title: str,
        content: str,
        summary: str = "",
        tags: Optional[List[str]] = None,
        related_links: Optional[List[str]] = None,
        folder: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Format an evergreen concept note with structured frontmatter and wikilinks.
        Returns:
            Tuple of (relative_path, note_content)
        """
        now_str = datetime.now(timezone.utc).isoformat()
        clean_title = title.strip()
        safe_title = sanitize_filename(clean_title)
        evergreen_folder = folder or cls.DEFAULT_FOLDER
        rel_path = f"{evergreen_folder}/{safe_title}.md"

        extra_tags_str = ""
        if tags:
            extra_tags_str = "\n".join(f"  - {t.lstrip('#')}" for t in tags if t)

        links_str = ""
        if related_links:
            links_str = "\n".join(
                f"- [[{link.strip('[]')}]]" for link in related_links if link.strip()
            )
        else:
            links_str = "- None recorded."

        rendered = render_template(
            EVERGREEN_NOTE_TEMPLATE,
            {
                "title": clean_title,
                "created": now_str,
                "updated": now_str,
                "extra_tags": extra_tags_str,
                "summary": summary.strip() or "Concept overview.",
                "content": content.strip(),
                "related_links": links_str,
            },
        )
        return rel_path, rendered

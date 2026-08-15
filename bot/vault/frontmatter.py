"""
Obsidian YAML Frontmatter and Markdown Parsing & Serialization Engine.

Parses, validates, and serializes YAML frontmatter bounded by `---` delimiters
with robust error recovery on malformed YAML, normalized metadata extraction,
and lossless preservation of markdown body, code blocks, and math formulas.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)



def _format_date_or_str(value: Any) -> Optional[str]:
    """Format string, date, or datetime into standard ISO 8601 string representation."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            # Format UTC timezone as Z
            return value.isoformat().replace("+00:00", "Z")
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _sanitize_value_for_meta(value: Any) -> Any:
    """Recursively convert date/datetime objects to ISO 8601 strings."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return _format_date_or_str(value)
    if isinstance(value, dict):
        return {k: _sanitize_value_for_meta(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_value_for_meta(v) for v in value]
    return value


def _normalize_string_or_list(value: Any) -> List[str]:
    """Normalize string (comma-separated or single) or list of values into List[str]."""
    if value is None:
        return []
    if isinstance(value, str):
        val = value.strip()
        if not val:
            return []
        if "," in val:
            parts = [p.strip().lstrip("#") for p in val.split(",") if p.strip()]
            return [p for p in parts if p]
        clean = val.lstrip("#")
        return [clean] if clean else []
    if isinstance(value, (list, tuple, set)):
        result: List[str] = []
        for item in value:
            if item is None:
                continue
            item_str = str(item).strip().lstrip("#")
            if item_str and item_str not in result:
                result.append(item_str)
        return result
    return [str(value).strip()]


@dataclass
class NoteMetadata:
    """
    Structured metadata extracted from Obsidian note YAML frontmatter.
    """

    title: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    created: Optional[str] = None
    updated: Optional[str] = None
    custom: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.tags = _normalize_string_or_list(self.tags)
        self.aliases = _normalize_string_or_list(self.aliases)
        if self.created is not None:
            self.created = _format_date_or_str(self.created)
        if self.updated is not None:
            self.updated = _format_date_or_str(self.updated)
        if not isinstance(self.custom, dict):
            self.custom = {}
        else:
            self.custom = _sanitize_value_for_meta(self.custom)

    def to_dict(self) -> Dict[str, Any]:
        """Convert NoteMetadata to standard dictionary for serialization."""
        data: Dict[str, Any] = {}
        if self.title is not None:
            data["title"] = self.title
        if self.tags:
            data["tags"] = list(self.tags)
        if self.aliases:
            data["aliases"] = list(self.aliases)
        if self.created is not None:
            data["created"] = self.created
        if self.updated is not None:
            data["updated"] = self.updated
        if self.custom:
            data.update(self.custom)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NoteMetadata:
        """Construct NoteMetadata from dictionary, separating known keys from custom."""
        if not isinstance(data, dict):
            return cls()

        known_keys = {"title", "tags", "aliases", "created", "updated", "date"}
        title = data.get("title")
        tags = _normalize_string_or_list(data.get("tags", []))
        aliases = _normalize_string_or_list(data.get("aliases", []))
        created = _format_date_or_str(data.get("created") or data.get("date"))
        updated = _format_date_or_str(data.get("updated"))

        custom = {k: _sanitize_value_for_meta(v) for k, v in data.items() if k not in known_keys}
        if "date" in data and "date" not in custom and "created" not in data:
            custom["date"] = _format_date_or_str(data["date"])

        return cls(
            title=str(title) if title is not None else None,
            tags=tags,
            aliases=aliases,
            created=created,
            updated=updated,
            custom=custom,
        )



class FrontmatterEngine:
    """
    Engine for parsing and serializing Obsidian note YAML frontmatter and markdown body.
    """

    FRONTMATTER_PATTERN = re.compile(
        r"^---\s*\r?\n(.*?)\r?\n(?:---|...)\s*(?:\r?\n|$)",
        re.DOTALL,
    )

    INLINE_CODE_PATTERN = re.compile(r"`[^`]*`")
    CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```")
    INLINE_TAG_PATTERN = re.compile(r"(?<!\w)#([a-zA-Z0-9_\-\/]+)(?!\w)")

    @classmethod
    def parse(cls, content: str) -> Tuple[NoteMetadata, str]:
        """
        Parse YAML frontmatter and extract body from markdown text.

        Returns:
            Tuple of (NoteMetadata, body_string)
        """
        if not content:
            return NoteMetadata(), ""

        match = cls.FRONTMATTER_PATTERN.match(content)
        if not match:
            # Check for unclosed frontmatter
            if content.startswith("---"):
                # Missing closing delimiter or invalid block - preserve content
                logger.debug("Detected unclosed frontmatter delimiter; treating as body.")
            return NoteMetadata(), content

        yaml_block = match.group(1)
        body = content[match.end():]

        if not yaml_block.strip():
            return NoteMetadata(), body

        if yaml is None:
            # Fallback simple parser if yaml is unavailable
            return cls._fallback_parse_yaml(yaml_block), body

        try:
            data = yaml.safe_load(yaml_block)
        except Exception as e:
            logger.warning(f"Malformed YAML frontmatter encountered: {e}. Preserving body.")
            return NoteMetadata(), body

        if not isinstance(data, dict):
            logger.debug(f"Frontmatter parsed to non-dict ({type(data).__name__}); returning empty metadata.")
            return NoteMetadata(), body

        meta = NoteMetadata.from_dict(data)
        return meta, body

    @classmethod
    def serialize(
        cls,
        metadata: Union[NoteMetadata, Dict[str, Any]],
        body: str,
    ) -> str:
        """
        Serialize NoteMetadata and markdown body into standard Obsidian Markdown format.
        """
        if isinstance(metadata, dict):
            meta_obj = NoteMetadata.from_dict(metadata)
        elif isinstance(metadata, NoteMetadata):
            meta_obj = metadata
        else:
            meta_obj = NoteMetadata()

        data = meta_obj.to_dict()
        clean_body = body.lstrip("\r\n") if body else ""

        if not data:
            return clean_body

        if yaml is not None:
            try:
                yaml_str = yaml.safe_dump(
                    data,
                    sort_keys=False,
                    allow_unicode=True,
                    default_flow_style=False,
                ).strip()
            except Exception as e:
                logger.warning(f"Error dumping YAML metadata: {e}")
                yaml_str = cls._fallback_dump_yaml(data)
        else:
            yaml_str = cls._fallback_dump_yaml(data)

        if not clean_body:
            return f"---\n{yaml_str}\n---\n"
        return f"---\n{yaml_str}\n---\n{clean_body}"

    @classmethod
    def extract_inline_tags(cls, body: str) -> List[str]:
        """
        Extract inline tags (e.g. #tag, #category/subtag) from markdown body.
        Excludes tags inside code blocks and inline code.
        """
        if not body:
            return []

        # Strip code blocks
        clean_text = cls.CODE_BLOCK_PATTERN.sub(" ", body)
        # Strip inline code
        clean_text = cls.INLINE_CODE_PATTERN.sub(" ", clean_text)

        tags: List[str] = []
        for match in cls.INLINE_TAG_PATTERN.finditer(clean_text):
            tag = match.group(1).strip()
            # Ignore purely numeric hashtags (like #1, #2) or markdown headers at line start
            if tag and not tag.isdigit() and tag not in tags:
                tags.append(tag)
        return tags

    @classmethod
    def _fallback_parse_yaml(cls, yaml_str: str) -> NoteMetadata:
        """Minimal fallback YAML parser for key-value lines when PyYAML is unavailable."""
        data: Dict[str, Any] = {}
        current_list_key: Optional[str] = None

        for line in yaml_str.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            if line_str.startswith("- ") and current_list_key:
                val = line_str[2:].strip().strip("\"'")
                if isinstance(data.get(current_list_key), list):
                    data[current_list_key].append(val)
                else:
                    data[current_list_key] = [val]
                continue

            if ":" in line_str:
                parts = line_str.split(":", 1)
                k = parts[0].strip()
                v = parts[1].strip().strip("\"'")
                current_list_key = None

                if not v:
                    # Potential list header
                    current_list_key = k
                    data[k] = []
                elif v.startswith("[") and v.endswith("]"):
                    items = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
                    data[k] = items
                else:
                    data[k] = v

        return NoteMetadata.from_dict(data)

    @classmethod
    def _fallback_dump_yaml(cls, data: Dict[str, Any]) -> str:
        """Minimal fallback YAML serializer."""
        lines: List[str] = []
        for k, v in data.items():
            if isinstance(v, list):
                if not v:
                    continue
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            elif isinstance(v, dict):
                lines.append(f"{k}:")
                for dk, dv in v.items():
                    lines.append(f"  {dk}: {dv}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)


# Aliases for convenience and contract compliance
FrontmatterParser = FrontmatterEngine
parse_frontmatter = FrontmatterEngine.parse
serialize_frontmatter = FrontmatterEngine.serialize

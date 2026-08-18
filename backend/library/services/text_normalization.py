from __future__ import annotations

import re
import unicodedata


_WHITESPACE = re.compile(r'\s+')


def normalize_text(value: str | None) -> str:
    """Normalize comparison text without discarding accents or non-Latin scripts."""
    if not value:
        return ''
    normalized = unicodedata.normalize('NFKC', value).casefold()
    normalized = ''.join(
        ' ' if unicodedata.category(character).startswith('P') else character
        for character in normalized
    )
    return _WHITESPACE.sub(' ', normalized).strip()


def normalize_author(value: str | None) -> str:
    """Also make the common ``Lastname, Firstname`` form comparable."""
    if not value:
        return ''
    normalized = unicodedata.normalize('NFKC', value).casefold().strip()
    if normalized.count(',') == 1:
        last_name, given_names = normalized.split(',', maxsplit=1)
        if last_name.strip() and given_names.strip():
            normalized = f'{given_names} {last_name}'
    return normalize_text(normalized)

"""Pick the best available image from RSS entries."""

from __future__ import annotations

from typing import Any

from services.content import upgrade_image_url


def _media_width(item: dict[str, Any]) -> int:
    width = item.get("width")
    if width is None:
        return 0
    try:
        return int(width)
    except (TypeError, ValueError):
        return 0


def extract_best_image(entry: dict[str, Any]) -> str | None:
    candidates: list[str] = []

    media_items = entry.get("media_content") or []
    media_items = sorted(media_items, key=_media_width, reverse=True)
    for media in media_items:
        url = media.get("url")
        if url:
            candidates.append(url)

    for thumb in entry.get("media_thumbnail") or []:
        url = thumb.get("url")
        if url:
            candidates.append(url)

    for link in entry.get("links") or []:
        if link.get("type", "").startswith("image/"):
            href = link.get("href")
            if href:
                candidates.append(href)

    enclosures = entry.get("enclosures") or []
    for enclosure in enclosures:
        if enclosure.get("type", "").startswith("image/"):
            href = enclosure.get("href")
            if href:
                candidates.append(href)

    summary = entry.get("summary") or entry.get("description") or ""
    if "<img" in summary:
        import re

        match = re.search(r'src=["\']([^"\']+)["\']', summary)
        if match:
            candidates.append(match.group(1))

    if not candidates:
        return None

    return upgrade_image_url(candidates[0])

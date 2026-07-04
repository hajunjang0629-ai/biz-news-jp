"""Translate news content into Japanese."""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any

from deep_translator import GoogleTranslator

_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL_SECONDS = 60 * 60 * 6
CHUNK_SIZE = 3500


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_for_translation(text: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    if not paragraphs:
        return [text[:CHUNK_SIZE]] if text else []

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= CHUNK_SIZE:
            current = candidate
            continue

        if current:
            chunks.append(current)
        if len(paragraph) <= CHUNK_SIZE:
            current = paragraph
        else:
            for index in range(0, len(paragraph), CHUNK_SIZE):
                chunks.append(paragraph[index : index + CHUNK_SIZE])
            current = ""

    if current:
        chunks.append(current)

    return chunks


def translate_to_japanese(text: str) -> str:
    if not text or not text.strip():
        return text

    key = _cache_key(text)
    cached = _cache.get(key)
    now = time.time()
    if cached and now - cached[1] < CACHE_TTL_SECONDS:
        return cached[0]

    try:
        translated = GoogleTranslator(source="auto", target="ja").translate(text[:4500])
    except Exception:
        translated = text

    _cache[key] = (translated, now)
    return translated


def translate_long_text(text: str) -> str:
    if not text or not text.strip():
        return text

    key = _cache_key(f"long::{text}")
    cached = _cache.get(key)
    now = time.time()
    if cached and now - cached[1] < CACHE_TTL_SECONDS:
        return cached[0]

    chunks = _split_for_translation(text.strip())
    translated_parts = [translate_to_japanese(chunk) for chunk in chunks]
    translated = "\n\n".join(part for part in translated_parts if part)

    _cache[key] = (translated, now)
    return translated


def translate_article(article: dict[str, Any]) -> dict[str, Any]:
    translated_tags = [translate_to_japanese(tag) for tag in article.get("interest_tags", [])]

    return {
        **article,
        "title_ja": translate_to_japanese(article["title"]),
        "summary_ja": translate_to_japanese(article["summary"]),
        "interest_tags_ja": translated_tags,
        "title_original": article["title"],
        "summary_original": article["summary"],
    }


def translate_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [translate_article(article) for article in articles]

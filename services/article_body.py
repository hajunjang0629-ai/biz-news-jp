"""Build article body API payloads with fast fallback."""

from __future__ import annotations

import hashlib
import time
from typing import Any

from services.content import clean_article_body, fetch_article_content, upgrade_image_url
from services.summarizer import summarize_to_bullets
from services.translator import translate_long_text

_body_cache: dict[str, tuple[dict[str, Any], float]] = {}
CACHE_TTL_SECONDS = 60 * 60 * 2


def _cache_key(article_id: str) -> str:
    return hashlib.sha256(article_id.encode("utf-8")).hexdigest()


def build_fallback_article_payload(article: dict[str, Any]) -> dict[str, Any]:
    summary_ja = article["summary_ja"]
    summary_original = article["summary_original"]
    image_url = article.get("image_url")
    if image_url:
        image_url = upgrade_image_url(image_url)

    return {
        "id": article["id"],
        "title_ja": article["title_ja"],
        "title_original": article["title_original"],
        "summary_ja": summary_ja,
        "body_ja": summary_ja,
        "body_original": summary_original,
        "bullet_summary": summarize_to_bullets(summary_ja) or [summary_ja[:120]],
        "source": article["source"],
        "url": article["url"],
        "published_at": article["published_at"],
        "image_url": image_url,
        "partial": True,
    }


def build_full_article_payload(article: dict[str, Any]) -> dict[str, Any]:
    cached = _body_cache.get(_cache_key(article["id"]))
    now = time.time()
    if cached and now - cached[1] < CACHE_TTL_SECONDS:
        return cached[0]

    content = fetch_article_content(article["url"])

    image_url = content.image_url or article.get("image_url")
    if image_url:
        image_url = upgrade_image_url(image_url)

    body_original = clean_article_body(content.body or article["summary_original"])
    if body_original:
        body_ja = clean_article_body(translate_long_text(body_original))
    else:
        body_ja = article["summary_ja"]
        body_original = article["summary_original"]

    summary_ja = article["summary_ja"]
    has_full_body = bool(content.body) and len(body_ja.strip()) > len(summary_ja.strip()) + 60

    bullet_summary = summarize_to_bullets(body_ja)
    if not bullet_summary:
        bullet_summary = summarize_to_bullets(summary_ja)

    payload = {
        "id": article["id"],
        "title_ja": article["title_ja"],
        "title_original": article["title_original"],
        "summary_ja": summary_ja,
        "body_ja": body_ja,
        "body_original": body_original,
        "bullet_summary": bullet_summary,
        "source": article["source"],
        "url": article["url"],
        "published_at": article["published_at"],
        "image_url": image_url,
        "partial": not has_full_body,
    }

    _body_cache[_cache_key(article["id"])] = (payload, now)
    return payload

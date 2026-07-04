"""Fetch full article body and high-quality images from source URLs."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
import trafilatura

_content_cache: dict[str, tuple[dict[str, Any], float]] = {}
_image_cache: dict[str, tuple[str | None, float]] = {}
CACHE_TTL_SECONDS = 60 * 60 * 2
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
LOW_RES_HINTS = ("thumb", "/240", "/320", "/480", "/640", "/976", "w=140", "width=140", "height=79")


@dataclass
class ArticleContent:
    body: str
    image_url: str | None

    def to_dict(self) -> dict[str, Any]:
        return {"body": self.body, "image_url": self.image_url}


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def upgrade_image_url(url: str | None) -> str | None:
    if not url:
        return None

    upgraded = url.strip()

    upgraded = re.sub(
        r"(ichef\.bbci\.co\.uk/news/)\d+(xn/)",
        r"\g<1>1200\2",
        upgraded,
    )
    upgraded = re.sub(
        r"(media\.gettyimages\.com/[^?]+)\?.*",
        r"\1?w=1600&h=900&fit=crop",
        upgraded,
    )

    parsed = urlparse(upgraded)
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        if "w" in params:
            params["w"] = ["1600"]
        if "width" in params:
            params["width"] = ["1600"]
        if "height" in params:
            params["height"] = ["900"]
        if "quality" in params:
            params["quality"] = ["90"]
        upgraded = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(params, doseq=True),
                parsed.fragment,
            )
        )

    upgraded = re.sub(r"/thumb(?:nail)?/(\d+)x(\d+)/", "/1200x675/", upgraded)
    upgraded = re.sub(r"_(\d{2,3})x(\d{2,3})\.", "_1200x675.", upgraded)

    return upgraded


def is_low_resolution(url: str | None) -> bool:
    if not url:
        return True
    lowered = url.lower()
    return any(hint in lowered for hint in LOW_RES_HINTS)


def fetch_og_image(url: str) -> str | None:
    key = _cache_key(f"og::{url}")
    cached = _image_cache.get(key)
    now = time.time()
    if cached and now - cached[1] < CACHE_TTL_SECONDS:
        return cached[0]

    image_url: str | None = None
    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=12.0,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        html = response.text[:120000]
        for pattern in (
            r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
            r'content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
            r'name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']',
        ):
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                image_url = upgrade_image_url(match.group(1))
                break
    except Exception:
        image_url = None

    _image_cache[key] = (image_url, now)
    return image_url


def resolve_best_image(page_url: str, rss_image: str | None) -> str | None:
    upgraded_rss = upgrade_image_url(rss_image)
    if upgraded_rss and not is_low_resolution(upgraded_rss):
        return upgraded_rss

    og_image = fetch_og_image(page_url)
    if og_image:
        return og_image

    return upgraded_rss


METADATA_LINE_PATTERN = re.compile(
    r"^[\s\-–—•]*"
    r"(?:Published|Updated|Publication date|Last updated|"
    r"公開されました|更新されました|公開日|更新日)"
    r"[^\n]*\n+",
    re.IGNORECASE | re.MULTILINE,
)

INLINE_METADATA_PATTERN = re.compile(
    r"^[\s\-–—•]*"
    r"(?:Published|Updated|Publication date|Last updated|"
    r"公開されました|更新されました|公開日|更新日)"
    r"(?:\s+(?:\d+\s+(?:hours?|days?|minutes?|hrs?)\s+ago"
    r"|(?:on\s+)?[\d]{1,2}\s+\w+\s+\d{4}"
    r"|(?:\d{4}[-/]\d{1,2}[-/]\d{1,2})))?"
    r"\s+",
    re.IGNORECASE,
)


def clean_article_body(text: str) -> str:
    if not text or not text.strip():
        return text

    cleaned = METADATA_LINE_PATTERN.sub("", text.strip()).strip()
    cleaned = INLINE_METADATA_PATTERN.sub("", cleaned, count=1).strip()
    cleaned = re.sub(r"^[\-\–—•]\s+", "", cleaned)
    return cleaned.strip()


def fetch_article_content(url: str) -> ArticleContent:
    key = _cache_key(url)
    cached = _content_cache.get(key)
    now = time.time()
    if cached and now - cached[1] < CACHE_TTL_SECONDS:
        payload = cached[0]
        return ArticleContent(body=payload["body"], image_url=payload.get("image_url"))

    body = ""
    image_url: str | None = None

    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=8.0,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        html = response.text
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if extracted:
            body = clean_article_body(extracted.strip())

        metadata = trafilatura.extract_metadata(html)
        if metadata and metadata.image:
            image_url = upgrade_image_url(metadata.image)
    except Exception:
        pass

    payload = {"body": body, "image_url": image_url}
    _content_cache[key] = (payload, now)
    return ArticleContent(body=body, image_url=image_url)

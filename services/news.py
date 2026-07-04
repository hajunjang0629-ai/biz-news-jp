"""Fetch and rank business news from RSS feeds."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import feedparser

from services.content import is_low_resolution, resolve_best_image, upgrade_image_url
from services.images import extract_best_image

RSS_FEEDS: list[dict[str, str]] = [
    {"name": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"name": "CNBC Top News", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"},
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss"},
    {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best"},
    {"name": "NPR Business", "url": "https://feeds.npr.org/1006/rss.xml"},
]

HIGH_INTEREST_KEYWORDS: dict[str, int] = {
    "acquisition": 4,
    "merges with": 4,
    "merger": 4,
    "takeover": 4,
    "ipo": 4,
    "goes public": 4,
    "bankruptcy": 4,
    "bankrupt": 4,
    "antitrust": 4,
    "monopoly": 3,
    "tariff": 4,
    "trade war": 4,
    "sanctions": 3,
    "artificial intelligence": 4,
    " ai ": 3,
    "startup": 3,
    "unicorn": 4,
    "venture capital": 3,
    "funding round": 3,
    "layoff": 3,
    "job cuts": 3,
    "restructuring": 3,
    "ceo": 2,
    "resigns": 3,
    "fired": 2,
    "federal reserve": 3,
    "interest rate": 3,
    "inflation": 2,
    "recession": 3,
    "earnings": 2,
    "record profit": 3,
    "record revenue": 3,
    "billion": 2,
    "partnership": 2,
    "strategic": 2,
    "breakthrough": 3,
    "regulation": 2,
    "lawsuit": 2,
    "investigation": 2,
    "chip": 2,
    "semiconductor": 3,
    "ev ": 2,
    "electric vehicle": 2,
    "crypto": 2,
    "bitcoin": 2,
}

LOW_INTEREST_KEYWORDS: list[str] = [
    "obituary",
    "horoscope",
    "celebrity",
    "sports",
    "weather",
    "recipe",
    "fashion week",
    "red carpet",
]

MIN_INTEREST_SCORE = 3
MAX_ARTICLES = 24


@dataclass
class NewsArticle:
    id: str
    title: str
    summary: str
    url: str
    source: str
    published_at: str
    interest_score: int
    interest_tags: list[str]
    image_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at,
            "interest_score": self.interest_score,
            "interest_tags": self.interest_tags,
            "image_url": self.image_url,
        }


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_published(entry: dict[str, Any]) -> str:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        dt = datetime(*parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return datetime.now(timezone.utc).isoformat()


def score_interest(title: str, summary: str) -> tuple[int, list[str]]:
    text = f" {title.lower()} {summary.lower()} "
    score = 0
    tags: list[str] = []

    for keyword in LOW_INTEREST_KEYWORDS:
        if keyword in text:
            return 0, []

    for keyword, points in HIGH_INTEREST_KEYWORDS.items():
        if keyword in text:
            score += points
            tag = keyword.strip().title()
            if tag not in tags:
                tags.append(tag)

    if len(summary) > 120:
        score += 1

    return score, tags[:4]


def fetch_interesting_business_news() -> list[NewsArticle]:
    candidates: list[NewsArticle] = []

    for feed in RSS_FEEDS:
        parsed = feedparser.parse(feed["url"])
        for entry in parsed.entries[:40]:
            title = _clean_html(entry.get("title", ""))
            summary = _clean_html(
                entry.get("summary")
                or entry.get("description")
                or entry.get("content", [{}])[0].get("value", "")
            )
            url = entry.get("link", "")
            if not title or not url:
                continue

            score, tags = score_interest(title, summary)
            if score < MIN_INTEREST_SCORE:
                continue

            article_id = re.sub(r"[^a-zA-Z0-9]", "", url)[-32:] or str(abs(hash(url)))

            rss_image = extract_best_image(entry)

            candidates.append(
                NewsArticle(
                    id=article_id,
                    title=title,
                    summary=summary[:400],
                    url=url,
                    source=feed["name"],
                    published_at=_parse_published(entry),
                    interest_score=score,
                    interest_tags=tags,
                    image_url=upgrade_image_url(rss_image),
                )
            )

    candidates.sort(key=lambda item: (item.interest_score, item.published_at), reverse=True)

    seen_urls: set[str] = set()
    unique: list[NewsArticle] = []
    for article in candidates:
        if article.url in seen_urls:
            continue
        seen_urls.add(article.url)
        unique.append(article)
        if len(unique) >= MAX_ARTICLES:
            break

    for index, article in enumerate(unique[:12]):
        if is_low_resolution(article.image_url):
            enriched = resolve_best_image(article.url, article.image_url)
            if enriched:
                unique[index] = NewsArticle(
                    id=article.id,
                    title=article.title,
                    summary=article.summary,
                    url=article.url,
                    source=article.source,
                    published_at=article.published_at,
                    interest_score=article.interest_score,
                    interest_tags=article.interest_tags,
                    image_url=enriched,
                )

    return unique

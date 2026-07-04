"""Generate bullet-point summaries from article text."""

from __future__ import annotations

import re

MAX_BULLETS = 6
MIN_SENTENCE_LEN = 16
SKIP_PATTERNS = (
    "click here",
    "read more",
    "subscribe",
    "sign up",
    "cookie",
    "javascript",
    "share this",
    "follow us",
    "広告",
    "続きを読む",
    "公開されました",
    "更新されました",
    "published",
    "updated",
)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?])\s*", text.strip())
    return [part.strip() for part in parts if len(part.strip()) >= MIN_SENTENCE_LEN]


def _trim_sentence(sentence: str, limit: int = 120) -> str:
    sentence = re.sub(r"\s+", " ", sentence).strip()
    if len(sentence) <= limit:
        return sentence
    return sentence[: limit - 1] + "…"


def summarize_to_bullets(text: str, max_bullets: int = MAX_BULLETS) -> list[str]:
    if not text or not text.strip():
        return []

    bullets: list[str] = []
    seen: set[str] = set()

    for sentence in _split_sentences(text):
        lowered = sentence.lower()
        if any(pattern in lowered for pattern in SKIP_PATTERNS):
            continue

        key = re.sub(r"\s+", "", sentence[:40])
        if key in seen:
            continue
        seen.add(key)
        bullets.append(_trim_sentence(sentence))
        if len(bullets) >= max_bullets:
            return bullets

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if len(part.strip()) >= MIN_SENTENCE_LEN]
    for paragraph in paragraphs:
        if len(bullets) >= max_bullets:
            break

        first_sentence = _split_sentences(paragraph)[0] if _split_sentences(paragraph) else paragraph
        key = re.sub(r"\s+", "", first_sentence[:40])
        if key in seen:
            continue
        seen.add(key)
        bullets.append(_trim_sentence(first_sentence))

    return bullets[:max_bullets]

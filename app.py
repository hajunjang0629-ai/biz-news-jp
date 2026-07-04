from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services.content import clean_article_body, fetch_article_content, upgrade_image_url
from services.news import fetch_interesting_business_news
from services.summarizer import summarize_to_bullets
from services.translator import translate_articles, translate_long_text

BASE_DIR = Path(__file__).resolve().parent
SITE_NAME = "BizNews JP"
SITE_DESCRIPTION = "世界中のビジネスニュースから、重要で興味深い記事だけを日本語でお届けします。"

app = FastAPI(title=SITE_NAME, description="Interesting business news in Japanese")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

_news_cache: list[dict] | None = None
_articles_by_id: dict[str, dict] = {}


def get_base_url(request: Request) -> str:
    configured = os.getenv("BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def build_page_context(
    request: Request,
    articles: list[dict],
    *,
    open_article_id: str | None = None,
    share_article: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_url = get_base_url(request)

    if share_article:
        og_title = share_article["title_ja"]
        og_description = share_article["summary_ja"]
        og_url = f"{base_url}/article/{share_article['id']}"
        og_image = share_article.get("image_url") or f"{base_url}/static/og-default.svg"
        page_title = f"{og_title} — {SITE_NAME}"
    else:
        og_title = SITE_NAME
        og_description = SITE_DESCRIPTION
        og_url = base_url
        og_image = f"{base_url}/static/og-default.svg"
        page_title = f"{SITE_NAME} — 厳選ビジネスニュース"

    return {
        "request": request,
        "articles": articles,
        "article_count": len(articles),
        "base_url": base_url,
        "site_name": SITE_NAME,
        "page_title": page_title,
        "og_title": og_title,
        "og_description": og_description,
        "og_url": og_url,
        "og_image": og_image,
        "open_article_id": open_article_id,
    }


def get_translated_news() -> list[dict]:
    global _news_cache, _articles_by_id
    articles = fetch_interesting_business_news()
    translated = translate_articles([article.to_dict() for article in articles])
    _news_cache = translated
    _articles_by_id = {article["id"]: article for article in translated}
    return translated


def get_article(article_id: str) -> dict:
    if not _articles_by_id:
        get_translated_news()
    article = _articles_by_id.get(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
    return article


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    articles = get_translated_news()
    context = build_page_context(request, articles)
    return templates.TemplateResponse("index.html", context)


@app.get("/article/{article_id}", response_class=HTMLResponse)
async def article_page(request: Request, article_id: str) -> HTMLResponse:
    articles = get_translated_news()
    share_article = get_article(article_id)
    context = build_page_context(
        request,
        articles,
        open_article_id=article_id,
        share_article=share_article,
    )
    return templates.TemplateResponse("index.html", context)


@app.get("/api/news")
async def api_news() -> JSONResponse:
    articles = get_translated_news()
    return JSONResponse({"count": len(articles), "articles": articles})


@app.get("/api/articles/{article_id}/body")
async def article_body(article_id: str) -> JSONResponse:
    article = get_article(article_id)
    content = fetch_article_content(article["url"])

    image_url = content.image_url or article.get("image_url")
    if image_url:
        image_url = upgrade_image_url(image_url)

    body_original = clean_article_body(content.body or article["summary_original"])
    body_ja = (
        clean_article_body(translate_long_text(body_original))
        if body_original
        else article["summary_ja"]
    )
    bullet_summary = summarize_to_bullets(body_ja)

    return JSONResponse(
        {
            "id": article["id"],
            "title_ja": article["title_ja"],
            "title_original": article["title_original"],
            "summary_ja": article["summary_ja"],
            "body_ja": body_ja,
            "body_original": body_original,
            "bullet_summary": bullet_summary,
            "source": article["source"],
            "url": article["url"],
            "published_at": article["published_at"],
            "image_url": image_url,
        }
    )


@app.post("/api/refresh")
async def refresh_news() -> JSONResponse:
    articles = get_translated_news()
    return JSONResponse({"count": len(articles), "articles": articles})

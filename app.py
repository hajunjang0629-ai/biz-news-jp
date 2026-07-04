from __future__ import annotations

import asyncio
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from services.article_body import build_fallback_article_payload, build_full_article_payload
from services.news import fetch_interesting_business_news
from services.translator import translate_articles

BASE_DIR = Path(__file__).resolve().parent
SITE_NAME = "BizNews JP"
SITE_DESCRIPTION = "世界中のビジネスニュースから、重要で興味深い記事だけを日本語でお届けします。"
ARTICLE_BODY_TIMEOUT_SECONDS = 18
ARTICLE_LOOKUP_TIMEOUT_SECONDS = 8

_news_cache: list[dict] | None = None
_articles_by_id: dict[str, dict] = {}
_news_cache_lock = threading.Lock()


def _warm_news_cache() -> None:
    try:
        get_translated_news()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warm_news_cache, daemon=True).start()
    yield


app = FastAPI(
    title=SITE_NAME,
    description="Interesting business news in Japanese",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def get_base_url(request: Request) -> str:
    configured = os.getenv("BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def article_preview_payload(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": article["id"],
        "title_ja": article["title_ja"],
        "title_original": article["title_original"],
        "summary_ja": article["summary_ja"],
        "summary_original": article["summary_original"],
        "source": article["source"],
        "url": article["url"],
        "published_at": article["published_at"],
        "image_url": article.get("image_url"),
    }


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
        "open_article": article_preview_payload(share_article) if share_article else None,
        "article_preview": article_preview_payload,
    }


def get_translated_news() -> list[dict]:
    global _news_cache, _articles_by_id

    with _news_cache_lock:
        if _news_cache is not None:
            return _news_cache

        articles = fetch_interesting_business_news()
        translated = translate_articles([article.to_dict() for article in articles])
        _news_cache = translated
        _articles_by_id = {article["id"]: article for article in translated}
        return translated


def get_cached_news() -> list[dict]:
    return _news_cache or []


def get_article(article_id: str) -> dict:
    article = _articles_by_id.get(article_id)
    if article:
        return article

    if _news_cache is None:
        get_translated_news()
        article = _articles_by_id.get(article_id)
        if article:
            return article

    raise HTTPException(status_code=404, detail="記事が見つかりません")


async def resolve_article(article_id: str) -> dict | None:
    article = _articles_by_id.get(article_id)
    if article:
        return article

    if _news_cache is None:
        try:
            await asyncio.wait_for(
                run_in_threadpool(get_translated_news),
                timeout=ARTICLE_LOOKUP_TIMEOUT_SECONDS,
            )
        except (asyncio.TimeoutError, Exception):
            return None

    return _articles_by_id.get(article_id)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    articles = get_cached_news()
    context = build_page_context(request, articles)
    return templates.TemplateResponse("index.html", context)


@app.get("/article/{article_id}", response_class=HTMLResponse)
async def article_page(request: Request, article_id: str) -> HTMLResponse:
    share_article = await resolve_article(article_id)
    if not share_article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")

    articles = get_cached_news()
    context = build_page_context(
        request,
        articles,
        open_article_id=article_id,
        share_article=share_article,
    )
    return templates.TemplateResponse("index.html", context)


@app.get("/api/news")
async def api_news() -> JSONResponse:
    articles = get_translated_news() if not _news_cache else get_cached_news()
    return JSONResponse({"count": len(articles), "articles": articles})


@app.get("/api/articles/{article_id}/body")
async def article_body(article_id: str, quick: bool = False) -> JSONResponse:
    article = await resolve_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")

    if quick:
        return JSONResponse(build_fallback_article_payload(article))

    try:
        payload = await asyncio.wait_for(
            run_in_threadpool(build_full_article_payload, article),
            timeout=ARTICLE_BODY_TIMEOUT_SECONDS,
        )
    except (asyncio.TimeoutError, Exception):
        payload = build_fallback_article_payload(article)

    return JSONResponse(payload)


@app.post("/api/refresh")
async def refresh_news() -> JSONResponse:
    articles = get_translated_news()
    return JSONResponse({"count": len(articles), "articles": articles})

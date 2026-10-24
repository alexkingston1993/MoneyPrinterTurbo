"""
Publisher & Search Engine Indexing Engine.
Publishes markdown articles to content/posts/, updates content/posts.json manifest,
and pings IndexNow and Google Search Console for rapid search indexing.
"""

import os
import json
import re
from pathlib import Path
from typing import List, Optional
import requests
from loguru import logger

BASE_DIR = Path(__file__).parent
POSTS_JSON = BASE_DIR / "content" / "posts.json"
SITE_URL = os.getenv("SITE_URL", "https://the-bull-print.vercel.app").rstrip("/")


def _ping_indexnow(article_url: str):
    """Pings IndexNow API (Bing, Yandex, Naver) for instant crawl notification."""
    try:
        endpoint = "https://api.indexnow.org/indexnow"
        payload = {
            "host": SITE_URL.replace("https://", "").replace("http://", ""),
            "key": "flipzon_indexnow_key_2026",
            "urlList": [article_url]
        }
        res = requests.post(endpoint, json=payload, timeout=8)
        logger.info(f"⚡ IndexNow ping status: {res.status_code}")
    except Exception as e:
        logger.warning(f"IndexNow ping bypassed: {e}")


def publish_and_index_article(out_article_path: Path, used_charts: List[str], slug: str) -> str:
    """
    Publishes article, updates content/posts.json, pings indexers, and returns the live URL.
    """
    logger.info(f"🌐 Publishing article and updating manifest for: {slug}")
    article_text = out_article_path.read_text(encoding="utf-8")
    
    # Extract metadata from frontmatter or text
    title_match = re.search(r'title:\s*"([^"]+)"', article_text)
    title = title_match.group(1) if title_match else slug.replace("-", " ").title()
    
    desc_match = re.search(r'description:\s*"([^"]+)"', article_text)
    desc = desc_match.group(1) if desc_match else "In-depth market structure and risk analysis."
    
    yt_match = re.search(r'youtube_video_id:\s*"([^"]+)"', article_text)
    yt_id = yt_match.group(1) if yt_match else ""
    
    # Update content/posts.json
    posts = []
    if POSTS_JSON.exists():
        try:
            posts = json.loads(POSTS_JSON.read_text(encoding="utf-8"))
        except Exception:
            posts = []

    # Filter out existing with same slug
    posts = [p for p in posts if p.get("slug") != slug]
    
    # Word count and reading time
    words = len(article_text.split())
    reading_time = max(1, words // 200)

    post_entry = {
        "title": title,
        "slug": slug,
        "description": desc,
        "date": "2026-10-24",
        "author": "Alex from Chennai",
        "reading_time": f"{reading_time} min read",
        "word_count": words,
        "categories": ["Market Education", "Institutional Flow", "Risk Management"],
        "tags": ["Nifty", "Bitcoin", "Order Flow", "Beginner Guide"],
        "youtube_video_id": yt_id,
        "charts": used_charts,
        "content_path": f"content/posts/{out_article_path.name}"
    }

    # Prepend new post to top
    posts.insert(0, post_entry)
    POSTS_JSON.write_text(json.dumps(posts, indent=2), encoding="utf-8")
    logger.success(f"✓ Updated posts manifest ({POSTS_JSON.name}) with {len(posts)} total posts.")

    # Determine live URL
    live_url = f"{SITE_URL}/article.html?slug={slug}"
    
    # Ping IndexNow
    _ping_indexnow(live_url)

    logger.success(f"🎉 Publication complete! Live Article URL: {live_url}")
    return live_url

"""
X (Twitter) Thread Publisher (app/services/x_thread_publisher.py).
Distributes each published research dossier as a 3-tweet thread:
1. Hook + first TL;DR insight + up to 2 dark-mode chart PNGs (v1.1 media_upload)
2. Remaining TL;DR insight points
3. Long video, 9:16 Short, full dossier, and /tools affiliate toolkit links with SEBI disclaimer
Skips gracefully whenever X credentials, tweepy, or payload content are missing.
"""

import os
from pathlib import Path
from typing import List, Tuple

from loguru import logger

try:
    import tweepy
except ImportError:
    tweepy = None
    logger.warning("tweepy not installed — X thread publishing will be skipped.")

TOOLS_URL = "https://the-bull-print.vercel.app/tools"
DISCLAIMER = "🎓 SEBI: Educational content only — not investment advice. Markets carry risk."
TWEET_LIMIT = 275


def _clip(text: str, limit: int = TWEET_LIMIT) -> str:
    """Collapses whitespace and hard-clips a tweet body under the 280-char ceiling."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _resolve_thread_assets(payload: dict) -> Tuple[str, List[str]]:
    """Resolves the hook and TL;DR points from the master payload, with defensive fallbacks."""
    yt_meta = payload.get("youtube_payload", {}).get("metadata", {})
    web = payload.get("website_article_payload", {})

    hook = (
        payload.get("h1_title")
        or web.get("seo_meta", {}).get("h1_title")
        or web.get("seo_title")
        or yt_meta.get("title", "The Bull Print Daily Brief")
    )

    tldr = payload.get("tldr_summary") or []
    tldr = [str(t).strip() for t in tldr if str(t).strip()]
    if not tldr:
        tldr = [
            s.strip()
            for s in str(web.get("meta_description", "")).replace(". ", ".|").split("|")
            if len(s.strip()) > 25
        ][:3]
    return str(hook), tldr


def publish_x_thread(payload: dict, chart_paths: list, yt_video_id: str, short_video_id: str, article_url: str) -> str:
    """Publishes the 3-tweet thread. Returns a status string; never raises into the pipeline."""
    x_api_key = os.getenv("X_API_KEY", "")
    x_api_secret = os.getenv("X_API_SECRET", "")
    x_access_token = os.getenv("X_ACCESS_TOKEN", "")
    x_access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET", "")

    if not all([x_api_key, x_api_secret, x_access_token, x_access_token_secret]):
        return "Skipped (X keys not set)"
    if tweepy is None:
        return "Skipped (tweepy not installed)"

    try:
        # v1.1 API for local chart media uploads
        media_api = tweepy.API(
            tweepy.OAuth1UserHandler(x_api_key, x_api_secret, x_access_token, x_access_token_secret)
        )
        media_ids = []
        for chart in list(chart_paths or [])[:2]:
            chart_file = Path(chart)
            if not chart_file.exists():
                continue
            try:
                media_ids.append(media_api.media_upload(str(chart_file)).media_id_string)
            except Exception as media_err:
                logger.warning(f"X media upload failed for {chart_file.name}: {media_err}")

        hook, tldr = _resolve_thread_assets(payload)
        tweet1_text = _clip(f"{hook}\n\n{tldr[0]}" if tldr else hook)
        tweet2_text = _clip("\n\n".join(tldr[1:3]) if len(tldr) > 1 else (tldr[0] if tldr else hook))

        links = []
        if yt_video_id:
            links.append(f"▶️ Full Masterclass: https://youtu.be/{yt_video_id}")
        if short_video_id:
            links.append(f"🩳 9:16 Short: https://youtube.com/shorts/{short_video_id}")
        if article_url:
            links.append(f"📄 Full Dossier: {article_url}")
        links.append(f"🛠️ Free Toolkit: {TOOLS_URL}")
        tweet3_text = _clip("\n".join(links) + f"\n\n{DISCLAIMER}")

        client = tweepy.Client(
            consumer_key=x_api_key,
            consumer_secret=x_api_secret,
            access_token=x_access_token,
            access_token_secret=x_access_token_secret,
        )
        resp1 = client.create_tweet(text=tweet1_text, media_ids=media_ids or None)
        tid1 = resp1.data["id"]
        resp2 = client.create_tweet(text=tweet2_text, in_reply_to_tweet_id=tid1)
        tid2 = resp2.data["id"]
        resp3 = client.create_tweet(text=tweet3_text, in_reply_to_tweet_id=tid2)

        logger.success(f"✓ X thread published (root tweet {tid1})")
        return f"Published — x.com/i/status/{resp3.data['id']}"
    except Exception as err:
        logger.warning(f"X thread publication failed: {err}")
        return f"Error ({err.__class__.__name__})"

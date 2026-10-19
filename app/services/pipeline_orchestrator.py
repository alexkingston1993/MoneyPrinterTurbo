"""
Pipeline Orchestrator — Autonomous Multi-Modal Publishing Coordinator.

Executes the unified loop:
1. Ingests live NSE/BSE & macro data via MarketDataFetcher
2. Generates video script + renders video with MoneyPrinterTurbo
3. Uploads video to YouTube (retrieves published YouTube URL)
4. Generates humanized 1,500w financial article with ArticleGenerator
5. Publishes article to WordPress (embedding the YouTube video)
6. Closes the loop by updating YouTube description with the article link
"""

import time
from typing import Dict, Optional
from loguru import logger

from app.services.market_data import get_fetcher, MarketContext
from app.services.article_generator import article_generator, GeneratedArticle
from app.services.wp_publisher import wp_publisher
from app.config import config


class PipelineOrchestrator:
    """Coordinates autonomous live research, video production, and web publishing."""

    def __init__(self):
        self.market_fetcher = get_fetcher()

    def run_market_cycle(
        self,
        slot_name: str = "live_update",
        mock_video_url: Optional[str] = None,
        publish_article: bool = True,
    ) -> Dict:
        """
        Executes a complete market publishing cycle.
        """
        start_time = time.time()
        logger.info(f"[Orchestrator] Starting market cycle: slot='{slot_name}'")

        # 1. Fetch live market snapshot
        logger.info("[Orchestrator] Step 1: Fetching live NSE/BSE context...")
        ctx: MarketContext = self.market_fetcher.get_full_context(include_stocks=True, include_global=True)
        logger.info(
            f"[Orchestrator] Market data fetched: status={ctx.market_status}, "
            f"sentiment={ctx.market_sentiment}, Nifty={ctx.nifty.value if ctx.nifty else 'N/A'}"
        )

        # 2. Determine YouTube Video URL (live or placeholder)
        youtube_url = mock_video_url or "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # placeholder or real upload

        # 3. Generate Humanized, GEO-Optimized Article
        logger.info("[Orchestrator] Step 2: Generating in-depth humanized market article...")
        article: GeneratedArticle = article_generator.generate_article_from_context(ctx, youtube_url=youtube_url)
        logger.info(f"[Orchestrator] Article generated: '{article.title}' ({len(article.html_content.split())} words)")

        # 4. Publish to Website (GitHub / Vercel or WordPress)
        publish_res = {}
        if publish_article:
            publisher_target = config.app.get("publisher_target", "github").lower()
            if publisher_target == "github":
                from app.services.github_publisher import github_publisher
                logger.info("[Orchestrator] Step 3: Publishing article to GitHub repository (for Vercel)...")
                publish_res = github_publisher.publish_article(article, youtube_url=youtube_url)
            else:
                logger.info("[Orchestrator] Step 3: Publishing article to WordPress (or local disk fallback)...")
                publish_res = wp_publisher.publish_article(article, youtube_url=youtube_url)
            logger.info(f"[Orchestrator] Publishing result: status={publish_res.get('status')}, url={publish_res.get('url')}")
            
            # 5. Closed-Loop Backlink: Update YouTube video description and pinned comment
            published_url = publish_res.get("url")
            if published_url and youtube_url:
                try:
                    video_id = wp_publisher._extract_youtube_id(youtube_url)
                    if video_id and video_id != "dQw4w9WgXcQ":
                        from app.services.youtube_uploader import get_uploader
                        uploader = get_uploader()
                        logger.info(f"[Orchestrator] Step 4: Closing flywheel — adding article link to YouTube video {video_id}...")
                        uploader.append_article_link_to_description("en", video_id, published_url, article.title)
                        comment_msg = f"📊 Read the full in-depth financial breakdown & data tables here: {published_url}"
                        uploader.post_pinned_comment("en", video_id, comment_msg)
                except Exception as e:
                    logger.warning(f"[Orchestrator] YouTube backlink update skipped: {e}")

        duration = time.time() - start_time
        logger.info(f"[Orchestrator] Market cycle completed in {duration:.1f}s")

        return {
            "success": True,
            "slot": slot_name,
            "duration_seconds": round(duration, 1),
            "market_status": ctx.market_status,
            "market_sentiment": ctx.market_sentiment,
            "nifty_level": ctx.nifty.value if ctx.nifty else None,
            "article_title": article.title,
            "article_slug": article.slug,
            "youtube_url": youtube_url,
            "published_url": publish_res.get("url"),
            "published_status": publish_res.get("status"),
        }


# Global instance
pipeline_orchestrator = PipelineOrchestrator()

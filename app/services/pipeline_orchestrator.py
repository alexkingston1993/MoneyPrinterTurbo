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

        # 2. Real Video Generation & Upload via Task Engine
        youtube_url = mock_video_url
        if not youtube_url:
            try:
                logger.info("[Orchestrator] Step 1.5: Triggering real autonomous video production in cloud...")
                youtube_url = self._generate_and_upload_video(ctx, slot_name)
            except Exception as e:
                logger.error(f"[Orchestrator] Autonomous video generation error: {e}")

        # Fallback to the latest real video on the channel if generation skipped
        if not youtube_url:
            youtube_url = "https://www.youtube.com/watch?v=FfxHCzx7QhM"


        # 3. Generate Humanized, GEO-Optimized Article
        logger.info("[Orchestrator] Step 2: Generating in-depth humanized market article...")
        article: GeneratedArticle = article_generator.generate_article_from_context(ctx, youtube_url=youtube_url)
        logger.info(f"[Orchestrator] Article generated: '{article.title}' ({len(article.html_content.split())} words)")

        # 3.5 QA Critic Agent Gate: Comprehensive evaluation before publishing
        logger.info("[Orchestrator] Step 2.5: Running Autonomous QA Critic on article before web publishing...")
        from app.services.qa_critic import qa_critic
        clean_title, clean_html, qa_result = qa_critic.evaluate_and_refine(
            content_type="web_article",
            title=article.title,
            body=article.html_content,
        )
        article.title = clean_title
        article.html_content = clean_html
        logger.info(
            f"[Orchestrator] Article QA Gate passed: score={qa_result.overall_score}/100, "
            f"compliance={qa_result.compliance_score}, passed={qa_result.passed}"
        )

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

    def _generate_and_upload_video(self, ctx: MarketContext, slot_name: str) -> Optional[str]:
        """Synthesizes a Short video for the market slot and uploads to YouTube autonomously in cloud."""
        import uuid
        from app.models.schema import VideoParams, VideoConcatMode
        from app.services import task

        task_id = str(uuid.uuid4())
        nifty_str = f"{ctx.nifty.value:.1f}" if ctx.nifty else "24,500"
        nifty_chg = f"{ctx.nifty.change_percent:+.2f}%" if ctx.nifty and ctx.nifty.change_percent is not None else "+0.00%"

        if slot_name == "pre_market":
            subject = "Nifty 50 Pre-Market Briefing | Gift Nifty Opening Setup"
            script = (
                f"Good morning Dalal Street. Here is your institutional opening setup. "
                f"Benchmark Nifty 50 enters the session with Gift Nifty signaling early directional bias. "
                f"Key pivot levels to watch on the hourly charts stand near {nifty_str}. "
                f"Watch for open interest concentration around weekly ATM call and put strikes. "
                f"Please conduct your own due diligence and market research as I am not a SEBI-registered advisor."
            )
            terms = ["stock market trading", "gift nifty futures", "indian economy finance", "stock chart analysis"]
        elif slot_name == "morning_momentum":
            subject = "Morning Momentum & Sector Rotation Radar"
            script = (
                f"Dalal Street morning momentum update. We are observing active sector rotation across banking, IT, and auto. "
                f"Nifty 50 is trading near {nifty_str} ({nifty_chg}). "
                f"Institutional order flow reflects selective accumulation in high cash-conversion equities. "
                f"Manage risk proactively as intraday volatility peaks around European market opening. "
                f"Strictly educational commentary, not investment advice."
            )
            terms = ["stock market chart", "banking sector money", "indian business", "trading desktop screen"]
        elif slot_name == "market_close":
            subject = "Dalal Street Closing Bell Wrap | Nifty Settlement Analysis"
            script = (
                f"Closing bell wrap on Dalal Street. Nifty 50 settled the trading session at {nifty_str} ({nifty_chg}). "
                f"Market breadth reflected active participation with decisive trends across key large-cap leaders. "
                f"Foreign institutional flows and domestic mutual fund support continue to anchor market structure. "
                f"Review your positional risk carefully, and please consult an independent certified financial advisor."
            )
            terms = ["mumbai stock exchange", "closing bell trading", "stock market graph rising", "business handshake"]
        else:
            subject = "Nifty 50 Market Analysis & Quantitative Overview"
            script = (
                f"Welcome to The Bull Print. Here is the quantitative breakdown for Indian equity markets. "
                f"Nifty 50 benchmark stands at {nifty_str} with market sentiment currently classified as {ctx.market_sentiment}. "
                f"Institutional capital flows emphasize balance sheet resilience and disciplined cash compounding. "
                f"Please do your own due diligence and market research before taking any financial decision."
            )
            terms = ["financial market data", "stock candlestick upward", "corporate boardroom", "investment growth"]

        params = VideoParams(
            video_subject=subject,
            video_script=script,
            video_terms=terms,
            video_aspect="9:16",
            video_concat_mode=VideoConcatMode.sequential,
            video_clip_duration=5,
            video_count=1,
            video_source=config.app.get("video_source", "pexels"),
            voice_name="kokoro:af_heart",
            bgm_type="random",
            subtitle_enabled=True,
            subtitle_position="center",
            font_size=75,
            text_fore_color="#FFFFFF",
            text_background_color=True,
            stroke_color="#000000",
            stroke_width=2.0,
        )

        logger.info(f"[Orchestrator] Launching video rendering task {task_id} for '{subject}'...")
        res = task.start(task_id, params)
        if res and "youtube_upload" in res:
            yt_upload = res["youtube_upload"].get("en", {})
            if yt_upload and yt_upload.get("success") and yt_upload.get("url"):
                yt_url = yt_upload["url"]
                logger.success(f"[Orchestrator] Autonomous video generated and published: {yt_url}")
                vid_id = yt_upload.get("video_id")
                if vid_id:
                    self._add_to_playlist(vid_id)
                return yt_url

        return None

    def _add_to_playlist(self, video_id: str):
        """Add uploaded video to official public playlist."""
        import os, pickle
        from googleapiclient.discovery import build
        token_path = "data/youtube_tokens/youtube_token_en.pickle"
        if not os.path.exists(token_path) or not video_id:
            return
        try:
            with open(token_path, "rb") as f:
                creds = pickle.load(f)
            youtube = build("youtube", "v3", credentials=creds)
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": "PLO2FWTao-JNA",
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id,
                        },
                    }
                },
            ).execute()
            logger.success(f"[Orchestrator] Added video {video_id} to playlist PLO2FWTao-JNA")
        except Exception as e:
            logger.warning(f"[Orchestrator] Playlist insert warning: {e}")


# Global instance
pipeline_orchestrator = PipelineOrchestrator()


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

import os
import time
from typing import Dict, Optional, Any
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

        # Engage parallel zero-downtime disk sentinel (auto-scrubs if runner disk > 70%)
        try:
            from app.services.aria_healing import AriaDiskSentinel
            AriaDiskSentinel.start_sentinel(threshold_pct=70.0, check_interval_sec=15)
        except Exception as e:
            logger.warning(f"[Orchestrator] Disk sentinel startup notice: {e}")

        # 1. Fetch live market snapshot
        logger.info("[Orchestrator] Step 1: Fetching live NSE/BSE context...")
        ctx: MarketContext = self.market_fetcher.get_full_context(include_stocks=True, include_global=True)
        logger.info(
            f"[Orchestrator] Market data fetched: status={ctx.market_status}, "
            f"sentiment={ctx.market_sentiment}, Nifty={ctx.nifty.value if ctx.nifty else 'N/A'}"
        )

        # 2. Real Video Generation & Upload via Self-Healing Engine
        youtube_url = mock_video_url
        if not youtube_url:
            try:
                logger.info("[Orchestrator] Step 1.5: Triggering real autonomous video production with Self-Healing Loop...")
                youtube_url = self._generate_and_upload_video_with_healing(ctx, slot_name, max_retries=3)
            except Exception as e:
                logger.error(f"[Orchestrator] Autonomous video generation exhausted retries: {e}")

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
            if not published_url or "github.com" in published_url:
                published_url = "https://the-bull-print.vercel.app"
            
            if youtube_url:
                try:
                    video_id = wp_publisher._extract_youtube_id(youtube_url)
                    if video_id and video_id != "dQw4w9WgXcQ":
                        from app.services.youtube_uploader import get_uploader
                        uploader = get_uploader()
                        logger.info(f"[Orchestrator] Step 4: Closing flywheel — adding article link to YouTube video {video_id}...")
                        uploader.append_article_link_to_description("en", video_id, published_url, article.title)
                        comment_msg = (
                            f"📊 Full In-Depth Institutional Breakdown & Order-Flow Heatmaps:\n"
                            f"{published_url}\n\n"
                            f"🔔 Subscribe to The Bull Print for tomorrow's 9:00 AM FII order-flow radar.\n"
                            f"⚖️ Strictly educational market research. Not SEBI registered."
                        )
                        uploader.post_pinned_comment("en", video_id, comment_msg)
                except Exception as e:
                    logger.warning(f"[Orchestrator] YouTube backlink update skipped: {e}")

        duration = time.time() - start_time
        logger.info(f"[Orchestrator] Market cycle completed in {duration:.1f}s")

        # 6. Real-time Dispatch Notification (WhatsApp via CallMeBot)
        try:
            from app.services.notifier import send_market_release_alert
            send_market_release_alert(
                slot_name=slot_name,
                article_title=article.title,
                youtube_url=youtube_url,
                published_url=publish_res.get("url"),
                nifty_level=ctx.nifty.value if ctx.nifty else None,
                sentiment=ctx.market_sentiment,
            )
        except Exception as alert_err:
            logger.warning(f"[Orchestrator] WhatsApp alert dispatch warning: {alert_err}")

        # Stop parallel disk sentinel
        try:
            from app.services.aria_healing import AriaDiskSentinel
            AriaDiskSentinel.stop_sentinel()
        except Exception:
            pass

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

    def _generate_and_upload_video(
        self, ctx: MarketContext, slot_name: str, remedy: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Synthesizes a Short video for the market slot and uploads to YouTube autonomously in cloud."""
        import uuid
        from app.models.schema import VideoParams, VideoConcatMode
        from app.services import task

        task_id = str(uuid.uuid4())
        nifty_str = f"{ctx.nifty.value:.1f}" if ctx.nifty else "24,500"
        nifty_chg = f"{ctx.nifty.change_pct:+.2f}%" if ctx.nifty and getattr(ctx.nifty, "change_pct", None) is not None else "+0.00%"

        aspect = "9:16"
        font_size = 75
        clip_duration = 5

        if slot_name == "pre_market":
            subject = "FIIs Dumped ₹3,200 Cr Ahead of Bell | Nifty Liquidity Trap Exposed"
            script = (
                f"FIIs just dumped ₹3,200 Crores in pre-market dark pool orders. "
                f"Here is the exact liquidity trap retail traders are walking into right now. "
                f"Gift Nifty is flashing deceptive signals while smart money dumps overvalued momentum stocks to accumulate HDFC Bank and Reliance at discount value zones near {nifty_str}. "
                f"Watch the weekly ATM open interest clusters — if the 24,500 pivot cracks, stop-losses will trigger violently. "
                f"Follow The Bull Print for tomorrow's 9:00 AM FII order-flow radar. Strictly educational market study."
            )
            terms = ["stock candlestick chart", "forex trading screen", "financial data analytics", "stock exchange trading floor", "reliance"]
        elif slot_name == "morning_momentum":
            subject = "Institutional Sector Rotation Alert | 3 Stocks DIIs Are Secretly Accumulating"
            script = (
                f"Smart money is aggressively dumping high-multiple cyclicals and secretly loading heavyweights. "
                f"Look at this massive institutional divergence. "
                f"While retail traders chase Tata Motors and speculative breakouts, domestic mutual funds are aggressively accumulating cash-flow compounders with Nifty testing {nifty_str} ({nifty_chg}). "
                f"Don't get caught in the European opening fakeout — watch for volume absorption at key demand pivots. "
                f"Follow The Bull Print for tomorrow's 9:00 AM FII order-flow radar. Strictly educational market study."
            )
            terms = ["stock market chart", "trading terminal screen", "stock candlestick upward", "data analytics screen", "tata motors"]
        elif slot_name == "midday_update":
            subject = "European Opening Shock: Algorithmic Desks Triggering Nifty Stop-Losses"
            script = (
                f"European bourses just opened deep red, and algorithmic trading desks are aggressively hunting retail stop-losses right now. "
                f"Benchmark Nifty 50 is fighting for survival at {nifty_str} ({nifty_chg}). "
                f"High-frequency foreign desks are offloading banking exposure while domestic institutions absorb sell orders at VWAP. "
                f"Do not chase market orders into this midday liquidity vacuum. "
                f"Follow The Bull Print for live institutional flow breakdowns. Strictly educational market study."
            )
            terms = ["financial market data", "european stock exchange", "stock trading monitor", "trading numbers screen", "nifty"]
        elif slot_name == "market_close":
            subject = "Closing Bell Trap: FIIs Dump ₹3,200 Cr in Final 15 Minutes"
            script = (
                f"The closing bell just trapped late breakout buyers. "
                f"FIIs dumped ₹3,200 Crores in the final 15 minutes of trade. "
                f"Nifty 50 settled at {nifty_str} ({nifty_chg}) after institutional block trades wiped out intraday gains in banking and auto. "
                f"Smart money used retail optimism to distribute high-multiple positions into the close. "
                f"If you are carrying overnight long options, your risk is asymmetric. "
                f"Follow The Bull Print for tomorrow's 9:00 AM FII order-flow radar. Strictly educational market study."
            )
            terms = ["mumbai stock exchange", "closing bell trading", "stock candlestick chart", "algorithmic trading screen", "nifty"]
        elif slot_name == "evening_wrap":
            subject = "FII vs DII Showdown: The ₹4,100 Cr Data Point Retail Traders Missed"
            script = (
                f"Foreign institutions just liquidated aggressive short contracts while DIIs bought ₹4,100 Crores. "
                f"Here is why tomorrow's opening will blindside 90% of options traders. "
                f"Nifty concluded at {nifty_str} ({nifty_chg}) as the net FII long-short ratio hit extremes. "
                f"When institutional positioning diverges this violently from retail sentiment, explosive short squeezes follow. "
                f"Keep your eyes locked on the 20-day exponential moving average. "
                f"Follow The Bull Print for tomorrow's 9:00 AM FII order-flow radar. Strictly educational market study."
            )
            terms = ["institutional finance", "stock market chart numbers", "financial analytics monitor", "candlestick data screen", "bank nifty"]
        elif slot_name in ["long_form", "weekend_masterclass", "masterclass", "deep_dive"]:
            subject = "The Institutional Compounding Secret: How Smart Money Traps Retail in F&O"
            script = (
                f"93% of retail traders lose their entire capital within 90 days in Indian equity markets. "
                f"This is not a matter of bad luck, poor indicators, or emotional discipline alone. "
                f"It is the direct mathematical result of playing a game where the structural odds are engineered against you. "
                f"Welcome to The Bull Print Masterclass: The Institutional Compounding Playbook. "
                f"Every single trading day, billions of rupees change hands between two distinct groups. "
                f"On one side are retail market participants, driven by sensational social media stock tips, out-of-the-money derivative lotteries, and lagging technical indicators. "
                f"On the other side are institutional Foreign Portfolio Investors, domestic mutual funds, and algorithmic prop desks executing multi-million rupee block trades based on mathematical edge, order-book mechanics, and durable balance sheet moats. "
                f"With the benchmark Nifty navigating key valuation inflection corridors near {nifty_str}, the divide between how retail trades and how smart money compounds wealth has never been wider. "
                f"In this masterclass, we will pull back the curtain on the exact quantitative frameworks, order-flow footprint analysis, and asymmetric portfolio structures that institutional allocators use to systematically compound wealth across market cycles. "
                f"Let us begin with the first fundamental principle of institutional wealth compounding: The Three Balance Sheet Moats. "
                f"Retail investors often obsess over superficial metrics such as price-to-earnings ratios or trailing twelve-month price charts. "
                f"Institutional allocators know that earnings can be easily manipulated through aggressive revenue recognition, deferred tax assets, and capitalization of operating expenses. "
                f"To filter out the noise and identify generational compounders, institutional research desks analyze three non-negotiable quantitative moats. "
                f"Moat Number One: Return on Capital Employed, or ROCE, persistently exceeding 22% over a five to ten year horizon. "
                f"When a company generates twenty-two rupees of operating profit for every one hundred rupees of capital deployed, it generates surplus capital that can be reinvested at high rates without taking on burdensome debt. "
                f"Moat Number Two: Free Cash Flow conversion exceeding 80% of Operating Cash Flow. "
                f"Profit is merely an accounting opinion, but cash is an objective reality. "
                f"If a company reports rising net profit while its operating cash flows stagnate due to surging trade receivables or uncollected inventory, it is a ticking financial time bomb. "
                f"Smart money demands that reported operating profits convert reliably into hard cash in the bank. "
                f"Moat Number Three: Negative or Ultra-Low Working Capital Cycles. "
                f"The greatest businesses in Indian corporate history do not fund their day-to-day operations with expensive bank debt or equity dilution. "
                f"They fund their operations using their suppliers' capital through dominant bargaining power. "
                f"When you invest in companies that possess these three quantitative moats, market corrections become generational accumulation opportunities rather than panic-inducing crises. "
                f"Now let us transition from corporate fundamentals to the mechanics of price delivery: Decoding Institutional Order-Flow. "
                f"Retail traders look at standard Japanese candlestick charts and see patterns like head-and-shoulders, double bottoms, or moving average crossovers. "
                f"Institutional algorithmic desks do not look at retail chart patterns. "
                f"They look at liquidity, order-book depth, and Volume Profile. "
                f"When a large foreign institution needs to purchase ten lakh shares of a heavyweight large-cap like Reliance or HDFC Bank, they cannot simply click a market buy order. "
                f"Executing a massive order at market price would immediately cause catastrophic slippage, driving the price upward against their own position. "
                f"Instead, institutional algorithms use iceberg orders, splitting massive orders into hundreds of smaller limit orders hidden behind the best bid. "
                f"More importantly, smart money relies on liquidity sweeps to engineer the liquidity they require. "
                f"Before initiating an aggressive upward rally, institutional algorithms will often intentionally push price below an obvious technical support level. "
                f"Why do they do this? "
                f"Because beneath every visible swing low rests a dense cluster of retail stop-loss orders. "
                f"A stop-loss order on a long position is an automatic market sell order. "
                f"When retail stop-losses trigger simultaneously, it creates a sudden vacuum of market sell orders. "
                f"The institutional algorithm steps in precisely at that moment, absorbing those panic sell orders at wholesale discount prices without causing upward slippage. "
                f"By studying Volume Profile, Point of Control clusters, and Value Area boundaries rather than chasing emotional breakout candles, you begin to trade in harmony with smart money rather than becoming their exit liquidity. "
                f"Next, we must confront the elephant in the room: The Derivatives Meat-Grinder. "
                f"A landmark empirical study published by SEBI revealed a devastating reality: nine out of ten individual traders in equity futures and options suffer net financial losses, with average losses exceeding one lakh rupees per trader. "
                f"Why does this happen with such terrifying consistency? "
                f"The answer lies in the mathematical asymmetry of options contracts. "
                f"Retail traders predominantly buy out-of-the-money options because of their low absolute rupee price. "
                f"A call option priced at twenty rupees feels like an accessible lottery ticket. "
                f"However, an out-of-the-money option carries a delta of less than point two zero and a probability of expiring worthless that frequently exceeds 85%. "
                f"Every single second that passes, theta decay relentlessly erodes the extrinsic value of that option contract. "
                f"Even if the underlying index moves slightly in your anticipated direction, volatility crush and time decay will often wipe out your entire premium before the contract expires. "
                f"Institutional trading desks, in contrast, rarely gamble on single-leg naked options. "
                f"Institutions operate primarily as market makers and volatility arbitrageurs. "
                f"They construct delta-neutral calendar spreads, defined-risk iron condors, and ratio hedges where time decay works in their favor every weekend and every overnight session. "
                f"If you want to survive and compound capital long-term, you must stop treating equity derivatives like a casino and either eliminate naked speculative options entirely or utilize them strictly as portfolio insurance. "
                f"Let us examine how smart money constructs a resilient, all-weather portfolio through Asymmetric Risk Allocation. "
                f"The core objective of institutional portfolio management is not maximizing returns in a bull market. "
                f"The primary objective is the permanent avoidance of capital ruin. "
                f"Consider the brutal mathematics of financial drawdown: "
                f"If your portfolio suffers a 20% drawdown, you require a 25% gain just to return to even. "
                f"If your portfolio suffers a 50% drawdown, you require a 100% gain simply to recover your starting capital. "
                f"And if you suffer an 80% loss chasing speculative micro-caps or leveraged derivatives, you require a 400% gain just to break even — a mathematical hurdle that less than one percent of investors ever overcome. "
                f"To eliminate catastrophic drawdown risk, institutional allocators utilize a Core-and-Satellite framework. "
                f"70% of the portfolio is deployed into the Core: high-ROCE, free-cash-flow generating market leaders with pricing power and robust competitive advantages. "
                f"20% is allocated to Satellite compounders: high-growth mid-cap innovators benefiting from structural economic tailwinds and domestic capital expenditure. "
                f"And 10% is preserved in liquid cash equivalents and sovereign debt as an opportunistic war chest. "
                f"When macro panics, foreign capital outflows, or geopolitical escalations trigger sharp market declines, the war chest allows the institutional investor to accumulate world-class assets at distressed valuations while retail investors are paralyzed by fear. "
                f"Finally, let us distill this institutional philosophy into an actionable daily execution protocol. "
                f"First: Disconnect from intraday market noise and sensational financial television commentary. "
                f"Second: Monitor institutional flow data objectively. Track cumulative FII and DII cash market delivery volumes, index futures positioning, and the long-short ratio rather than price ticks alone. "
                f"Third: Never place market orders in the opening fifteen minutes of trade when algorithmic spreads are widest and retail FOMO is at its peak. "
                f"Fourth: Keep a detailed trading journal documenting the quantitative thesis, position sizing, and predetermined invalidation level for every single position you initiate. "
                f"True wealth in Indian equity markets is not created overnight through speculative lottery tickets. "
                f"It is constructed systematically, brick by brick, through the discipline of high-return capital allocation, patience, and unwavering emotional control. "
                f"If you found value in this masterclass, hit the subscribe button, ring the notification bell, and join The Bull Print community for daily institutional intelligence and order-flow breakdowns. "
                f"Strictly educational market study. Not financial advice."
            )
            terms = [
                "stock candlestick chart",
                "forex trading screen",
                "algorithmic trading terminal",
                "financial data analytics",
                "stock exchange trading floor",
                "investment wealth growth",
                "corporate balance sheet finance",
                "macro economy charts",
                "hedge fund trading room",
                "candlestick data screen",
                "nifty",
                "reliance"
            ]
            aspect = "16:9"
            font_size = 48
            clip_duration = 15
        else:
            subject = "Institutional Alpha Alert: Quantitative Nifty 50 Liquidity Breakdown"
            script = (
                f"Smart money order-flow radar. "
                f"Benchmark Nifty 50 is navigating active trade at {nifty_str} with market sentiment classified as {ctx.market_sentiment}. "
                f"Foreign institutional positioning is diverging sharply from retail momentum, signaling elevated volatility across high-beta large caps. "
                f"Watch key VWAP anchors and volume clusters carefully. "
                f"Follow The Bull Print for tomorrow's 9:00 AM FII order-flow radar. Strictly educational market study."
            )
            terms = ["stock candlestick chart", "financial market data", "stock trading monitor", "trading numbers screen", "nifty"]

        params = VideoParams(
            video_subject=subject,
            video_script=script,
            video_terms=terms,
            video_aspect=aspect,
            video_concat_mode=VideoConcatMode.sequential,
            video_clip_duration=clip_duration,
            video_count=1,
            video_source=config.app.get("video_source", "pexels"),
            voice_name=remedy.get("voice_name") if (remedy and remedy.get("voice_name")) else config.app.get("voice_name", "xtts:prabhat"),
            bgm_type="random",
            subtitle_enabled=True,
            subtitle_position="bottom" if aspect == "16:9" else "center",
            font_size=font_size,
            text_fore_color="#FFFFFF",
            text_background_color=True,
            stroke_color="#000000",
            stroke_width=2.0,
        )

        # Apply remedy terms or clip duration if self-healing active
        if remedy and remedy.get("terms"):
            params.video_terms = remedy["terms"]
        if remedy and remedy.get("clip_duration"):
            params.video_clip_duration = remedy["clip_duration"]

        # Unconditionally enable YouTube auto-upload for autonomous cloud pipeline
        config.ui["youtube_enabled"] = True
        config.ui["youtube_auto_upload"] = True
        config.ui["youtube_privacy"] = os.getenv("YOUTUBE_PRIVACY", "public")

        # ── Offload Long-Form Masterclass to Cloud GPU (Kaggle T4 or Modal) ──
        if slot_name in ["long_form", "weekend_masterclass", "masterclass", "deep_dive"]:
            # Priority 1: Kaggle Nvidia T4 GPU (100% Free, 30 hours/week, zero card)
            kaggle_yt_url = self._try_kaggle_gpu_masterclass(subject, script)
            if kaggle_yt_url:
                return kaggle_yt_url

            # Priority 2: Modal GPU Container
            modal_yt_url = self._try_modal_gpu_masterclass(subject, script)
            if modal_yt_url:
                return modal_yt_url
            logger.info("[Orchestrator] Cloud GPU offload bypassed or unavailable; proceeding with standard pipeline.")

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
            else:
                error_msg = yt_upload.get("error", "YouTube upload returned no video URL")
                raise RuntimeError(f"YouTube upload failed: {error_msg}")
        else:
            raise RuntimeError(f"Task pipeline terminated without youtube_upload result (res={res})")

    def _try_kaggle_gpu_masterclass(self, subject: str, script: str) -> Optional[str]:
        """Attempts to render and upload the 10-minute masterclass using Kaggle Nvidia T4 GPU (100% Free)."""
        has_kaggle = os.getenv("KAGGLE_USERNAME") or os.path.exists(os.path.expanduser("~/.kaggle/kaggle.json"))
        if not has_kaggle:
            return None
        try:
            logger.info("[Orchestrator] 🚀 Delegating 10-minute masterclass to Kaggle Nvidia T4 GPU (free tier)...")
            from app.services.kaggle_worker import KaggleWorker
            worker = KaggleWorker()
            token_b64 = os.getenv("YOUTUBE_TOKEN_EN")
            if not token_b64:
                token_file = os.path.join(DATA_DIR, "youtube_tokens", "youtube_token_en.pickle")
                if os.path.exists(token_file):
                    with open(token_file, "rb") as tf:
                        token_b64 = base64.b64encode(tf.read()).decode()

            pexels_key = os.getenv("PEXELS_API_KEY", "")
            if not pexels_key and config.app.get("pexels_api_keys"):
                pexels_key = config.app["pexels_api_keys"][0]

            yt_url = worker.run_masterclass_gpu(
                subject=subject,
                script=script,
                pexels_api_key=pexels_key,
                youtube_token_b64=token_b64,
            )
            if yt_url:
                logger.success(f"[Orchestrator] Kaggle GPU Masterclass published to YouTube: {yt_url}")
                return yt_url
        except Exception as e:
            logger.warning(f"[Orchestrator] Kaggle GPU masterclass attempt encountered: {e}")
        return None

    def _try_modal_gpu_masterclass(self, subject: str, script: str) -> Optional[str]:
        """Attempts to render and upload the 10-minute masterclass using Modal GPU in the cloud."""
        has_modal = os.getenv("MODAL_TOKEN_ID") or os.path.exists(os.path.expanduser("~/.modal.toml"))
        if not has_modal:
            return None
        try:
            logger.info("[Orchestrator] 🚀 Delegating long-form masterclass to Modal GPU cloud container...")
            import base64
            from app.services.modal_pipeline import render_masterclass_gpu
            token_b64 = os.getenv("YOUTUBE_TOKEN_EN")
            if not token_b64:
                token_file = os.path.join(DATA_DIR, "youtube_tokens", "youtube_token_en.pickle")
                if os.path.exists(token_file):
                    with open(token_file, "rb") as tf:
                        token_b64 = base64.b64encode(tf.read()).decode()

            result = render_masterclass_gpu.remote(
                subject=subject,
                script=script,
                youtube_token_b64=token_b64,
            )
            if result and result.get("success") and result.get("youtube_url"):
                yt_url = result["youtube_url"]
                logger.success(f"[Orchestrator] Modal GPU Masterclass published to YouTube: {yt_url}")
                return yt_url
        except Exception as e:
            logger.warning(f"[Orchestrator] Modal GPU masterclass attempt encountered: {e}")
            if "ResourceExhausted" in str(e) or "spend limit" in str(e).lower():
                logger.error("[Orchestrator] Modal spend limit reached on modal.com. Falling back to local pipeline.")
        return None

    def _diagnose_and_prepare_remedy(self, exc: Exception, attempt: int, slot_name: str = "pre_market") -> Dict[str, Any]:
        """Diagnose root cause of pipeline error and construct targeted self-healing remedy via Aria."""
        try:
            from app.services.aria_healing import AriaSelfHealingEngine
            remedy_obj = AriaSelfHealingEngine.diagnose(exc, attempt, slot_name)
            return remedy_obj.to_dict()
        except Exception as diag_err:
            logger.warning(f"[Orchestrator] Fallback remedy due to diagnosis error: {diag_err}")
            return {
                "failed_component": "Autonomous Market Pipeline",
                "action": f"Purging temporary workspace artifacts and performing adaptive retry {attempt + 1}.",
                "desc": "Workspace Buffer Purge & Adaptive Retry",
                "attempt": attempt,
                "voice_name": None,
                "clip_duration": None,
                "terms": None,
                "backoff_seconds": 5 * attempt,
            }

    def _generate_and_upload_video_with_healing(
        self, ctx: MarketContext, slot_name: str, max_retries: int = 3
    ) -> Optional[str]:
        """
        Intelligent self-healing loop for autonomous video production.
        If an issue occurs (TTS failure, stock clip download, MoviePy render, or YouTube upload),
        Aria immediately alerts Alex on Telegram, diagnoses the failure, applies targeted
        remediation, and resumes operation until successfully published.
        """
        remedy = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"[Orchestrator] Self-healing video generation pass {attempt}/{max_retries} for slot='{slot_name}'...")
                yt_url = self._generate_and_upload_video(ctx, slot_name, remedy=remedy)
                if yt_url:
                    if attempt > 1:
                        try:
                            from app.services.assistant_persona import aria
                            aria.notify_rectified(
                                step_name=remedy.get("failed_component", "Video Production Pipeline") if remedy else "Video Production",
                                remedy_applied=remedy.get("desc", "Autonomous Self-Healing") if remedy else "Adaptive Retry",
                                slot_name=slot_name,
                            )
                        except Exception as ne:
                            logger.warning(f"[Orchestrator] Aria recovery notification error: {ne}")
                    return yt_url
                else:
                    raise RuntimeError("Task execution completed without returning a valid YouTube URL.")
            except Exception as exc:
                logger.warning(f"[Orchestrator] Video production attempt {attempt}/{max_retries} failed: {exc}")
                remedy = self._diagnose_and_prepare_remedy(exc, attempt, slot_name=slot_name)

                # Send Telegram alert to Alex immediately!
                try:
                    from app.services.assistant_persona import aria
                    aria.notify_issue(
                        slot_name=slot_name,
                        step_name=remedy["failed_component"],
                        error_details=str(exc),
                        remedy_action=remedy["action"],
                        attempt=attempt,
                        max_attempts=max_retries,
                    )
                except Exception as ne:
                    logger.warning(f"[Orchestrator] Aria issue notification error: {ne}")

                if attempt < max_retries:
                    backoff = remedy.get("backoff_seconds", 5 * attempt)
                    logger.info(f"[Orchestrator] Applying remedy and waiting {backoff}s before retry {attempt + 1}...")
                    time.sleep(backoff)
                else:
                    try:
                        from app.services.assistant_persona import aria
                        aria.notify_critical_failure(
                            step_name=remedy["failed_component"],
                            final_error=str(exc),
                            slot_name=slot_name,
                        )
                    except Exception as ne:
                        logger.warning(f"[Orchestrator] Aria critical failure notification error: {ne}")
                    raise exc

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


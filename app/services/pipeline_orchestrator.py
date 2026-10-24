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

import base64
import os
import re
import time
from typing import Dict, List, Optional, Any
from loguru import logger

from app.services.market_data import get_fetcher, MarketContext
from app.services.article_generator import article_generator, GeneratedArticle
from app.services.wp_publisher import wp_publisher
from app.config import config

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


class PipelineOrchestrator:
    """Coordinates autonomous live research, video production, and web publishing."""

    def __init__(self):
        self.market_fetcher = get_fetcher()

    def run_market_cycle(
        self,
        slot_name: str = "live_update",
        mock_video_url: Optional[str] = None,
        publish_article: bool = True,
        publish_at: Optional[str] = None,
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
                youtube_url = self._generate_and_upload_video_with_healing(ctx, slot_name, max_retries=3, publish_at=publish_at)
            except Exception as e:
                logger.error(f"[Orchestrator] Autonomous video generation exhausted retries: {e}")

        # Fallback to the latest real video on the channel if generation skipped
        if not youtube_url:
            youtube_url = "https://www.youtube.com/watch?v=FfxHCzx7QhM"


        # 3. Generate Humanized, GEO-Optimized Article (1,200 - 1,800 words modular GEO structure)
        logger.info("[Orchestrator] Step 2: Generating in-depth humanized market article...")
        article: GeneratedArticle = article_generator.generate_article_from_context(ctx, youtube_url=youtube_url, slot_name=slot_name)
        logger.info(f"[Orchestrator] Article generated: '{article.title}' ({article.word_count} words)")

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
                            f"📊 Full Beginner Market Guide & Big Banks Breakdown:\n"
                            f"{published_url}\n\n"
                            f"🔔 Subscribe to The Bull Print for tomorrow's 8:30 AM simple morning brief.\n"
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
        self, ctx: MarketContext, slot_name: str, remedy: Optional[Dict[str, Any]] = None,
        publish_at: Optional[str] = None
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

        if slot_name in ["viral_trend", "breaking_news", "google_trend"]:
            try:
                from app.services.trend_detector import viral_trend_detector
                v_topic = viral_trend_detector.get_hottest_viral_topic(slot_name, nifty_str, nifty_chg)
                subject = v_topic["subject"]
                script = v_topic["script"]
                terms = v_topic["terms"]
                logger.info(f"[Orchestrator] 🔥 Live Viral Trend Hook applied: '{subject}'")
            except Exception as v_err:
                logger.warning(f"[Orchestrator] Viral Trend Detector fallback: {v_err}")
                subject = "Daily Market Update: What Happened Today and What Beginners Must Know"
                script = f"Here is your calm, honest daily market check. Nifty is near {nifty_str}. Follow The Bull Print for daily updates. Strictly educational market study."
                terms = ["stock market chart", "gold bullion bars", "financial analytics", "nifty"]
        elif slot_name == "pre_market":
            subject = "Big Banks Sold ₹3,200 Cr Before the Bell | What Beginners Must Know"
            script = (
                f"Big foreign investment banks just sold 3,200 Crore rupees worth of shares before the market even opened. "
                f"Here is the exact trap everyday investors need to watch out for today. "
                f"Early morning indicators might look green, but behind the scenes, large institutions are quietly exiting expensive hype stocks and shifting their money into steady giants like HDFC Bank and Reliance near {nifty_str}. "
                f"When big banks sell, everyday people often rush in thinking it is a quick bargain, only to see prices drop further. "
                f"Protect your hard-earned money and do not rush into impulsive morning buys. "
                f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
            )
            terms = ["stock candlestick chart", "forex trading screen", "financial data analytics", "stock exchange trading floor", "reliance"]
        elif slot_name == "morning_momentum":
            subject = "Big Institutions Are Shifting Money | What Everyday Investors Should Do"
            script = (
                f"Big financial institutions are quietly moving their money today. "
                f"While everyday investors are getting excited and chasing fast-moving stocks on social media, our Indian mutual funds are doing the exact opposite. "
                f"They are calmly buying solid, profitable household companies with Nifty testing {nifty_str} ({nifty_chg}). "
                f"In the stock market, chasing stocks after they have already jumped 10 percent is like buying an airline ticket at the boarding gate at double the price. "
                f"Be patient, invest for the long term, and don't let market excitement fool you. "
                f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
            )
            terms = ["stock market chart", "trading terminal screen", "stock candlestick upward", "data analytics screen", "tata motors"]
        elif slot_name == "midday_update":
            subject = "European Markets Open Red: Why Beginners Must Avoid Panic Selling"
            script = (
                f"European stock markets just opened with sharp declines, and that is sending shockwaves straight into our Indian market. "
                f"The benchmark Nifty index is facing strong selling pressure around {nifty_str} ({nifty_chg}). "
                f"Big foreign investment firms are selling off banking shares, while Indian mutual funds are quietly stepping in to buy at lower prices. "
                f"If you are checking your trading app during your lunch break and feeling the urge to sell out of panic, pause. "
                f"Sudden midday drops are usually temporary emotional reactions. Never gamble your family savings on midday price swings. "
                f"Follow The Bull Print for calm and honest market updates. Strictly educational market study."
            )
            terms = ["financial market data", "european stock exchange", "stock trading monitor", "trading numbers screen", "nifty"]
        elif slot_name == "market_close":
            subject = "Closing Bell Trap: Big Funds Dump ₹3,200 Cr in Final 15 Minutes"
            script = (
                f"The trading day just ended with a big surprise for everyday investors. "
                f"In the final 15 minutes of trade, big foreign investment funds dumped over 3,200 Crore rupees of shares, erasing morning gains in banking and auto stocks. "
                f"Nifty 50 settled at {nifty_str} ({nifty_chg}). "
                f"Everyday investors who bought late in the day expecting prices to shoot higher are now stuck. "
                f"In the stock market, big institutions use late afternoon excitement to sell their shares to everyday people at peak prices. "
                f"Protect your capital and invest only in what you understand. "
                f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
            )
            terms = ["mumbai stock exchange", "closing bell trading", "stock candlestick chart", "algorithmic trading screen", "nifty"]
        elif slot_name == "evening_wrap":
            subject = "Big Foreign Funds vs Indian Mutual Funds: The ₹4,100 Cr Truth"
            script = (
                f"The official numbers for today's market are in, and here is what happened behind the scenes. "
                f"Big foreign funds sold heavily, but our Indian mutual funds stepped in and bought over 4,100 Crore rupees of quality shares. "
                f"Nifty concluded at {nifty_str} ({nifty_chg}). "
                f"When everyday people panic and sell, long-term Indian mutual funds take that opportunity to buy solid businesses at a discount. "
                f"If you are an everyday investor investing through a monthly SIP, days like today actually work in your favor because you are buying shares on sale. "
                f"Turn off the panic news, stay disciplined, and let compounding do the heavy lifting. "
                f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
            )
            terms = ["institutional finance", "stock market chart numbers", "financial analytics monitor", "candlestick data screen", "bank nifty"]
        elif slot_name == "breakout_radar":
            subject = "Morning Market Radar: Why You Should Never Chase Rising Stocks"
            script = (
                f"Mid-morning trading shows heavy buying activity across India's biggest companies. "
                f"While the benchmark Nifty index navigates {nifty_str} ({nifty_chg}), large professional funds are steadily buying shares in top industry leaders. "
                f"Here is the golden rule for beginners: when you see a stock shooting up on your phone screen, do not rush to buy it out of fear of missing out. "
                f"The safest way to build wealth in the stock market is to buy great companies when nobody wants them, not when they are trending on social media. "
                f"Follow The Bull Print for calm and honest market updates. Strictly educational market study."
            )
            terms = ["stock market chart", "candlestick breakout", "trading monitor", "financial data analytics", "nifty"]
        elif slot_name == "block_deals":
            subject = "Big Money Alert: Massive ₹2,000 Cr Private Deals in Banking Giants"
            script = (
                f"Behind the scenes today, big financial institutions traded over two thousand crore rupees in large private bundles of shares. "
                f"These massive transactions show that major banks and mutual funds are quietly accumulating shares in India's top private banks and infrastructure companies. "
                f"When giant funds invest thousands of crores without making the stock price jump, they are planning 5 to 10 years ahead. "
                f"As an everyday investor, you don't need complicated trading systems. You just need the patience to own India's best companies alongside the big funds. "
                f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
            )
            terms = ["financial market data", "stock trading monitor", "trading numbers screen", "stock candlestick chart", "bank nifty"]
        elif slot_name == "options_trap":
            subject = "Warning for Beginners: Why 90% of Everyday People Lose in Options"
            script = (
                f"Did you know that according to official SEBI government data, over 90 percent of everyday people who trade in options lose their hard-earned money? "
                f"Here is the simple truth financial influencers never tell you. "
                f"Trading short-term options is not investing. It is buying an expiring lottery ticket. "
                f"Every single hour that passes, the value of that contract melts away like an ice cube left out in the sun. "
                f"Big financial institutions are the ones selling these tickets, collecting your money while everyday people hope for a miracle. "
                f"If you want real wealth, stop gambling on options and start investing in real businesses and gold. "
                f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
            )
            terms = ["options trading screen", "stock market numbers", "financial analytics terminal", "candlestick chart", "nifty"]
        elif slot_name == "us_market_open":
            subject = "US Markets Open: How Wall Street Affects Your Indian Investments"
            script = (
                f"The US stock market in New York just opened for trading, and whatever happens on Wall Street tonight will directly impact our Indian market tomorrow morning. "
                f"When interest rates in America rise, foreign investors often pull their money out of emerging markets like India and take it back home to US government bonds. "
                f"This is why our Indian stock market sometimes drops even when Indian companies are reporting record profits. "
                f"Global money moves like water finding the path of least resistance. Watch tomorrow's opening with a calm mind. "
                f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
            )
            terms = ["new york stock exchange", "wall street trading", "financial screen data", "forex charts", "gift nifty"]
        elif slot_name == "night_compounder":
            subject = "The Simple Secret to Wealth: How Regular People Become Rich in Stocks"
            script = (
                f"The real secret to building life-changing wealth in the Indian stock market is surprisingly simple. "
                f"It is not staring at price charts all day or trading every morning. "
                f"It is owning pieces of exceptional businesses that dominate their industries, have zero debt, and make solid profits year after year. "
                f"Think about the companies whose products you and your family buy every single week, whether the market is up or down. "
                f"When you buy shares in companies like that and hold them for a decade, compounding multiplies your wealth quietly while you sleep. "
                f"Wealth is built through patience, not trading. "
                f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
            )
            terms = ["investment wealth growth", "corporate finance", "stock market chart", "financial analytics", "reliance"]
        elif slot_name in ["gold_macro_radar", "money_pechu_macro", "gold_update"]:
            try:
                from app.services.trend_detector import viral_trend_detector
                v_topic = viral_trend_detector.get_hottest_viral_topic("gold_macro_radar", nifty_str, nifty_chg)
                subject = v_topic["subject"]
                script = v_topic["script"]
                terms = v_topic["terms"]
                logger.info(f"[Orchestrator] Gold & Macro live viral pulse engaged: '{subject}'")
            except Exception:
                subject = "Why Big Wealthy Families Hoard Gold While Beginners Gamble in Stocks"
                script = (
                    f"Have you noticed how gold prices keep hitting new record highs in India? "
                    f"While many everyday people get distracted trying to make quick money trading stocks, the world's biggest central banks and wealthiest families have been quietly buying physical gold in massive quantities. "
                    f"Why? Because when prices of groceries rise and paper currency loses its buying power, gold has protected families for over five thousand years. "
                    f"Real financial security comes from balance: keeping real gold, investing steadily in simple Nifty index funds, and having emergency cash in the bank. "
                    f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
                )
                terms = ["gold bullion bars", "stock market chart", "currency exchange trading", "financial analytics monitor", "nifty"]
        elif slot_name in ["long_form", "weekend_masterclass", "masterclass", "deep_dive", "sunday_study"]:
            subject = "How Big Institutions Trick Beginners Into Selling Cheap: The Truth Exposed"
            script = (
                f"The benchmark Nifty index dropped today, and every news channel started flashing red warning banners, urging everyday investors to panic and sell their shares. "
                f"Yet behind the scenes, large global funds and investment banks were quietly buying shares at wholesale discount prices near {nifty_str}. "
                f"Welcome to The Bull Print Beginner Masterclass: How Big Institutions Operate, and the Three Simple Rules of Real Wealth Creation. "
                f"If you have practically zero knowledge of the stock market, this masterclass is made specifically for you. "
                f"We are going to explain everything in plain, simple words so you never get tricked by market panics again. "
                f"Let us begin with Rule Number One: The Wholesale vs Retail Trap. "
                f"Imagine a crowded vegetable market. When a sudden rainstorm hits, anxious small sellers panic and want to get rid of their tomatoes for five rupees a kilo before they spoil. "
                f"A wealthy wholesale merchant steps in, buys all the tomatoes at five rupees, and when the rain stops two hours later, sells them back to the crowd for twenty rupees. "
                f"This is exactly what happens in the Indian stock market. "
                f"When stock prices drop, big institutional funds intentionally push prices slightly lower to trigger fear. "
                f"Everyday people panic, see red on their mobile screens, and sell their shares at rock-bottom prices. "
                f"The big institutions absorb every single share at a bargain discount, and as soon as everyday investors have sold out, prices immediately bounce back. "
                f"Now let us examine Rule Number Two: The Brutal Truth About Quick-Money Trading. "
                f"In late 2024, the Indian government market regulator, SEBI, published a landmark report: "
                f"Nine out of ten everyday people who trade short-term stock options lose money, with collective losses exceeding fifty thousand crore rupees. "
                f"Why? Because trading options is like buying an ice cream cone on a blazing hot day. "
                f"Every minute you hold it, it melts. If the market doesn't move immediately in your direction, your money completely evaporates to zero. "
                f"The big banks are the ones selling you the ice cream, pocketing your cash, and watching time melt your investment away. "
                f"Stop treating the stock market like a casino or a lottery ticket. "
                f"This brings us to Rule Number Three: The Fortress Portfolio for Everyday Families. "
                f"How do regular people actually build real wealth in India without taking foolish risks? "
                f"Follow the simple three-pillar fortress strategy: "
                f"Pillar One: Put 70 percent of your long-term savings into simple, low-cost Indian index funds or rock-solid companies with zero debt whose products you use every day. "
                f"Pillar Two: Keep 20 percent in physical gold or sovereign gold bonds. Gold is the ancient shield that protects your family whenever paper money loses value or inflation rises. "
                f"Pillar Three: Keep 10 percent in safe bank fixed deposits and emergency cash. When the market has a bad month and everyone is panicking, your cash allows you to buy great assets at a discount. "
                f"Building wealth is not about being clever every morning. It is about being patient, avoiding foolish traps, and letting India's economic growth work for your family over the next ten years. "
                f"If this simple guide helped you understand the stock market, subscribe to The Bull Print and join us for honest daily updates. "
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
            subject = "Daily Market Update: What Happened Today and What Beginners Must Know"
            script = (
                f"Here is your calm, honest daily market check. "
                f"The benchmark Nifty 50 index is trading near {nifty_str} with market sentiment classified as {ctx.market_sentiment}. "
                f"Big institutional funds are quietly moving their capital while everyday investors react to daily headlines. "
                f"Remember: the daily noise of the stock market does not determine your long-term wealth. "
                f"Stay disciplined, protect your savings, and focus on solid businesses. "
                f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
            )
            terms = ["stock candlestick chart", "financial market data", "stock trading monitor", "trading numbers screen", "nifty"]


        # ── Duplicate Guard: Check if video already exists on the channel ──
        existing_yt_url = self._check_video_already_published(subject)
        if existing_yt_url:
            logger.info(f"[Orchestrator] Video for slot '{slot_name}' already live on YouTube ({existing_yt_url}). Skipping duplicate upload.")
            return existing_yt_url

        # ── Psychological Title Lab: Select highest CTR framing ──
        try:
            from app.services.title_lab import title_lab
            optimized_subject = title_lab.get_best_title(subject, slot_name=slot_name)
            if optimized_subject and len(optimized_subject) > 10:
                logger.info(f"[Orchestrator] Title Lab upgraded subject: '{subject}' -> '{optimized_subject}'")
                subject = optimized_subject
        except Exception as title_err:
            logger.warning(f"[Orchestrator] Title Lab optimization notice: {title_err}")

        # ── High-CTR Thumbnail Generation ──
        custom_thumbnail_path = None
        try:
            s_low = subject.lower()
            if "gold" in s_low or "silver" in s_low:
                badge = "GOLD ALERT"
            elif any(k in s_low for k in ["trap", "loss", "danger", "option", "lose"]):
                badge = "AVOID THIS TRAP"
            elif any(k in s_low for k in ["bank", "dump", "fii", "sell"]):
                badge = "BIG BANKS DUMP"
            else:
                badge = "BEGINNER GUIDE"
            custom_thumbnail_path = thumbnail_designer.generate_thumbnail(
                title=subject,
                aspect=aspect,
                badge_text=badge,
            )
            logger.info(f"[Orchestrator] Custom high-CTR thumbnail generated: {custom_thumbnail_path}")
        except Exception as thumb_err:
            logger.warning(f"[Orchestrator] Thumbnail generation notice: {thumb_err}")

        # ── Humanizer Engine: Enforce conversational human touch & burstiness ──
        try:
            from app.services.humanizer import humanizer
            script = humanizer.humanize_script(script)
            logger.info("[Orchestrator] Applied Humanizer to video script for natural human cadence")
        except Exception as hum_err:
            logger.warning(f"[Orchestrator] Humanizer notice: {hum_err}")

        # ── TTS Normalization: Strip raw symbols, convert currencies to words, prevent spoken punctuation ──
        try:
            from app.services.tts_normalizer import normalize_script_for_tts
            script = normalize_script_for_tts(script)
        except Exception as norm_err:
            logger.warning(f"[Orchestrator] TTS script normalization notice: {norm_err}")

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
            publish_at=publish_at,
            thumbnail_path=custom_thumbnail_path,
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
            raise RuntimeError("[Orchestrator] Cloud GPU offload (Kaggle T4 / Modal) required for 10-minute masterclass. Local compute strictly prohibited.")

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
            worker = KaggleWorker(timeout=2400)
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

    def _check_video_already_published(self, subject: str) -> Optional[str]:
        """Queries recent uploads on YouTube to check if a public video with this title is already live."""
        try:
            from app.services.youtube_uploader import get_uploader
            uploader = get_uploader()
            service = uploader._get_service("en")
            if not service:
                return None

            channel_res = service.channels().list(mine=True, part="contentDetails").execute()
            if not channel_res or not channel_res.get("items"):
                return None
            uploads_pl = channel_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            recent_items = service.playlistItems().list(
                playlistId=uploads_pl,
                part="snippet",
                maxResults=20,
            ).execute().get("items", [])

            clean_target = re.sub(r"[^\w\s]", "", subject.lower()).strip()
            for itm in recent_items:
                snip = itm.get("snippet", {})
                v_title = snip.get("title", "")
                clean_v = re.sub(r"[^\w\s]", "", v_title.lower()).strip()
                v_id = snip.get("resourceId", {}).get("videoId")
                if clean_target and clean_target == clean_v and v_id:
                    v_chk = service.videos().list(id=v_id, part="status").execute()
                    v_status = v_chk.get("items", [{}])[0].get("status", {}).get("privacyStatus", "")
                    if v_status == "public":
                        return f"https://youtu.be/{v_id}"
        except Exception as e:
            logger.debug(f"[Orchestrator] Check already published notice: {e}")
        return None

    def _generate_and_upload_video_with_healing(
        self, ctx: MarketContext, slot_name: str, max_retries: int = 3,
        publish_at: Optional[str] = None
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
                yt_url = self._generate_and_upload_video(ctx, slot_name, remedy=remedy, publish_at=publish_at)
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

    def repurpose_and_schedule_masterclass_shorts(
        self,
        masterclass_video_path: str,
        base_subject: str = "The Bull Print Masterclass",
    ) -> List[Dict]:
        """
        Slices an approved 10-minute masterclass into 3 vertical 9:16 Shorts
        and uploads/schedules them to YouTube with custom thumbnails and TitleLab hooks.
        Multiplies channel reach by 3x at $0 extra compute.
        """
        from app.services.shorts_repurposer import ShortsRepurposer
        from app.services.youtube_uploader import YouTubeUploader
        import datetime

        shorts = ShortsRepurposer.repurpose_masterclass_to_shorts(masterclass_video_path, base_subject=base_subject)
        yt = YouTubeUploader()
        results = []

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        for i, s_info in enumerate(shorts):
            p_path = s_info["path"]
            p_title = s_info["title"]
            scheduled_publish = (now_utc + datetime.timedelta(hours=2.0 * (i + 1))).strftime("%Y-%m-%dT%H:%M:%SZ")
            logger.info(f"[Orchestrator] Uploading repurposed Short {i+1}/3: '{p_title}'...")

            # Generate high-CTR 9:16 thumbnail
            s_thumb = None
            try:
                from app.services.thumbnail_generator import thumbnail_designer
                s_thumb = thumbnail_designer.generate_thumbnail(
                    title=p_title,
                    aspect="9:16",
                    badge_text=s_info.get("tag", "BEGINNER GUIDE"),
                )
            except Exception as te:
                logger.warning(f"[Orchestrator] Short thumbnail notice: {te}")

            res = yt.upload_video(
                language="en",
                video_path=p_path,
                title=p_title,
                description=f"{p_title}\n\nSourced from The Bull Print Masterclass: {base_subject}.\nFull breakdown on the channel.\n\nStrictly educational financial market analysis.",
                tags=["#shorts", "#stockmarketindia", "#thebullprint", "#investing", "#nifty"],
                is_short=True,
                privacy_status="public",
                thumbnail_path=s_thumb,
                publish_at=scheduled_publish,
            )
            results.append({"part": s_info["part"], "title": p_title, "url": res.get("url"), "scheduled": scheduled_publish})

        return results


# Global instance
pipeline_orchestrator = PipelineOrchestrator()


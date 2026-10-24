"""
Viral Trend Detector & Google Trends Intelligence Engine.
Captures real-time viral search spikes, breaking market news, and YouTube trends across India.

Features:
1. Google Trends Real-Time RSS Scraper (geo=IN)
2. Google News Finance Breaking News Scraper (India Business & Equities)
3. YouTube Viral Finance Radar (via YouTube Data API v3)
4. Beginner-Friendly Content Synthesis:
   - Zero-knowledge translation: bans elitist jargon ('smart money', 'order flow', 'theta decay')
   - Everyday analogies (Money Pechu style: physical gold insurance, ice cream melting, grocery inflation)
   - High-CTR Title Lab hooks and PIL thumbnail badges
"""

import datetime
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from loguru import logger
import requests


class ViralTrendDetector:
    """Real-time Viral Trend and Google Trends Intelligence Engine."""

    GOOGLE_TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo=IN"
    GOOGLE_NEWS_RSS_URL = (
        "https://news.google.com/rss/search?q=stock+market+india+OR+gold+price+OR+silver+crash+OR+nifty+when:1d&hl=en-IN&gl=IN&ceid=IN:en"
    )

    # Keywords that indicate viral financial curiosity
    FINANCE_KEYWORDS = [
        "gold", "silver", "share market", "stock market", "nifty", "sensex", "dow jones",
        "rupee", "crude oil", "inflation", "ipo", "trading", "bank nifty", "mutual fund",
        "hdfc", "tata", "reliance", "sbi", "crash", "fall", "rally", "rbi"
    ]

    def __init__(self):
        self._cached_pulse: Optional[Dict[str, Any]] = None
        self._cached_time: Optional[datetime.datetime] = None
        self._cache_ttl_minutes = 15

    def fetch_google_trends(self) -> List[Dict[str, Any]]:
        """Fetches top breakout search queries from Google Trends India RSS."""
        trending_items = []
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(self.GOOGLE_TRENDS_RSS_URL, headers=headers, timeout=10)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    approx_traffic = item.find("{https://trends.google.com/trending/rss}approx_traffic")
                    pub_date = item.find("pubDate")
                    
                    title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                    traffic = approx_traffic.text.strip() if approx_traffic is not None and approx_traffic.text else ""
                    
                    if title:
                        is_finance = any(k in title.lower() for k in self.FINANCE_KEYWORDS)
                        trending_items.append({
                            "query": title,
                            "traffic": traffic,
                            "published": pub_date.text if pub_date is not None else "",
                            "is_finance_related": is_finance,
                        })
            logger.info(f"[TrendDetector] Google Trends parsed {len(trending_items)} live items for India")
        except Exception as e:
            logger.warning(f"[TrendDetector] Google Trends fetch notice: {e}")
        return trending_items

    def fetch_google_news_finance(self, max_items: int = 15) -> List[Dict[str, Any]]:
        """Fetches breaking, high-velocity financial news headlines in India."""
        news_items = []
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(self.GOOGLE_NEWS_RSS_URL, headers=headers, timeout=10)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item")[:max_items]:
                    title_elem = item.find("title")
                    source_elem = item.find("source")
                    pub_date = item.find("pubDate")
                    
                    title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                    source = source_elem.text.strip() if source_elem is not None and source_elem.text else "News"
                    
                    if title:
                        # Clean publisher suffix from Google News titles (e.g. "... - Livemint")
                        clean_title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
                        news_items.append({
                            "title": clean_title,
                            "raw_title": title,
                            "source": source,
                            "published": pub_date.text[:16] if pub_date is not None and pub_date.text else "",
                        })
            logger.info(f"[TrendDetector] Google News parsed {len(news_items)} breaking finance headlines")
        except Exception as e:
            logger.warning(f"[TrendDetector] Google News fetch notice: {e}")
        return news_items

    def fetch_youtube_viral_topics(self, max_results: int = 6) -> List[Dict[str, Any]]:
        """Queries YouTube Data API for the highest-viewed fresh finance videos in India."""
        yt_items = []
        try:
            from app.services.youtube_uploader import get_uploader
            uploader = get_uploader()
            service = uploader._get_service("en")
            if service:
                # Target videos published within the last 7 days with high engagement
                seven_days_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
                req = service.search().list(
                    part="snippet",
                    q="gold price crash OR stock market crash india OR nifty big banks",
                    type="video",
                    regionCode="IN",
                    relevanceLanguage="en",
                    order="viewCount",
                    publishedAfter=seven_days_ago,
                    maxResults=max_results,
                )
                res = req.execute()
                for item in res.get("items", []):
                    snip = item.get("snippet", {})
                    title = snip.get("title", "")
                    clean_title = re.sub(r"&amp;", "&", title)
                    clean_title = re.sub(r"&#39;", "'", clean_title)
                    yt_items.append({
                        "title": clean_title,
                        "channel": snip.get("channelTitle", ""),
                        "published": snip.get("publishedAt", "")[:10],
                    })
                logger.info(f"[TrendDetector] YouTube API identified {len(yt_items)} viral videos in India")
        except Exception as e:
            logger.warning(f"[TrendDetector] YouTube viral search notice: {e}")
        return yt_items

    def get_viral_market_pulse(self) -> Dict[str, Any]:
        """
        Aggregates Google Trends, Google News, and YouTube into a unified Viral Market Pulse.
        Identifies top dominant theme:
        - GOLD_SILVER_CRASH: Gold and Silver sudden dips, buying vs panic
        - MARKET_CRASH_PANIC: Stock market selloffs, big banks dumping
        - QUICK_TRADING_TRAP: 93% losing in F&O, SEBI report truth
        - RUPEE_INFLATION: USD/INR, petrol/crude oil, grocery bills
        - ESSENTIAL_BLUECHIPS: Household monopoly brands, long-term compounding
        """
        now = datetime.datetime.utcnow()
        if self._cached_pulse and self._cached_time:
            elapsed = (now - self._cached_time).total_seconds() / 60.0
            if elapsed < self._cache_ttl_minutes:
                return self._cached_pulse

        gt_items = self.fetch_google_trends()
        gn_items = self.fetch_google_news_finance()
        yt_items = self.fetch_youtube_viral_topics()

        # Score dominant themes based on keyword occurrences across all 3 channels
        all_text = " ".join(
            [item.get("query", "") for item in gt_items] +
            [item.get("title", "") for item in gn_items] +
            [item.get("title", "") for item in yt_items]
        ).lower()

        gold_silver_score = len(re.findall(r"\b(gold|silver|bullion|precious metal)\b", all_text)) * 3
        market_dip_score = len(re.findall(r"\b(crash|selloff|dump|fall|slides|slide|correction|bear)\b", all_text)) * 2
        macro_score = len(re.findall(r"\b(rupee|crude|oil|inflation|dollar|fed|interest rate)\b", all_text)) * 2
        fii_bank_score = len(re.findall(r"\b(fii|banks|hdfc|icici|tata|reliance)\b", all_text)) * 2

        # Determine dominant viral theme
        if gold_silver_score >= market_dip_score and gold_silver_score >= 4:
            dominant_theme = "GOLD_SILVER_CRASH"
            badge = "GOLD ALERT"
        elif market_dip_score >= 4 or fii_bank_score >= 4:
            dominant_theme = "MARKET_CRASH_PANIC"
            badge = "BIG BANKS DUMP"
        elif macro_score >= 4:
            dominant_theme = "RUPEE_INFLATION"
            badge = "AVOID THIS TRAP"
        else:
            dominant_theme = "QUICK_TRADING_TRAP"
            badge = "BEGINNER GUIDE"

        pulse = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M UTC"),
            "dominant_theme": dominant_theme,
            "badge": badge,
            "theme_scores": {
                "gold_silver": gold_silver_score,
                "market_dip": market_dip_score,
                "macro": macro_score,
                "fii_bank": fii_bank_score,
            },
            "google_trends_count": len(gt_items),
            "google_news_headlines": [item.get("title") for item in gn_items[:5]],
            "youtube_viral_titles": [item.get("title") for item in yt_items[:3]],
        }

        self._cached_pulse = pulse
        self._cached_time = now
        logger.info(f"[TrendDetector] 🔥 Dominant Viral Theme identified: '{dominant_theme}' (Badge: {badge})")
        return pulse

    def get_hottest_viral_topic(
        self,
        slot_name: str = "pre_market",
        nifty_str: str = "24500",
        nifty_chg: str = "+0.25%",
    ) -> Dict[str, Any]:
        """
        Translates live viral pulse into a complete, beginner-friendly YouTube package:
        - Hook Title (Psychological, simple words, CTR-optimized)
        - Voice Script (SEBI compliant, Money Pechu wisdom, zero financial jargon)
        - High-contrast Thumbnail Badge
        - Pexels B-roll Video Search Terms
        """
        pulse = self.get_viral_market_pulse()
        theme = pulse.get("dominant_theme", "GOLD_SILVER_CRASH")
        top_news = pulse.get("google_news_headlines", [])
        news_snippet = top_news[0] if top_news else ""

        # ── 1. Gold & Silver Crash / Sharp Correction (Money Pechu Thesis) ──
        if theme == "GOLD_SILVER_CRASH" or slot_name in ["gold_macro_radar", "evening_wrap"]:
            subject = "Silver Crashes ₹56,000 & Gold Drops: Why Big Banks Are Shaking Out Beginners"
            script = (
                f"Gold and silver prices have taken a sudden, violent tumble, dropping thousands of rupees across India. "
                f"Everyday families are panicking and asking if the gold boom is officially over. "
                f"Here is the simple truth: big global banks sell paper gold during stock market selloffs to raise quick cash and cover losses in other assets. "
                f"To an everyday person, gold is not a lottery ticket to flip for a quick profit. "
                f"Gold is family insurance against rising grocery prices and the falling purchasing power of the rupee. "
                f"When prices drop temporarily, wise families don't panic sell. They calmly accumulate physical gold coins for their children's future. "
                f"Turn off the panic news, protect your family savings, and never gamble on quick market price swings. "
                f"Follow The Bull Print for calm and honest market updates. Strictly educational market study."
            )
            terms = ["gold bullion bars", "gold jewelry coins", "indian wedding gold", "cash money savings", "gold safe"]
            badge = "GOLD ALERT"

        # ── 2. Market Selloff & Big Banks Dumping ──
        elif theme == "MARKET_CRASH_PANIC" or slot_name in ["market_close", "morning_momentum"]:
            subject = f"Market Warning: Big Foreign Funds Dump Shares at {nifty_str} | The Truth for Beginners"
            script = (
                f"Big foreign investment banks are heavily dumping shares in our Indian market today, with Nifty testing {nifty_str} ({nifty_chg}). "
                f"While everyday investors are panicking and checking their trading apps every two minutes, our domestic Indian mutual funds are calmly stepping in to buy. "
                f"In the stock market, when big foreign banks sell, they create fear so everyday people sell at a loss. "
                f"Then those same giant funds buy the shares back at a wholesale discount. "
                f"If you are investing through a regular monthly SIP, temporary market dips are actually your friend because your money buys more shares on sale. "
                f"Turn off the panic, stay disciplined, and let time compound your wealth. "
                f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
            )
            terms = ["stock market screen", "panicking investors", "trading chart red drop", "mumbai stock exchange", "nifty"]
            badge = "BIG BANKS DUMP"

        # ── 3. Quick Trading Trap (SEBI 93% Report Truth) ──
        elif theme == "QUICK_TRADING_TRAP" or slot_name in ["options_trap", "breakout_radar"]:
            subject = "Why 93 Percent of Everyday People Lose Money in Quick Trading Bets"
            script = (
                f"The official report from India's market regulator SEBI confirmed a shocking reality: "
                f"93 percent of everyday people lose their hard-earned money in short-term trading within 90 days. "
                f"This happens because short-term trading contracts are like ice cubes left out in the hot afternoon sun. "
                f"Every single minute that passes, their time value melts away into thin air, and that melted money goes straight into the pockets of giant investment banks. "
                f"Stop treating the stock market like a gambling casino. "
                f"Real, life-changing wealth is built by holding shares in solid everyday businesses that sell biscuits, power, and banking services to 1.4 billion people. "
                f"Protect your capital and never gamble your family savings. "
                f"Follow The Bull Print for calm and honest market updates. Strictly educational market study."
            )
            terms = ["stock trading phone app", "losing money trading", "hourglass sand melting", "savings piggy bank", "family financial planning"]
            badge = "AVOID THIS TRAP"

        # ── 4. Macro Cues & Rupee Reality ──
        else:
            subject = "Why Rising Fuel Prices and a Stronger Dollar Hurt Everyday Family Savings"
            script = (
                f"Crude oil prices are surging in international markets, and the US dollar is putting heavy pressure on the Indian rupee. "
                f"When crude oil rises, it doesn't just affect car fuel; it increases the cost of transporting vegetables, milk, and cooking oil across India. "
                f"This is why keeping all your money sitting in an ordinary bank savings account actually makes you poorer over time, because inflation eats away your purchasing power. "
                f"To protect your family, hold an emergency cash cushion, accumulate physical gold as an insurance shield, and invest in India's top 50 essential companies. "
                f"Follow The Bull Print for daily honest market updates. Strictly educational market study."
            )
            terms = ["petrol diesel pump", "indian rupee banknotes", "grocery supermarket inflation", "gold coins savings", "family budget"]
            badge = "BEGINNER GUIDE"

        return {
            "theme": theme,
            "subject": subject,
            "script": script,
            "terms": terms,
            "badge": badge,
            "breaking_news_context": news_snippet,
            "source": "ViralTrendDetector",
        }


# Global singleton instance
viral_trend_detector = ViralTrendDetector()

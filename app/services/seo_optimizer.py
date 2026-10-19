"""
SEO & Viral Optimization Engine for The Compounder channel.

Integrates Google Trends, keyword research, and LLM-powered
title/description/thumbnail optimization to maximize reach and engagement.
"""

import datetime
import json
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests
from loguru import logger

from app.services import llm

try:
    from pytrends.request import TrendReq
    PYTREENDS_AVAILABLE = True
except ImportError:
    PYTREENDS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Core keywords for our niche
# ---------------------------------------------------------------------------

NICHE_KEYWORDS = [
    "Indian stock market",
    "SIP investment",
    "Nifty 50",
    "Sensex today",
    "mutual funds India",
    "long term investing",
    "stock market for beginners",
    "best stocks to buy",
    "share market India",
    "how to invest in stocks",
    "compounding",
    "trading vs investing",
    "retirement planning India",
    "financial freedom India",
    "passive income India",
]

NICHE_KEYWORD_HINDI = [
    "शेयर बाजार",
    "निवेश",
    "म्यूचुअल फंड",
    "SIP",
]

NICHE_KEYWORD_TAMIL = [
    "பங்குச் சந்தை",
    "முதலீடு",
    "பரஸ்பர நிதி",
]

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class TrendData:
    keyword: str
    score: int  # 0-100
    trending: bool  # rising search
    breakout: bool  # major spike
    related_queries: List[str] = field(default_factory=list)


@dataclass
class OptimizedTitle:
    title: str
    clickability_score: int  # 0-100
    seo_score: int  # 0-100
    keyword_included: str = ""
    hook_type: str = ""


@dataclass
class ThumbnailStrategy:
    text_overlay: str
    background_style: str  # "bullish_green", "bearish_red", "neutral_blue", "contrast_split"
    focal_point: str  # what to highlight
    color_scheme: List[str]
    avoid_elements: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Google Trends Fetcher
# ---------------------------------------------------------------------------

class TrendsFetcher:
    """Fetches trending data from Google Trends for our niche keywords."""

    def __init__(self):
        self.pytrends = None
        if PYTREENDS_AVAILABLE:
            try:
                self.pytrends = TrendReq(hl="en-IN", tz=330, timeout=10)
            except Exception as e:
                logger.warning(f"pytrends init failed: {e}")

    def fetch_trending_keywords(self) -> List[TrendData]:
        """Get daily trending searches in India for finance/investing niche."""
        if not self.pytrends:
            logger.warning("pytrends not available, using fallback")
            return self._fallback_trends()

        results = []
        try:
            self.pytrends.build_payload(
                kw_list=NICHE_KEYWORDS[:5],
                cat=0,
                timeframe="now 7-d",
                geo="IN",
                gprop="",
            )
            interest = self.pytrends.interest_over_time()
            if not interest.empty:
                for kw in NICHE_KEYWORDS[:5]:
                    if kw in interest.columns:
                        avg_score = int(interest[kw].mean())
                        # Check if rising
                        recent = interest[kw].iloc[-3:].mean() if len(interest) >= 3 else 0
                        older = interest[kw].iloc[:3].mean() if len(interest) >= 3 else 0
                        is_trending = recent > older * 1.2 if older > 0 else False
                        results.append(TrendData(
                            keyword=kw,
                            score=avg_score,
                            trending=is_trending,
                            breakout=recent > older * 2 if older > 0 else False,
                        ))

            # Get related queries
            for kw in NICHE_KEYWORDS[:3]:
                try:
                    related = self.pytrends.related_queries()
                    if kw in related and related[kw] is not None:
                        top = related[kw]["top"]
                        if top is not None and not top.empty:
                            queries = top["query"].head(5).tolist()
                            for td in results:
                                if td.keyword == kw:
                                    td.related_queries = queries
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"pytrends fetch failed: {e}")
            return self._fallback_trends()

        if not results:
            return self._fallback_trends()

        return results

    def _fallback_trends(self) -> List[TrendData]:
        """Fallback when pytrends is unavailable — uses structured data + recent news."""
        today = datetime.date.today()
        month = today.strftime("%B")

        # Seasonal trends based on Indian financial calendar
        seasonal = {
            (1, 3): "budget session, tax saving investments",
            (4, 6): "new financial year, IPO boom",
            (7, 9): "monsoon impact, Q1 results",
            (10, 12): "festive spending, Diwali picks",
        }

        season_keywords = ""
        for (start, end), kw in seasonal.items():
            if start <= today.month <= end:
                season_keywords = kw
                break

        return [
            TrendData("SIP investment", 85, trending=True, breakout=False,
                      related_queries=["SIP calculator", "best SIP funds", "SIP for 5 years"]),
            TrendData("Nifty 50", 78, trending=False, breakout=False,
                      related_queries=["Nifty today", "Nifty prediction", "Nifty bank"]),
            TrendData("stock market for beginners", 72, trending=True, breakout=False,
                      related_queries=["how to start investing", "best stocks for beginners", "stock market basics"]),
            TrendData("compounding", 45, trending=True, breakout=True,
                      related_queries=["power of compounding", "compounding calculator", "compounding in stocks"]),
            TrendData("trading vs investing", 38, trending=True, breakout=False,
                      related_queries=["why traders lose money", "investing for long term", "trading losses"]),
            TrendData("mutual funds India", 80, trending=False, breakout=False,
                      related_queries=["best mutual funds", "mutual fund vs SIP", "large cap funds"]),
        ]

    def get_rising_searches(self) -> List[str]:
        """Get fast-rising keywords in our niche."""
        trends = self.fetch_trending_keywords()
        rising = [t.keyword for t in trends if t.trending]
        # Also get from related queries
        for t in trends:
            if t.related_queries:
                rising.extend(t.related_queries[:2])
        return rising[:10]

    def get_related_queries(self, keyword: str, limit: int = 10) -> List[str]:
        """Get related search queries for a keyword."""
        if not self.pytrends:
            return []

        try:
            self.pytrends.build_payload(
                kw_list=[keyword],
                cat=0,
                timeframe="now 7-d",
                geo="IN",
            )
            related = self.pytrends.related_queries()
            if keyword in related and related[keyword] is not None:
                top = related[keyword]["top"]
                rising = related[keyword]["rising"]
                queries = []
                if top is not None and not top.empty:
                    queries.extend(top["query"].head(limit // 2).tolist())
                if rising is not None and not rising.empty:
                    queries.extend(rising["query"].head(limit // 2).tolist())
                return queries
        except Exception as e:
            logger.warning(f"related queries failed for {keyword}: {e}")

        return []


# ---------------------------------------------------------------------------
# YouTube Search Suggestion Fetcher
# ---------------------------------------------------------------------------

class YouTubeSuggestions:
    """Fetches YouTube autocomplete suggestions for keyword research."""

    def __init__(self):
        self.base_url = "https://suggestqueries.google.com/complete/search"

    def search(self, query: str, hl: str = "en", limit: int = 10) -> List[str]:
        """Get YouTube search suggestions for a query."""
        try:
            params = {
                "client": "youtube",
                "ds": "yt",
                "q": query,
                "hl": hl,
                "gl": "IN",
            }
            resp = requests.get(
                self.base_url, params=params, timeout=5,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            text = resp.text
            # Strip JSONP wrapper: window.google.ac.HandleSuggestion([...])
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                if len(data) > 1 and isinstance(data[1], list):
                    return [s[0] if isinstance(s, list) else s for s in data[1][:limit]]
                return []
            return []
        except Exception as e:
            logger.warning(f"YouTube suggest failed for '{query}': {e}")
            return []

    def trending_in_niche(self) -> Dict[str, List[str]]:
        """Get what people are searching for in our niche on YouTube."""
        seed_queries = [
            "stock market", "investing", "SIP", "Nifty",
            "share bazaar", "mutual funds",
            "nivesh", "share market",
        ]
        results = {}
        for q in seed_queries:
            suggestions = self.search(q)
            if suggestions:
                results[q] = suggestions
            time.sleep(0.3)  # rate limit
        return results


# ---------------------------------------------------------------------------
# LLM-Powered Optimization
# ---------------------------------------------------------------------------

class SEOOptimizer:
    """LLM-powered title, description, and thumbnail optimization."""

    TITLE_PROMPT = """Generate ONE YouTube title for this video topic.

Channel: The Compounder (Indian stock market education, long-term investing)

RULES (CRITICAL):
1. Must be under 60 characters
2. Must include at least one trending keyword: {keywords}
3. Use one of these hook patterns:
   - Curiosity gap: "Why X...", "The Real Reason..."
   - Pain point: "Stop X", "Why You're X"
   - Numbers: "3 Reasons...", "5 Stocks..."
   - Bold statement: "X Is a Lie", "The Truth About X"
   - How-to: "How to X in Y"
4. NO clickbait that misleads (harms long-term retention)
5. MUST include power words: Secret, Truth, Proven, Simple, Powerful, Easy, Essential, Expert
6. Output ONLY the title, nothing else

Topic: {topic}
Hook style: {hook_category}
"""

    DESCRIPTION_PROMPT = """Write a YouTube description for this video.

Channel: The Compounder
Target: Indian retail investors

RULES:
1. First 2 lines must hook the viewer (these appear in search results)
2. Include these keywords naturally: {keywords}
3. Add 3-5 bullet points of what viewer will learn
4. Include timestamps (00:00 - Introduction, etc.)
5. End with: "Subscribe to The Compounder for more."
6. Add disclaimer (not SEBI registered, educational only)
7. Max 5000 chars, min 200 chars
8. Use simple English, short sentences

Video Title: {title}
Video Topic: {topic}
Script Preview: {script_preview}
"""

    TAGS_PROMPT = """Generate 10-15 YouTube tags for this video.

Channel: The Compounder - Indian stock market education.

Rules:
1. Mix broad tags (stock market India) and specific tags (video topic)
2. Include 3 long-tail tags (4+ words)
3. Include keywords: {keywords}
4. Prioritize tags with high search volume in India
5. Add tags in Tamil and Hindi if relevant
6. Return ONLY a JSON array of strings

Topic: {topic}
"""

    THUMBNAIL_PROMPT = """Design a thumbnail strategy for this video.

Channel: The Compounder (finance education, Indian audience)

RULES:
1. Text overlay: max 3-4 words, huge font, high contrast
2. Background style: bullish_green | bearish_red | neutral_dark | contrast_split | chart_focus
3. Focal point: what grabs attention in 0.5 seconds
4. Color scheme: exactly 3 colors that pop
5. Avoid elements: what NOT to put in thumbnail
6. MUST follow YouTube's "promise vs delivery" rule (don't promise what video doesn't deliver)

Return ONLY valid JSON:
{{
    "text_overlay": "BOLD TEXT",
    "background_style": "...",
    "focal_point": "...",
    "color_scheme": ["#color1", "#color2", "#color3"],
    "avoid_elements": ["..."],
    "description": "designer brief (1 sentence)"
}}

Topic: {topic}
Title: {title}
"""

    def __init__(self, trends_fetcher: Optional[TrendsFetcher] = None):
        self.trends = trends_fetcher or TrendsFetcher()

    def get_trending_keywords(self) -> List[str]:
        """Get keywords to target, ranked by trend score."""
        trends = self.trends.fetch_trending_keywords()
        keywords = []
        for t in sorted(trends, key=lambda x: x.score, reverse=True):
            keywords.append(t.keyword)
            if t.related_queries:
                keywords.extend(t.related_queries[:2])
        return keywords[:15]

    def optimize_title(
        self,
        topic: str,
        hook_category: str = "question",
        keywords: Optional[List[str]] = None,
    ) -> OptimizedTitle:
        """Generate an optimized YouTube title."""
        if keywords is None:
            keywords = self.get_trending_keywords()[:5]

        prompt = self.TITLE_PROMPT.format(
            topic=topic,
            hook_category=hook_category,
            keywords=", ".join(keywords[:5]),
        )

        try:
            response = llm._generate_response(prompt=prompt)
            title = response.strip().strip('"').strip("'")
            # Score it
            seo_score = self._score_title(title, keywords)
            return OptimizedTitle(
                title=title,
                clickability_score=min(95, seo_score + 10),
                seo_score=seo_score,
                keyword_included=self._find_keyword(title, keywords),
                hook_type=hook_category,
            )
        except Exception as e:
            logger.warning(f"title optimization failed: {e}")
            return OptimizedTitle(
                title=topic[:60],
                clickability_score=50,
                seo_score=50,
            )

    def optimize_description(
        self,
        title: str,
        topic: str,
        script: str = "",
        keywords: Optional[List[str]] = None,
    ) -> str:
        """Generate an SEO-optimized description."""
        if keywords is None:
            keywords = self.get_trending_keywords()[:8]

        prompt = self.DESCRIPTION_PROMPT.format(
            title=title,
            topic=topic,
            keywords=", ".join(keywords[:8]),
            script_preview=script[:300] if script else topic,
        )

        try:
            response = llm._generate_response(prompt=prompt)
            return response.strip()
        except Exception as e:
            logger.warning(f"description optimization failed: {e}")
            return f"Learn about {topic}. Subscribe to The Compounder for more."

    def generate_tags(
        self,
        topic: str,
        keywords: Optional[List[str]] = None,
    ) -> List[str]:
        """Generate optimized tags."""
        if keywords is None:
            keywords = self.get_trending_keywords()[:5]

        prompt = self.TAGS_PROMPT.format(
            topic=topic,
            keywords=", ".join(keywords[:5]),
        )

        try:
            response = llm._generate_response(prompt=prompt)
            tags = json.loads(response.strip())
            if isinstance(tags, list):
                return tags[:15]
        except Exception:
            pass

        # Fallback tags
        return [
            topic.lower(),
            "stock market India",
            "investing for beginners",
            "long term investing",
        ] + [k.lower() for k in (keywords or [])[:8]]

    def design_thumbnail(
        self,
        topic: str,
        title: str,
    ) -> ThumbnailStrategy:
        """Generate thumbnail design strategy."""
        prompt = self.THUMBNAIL_PROMPT.format(topic=topic, title=title)

        try:
            response = llm._generate_response(prompt=prompt)
            data = json.loads(response.strip())
            return ThumbnailStrategy(
                text_overlay=data.get("text_overlay", topic[:20].upper()),
                background_style=data.get("background_style", "neutral_dark"),
                focal_point=data.get("focal_point", topic[:30]),
                color_scheme=data.get("color_scheme", ["#00c853", "#1a1a2e", "#ffffff"]),
                avoid_elements=data.get("avoid_elements", []),
            )
        except Exception as e:
            logger.warning(f"thumbnail design failed: {e}")
            return ThumbnailStrategy(
                text_overlay=topic[:20].upper(),
                background_style="contrast_split",
                focal_point=topic[:30],
                color_scheme=["#00c853", "#1a1a2e", "#ff1744"],
            )

    def full_optimization(
        self,
        topic: str,
        hook_category: str = "question",
        script: str = "",
    ) -> Dict:
        """Run full SEO optimization and return everything."""
        keywords = self.get_trending_keywords()

        title = self.optimize_title(topic, hook_category, keywords)
        description = self.optimize_description(title.title, topic, script, keywords)
        tags = self.generate_tags(topic, keywords)
        thumbnail = self.design_thumbnail(topic, title.title)

        return {
            "title": title.title,
            "title_score": title.clickability_score,
            "title_seo_score": title.seo_score,
            "description": description,
            "tags": tags,
            "thumbnail": {
                "text_overlay": thumbnail.text_overlay,
                "background_style": thumbnail.background_style,
                "focal_point": thumbnail.focal_point,
                "color_scheme": thumbnail.color_scheme,
                "avoid_elements": thumbnail.avoid_elements,
            },
            "trending_keywords_used": keywords[:5],
            "generated_at": datetime.datetime.now().isoformat(),
        }

    def _score_title(self, title: str, keywords: List[str]) -> int:
        """Score a title for SEO quality."""
        score = 50  # base
        title_lower = title.lower()

        # Length check (ideal: 40-60 chars)
        length = len(title)
        if 40 <= length <= 60:
            score += 15
        elif 30 <= length <= 70:
            score += 10
        else:
            score -= 10

        # Keyword inclusion
        for kw in keywords:
            if kw.lower() in title_lower:
                score += 5

        # Power words
        power_words = ["secret", "truth", "proven", "simple", "powerful", "easy",
                       "essential", "expert", "ultimate", "best", "top", "guide",
                       "why", "how", "what", "stop", "never", "real"]
        for pw in power_words:
            if pw in title_lower.split():
                score += 3

        # Hook patterns
        if title_lower.startswith(("why", "how", "what", "the ")):
            score += 5
        if "?" in title:
            score += 3
        if any(c.isdigit() for c in title):
            score += 3  # numbers in titles perform better

        return min(100, max(0, score))

    def _find_keyword(self, title: str, keywords: List[str]) -> str:
        """Find which keyword from our list appears in the title."""
        title_lower = title.lower()
        for kw in keywords:
            if kw.lower() in title_lower:
                return kw
        return ""


# ---------------------------------------------------------------------------
# Competitor Analysis
# ---------------------------------------------------------------------------

class CompetitorAnalyzer:
    """Analyzes top Indian finance YouTube channels for patterns."""

    TOP_CHANNELS = [
        "CA Rachana Phadke Ranade",
        "pranjit bhuyan",
        "Finance with Sharan",
        "Labour Law Advisor",
        "Groww",
        "Zerodha Varsity",
        "Asset Yogi",
        "Ankur Warikoo",
    ]

    def analyze_titles(self) -> Dict:
        """Return known high-performing title patterns in this niche."""
        return {
            "patterns": [
                "Why + [pain point] + ?",
                "How to + [goal] + in India",
                "[Number] + [noun] + for [audience]",
                "Stop + [bad habit] + [timeframe]",
                "The Truth About + [topic]",
            ],
            "high_performance_hooks": [
                "question", "contrast", "stat_shock", "bold_claim",
            ],
            "best_performing_topics": [
                "tax saving", "SIP", "budget", "retirement",
                "credit card", "loan", "mutual funds", "FD vs SIP",
            ],
            "avg_ideal_length": "8-12 minutes for long-form, 30-60 seconds for shorts",
        }

    def get_winning_formula(self) -> str:
        """Return a summary of what's working for competitors."""
        return (
            "Top Indian finance channels use: "
            "1. Numbers in titles (3 reasons, 5 stocks, 7 steps) "
            "2. Pain-point hooks (Why you're poor, Stop losing money) "
            "3. Hinglish for wider reach "
            "4. Thumbnails with bold SINGLE word + shocked face "
            "5. Consistency: daily shorts + weekly long-form "
            "6. Strong CTA in first 30 seconds "
        )


# ---------------------------------------------------------------------------
# Main Optimization Pipeline
# ---------------------------------------------------------------------------

class ViralEngine:
    """Complete viral optimization engine that integrates all signals.

    Combines Google Trends, YouTube autocomplete, competitor analysis,
    and LLM optimization to maximize every piece of content.
    """

    def __init__(self):
        self.trends = TrendsFetcher()
        self.yt_suggest = YouTubeSuggestions()
        self.seo = SEOOptimizer(self.trends)
        self.competitor = CompetitorAnalyzer()
        self._cache = {}

    def refresh_trends(self):
        """Refresh all trend data (call daily via cron)."""
        logger.info("[ViralEngine] Refreshing trends...")
        self._cache["trends"] = self.trends.fetch_trending_keywords()
        self._cache["yt_suggestions"] = self.yt_suggest.trending_in_niche()
        self._cache["keywords"] = self.seo.get_trending_keywords()
        self._cache["last_refresh"] = datetime.datetime.now().isoformat()
        logger.info(f"[ViralEngine] Refreshed {len(self._cache.get('keywords', []))} keywords")

    def optimize(self, topic: str, hook_category: str = "question",
                 script: str = "", is_short: bool = False) -> Dict:
        """Run full optimization for a piece of content."""
        logger.info(f"[ViralEngine] Optimizing: {topic}")

        if "keywords" not in self._cache:
            self.refresh_trends()

        result = self.seo.full_optimization(topic, hook_category, script)

        # Add viral scoring
        result["viral_potential"] = self._score_viral_potential(
            result["title"], result["title_score"], is_short
        )
        result["competitor_insight"] = self.competitor.get_winning_formula()
        result["trending_keywords"] = self._cache.get("keywords", [])
        result["is_short"] = is_short

        # For shorts, suggest different length
        if is_short:
            result["thumbnail"]["text_overlay"] = self._shorten_text(result["thumbnail"]["text_overlay"], 3)

        return result

    def trending_topics(self, limit: int = 10) -> List[str]:
        """Get the hottest topics to create content about RIGHT NOW."""
        if "keywords" not in self._cache:
            self.refresh_trends()

        topics = []

        # From trends
        trends = self._cache.get("trends", [])
        for t in sorted(trends, key=lambda x: x.score + (20 if x.trending else 0), reverse=True):
            if t.trending or t.breakout:
                topics.append(f"{t.keyword} — trending +{t.score}")
            else:
                topics.append(t.keyword)

        # From YouTube suggestions
        yt = self._cache.get("yt_suggestions", {})
        for seed, suggestions in yt.items():
            for s in suggestions[:2]:
                s_clean = s.replace(seed, "").strip()
                if s_clean and s_clean not in topics:
                    topics.append(s_clean)

        return topics[:limit]

    def _score_viral_potential(self, title: str, title_score: int, is_short: bool) -> int:
        """Score how likely this content is to go viral (0-100)."""
        score = title_score

        # Timing bonus
        now = datetime.datetime.now()
        # Evening uploads perform better (6-9 PM IST)
        if 18 <= now.hour <= 21:
            score += 5
        # Weekend bonus
        if now.weekday() >= 5:
            score += 5

        # Shorts bonus (algorithm favors shorts)
        if is_short:
            score += 10

        return min(100, score)

    def _shorten_text(self, text: str, max_words: int) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words])


# Singleton
_engine: Optional[ViralEngine] = None


def get_engine() -> ViralEngine:
    global _engine
    if _engine is None:
        _engine = ViralEngine()
        _engine.refresh_trends()
    return _engine

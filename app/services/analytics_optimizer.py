"""
Analytics Optimizer — Autonomous Channel Intelligence & Performance Feedback Loop.

Inspired by darkzOGx/youtube-automation-agent and raunakpatil/youtube-agentic-ai-studio:
1. Audits live YouTube video metrics (views, likes, comments, engagement rate).
2. Categorizes content into core Indian market themes (FII Order Flow, Sector Rotation, Options Chains, Moats, Global Macro).
3. Evaluates top-performing content buckets to drive high-retention scheduling and topic selection.
4. Closes the autonomous feedback loop: Performance Data -> Topic Strategy -> Title Lab -> Thumbnail Designer.
"""

import os
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from loguru import logger

from app.services.youtube_uploader import YouTubeUploader


THEME_RULES = {
    "FII_ORDER_FLOW": {
        "keywords": ["fii", "dii", "dump", "cr", "crore", "dark pool", "liquidity", "order-flow", "institutional flow"],
        "display_name": "FII Order-Flow & Institutional Liquidity",
        "default_badge": "ORDER FLOW",
    },
    "SECTOR_ROTATION": {
        "keywords": ["rotation", "sector", "accumulation", "breakout", "momentum", "heavyweights"],
        "display_name": "Institutional Sector Rotation & Accumulation",
        "default_badge": "SECTOR ROTATION",
    },
    "OPTIONS_DERIVATIVES": {
        "keywords": ["options", "strike", "theta", "gamma", "put", "call", "expiry", "derivatives"],
        "display_name": "Options Chain & Derivative Traps",
        "default_badge": "OPTIONS CHAIN",
    },
    "LONG_TERM_MOATS": {
        "keywords": ["compounding", "monopoly", "bluechip", "wealth", "roce", "dividend", "deep-dive"],
        "display_name": "Monopolistic Moats & Generational Compounding",
        "default_badge": "COMPOUNDING",
    },
    "GLOBAL_MACRO": {
        "keywords": ["us market", "gift nifty", "wall street", "nasdaq", "fed", "treasury", "crude"],
        "display_name": "Global Macro & Inter-market Liquidity",
        "default_badge": "MACRO RADAR",
    },
}


class AnalyticsOptimizer:
    """Provides data-driven feedback on channel performance to optimize video topics and titles."""

    def __init__(self):
        self.uploader = YouTubeUploader()

    def get_channel_performance_report(self, language: str = "en", max_videos: int = 30) -> Dict[str, Any]:
        """
        Queries YouTube Data API to analyze recent video statistics and theme distribution.
        """
        service = self.uploader._get_service(language)
        if not service:
            logger.warning(f"[AnalyticsOptimizer] Could not authenticate with YouTube for '{language}'. Returning baseline intelligence.")
            return self._get_baseline_intelligence()

        try:
            # 1. Fetch channel's uploads playlist ID
            channel_res = service.channels().list(mine=True, part="contentDetails,statistics").execute()
            items = channel_res.get("items", [])
            if not items:
                return self._get_baseline_intelligence()

            channel_stats = items[0].get("statistics", {})
            uploads_pl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

            # 2. Fetch recent videos
            pl_items = service.playlistItems().list(
                playlistId=uploads_pl,
                part="snippet",
                maxResults=max_videos,
            ).execute().get("items", [])

            if not pl_items:
                return self._get_baseline_intelligence()

            video_ids = [it["snippet"]["resourceId"]["videoId"] for it in pl_items if it.get("snippet", {}).get("resourceId", {}).get("videoId")]

            # 3. Batch query video statistics
            videos_data = []
            for i in range(0, len(video_ids), 50):
                chunk = video_ids[i:i+50]
                v_res = service.videos().list(
                    id=",".join(chunk),
                    part="snippet,statistics,status",
                ).execute().get("items", [])
                videos_data.extend(v_res)

            # 4. Analyze video metrics and categorize themes
            analyzed_videos = []
            theme_metrics = {theme: {"views": 0, "likes": 0, "comments": 0, "count": 0} for theme in THEME_RULES}

            for v in videos_data:
                snippet = v.get("snippet", {})
                stats = v.get("statistics", {})
                title = snippet.get("title", "")
                views = int(stats.get("viewCount", 0))
                likes = int(stats.get("likeCount", 0))
                comments = int(stats.get("commentCount", 0))
                vid_id = v.get("id")

                # Match theme
                matched_theme = "FII_ORDER_FLOW"
                title_lower = title.lower()
                for theme_code, theme_info in THEME_RULES.items():
                    if any(kw in title_lower for kw in theme_info["keywords"]):
                        matched_theme = theme_code
                        break

                theme_metrics[matched_theme]["views"] += views
                theme_metrics[matched_theme]["likes"] += likes
                theme_metrics[matched_theme]["comments"] += comments
                theme_metrics[matched_theme]["count"] += 1

                engagement_rate = ((likes + comments) / views * 100) if views > 0 else 0.0

                analyzed_videos.append({
                    "id": vid_id,
                    "title": title,
                    "theme": matched_theme,
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "engagement_rate": round(engagement_rate, 2),
                    "url": f"https://youtu.be/{vid_id}",
                })

            # 5. Calculate theme averages and rank them
            theme_rankings = []
            for theme_code, metrics in theme_metrics.items():
                count = metrics["count"]
                avg_views = round(metrics["views"] / count, 1) if count > 0 else 0.0
                avg_likes = round(metrics["likes"] / count, 1) if count > 0 else 0.0
                theme_rankings.append({
                    "theme": theme_code,
                    "display_name": THEME_RULES[theme_code]["display_name"],
                    "video_count": count,
                    "total_views": metrics["views"],
                    "avg_views": avg_views,
                    "avg_likes": avg_likes,
                    "badge": THEME_RULES[theme_code]["default_badge"],
                })

            theme_rankings.sort(key=lambda x: (x["avg_views"], x["total_views"]), reverse=True)

            return {
                "success": True,
                "channel_total_views": int(channel_stats.get("viewCount", 0)),
                "channel_subscribers": int(channel_stats.get("subscriberCount", 0)),
                "total_analyzed_videos": len(analyzed_videos),
                "top_themes": theme_rankings,
                "top_performing_theme": theme_rankings[0]["theme"] if theme_rankings else "FII_ORDER_FLOW",
                "recent_videos": analyzed_videos[:10],
            }

        except Exception as e:
            logger.error(f"[AnalyticsOptimizer] Error analyzing channel metrics: {e}")
            return self._get_baseline_intelligence()

    def get_top_performing_topics(self) -> List[str]:
        """
        Returns an ordered list of high-impact topic recommendations based on live performance data.
        """
        report = self.get_channel_performance_report()
        top_theme = report.get("top_performing_theme", "FII_ORDER_FLOW")

        if top_theme == "FII_ORDER_FLOW":
            return [
                "Big Foreign Banks Dumped ₹3,200 Cr in Final 15 Minutes | Danger for Everyday Buyers",
                "Foreign Banks vs Indian Mutual Funds: The ₹4,100 Cr Move Everyday Investors Missed",
                "Behind the Scenes: What Big Investment Banks Are Secretly Buying Today",
            ]
        elif top_theme == "SECTOR_ROTATION":
            return [
                "Big Funds Are Moving Money: 3 Safe Stocks Indian Mutual Funds Are Accumulating",
                "Morning Momentum Radar: 3 Everyday Bluechip Companies Testing New Highs",
                "Why Big Investment Banks Are Moving Cash Into Safe Essential Companies",
            ]
        elif top_theme == "OPTIONS_DERIVATIVES":
            return [
                "The Stock Market Trap: Why 93 Percent of Everyday People Lose Money in Quick Bets",
                "The Price Trap: How Giant Institutions Trick Beginners into Selling Cheap",
                "Why Your Money Melts Away in Short-Term Bets: The Truth Behind Market Traps",
            ]
        else:
            return [
                "The Hidden Price Trap: How Big Banks Buy Wholesale When Everyday People Panic",
                "Essential Brand Secrets: Why Holding Everyday Monopolies Beats Short-Term Betting",
                "Gold vs Rupee Reality: Why Physical Gold Protects Your Family From Rising Prices",
            ]

    def _get_baseline_intelligence(self) -> Dict[str, Any]:
        """High-CTR baseline fallback when offline or during initial cold starts."""
        return {
            "success": False,
            "fallback": True,
            "channel_total_views": 526,
            "channel_subscribers": 3,
            "total_analyzed_videos": 18,
            "top_themes": [
                {"theme": "FII_ORDER_FLOW", "display_name": "FII Order-Flow & Institutional Liquidity", "avg_views": 10.5, "badge": "ORDER FLOW"},
                {"theme": "SECTOR_ROTATION", "display_name": "Institutional Sector Rotation & Accumulation", "avg_views": 11.0, "badge": "SECTOR ROTATION"},
                {"theme": "OPTIONS_DERIVATIVES", "display_name": "Options Chain & Derivative Traps", "avg_views": 8.0, "badge": "OPTIONS CHAIN"},
                {"theme": "LONG_TERM_MOATS", "display_name": "Monopolistic Moats & Generational Compounding", "avg_views": 6.5, "badge": "COMPOUNDING"},
            ],
            "top_performing_theme": "FII_ORDER_FLOW",
            "recent_videos": [],
        }


analytics_optimizer = AnalyticsOptimizer()


if __name__ == "__main__":
    report = analytics_optimizer.get_channel_performance_report()
    print("--- Channel Performance Report ---")
    print(f"Total Views: {report.get('channel_total_views')}")
    print(f"Top Theme: {report.get('top_performing_theme')}")
    for t in report.get("top_themes", []):
        print(f"  * {t['display_name']} -> Avg Views: {t.get('avg_views', 0)}")
    print("\nRecommended Next Topics:")
    for topic in analytics_optimizer.get_top_performing_topics():
        print(f"  - {topic}")

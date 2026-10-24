"""
Generate and publish 4 benchmark 1,200–1,800-word SEO + GEO articles
using The Bull Print's modular engine for zero-jargon everyday investors.
"""

import os
import sys
import json
from datetime import datetime, timezone
from loguru import logger

from app.services.market_data import MarketDataFetcher
from app.services.article_generator import article_generator, GeneratedArticle
from app.services.github_publisher import github_publisher
from app.services.compliance import check_banned_phrases

SLOTS = [
    {
        "slot": "gold_macro_radar",
        "youtube_url": "https://www.youtube.com/watch?v=FfxHCzx7QhM",
        "custom_title": "Silver Crashes ₹56,000 & Gold Drops: Why Big Banks Are Shaking Out Everyday Investors"
    },
    {
        "slot": "options_trap",
        "youtube_url": "https://www.youtube.com/watch?v=9AVhwVNCKug",
        "custom_title": "The Option Buyers Trap: Why 90% of Retail Traders Lose Money and How to Build Wealth Like Landlords"
    },
    {
        "slot": "market_close",
        "youtube_url": "https://www.youtube.com/watch?v=FfxHCzx7QhM",
        "custom_title": "Nifty & Sensex Today: Why Indian Markets Moved, What Institutions Are Buying, and 3 Wealth Rules for Everyday Investors"
    },
    {
        "slot": "viral_breakout",
        "youtube_url": "https://www.youtube.com/watch?v=9AVhwVNCKug",
        "custom_title": "Market Crash Panic? What to Do When Your Stocks Turn Red (The Fruit Market Rule)"
    }
]

def main():
    logger.info("Initializing Market Data Fetcher...")
    fetcher = MarketDataFetcher()
    ctx = fetcher.get_full_context(include_stocks=True, include_global=True)
    logger.info(f"Market context retrieved: Nifty={ctx.nifty.value if ctx.nifty else 'N/A'}")

    published_articles = []

    for item in SLOTS:
        slot_name = item["slot"]
        yt_url = item["youtube_url"]
        logger.info(f"Generating 1,500+ word modular GEO article for slot: '{slot_name}'...")

        article: GeneratedArticle = article_generator.generate_article_from_context(
            ctx=ctx,
            youtube_url=yt_url,
            slot_name=slot_name
        )

        # Check compliance
        banned = check_banned_phrases(article.html_content)
        if banned:
            logger.warning(f"Compliance issues detected: {banned}. Adjusting...")
            for b in banned:
                article.html_content = article.html_content.replace(b, "steady cash flow")

        # Save locally to content/posts/ and content/posts.json
        github_publisher.publish_article(article, youtube_url=yt_url)

        published_articles.append({
            "title": article.title,
            "slug": article.slug,
            "word_count": article.word_count,
            "reading_time": article.reading_time_min,
            "category": article.categories[0] if article.categories else "Education",
            "faqs": len(article.faq_items),
            "schema_keys": len(article.schema_jsonld.get("@graph", []))
        })
        logger.info(f"✅ Published: '{article.title}' | Words: {article.word_count} | Reading: {article.reading_time_min}m")

    print("\n==================================================")
    print("🚀 BENCHMARK ARTICLES PUBLISHED SUCCESSFULLY")
    print("==================================================")
    for i, a in enumerate(published_articles, 1):
        print(f"{i}. {a['title']}")
        print(f"   Slug: {a['slug']}")
        print(f"   Word Count: {a['word_count']} words | Reading Time: {a['reading_time']} min | Category: {a['category']}")
        print(f"   FAQs: {a['faqs']} items | Schema Graph: {a['schema_keys']} types")
        print("--------------------------------------------------")

if __name__ == "__main__":
    main()

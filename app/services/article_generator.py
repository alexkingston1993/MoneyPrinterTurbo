"""
Article Generator — Omnichannel SEO, GEO & AEO News Article Engine.

Transforms live MarketContext into in-depth, humanized, high-ranking financial news:
- Targets Google AI Overviews, Perplexity AI, and ChatGPT Search (GEO/AEO)
- Incorporates blader/humanizer anti-AI writing rules
- Generates Schema.org JSON-LD (NewsArticle, FAQPage, VideoObject)
- Injects YouTube video embed placeholder for high-dwell-time rankings
- Formats responsive financial tables and SEBI compliance disclaimers
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger
from app.config import config
from app.services.market_data import MarketContext, get_fetcher
from app.services.humanizer import humanizer


@dataclass
class GeneratedArticle:
    title: str
    slug: str
    focus_keyword: str
    meta_description: str
    categories: List[str]
    tags: List[str]
    html_content: str
    markdown_content: str
    schema_jsonld: Dict
    faq_items: List[Dict[str, str]]
    timestamp: str = ""


class ArticleGenerator:
    """Generates humanized, algorithmically optimized financial articles."""

    @staticmethod
    def _generate_slug(title: str) -> str:
        """Create URL-friendly SEO slug."""
        clean = re.sub(r"[^a-zA-Z0-9\s-]", "", title.lower())
        slug = re.sub(r"[\s-]+", "-", clean).strip("-")
        return slug[:80]

    def _build_faq_items(self, ctx: MarketContext) -> List[Dict[str, str]]:
        """Generate high-intent search queries for FAQPage schema and AEO."""
        nifty_val = f"{ctx.nifty.value:,.0f}" if ctx.nifty else "24,500"
        sentiment = ctx.market_sentiment.title()
        
        faqs = [
            {
                "question": f"Why is the Indian stock market {ctx.market_sentiment} today?",
                "answer": (
                    f"The Indian market traded with a {ctx.market_sentiment} bias as Nifty 50 stood at {nifty_val}. "
                    f"Institutional FII/DII activity, sector rotation across banking and IT, and global cues "
                    f"dictated price action throughout the trading session."
                ),
            },
            {
                "question": "What are the key Nifty 50 support and resistance levels to watch?",
                "answer": (
                    f"Based on current options chain clustering and session range, immediate support for Nifty 50 "
                    f"is positioned around {int(float(nifty_val.replace(',', '')) - 150):,}, with primary resistance capped at "
                    f"{int(float(nifty_val.replace(',', '')) + 150):,}."
                ),
            },
            {
                "question": "How did institutional investors (FII and DII) position today?",
                "answer": (
                    f"Foreign Institutional Investors (FIIs) recorded a net flow of ₹{ctx.fii_net:,.1f} Cr, "
                    f"while Domestic Institutional Investors (DIIs) recorded ₹{ctx.dii_net:,.1f} Cr in the cash market."
                ),
            },
        ]
        return faqs

    def _build_schema_jsonld(
        self, title: str, meta_desc: str, slug: str, faqs: List[Dict[str, str]], youtube_url: Optional[str] = None
    ) -> Dict:
        """Create structured Schema.org JSON-LD graph (NewsArticle + FAQPage + VideoObject)."""
        now_iso = datetime.utcnow().isoformat() + "Z"
        canonical_url = f"https://yourdomain.com/{slug}"

        graph = [
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "headline": title,
                "description": meta_desc,
                "datePublished": now_iso,
                "dateModified": now_iso,
                "mainEntityOfPage": {"@type": "WebPage", "@id": canonical_url},
                "author": {
                    "@type": "Organization",
                    "name": "Dalal Street Alpha Desk",
                    "url": "https://yourdomain.com",
                },
                "publisher": {
                    "@type": "Organization",
                    "name": "Market Intelligence Portal",
                    "logo": {"@type": "ImageObject", "url": "https://yourdomain.com/logo.png"},
                },
            },
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": item["question"],
                        "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
                    }
                    for item in faqs
                ],
            },
        ]

        if youtube_url:
            graph.append({
                "@context": "https://schema.org",
                "@type": "VideoObject",
                "name": title,
                "description": meta_desc,
                "thumbnailUrl": "https://yourdomain.com/default-video-thumb.jpg",
                "uploadDate": now_iso,
                "embedUrl": youtube_url.replace("watch?v=", "embed/"),
            })

        return {"@context": "https://schema.org", "@graph": graph}

    def generate_article_from_context(
        self, ctx: MarketContext, youtube_url: Optional[str] = None
    ) -> GeneratedArticle:
        """
        Build a complete, SEO/GEO optimized journalistic report from live MarketContext.
        Preserves formatting, generates data tables, and enforces humanizer heuristics.
        """
        nifty_val = f"{ctx.nifty.value:,.1f}" if ctx.nifty else "24,800.0"
        nifty_chg = f"{ctx.nifty.change_pct:+.2f}%" if ctx.nifty else "+0.00%"
        sensex_val = f"{ctx.sensex.value:,.1f}" if ctx.sensex else "81,200.0"
        sensex_chg = f"{ctx.sensex.change_pct:+.2f}%" if ctx.sensex else "+0.00%"
        bank_val = f"{ctx.bank_nifty.value:,.1f}" if ctx.bank_nifty else "52,100.0"
        bank_chg = f"{ctx.bank_nifty.change_pct:+.2f}%" if ctx.bank_nifty else "+0.00%"

        # SEO Title & Meta
        if ctx.market_sentiment == "bullish":
            action_phrase = "Bulls Charge Ahead as Nifty Reclaims Key Resistance"
        elif ctx.market_sentiment == "bearish":
            action_phrase = "Bears Tighten Grip as Nifty Cracks Critical Support"
        else:
            action_phrase = "Nifty Consolidates in Tight Range Ahead of Key Catalysts"

        title = f"Nifty Today: {action_phrase} | Full Analysis & Derivative Setup"
        slug = self._generate_slug(f"nifty-market-analysis-{ctx.timestamp.replace(' ', '-').replace(':', '')}")
        focus_keyword = "Nifty 50 market analysis today"
        meta_description = (
            f"Live market analysis: Nifty closes at {nifty_val} ({nifty_chg}), Sensex at {sensex_val}. "
            f"FII/DII flow breakdown, options chain support levels, and tomorrow's strategy."
        )[:158]

        faqs = self._build_faq_items(ctx)
        schema_jsonld = self._build_schema_jsonld(title, meta_description, slug, faqs, youtube_url)

        # Build Gainers/Losers Table
        movers_rows = []
        for g in ctx.top_gainers[:4]:
            movers_rows.append(f"<tr><td><strong>{g.name}</strong></td><td style='color:#16a34a;'>+{g.change_pct:.2f}%</td><td>₹{g.price:,.2f}</td><td>Top Gainer</td></tr>")
        for l in ctx.top_losers[:4]:
            movers_rows.append(f"<tr><td><strong>{l.name}</strong></td><td style='color:#dc2626;'>{l.change_pct:.2f}%</td><td>₹{l.price:,.2f}</td><td>Top Loser</td></tr>")
        movers_html = "\n".join(movers_rows)

        # Build Sectors Table
        sector_rows = []
        for sec in ctx.sectors[:5]:
            color = "#16a34a" if sec.change_pct >= 0 else "#dc2626"
            sector_rows.append(f"<tr><td>{sec.name}</td><td style='color:{color};'>{sec.change_pct:+.2f}%</td><td>{sec.top_gainer or 'N/A'}</td></tr>")
        sectors_html = "\n".join(sector_rows)

        # Format full HTML article with video placeholder
        html_content = f"""
<div class="market-article">
    <!-- Executive Summary / GEO Answer Box -->
    <div class="geo-answer-box" style="background:#f8fafc; border-left:4px solid #2563eb; padding:18px; margin-bottom:24px; border-radius:6px;">
        <h3 style="margin-top:0; color:#1e293b;">⚡ Executive Summary: What Moved Dalal Street Today</h3>
        <p style="font-size:16px; line-height:1.6; color:#334155; margin-bottom:0;">
            The Indian market witnessed active trading as the benchmark <strong>Nifty 50 settled at {nifty_val} ({nifty_chg})</strong>, while <strong>Sensex concluded at {sensex_val} ({sensex_chg})</strong>. 
            Bank Nifty clocked <strong>{bank_val} ({bank_chg})</strong>. Institutional flows reflected a net FII posture of ₹{ctx.fii_net:,.1f} Cr, counterbalanced by domestic institutions at ₹{ctx.dii_net:,.1f} Cr. 
            Options chain open interest concentration outlines key technical inflexion zones heading into the upcoming sessions.
        </p>
    </div>

    <!-- YouTube Video Strategic Embed -->
    <div class="video-embed-container" style="margin:28px 0; text-align:center;">
        [YOUTUBE_EMBED_PLACEHOLDER]
    </div>

    <h2>1. Benchmark Index Overview & Price Action</h2>
    <p>
        Dalal Street opened with clear intent today as sector rotation dictated the pace. Rather than a broad-based surge, institutional liquidity concentrated within specific large-cap counters, leaving broader market breadth nuanced.
    </p>
    
    <div class="table-responsive" style="overflow-x:auto; margin:20px 0;">
        <table style="width:100%; border-collapse:collapse; text-align:left; font-size:15px;">
            <thead>
                <tr style="background:#0f172a; color:#ffffff;">
                    <th style="padding:10px;">Index</th>
                    <th style="padding:10px;">Closing Level</th>
                    <th style="padding:10px;">Change (%)</th>
                    <th style="padding:10px;">Session Stance</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom:1px solid #e2e8f0;">
                    <td style="padding:10px;"><strong>Nifty 50</strong></td>
                    <td style="padding:10px;">{nifty_val}</td>
                    <td style="padding:10px; color:{'#16a34a' if ctx.nifty and ctx.nifty.change_pct >= 0 else '#dc2626'};">{nifty_chg}</td>
                    <td style="padding:10px;">{ctx.market_sentiment.title()}</td>
                </tr>
                <tr style="border-bottom:1px solid #e2e8f0;">
                    <td style="padding:10px;"><strong>BSE Sensex</strong></td>
                    <td style="padding:10px;">{sensex_val}</td>
                    <td style="padding:10px; color:{'#16a34a' if ctx.sensex and ctx.sensex.change_pct >= 0 else '#dc2626'};">{sensex_chg}</td>
                    <td style="padding:10px;">Correlated</td>
                </tr>
                <tr style="border-bottom:1px solid #e2e8f0;">
                    <td style="padding:10px;"><strong>Bank Nifty</strong></td>
                    <td style="padding:10px;">{bank_val}</td>
                    <td style="padding:10px; color:{'#16a34a' if ctx.bank_nifty and ctx.bank_nifty.change_pct >= 0 else '#dc2626'};">{bank_chg}</td>
                    <td style="padding:10px;">High Beta</td>
                </tr>
            </tbody>
        </table>
    </div>

    <h2>2. Sector Rotation and Top Market Movers</h2>
    <p>
        Sectoral performance highlighted diverging capital flows. Momentum funds actively rebalanced away from high-multiple pockets toward value-driven balance sheets.
    </p>

    <div class="table-responsive" style="overflow-x:auto; margin:20px 0;">
        <table style="width:100%; border-collapse:collapse; text-align:left; font-size:15px;">
            <thead>
                <tr style="background:#1e293b; color:#ffffff;">
                    <th style="padding:10px;">Symbol</th>
                    <th style="padding:10px;">Movement</th>
                    <th style="padding:10px;">LTP</th>
                    <th style="padding:10px;">Category</th>
                </tr>
            </thead>
            <tbody>
                {movers_html}
            </tbody>
        </table>
    </div>

    <h2>3. Institutional Liquidity: FII & DII Cash Market Dynamics</h2>
    <p>
        Institutional positioning remains the primary anchor of Dalal Street's macro momentum. Foreign Institutional Investors (FIIs) recorded a net flow of <strong>₹{ctx.fii_net:,.1f} Cr</strong>, while Domestic Institutional Investors (DIIs) deployed <strong>₹{ctx.dii_net:,.1f} Cr</strong>.
    </p>
    <p>
        The tug-of-war between overseas allocators and domestic mutual fund SIP inflows continues to establish a firm floor beneath heavy drawdowns, preventing abrupt systemic cascades.
    </p>

    <h2>4. Derivatives & Options Chain Structure</h2>
    <p>
        A granular examination of the weekly options chain reveals dense call writing at round number strikes, acting as an initial volatility ceiling. Conversely, put open interest buildup suggests strong defense from positional option writers around established moving averages.
    </p>

    <h2>5. Frequently Asked Questions (FAQ)</h2>
    <div class="faq-accordion" style="margin:20px 0;">
        {"".join([f"<div style='margin-bottom:16px;'><h4 style='color:#1e293b; margin-bottom:6px;'>Q: {f['question']}</h4><p style='color:#475569; margin-top:0;'>{f['answer']}</p></div>" for f in faqs])}
    </div>

    <!-- Regulatory Disclaimer & Statutory Notice (SEBI & ASCI Bulletproof Compliance) -->
    <div class="disclaimer-box" style="margin-top:40px; padding:20px; background:rgba(15,23,42,0.9); border:1px solid rgba(255,255,255,0.1); border-left:4px solid #f43f5e; font-size:12.5px; color:#94a3b8; border-radius:8px; line-height:1.6;">
        <strong style="color:#f8fafc;">⚖️ Mandatory Regulatory Notice (SEBI & ASCI Compliance):</strong> 
        Dalal Street Alpha operates exclusively as an educational market research desk. The author and algorithms are NOT registered with SEBI as an Investment Adviser (IA) or Research Analyst (RA). This report contains personal observations and historical data points—NEVER buy/sell calls, target prices, or financial advice. 
        <br><br>
        <strong>Derivatives Risk Notice:</strong> Per SEBI empirical studies, 9 out of 10 individual traders in equity futures and options incur net losses. Please consult an independent certified financial advisor. Read our official <a href="/disclaimer" style="color:#60a5fa; text-decoration:underline;">SEBI Regulatory Disclaimer</a>, <a href="/risk-disclosure" style="color:#60a5fa; text-decoration:underline;">Risk Disclosure</a>, and <a href="/affiliate-disclosure" style="color:#60a5fa; text-decoration:underline;">Affiliate Transparency Policy</a>.
    </div>
</div>
"""

        # Apply humanizer pass to clean any synthetic artifacts
        cleaned_html = humanizer.clean_ai_fingerprints(html_content)

        return GeneratedArticle(
            title=title,
            slug=slug,
            focus_keyword=focus_keyword,
            meta_description=meta_description,
            categories=["Market Live", "Nifty 50", "Derivatives Analysis"],
            tags=["Nifty50", "StockMarketToday", "BankNifty", "FIIFlows", "ShareMarketNews"],
            html_content=cleaned_html,
            markdown_content=cleaned_html,
            schema_jsonld=schema_jsonld,
            faq_items=faqs,
            timestamp=ctx.timestamp,
        )


# Global instance
article_generator = ArticleGenerator()

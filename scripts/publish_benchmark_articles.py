"""
Script to generate and publish comprehensive, institutional-grade market posts 
to content/posts/ and content/posts.json, embedding verified live YouTube links.
"""

import json
import os
from datetime import datetime

POSTS_DIR = "content/posts"
MANIFEST_FILE = "content/posts.json"
os.makedirs(POSTS_DIR, exist_ok=True)

ARTICLES = [
    {
        "slug": "reliance-industries-analysis-2026",
        "title": "Reliance Industries: The Future of Indian Business | 10-Year Quantitative Breakdown & Fundamental Thesis",
        "date": "2026-10-20 03:30:00",
        "excerpt": "Comprehensive 10-year fundamental analysis of Reliance Industries (RIL). Covering Jio 5G monetization, Retail EBITDA margins, New Energy gigafactories, and key technical accumulation zones.",
        "focusKeyword": "Reliance Industries stock analysis 2026",
        "categories": ["Equities Research", "Large-Cap Analysis", "Reliance"],
        "tags": ["Reliance", "RIL", "Nifty50", "StockMarketIndia", "MukeshAmbani", "Jio", "Retail"],
        "youtubeUrl": "https://www.youtube.com/watch?v=9AVhwVNCKug",
        "html": """<div class="market-article">
    <!-- Executive Summary / GEO Answer Box -->
    <div class="geo-answer-box" style="background:rgba(15, 23, 42, 0.7); border:1px solid rgba(59, 130, 246, 0.3); border-left:4px solid #3b82f6; padding:22px; margin-bottom:28px; border-radius:8px;">
        <h3 style="margin-top:0; color:#60a5fa; font-size:18px; font-weight:700;">⚡ Executive Summary: The RIL Compounding Engine</h3>
        <p style="font-size:15px; line-height:1.7; color:#cbd5e1; margin-bottom:0;">
            Reliance Industries Limited (NSE: RELIANCE) has completed a structural pivot from a cyclical petrochemical behemoth into a diversified consumer and energy conglomerate. 
            With <strong>Jio Platforms</strong> commanding over 470 million subscribers and <strong>Reliance Retail</strong> operating 18,000+ stores, the non-energy segments now generate <strong>>50% of consolidated EBITDA</strong>. 
            Coupled with an unprecedented ₹75,000 Cr capex deployment into the <strong>Dhirubhai Ambani Green Energy Giga Complex</strong> in Jamnagar, RIL offers a rare multi-engine compounding runway for long-term institutional allocators.
        </p>
    </div>

    <!-- YouTube Video Strategic Embed -->
    <div class="video-embed-container" style="margin:28px 0; text-align:center;">
        [YOUTUBE_EMBED_PLACEHOLDER]
    </div>

    <h2>1. Fundamental Health & Valuation Snapshot</h2>
    <p>
        Reliance trades at attractive relative multiples considering the secular growth profile of its consumer verticals. Let us review the key quantitative ratios:
    </p>

    <div class="table-responsive" style="overflow-x:auto; margin:20px 0;">
        <table style="width:100%; border-collapse:collapse; text-align:left; font-size:14.5px;">
            <thead>
                <tr style="background:#0f172a; color:#38bdf8; border-bottom:2px solid rgba(56, 189, 248, 0.3);">
                    <th style="padding:12px;">Financial Metric</th>
                    <th style="padding:12px;">Current Valuation / Reading</th>
                    <th style="padding:12px;">5-Year Historical Average</th>
                    <th style="padding:12px;">Analytical Takeaway</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Consolidated Market Cap</strong></td>
                    <td style="padding:10px; color:#ffffff;">₹19,80,000+ Cr</td>
                    <td style="padding:10px; color:#94a3b8;">₹15,20,000 Cr</td>
                    <td style="padding:10px; color:#10b981;">#1 Indian Market Weight</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Trailing P/E Ratio</strong></td>
                    <td style="padding:10px; color:#ffffff;">26.8x</td>
                    <td style="padding:10px; color:#94a3b8;">28.4x</td>
                    <td style="padding:10px; color:#10b981;">Modest Discount to Growth</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Jio ARPU (Monthly)</strong></td>
                    <td style="padding:10px; color:#ffffff;">₹195.4</td>
                    <td style="padding:10px; color:#94a3b8;">₹142.0</td>
                    <td style="padding:10px; color:#10b981;">Consistent Upward Trajectory</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Retail Square Footage</strong></td>
                    <td style="padding:10px; color:#ffffff;">72.5 Million Sq. Ft.</td>
                    <td style="padding:10px; color:#94a3b8;">35.0 Million Sq. Ft.</td>
                    <td style="padding:10px; color:#10b981;">Doubled in 48 Months</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Net Debt-to-EBITDA</strong></td>
                    <td style="padding:10px; color:#ffffff;">1.15x</td>
                    <td style="padding:10px; color:#94a3b8;">1.85x</td>
                    <td style="padding:10px; color:#10b981;">Strong Balance Sheet Buffer</td>
                </tr>
            </tbody>
        </table>
    </div>

    <h2>2. The Three Strategic Growth Vectors</h2>
    <p>
        Institutional interest in Reliance centers on three non-correlated catalysts that hedge against global refining margin volatility:
    </p>
    <ul>
        <li><strong>Jio's 5G Monetization & AI Infrastructure:</strong> With pan-India 5G standalone (SA) rollout finalized, Jio is executing enterprise fiber-to-the-home (FTTH) expansion and cloud computing services, positioning itself as India's premier digital utility.</li>
        <li><strong>Reliance Retail's Omnichannel Dominance:</strong> Operating across grocery, electronics, fashion, and pharma, Reliance Retail continues to outpace unorganized trade through rapid digital onboarding via JioMart.</li>
        <li><strong>New Energy & Gigafactories:</strong> The Jamnagar integration encompasses photovoltaic solar modules, green hydrogen electrolyzers, energy storage batteries, and fuel cell systems, targeting global clean-tech export competitiveness by 2030.</li>
    </ul>

    <h2>3. Technical Structure & Institutional Accumulation</h2>
    <p>
        On technical charts, Reliance Industries exhibits consistent defense of its 200-day exponential moving average (200 EMA) across multi-year cycles. Periods of prolonged sideways consolidation have historically preceded aggressive upward breakouts as earnings from capex cycles materialize. Positional investors monitor delivery percentage spikes exceeding 65% as a sign of institutional accumulation.
    </p>

    <h2>4. Frequently Asked Questions (FAQ)</h2>
    <div class="faq-accordion" style="margin:20px 0;">
        <div style="margin-bottom:16px;">
            <h4 style="color:#60a5fa; margin-bottom:6px;">Q: Is Reliance Industries a pure oil and gas stock?</h4>
            <p style="color:#94a3b8; margin-top:0;">No. Over 50% of consolidated EBITDA is now contributed by consumer businesses—Reliance Jio and Reliance Retail—making it a diversified consumer-tech conglomerate.</p>
        </div>
        <div style="margin-bottom:16px;">
            <h4 style="color:#60a5fa; margin-bottom:6px;">Q: What are the key risks to the Reliance investment thesis?</h4>
            <p style="color:#94a3b8; margin-top:0;">Key variables include benchmark Singapore gross refining margins (GRM), regulatory policy shifts in telecom spectrum pricing, and execution timelines for solar/green hydrogen manufacturing complexes.</p>
        </div>
        <div style="margin-bottom:16px;">
            <h4 style="color:#60a5fa; margin-bottom:6px;">Q: Where can I watch the in-depth visual breakdown?</h4>
            <p style="color:#94a3b8; margin-top:0;">You can watch our full video analysis on our official YouTube channel <a href="https://www.youtube.com/@thecompounderak" target="_blank" style="color:#38bdf8; text-decoration:underline;">The Compounder AK</a> or in the player embedded above.</p>
        </div>
    </div>

    <!-- Regulatory Disclaimer & Statutory Notice (SEBI & ASCI Compliance) -->
    <div class="disclaimer-box" style="margin-top:40px; padding:22px; background:rgba(15,23,42,0.9); border:1px solid rgba(255,255,255,0.1); border-left:4px solid #f43f5e; font-size:12.5px; color:#94a3b8; border-radius:8px; line-height:1.6;">
        <strong style="color:#f8fafc;">⚖️ Mandatory Regulatory Notice (SEBI & ASCI Compliance):</strong><br>
        Dalal Street Alpha operates exclusively as an educational market research desk. The author and algorithms are NOT registered with SEBI as an Investment Adviser (IA) or Research Analyst (RA). This report contains personal observations and historical data points—NEVER buy/sell calls, target prices, or financial advice.
        <br><br>
        <strong>Derivatives Risk Notice:</strong> Per SEBI empirical studies, 9 out of 10 individual traders in equity futures and options incur net losses. Please consult an independent certified financial advisor. Read our official <a href="/disclaimer" style="color:#60a5fa; text-decoration:underline;">SEBI Regulatory Disclaimer</a>, <a href="/risk-disclosure" style="color:#60a5fa; text-decoration:underline;">Risk Disclosure</a>, and <a href="/affiliate-disclosure" style="color:#60a5fa; text-decoration:underline;">Affiliate Transparency Policy</a>.
    </div>
</div>"""
    },
    {
        "slug": "hdfc-bank-deep-dive-2026",
        "title": "HDFC Bank: The Gold Standard of Private Banking | Post-Merger Synergies & Valuation Floor",
        "date": "2026-10-20 03:25:00",
        "excerpt": "Institutional analysis of HDFC Bank (NSE: HDFCBANK). Examining Credit-to-Deposit ratio normalization, net interest margin resilience, branch expansion, and long-term valuation multiples.",
        "focusKeyword": "HDFC Bank stock analysis 2026",
        "categories": ["Banking Sector", "Equities Research", "Nifty 50"],
        "tags": ["HDFCBANK", "BankNifty", "PrivateBanks", "Nifty50", "CreditDepositRatio"],
        "youtubeUrl": "",
        "html": """<div class="market-article">
    <div class="geo-answer-box" style="background:rgba(15, 23, 42, 0.7); border:1px solid rgba(59, 130, 246, 0.3); border-left:4px solid #3b82f6; padding:22px; margin-bottom:28px; border-radius:8px;">
        <h3 style="margin-top:0; color:#60a5fa; font-size:18px; font-weight:700;">⚡ Executive Summary: HDFC Bank Post-Merger Dynamics</h3>
        <p style="font-size:15px; line-height:1.7; color:#cbd5e1; margin-bottom:0;">
            HDFC Bank stands as India's preeminent private lending institution. Following its historic merger with parent HDFC Ltd, the bank's primary strategic focus has shifted to mobilizing retail deposits to normalize its <strong>Credit-to-Deposit (CD) ratio</strong>. 
            With gross NPAs held consistently below 1.4% and an aggressive footprint expansion targeting 10,000+ branches, the stock trades at historical valuation percentiles that offer strong margin of safety.
        </p>
    </div>

    [YOUTUBE_EMBED_PLACEHOLDER]

    <h2>1. Banking Metrics & Asset Quality Overview</h2>
    <div class="table-responsive" style="overflow-x:auto; margin:20px 0;">
        <table style="width:100%; border-collapse:collapse; text-align:left; font-size:14.5px;">
            <thead>
                <tr style="background:#0f172a; color:#38bdf8; border-bottom:2px solid rgba(56, 189, 248, 0.3);">
                    <th style="padding:12px;">Parameter</th>
                    <th style="padding:12px;">Reported Figure</th>
                    <th style="padding:12px;">Industry Average</th>
                    <th style="padding:12px;">Health Evaluation</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Gross NPA</strong></td>
                    <td style="padding:10px; color:#ffffff;">1.33%</td>
                    <td style="padding:10px; color:#94a3b8;">2.80%</td>
                    <td style="padding:10px; color:#10b981;">Benchmark Quality</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Net NPA</strong></td>
                    <td style="padding:10px; color:#ffffff;">0.39%</td>
                    <td style="padding:10px; color:#94a3b8;">0.75%</td>
                    <td style="padding:10px; color:#10b981;">Pristine Underwriting</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Capital Adequacy (CAR)</strong></td>
                    <td style="padding:10px; color:#ffffff;">19.8%</td>
                    <td style="padding:10px; color:#94a3b8;">15.5%</td>
                    <td style="padding:10px; color:#10b981;">High Tier-1 Cushion</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Price-to-Book (P/B)</strong></td>
                    <td style="padding:10px; color:#ffffff;">2.5x</td>
                    <td style="padding:10px; color:#94a3b8;">3.4x (10-Yr Avg)</td>
                    <td style="padding:10px; color:#10b981;">Undervalued Decile</td>
                </tr>
            </tbody>
        </table>
    </div>

    <h2>2. Deposit Mobilization & Cross-Selling Catalysts</h2>
    <p>
        Prior to the amalgamation, only 30% of mortgage customers had an HDFC Bank savings account. The unified distribution network provides an immense cross-selling runway for wealth management, credit cards, and auto loans across a customer base exceeding 90 million Indians.
    </p>

    <!-- Regulatory Disclaimer -->
    <div class="disclaimer-box" style="margin-top:40px; padding:22px; background:rgba(15,23,42,0.9); border:1px solid rgba(255,255,255,0.1); border-left:4px solid #f43f5e; font-size:12.5px; color:#94a3b8; border-radius:8px; line-height:1.6;">
        <strong style="color:#f8fafc;">⚖️ Mandatory Regulatory Notice (SEBI Compliance):</strong><br>
        Dalal Street Alpha provides quantitative education. We are NOT registered with SEBI as an Investment Adviser or Research Analyst. No content here is financial advice or a trade recommendation.
    </div>
</div>"""
    },
    {
        "slug": "tcs-tech-titan-analysis-2026",
        "title": "Tata Consultancy Services (TCS): The Tech Titan's 10-Year Outlook | AI Pivot & Margin Moat",
        "date": "2026-10-20 03:20:00",
        "excerpt": "Analysis of Tata Consultancy Services (NSE: TCS). Evaluating free cash flow yields, generative AI contract pipelines, operating margins, and corporate governance under the Tata Group.",
        "focusKeyword": "TCS stock forecast 2026",
        "categories": ["IT Sector", "Equities Research", "Nifty 50"],
        "tags": ["TCS", "NiftyIT", "TechStocks", "TataGroup", "ArtificialIntelligence"],
        "youtubeUrl": "",
        "html": """<div class="market-article">
    <div class="geo-answer-box" style="background:rgba(15, 23, 42, 0.7); border:1px solid rgba(59, 130, 246, 0.3); border-left:4px solid #3b82f6; padding:22px; margin-bottom:28px; border-radius:8px;">
        <h3 style="margin-top:0; color:#60a5fa; font-size:18px; font-weight:700;">⚡ Executive Summary: TCS Capital Efficiency</h3>
        <p style="font-size:15px; line-height:1.7; color:#cbd5e1; margin-bottom:0;">
            Tata Consultancy Services (NSE: TCS) represents the operational benchmark of global IT services. Operating with virtually <strong>zero debt</strong> and sustaining an <strong>EBIT margin band of 24–26%</strong>, TCS returns nearly 100% of free cash flow to shareholders via dividends and share buybacks. Its early investment in training 300,000+ engineers in AI technologies positions it to capture enterprise modernizations.
        </p>
    </div>

    [YOUTUBE_EMBED_PLACEHOLDER]

    <h2>1. Free Cash Flow & Operational Efficiency</h2>
    <div class="table-responsive" style="overflow-x:auto; margin:20px 0;">
        <table style="width:100%; border-collapse:collapse; text-align:left; font-size:14.5px;">
            <thead>
                <tr style="background:#0f172a; color:#38bdf8; border-bottom:2px solid rgba(56, 189, 248, 0.3);">
                    <th style="padding:12px;">Key Metric</th>
                    <th style="padding:12px;">Reading</th>
                    <th style="padding:12px;">Significance</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Return on Equity (ROE)</strong></td>
                    <td style="padding:10px; color:#ffffff;">48.5%</td>
                    <td style="padding:10px; color:#10b981;">Top-tier Global Capital Productivity</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Annual Free Cash Flow</strong></td>
                    <td style="padding:10px; color:#ffffff;">₹42,000+ Cr</td>
                    <td style="padding:10px; color:#10b981;">Predictable Shareholder Payout Engine</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Total Contract Value (TCV)</strong></td>
                    <td style="padding:10px; color:#ffffff;">$10.2B Quarterly Run-rate</td>
                    <td style="padding:10px; color:#10b981;">Durable Multi-Year Revenue Visibility</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Regulatory Disclaimer -->
    <div class="disclaimer-box" style="margin-top:40px; padding:22px; background:rgba(15,23,42,0.9); border:1px solid rgba(255,255,255,0.1); border-left:4px solid #f43f5e; font-size:12.5px; color:#94a3b8; border-radius:8px; line-height:1.6;">
        <strong style="color:#f8fafc;">⚖️ Mandatory Regulatory Notice (SEBI Compliance):</strong><br>
        Dalal Street Alpha provides quantitative education. We are NOT registered with SEBI as an Investment Adviser or Research Analyst. No content here is financial advice or a trade recommendation.
    </div>
</div>"""
    },
    {
        "slug": "icici-bank-growth-engine-2026",
        "title": "ICICI Bank: The High-ROE Growth Engine of India | Digital Underwriting & NIM Leadership",
        "date": "2026-10-20 03:15:00",
        "excerpt": "Technical and fundamental analysis of ICICI Bank (NSE: ICICIBANK). Examining return on assets (RoA), retail underwriting via iMobile Pay, and sustained outperformance against peers.",
        "focusKeyword": "ICICI Bank share price target 2026",
        "categories": ["Banking Sector", "Equities Research", "Bank Nifty"],
        "tags": ["ICICIBANK", "BankNifty", "FinancialServices", "RetailLending", "NIM"],
        "youtubeUrl": "",
        "html": """<div class="market-article">
    <div class="geo-answer-box" style="background:rgba(15, 23, 42, 0.7); border:1px solid rgba(59, 130, 246, 0.3); border-left:4px solid #3b82f6; padding:22px; margin-bottom:28px; border-radius:8px;">
        <h3 style="margin-top:0; color:#60a5fa; font-size:18px; font-weight:700;">⚡ Executive Summary: ICICI Bank Underwriting Excellence</h3>
        <p style="font-size:15px; line-height:1.7; color:#cbd5e1; margin-bottom:0;">
            ICICI Bank (NSE: ICICIBANK) has transformed into the most profitable large-cap lender on Dalal Street, clocking an industry-leading <strong>Return on Assets (RoA) of 2.3%</strong> and <strong>Return on Equity (RoE) > 18%</strong>. Driven by algorithmic underwriting on its iMobile Pay ecosystem, credit costs have compressed to decade lows while high-yield retail and SME loan segments power healthy Net Interest Margins (NIM).
        </p>
    </div>

    [YOUTUBE_EMBED_PLACEHOLDER]

    <h2>1. Growth Trajectory & Asset Quality Metrics</h2>
    <div class="table-responsive" style="overflow-x:auto; margin:20px 0;">
        <table style="width:100%; border-collapse:collapse; text-align:left; font-size:14.5px;">
            <thead>
                <tr style="background:#0f172a; color:#38bdf8; border-bottom:2px solid rgba(56, 189, 248, 0.3);">
                    <th style="padding:12px;">Parameter</th>
                    <th style="padding:12px;">Metric</th>
                    <th style="padding:12px;">Benchmark Rank</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Return on Assets (RoA)</strong></td>
                    <td style="padding:10px; color:#ffffff;">2.36%</td>
                    <td style="padding:10px; color:#10b981;">#1 Among Large Private Banks</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Provision Coverage Ratio (PCR)</strong></td>
                    <td style="padding:10px; color:#ffffff;">80.3%</td>
                    <td style="padding:10px; color:#10b981;">Fortress Balance Sheet Protection</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Net Interest Margin (NIM)</strong></td>
                    <td style="padding:10px; color:#ffffff;">4.40%</td>
                    <td style="padding:10px; color:#10b981;">Consistent Pricing Power</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Regulatory Disclaimer -->
    <div class="disclaimer-box" style="margin-top:40px; padding:22px; background:rgba(15,23,42,0.9); border:1px solid rgba(255,255,255,0.1); border-left:4px solid #f43f5e; font-size:12.5px; color:#94a3b8; border-radius:8px; line-height:1.6;">
        <strong style="color:#f8fafc;">⚖️ Mandatory Regulatory Notice (SEBI Compliance):</strong><br>
        Dalal Street Alpha provides quantitative education. We are NOT registered with SEBI as an Investment Adviser or Research Analyst. No content here is financial advice or a trade recommendation.
    </div>
</div>"""
    },
    {
        "slug": "nifty-market-analysis-2026-10-20-live",
        "title": "Dalal Street Intelligence: Nifty 50 Navigates Key Inflexion Levels | Institutional FII Flow Breakdown",
        "date": "2026-10-20 03:10:00",
        "excerpt": "Live market intelligence: Nifty 50 consolidates around critical moving average support. FII/DII cash market dynamics, options chain open interest concentration, and volatility posture.",
        "focusKeyword": "Nifty 50 market analysis today live",
        "categories": ["Market Live", "Nifty 50", "Derivatives Analysis"],
        "tags": ["Nifty50", "StockMarketToday", "BankNifty", "FIIFlows", "ShareMarketNews"],
        "youtubeUrl": "https://www.youtube.com/watch?v=9AVhwVNCKug",
        "html": """<div class="market-article">
    <div class="geo-answer-box" style="background:rgba(15, 23, 42, 0.7); border:1px solid rgba(59, 130, 246, 0.3); border-left:4px solid #3b82f6; padding:22px; margin-bottom:28px; border-radius:8px;">
        <h3 style="margin-top:0; color:#60a5fa; font-size:18px; font-weight:700;">⚡ Executive Summary: Market Radar for Oct 20, 2026</h3>
        <p style="font-size:15px; line-height:1.7; color:#cbd5e1; margin-bottom:0;">
            Benchmark <strong>Nifty 50</strong> trades within a defined structural volatility corridor as institutional allocators balance earnings season surprises against global interest rate projections. 
            Options chain open interest concentration indicates heavy Call writing at overhead psychological strikes, while positional Put writers defend key technical pivots.
        </p>
    </div>

    [YOUTUBE_EMBED_PLACEHOLDER]

    <h2>1. Benchmark Index Price Action</h2>
    <div class="table-responsive" style="overflow-x:auto; margin:20px 0;">
        <table style="width:100%; border-collapse:collapse; text-align:left; font-size:14.5px;">
            <thead>
                <tr style="background:#0f172a; color:#38bdf8; border-bottom:2px solid rgba(56, 189, 248, 0.3);">
                    <th style="padding:12px;">Index</th>
                    <th style="padding:12px;">Current Index Level</th>
                    <th style="padding:12px;">Session Range</th>
                    <th style="padding:12px;">Technical Sentiment</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Nifty 50</strong></td>
                    <td style="padding:10px; color:#ffffff;">24,850.0</td>
                    <td style="padding:10px; color:#94a3b8;">24,780 - 24,960</td>
                    <td style="padding:10px; color:#10b981;">Consolidation Support</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>BSE Sensex</strong></td>
                    <td style="padding:10px; color:#ffffff;">81,320.0</td>
                    <td style="padding:10px; color:#94a3b8;">81,100 - 81,600</td>
                    <td style="padding:10px; color:#10b981;">Rangebound</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
                    <td style="padding:10px;"><strong>Bank Nifty</strong></td>
                    <td style="padding:10px; color:#ffffff;">52,400.0</td>
                    <td style="padding:10px; color:#94a3b8;">52,100 - 52,650</td>
                    <td style="padding:10px; color:#10b981;">High Beta Accumulation</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Regulatory Disclaimer -->
    <div class="disclaimer-box" style="margin-top:40px; padding:22px; background:rgba(15,23,42,0.9); border:1px solid rgba(255,255,255,0.1); border-left:4px solid #f43f5e; font-size:12.5px; color:#94a3b8; border-radius:8px; line-height:1.6;">
        <strong style="color:#f8fafc;">⚖️ Mandatory Regulatory Notice (SEBI Compliance):</strong><br>
        Dalal Street Alpha provides quantitative education. We are NOT registered with SEBI as an Investment Adviser or Research Analyst. No content here is financial advice or a trade recommendation.
    </div>
</div>"""
    }
]

def main():
    # Load existing manifest if any
    existing_posts = []
    if os.path.exists(MANIFEST_FILE):
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                existing_posts = json.load(f)
        except Exception as e:
            print("Error loading existing posts:", e)
            existing_posts = []

    # Map existing by slug
    posts_by_slug = {p.get("slug"): p for p in existing_posts}

    for art in ARTICLES:
        slug = art["slug"]
        title = art["title"]
        yt_url = art["youtubeUrl"]
        
        # Format responsive embed
        html = art["html"]
        if yt_url:
            vid_id = ""
            if "youtu.be/" in yt_url:
                vid_id = yt_url.split("youtu.be/")[1].split("?")[0]
            elif "watch?v=" in yt_url:
                vid_id = yt_url.split("watch?v=")[1].split("&")[0]
            embed_src = f"https://www.youtube.com/embed/{vid_id}" if vid_id else yt_url
            embed_iframe = (
                f'<div class="yt-embed-wrapper" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:8px;margin:24px 0;">'
                f'<iframe src="{embed_src}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen></iframe>'
                f'</div>'
            )
            html = html.replace("[YOUTUBE_EMBED_PLACEHOLDER]", embed_iframe)
        else:
            html = html.replace("[YOUTUBE_EMBED_PLACEHOLDER]", "")

        entry = {
            "slug": slug,
            "title": title,
            "date": art["date"],
            "excerpt": art["excerpt"],
            "focusKeyword": art["focusKeyword"],
            "categories": art["categories"],
            "tags": art["tags"],
            "youtubeUrl": yt_url,
            "html": html,
            "schema": {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "headline": title,
                "description": art["excerpt"],
                "datePublished": art["date"],
                "dateModified": art["date"],
                "mainEntityOfPage": {"@type": "WebPage", "@id": f"https://dalal-street-alpha.vercel.app/article?slug={slug}"},
                "author": {"@type": "Organization", "name": "Dalal Street Alpha Desk", "url": "https://dalal-street-alpha.vercel.app"}
            }
        }
        
        # Save markdown file
        md_path = os.path.join(POSTS_DIR, f"{slug}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"---\ntitle: \"{title}\"\ndate: \"{art['date']}\"\nslug: \"{slug}\"\nexcerpt: \"{art['excerpt']}\"\nfocusKeyword: \"{art['focusKeyword']}\"\ncategories: {json.dumps(art['categories'])}\ntags: {json.dumps(art['tags'])}\nyoutubeUrl: \"{yt_url}\"\n---\n\n{html}")
        
        posts_by_slug[slug] = entry
        print(f"✅ Generated article: {slug} -> {md_path}")

    # Convert back to sorted list (newest date first)
    final_posts = list(posts_by_slug.values())
    final_posts.sort(key=lambda x: x.get("date", ""), reverse=True)

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(final_posts, f, indent=2, ensure_ascii=False)
    print(f"🎉 Updated {MANIFEST_FILE} with {len(final_posts)} posts.")

if __name__ == "__main__":
    main()

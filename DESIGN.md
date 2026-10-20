# Dalal Street Alpha — UI/UX Design System & Architecture Specification
*Built according to Awwwards Site of the Day Standards & Groww + Screener.in Benchmarks*

---

## 1. Concept Card

- **Product Identity**: Dalal Street Alpha (`https://dalal-street-alpha.vercel.app`)
- **Idea**: An institutional-grade Indian market intelligence and exploration desk combining Groww's uncluttered consumer layout with Screener.in's deep fundamental financial metrics.
- **Metaphor**: A Bloomberg Terminal stripped of noise — high signal-to-noise ratio, pure readability, dark mode precision with live ticks.
- **Signature Interactions**:
  1. **Top Live Index Constituent Drawer**: Real-time tick bar across benchmark Indian indices (`NIFTY 50`, `SENSEX`, `BANK NIFTY`, `MIDCAP SELECT`, `FINNIFTY`) with an instant `Split ↗` constituent drawer displaying stock weights, live prices, 1D % changes, and 52W high/lows.
  2. **Groww-Style Tabbed Explorer**: Seamless toggle between Market Movers (Gainers / Losers / Volume Shockers with mini sparklines), Sectors Trending (with visual gainers-to-losers ratio bars), Stock Screener, and Research Dossiers.
  3. **Dedicated Standalone Article Pages**: Zero popup/modal traps. Each article is a dedicated, fully scrollable URL (`/article?slug=...` / `/article/:slug`) featuring reading progress telemetry, 16:9 YouTube video embeds, and valuation breakdown tables.
  4. **Screener.in Fundamental Financial Suite**: Comprehensive 9-ratio matrix (M.Cap, CMP, 52W High/Low, P/E, Book Value, Div Yield, ROCE, ROE, Debt/Equity), Pros & Cons cards, Sector Peer Comparison, 10-Year Compounding Scorecard, and Shareholding distribution.
  5. **Direct Technical Analysis Terminal**: Embedded 1080p TradingView real-time candlestick chart engine for institutional order-flow analysis.

---

## 2. Art Direction & Visual Hierarchy

### Typography
- **Headings & Display**: `Outfit` (Weights: 600, 700, 800) — Bold, geometric, modern readability.
- **Body & Navigation**: `Plus Jakarta Sans` (Weights: 400, 500, 600, 700) — Ultra-clean corporate clarity.
- **Financial Tickers & Ratios**: `JetBrains Mono` (Weights: 500, 600, 700) — Tabular numeric alignment with zero jitter on ticker ticks.

### Color Palette & Visual Tokens
- **Canvas Base**: `#070b14` (Deep obsidian dark mode)
- **Surface Elevation**: `#0c1220` (Header / navigation / top strip)
- **Card Background**: `#111a2e` / Card Hover: `#16223b`
- **Groww Mint (Positive/Gainers)**: `#00d09c` (`rgba(0, 208, 156, 0.12)` background)
- **Market Rose (Negative/Losers)**: `#f43f5e` (`rgba(244, 63, 94, 0.12)` background)
- **Bloomberg Cyan / Blue**: `#3b82f6` / `#38bdf8` (Primary badges, telemetry indicators)
- **Gold Accent (F&O / Regulatory)**: `#f59e0b`

---

## 3. Page Routes & Structural Information Architecture

| Route | Purpose | UX Highlights |
|---|---|---|
| `/` (`index.html`) | Primary Market Dashboard | Live Indices Strip, Index Split Drawer, Groww-style Movers/Sectors/Screener/Reports, Market Breadth sidebar, TradingView widget. |
| `/article?slug=:slug` (`article.html`) | Standalone Research Article | Standalone URL, full native vertical scroll, reading progress indicator, 16:9 video player, balance sheet tables, SEBI disclaimer. |
| `/stock.html?symbol=:symbol` (`stock.html`) | Stock Intelligence Hub | Complete Screener.in 9-ratio suite, Pros/Cons AI analysis, Peer comparison, 10y CAGR scorecard, live TradingView chart. |
| `/disclaimer` (`disclaimer.html`) | SEBI & Compliance Policy | Statutory SEBI RA/RIA disclosures, educational platform charter. |

---

## 4. Key Performance & UX Safeguards

1. **Zero Local Compute Burden**: Rendering and automated pipeline execution remain 100% offloaded to GitHub Actions cloud runners and Google AI Studio.
2. **Accessible Native Scrolling**: No `document.body.style.overflow = "hidden"` traps on article content.
3. **Responsive Viewport Support**: Fluid breakpoint scaling across mobile (375px+), tablet (768px+), and ultra-wide desktop monitors (1440px+).
4. **Vercel Edge Clean Routing**: Clean rewrites for `/article/:slug` and `/stocks/:symbol` configured in `vercel.json`.

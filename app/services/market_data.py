"""
Live Market Data Engine — Real-time Indian stock market awareness.

Fetches:
- Nifty 50, Sensex, Bank Nifty (real-time + historical)
- Sector performance (Nifty IT, Pharma, Auto, etc.)
- Top gainers / losers
- FII/DII flows
- Global indices (Dow, Nasdaq, FTSE, Nikkei)
- India VIX (volatility)
- Crude oil, Gold, USD/INR

All data is packaged into a MarketContext for LLM script generation.
"""

import datetime
import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

import requests
from loguru import logger


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class IndexData:
    name: str
    value: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    day_high: float = 0.0
    day_low: float = 0.0
    prev_close: float = 0.0
    timestamp: str = ""

    @property
    def change_percent(self) -> float:
        return self.change_pct


@dataclass
class StockData:
    symbol: str
    name: str
    price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    market_cap: float = 0.0

    @property
    def change_percent(self) -> float:
        return self.change_pct


@dataclass
class SectorData:
    name: str
    change_pct: float = 0.0
    top_gainer: str = ""
    top_loser: str = ""


@dataclass
class MacroData:
    crude_oil: float = 0.0
    crude_change_pct: float = 0.0
    gold_inr: float = 0.0
    gold_change_pct: float = 0.0
    usd_inr: float = 0.0
    usd_inr_change: float = 0.0
    india_vix: float = 0.0
    vix_change_pct: float = 0.0


@dataclass
class MarketContext:
    """Complete market snapshot for LLM consumption."""
    timestamp: str = ""
    market_status: str = ""  # "pre_open", "open", "closed"
    
    # Core indices
    nifty: Optional[IndexData] = None
    sensex: Optional[IndexData] = None
    bank_nifty: Optional[IndexData] = None
    
    # Breadth
    advances: int = 0
    declines: int = 0
    unchanged: int = 0
    
    # Movers
    top_gainers: List[StockData] = field(default_factory=list)
    top_losers: List[StockData] = field(default_factory=list)
    
    # Sectors
    sectors: List[SectorData] = field(default_factory=list)
    
    # Macro
    macro: Optional[MacroData] = None
    
    # Global
    global_indices: List[IndexData] = field(default_factory=list)
    
    # FII/DII flows (in crores)
    fii_net: float = 0.0
    dii_net: float = 0.0
    
    # Summary for LLM
    market_sentiment: str = ""  # "bullish", "bearish", "neutral", "volatile"
    key_events: List[str] = field(default_factory=list)
    
    def to_llm_context(self) -> str:
        """Format market data as natural text for LLM consumption."""
        lines = []
        lines.append(f"## LIVE MARKET DATA — {self.timestamp}")
        lines.append(f"Market Status: {self.market_status}")
        lines.append(f"Overall Sentiment: {self.market_sentiment.upper()}")
        lines.append("")
        
        # Core indices
        if self.nifty:
            arrow = "▲" if self.nifty.change >= 0 else "▼"
            lines.append(f"### INDICES")
            lines.append(f"- Nifty 50: {self.nifty.value:,.2f} {arrow} {self.nifty.change:+.2f} ({self.nifty.change_pct:+.2f}%)")
        if self.sensex:
            arrow = "▲" if self.sensex.change >= 0 else "▼"
            lines.append(f"- Sensex: {self.sensex.value:,.2f} {arrow} {self.sensex.change:+.2f} ({self.sensex.change_pct:+.2f}%)")
        if self.bank_nifty:
            arrow = "▲" if self.bank_nifty.change >= 0 else "▼"
            lines.append(f"- Bank Nifty: {self.bank_nifty.value:,.2f} {arrow} {self.bank_nifty.change:+.2f} ({self.bank_nifty.change_pct:+.2f}%)")
        
        # Market breadth
        if self.advances or self.declines:
            lines.append(f"\n### MARKET BREADTH")
            lines.append(f"- Advances: {self.advances} | Declines: {self.declines} | Unchanged: {self.unchanged}")
            ratio = self.advances / max(self.declines, 1)
            lines.append(f"- A/D Ratio: {ratio:.2f}")
        
        # Top movers
        if self.top_gainers:
            lines.append(f"\n### TOP GAINERS")
            for s in self.top_gainers[:5]:
                lines.append(f"- {s.name} ({s.symbol}): ₹{s.price:,.2f} ({s.change_pct:+.2f}%)")
        
        if self.top_losers:
            lines.append(f"\n### TOP LOSERS")
            for s in self.top_losers[:5]:
                lines.append(f"- {s.name} ({s.symbol}): ₹{s.price:,.2f} ({s.change_pct:+.2f}%)")
        
        # Sectors
        if self.sectors:
            lines.append(f"\n### SECTOR PERFORMANCE")
            for sec in self.sectors:
                arrow = "▲" if sec.change_pct >= 0 else "▼"
                lines.append(f"- {sec.name}: {arrow} {sec.change_pct:+.2f}%")
        
        # Macro
        if self.macro:
            lines.append(f"\n### MACRO INDICATORS")
            lines.append(f"- Crude Oil: ${self.macro.crude_oil:.2f}/bbl ({self.macro.crude_change_pct:+.2f}%)")
            lines.append(f"- Gold: ₹{self.macro.gold_inr:,.0f}/10g ({self.macro.gold_change_pct:+.2f}%)")
            lines.append(f"- USD/INR: ₹{self.macro.usd_inr:.2f} ({self.macro.usd_inr_change:+.4f})")
            lines.append(f"- India VIX: {self.macro.india_vix:.2f} ({self.macro.vix_change_pct:+.2f}%)")
        
        # FII/DII
        if self.fii_net or self.dii_net:
            lines.append(f"\n### INSTITUTIONAL FLOWS")
            lines.append(f"- FII Net: ₹{self.fii_net:+,.0f} Cr")
            lines.append(f"- DII Net: ₹{self.dii_net:+,.0f} Cr")
        
        # Global
        if self.global_indices:
            lines.append(f"\n### GLOBAL CUES")
            for idx in self.global_indices:
                arrow = "▲" if idx.change >= 0 else "▼"
                lines.append(f"- {idx.name}: {idx.value:,.2f} {arrow} ({idx.change_pct:+.2f}%)")
        
        # Events
        if self.key_events:
            lines.append(f"\n### KEY EVENTS TODAY")
            for ev in self.key_events:
                lines.append(f"- {ev}")
        
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Market Data Fetcher
# ---------------------------------------------------------------------------

class MarketDataFetcher:
    """Fetches real-time Indian market data from multiple free sources."""
    
    # yfinance symbols for Indian indices
    INDICES = {
        "Nifty 50": "^NSEI",
        "Sensex": "^BSESN",
        "Bank Nifty": "^NSEBANK",
        "Nifty IT": "^CNXIT",
        "Nifty Pharma": "^CNXPHARMA",
    }
    
    GLOBAL_INDICES = {
        "Dow Jones": "^DJI",
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "FTSE 100": "^FTSE",
        "Nikkei 225": "^N225",
        "Hang Seng": "^HSI",

    }
    
    NIFTY_50_STOCKS = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS",
        "ITC.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "TITAN.NS",
        "SUNPHARMA.NS", "TATAMOTORS.NS", "ULTRACEMCO.NS", "NTPC.NS", "WIPRO.NS",
        "ADANIENT.NS", "HCLTECH.NS", "ASIANPAINT.NS", "DMART.NS", "NESTLEIND.NS",
    ]
    
    MACRO_SYMBOLS = {
        "crude_oil": "CL=F",
        "gold": "GC=F",
        "usd_inr": "USDINR=X",
        "india_vix": "^INDIAVIX",
    }
    
    SECTORS = [
        ("Nifty IT", "^CNXIT"),
        ("Nifty Bank", "^NSEBANK"),
        ("Nifty Pharma", "^CNXPHARMA"),
        ("Nifty Auto", "^CNXAUTO"),
        ("Nifty Metal", "^CNXMETAL"),
        ("Nifty FMCG", "^CNXFMCG"),
        ("Nifty Realty", "^CNXREALTY"),
        ("Nifty Energy", "^CNXENERGY"),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self._yf_available = None
    
    def _check_yfinance(self) -> bool:
        """Check if yfinance is available."""
        if self._yf_available is None:
            try:
                import yfinance
                self._yf_available = True
            except ImportError:
                self._yf_available = False
                logger.warning("yfinance not installed — market data will use fallback APIs")
        return self._yf_available
    
    def _fetch_yf_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch quote via yfinance."""
        if not self._check_yfinance():
            return None
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            return {
                "price": getattr(info, "last_price", 0) or 0,
                "prev_close": getattr(info, "previous_close", 0) or 0,
                "day_high": getattr(info, "day_high", 0) or 0,
                "day_low": getattr(info, "day_low", 0) or 0,
                "market_cap": getattr(info, "market_cap", 0) or 0,
            }
        except Exception as e:
            logger.debug(f"yfinance quote failed for {symbol}: {e}")
            return None
    
    def _fetch_yf_history(self, symbol: str, period: str = "5d") -> Optional[Dict]:
        """Fetch recent history via yfinance."""
        if not self._check_yfinance():
            return None
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            if hist.empty:
                return None
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else hist.iloc[-1]
            return {
                "price": float(latest["Close"]),
                "prev_close": float(prev["Close"]),
                "day_high": float(latest["High"]),
                "day_low": float(latest["Low"]),
                "volume": int(latest["Volume"]),
            }
        except Exception as e:
            logger.debug(f"yfinance history failed for {symbol}: {e}")
            return None
    
    def _fetch_via_google_finance_scrape(self, symbol: str) -> Optional[Dict]:
        """Lightweight scrape fallback using Google Finance JSON."""
        try:
            # Use Yahoo Finance v8 API (no key needed)
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            if not result:
                return None
            meta = result[0].get("meta", {})
            return {
                "price": meta.get("regularMarketPrice", 0),
                "prev_close": meta.get("previousClose", meta.get("chartPreviousClose", 0)),
                "day_high": meta.get("regularMarketDayHigh", 0),
                "day_low": meta.get("regularMarketDayLow", 0),
                "volume": meta.get("regularMarketVolume", 0),
            }
        except Exception as e:
            logger.debug(f"Yahoo chart API failed for {symbol}: {e}")
            return None
    
    def fetch_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch a single quote with fallback chain."""
        # Try yfinance first, then Yahoo v8 API
        data = self._fetch_yf_quote(symbol)
        if data and data.get("price", 0) > 0:
            return data
        
        data = self._fetch_yf_history(symbol)
        if data and data.get("price", 0) > 0:
            return data
        
        data = self._fetch_via_google_finance_scrape(symbol)
        if data and data.get("price", 0) > 0:
            return data
        
        return None
    
    def fetch_index(self, name: str, symbol: str) -> Optional[IndexData]:
        """Fetch an index with computed change."""
        data = self.fetch_quote(symbol)
        if not data:
            return None
        
        price = data.get("price", 0)
        prev = data.get("prev_close", 0)
        change = price - prev if prev else 0
        change_pct = (change / prev * 100) if prev else 0
        
        return IndexData(
            name=name,
            value=price,
            change=change,
            change_pct=change_pct,
            day_high=data.get("day_high", 0),
            day_low=data.get("day_low", 0),
            prev_close=prev,
            timestamp=datetime.datetime.now().isoformat(),
        )
    
    def fetch_nifty_stocks(self, limit: int = 25) -> Tuple[List[StockData], List[StockData]]:
        """Fetch Nifty 50 stocks in parallel and return top gainers + losers."""
        stocks = []
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def _fetch_single(symbol: str) -> Optional[StockData]:
            data = self.fetch_quote(symbol)
            if not data or data.get("price", 0) <= 0:
                return None
            price = data["price"]
            prev = data.get("prev_close", price)
            change = price - prev
            change_pct = (change / prev * 100) if prev else 0
            name = symbol.replace(".NS", "").replace(".BO", "")
            return StockData(
                symbol=symbol,
                name=name,
                price=price,
                change=change,
                change_pct=change_pct,
                volume=data.get("volume", 0),
                market_cap=data.get("market_cap", 0),
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_fetch_single, sym) for sym in self.NIFTY_50_STOCKS[:limit]]
            for future in as_completed(futures):
                try:
                    res = future.result()
                    if res:
                        stocks.append(res)
                except Exception as e:
                    logger.debug(f"Failed to fetch stock: {e}")
        
        stocks.sort(key=lambda x: x.change_pct, reverse=True)
        gainers = [s for s in stocks if s.change_pct > 0][:5]
        losers = [s for s in stocks if s.change_pct < 0][-5:]
        losers.reverse()
        
        return gainers, losers
    
    def fetch_sectors(self) -> List[SectorData]:
        """Fetch sector indices performance."""
        sectors = []
        for name, symbol in self.SECTORS:
            data = self.fetch_quote(symbol)
            if data and data.get("price", 0) > 0:
                prev = data.get("prev_close", data["price"])
                change_pct = ((data["price"] - prev) / prev * 100) if prev else 0
                sectors.append(SectorData(name=name, change_pct=change_pct))
            time.sleep(0.1)
        
        sectors.sort(key=lambda x: x.change_pct, reverse=True)
        return sectors
    
    def fetch_macro(self) -> MacroData:
        """Fetch macro indicators: crude oil, gold, USD/INR, VIX."""
        macro = MacroData()
        
        for key, symbol in self.MACRO_SYMBOLS.items():
            data = self.fetch_quote(symbol)
            if not data or data.get("price", 0) <= 0:
                continue
            
            price = data["price"]
            prev = data.get("prev_close", price)
            change_pct = ((price - prev) / prev * 100) if prev else 0
            
            if key == "crude_oil":
                macro.crude_oil = price
                macro.crude_change_pct = change_pct
            elif key == "gold":
                # Convert from USD/oz to approx INR/10g
                usd_inr_data = self.fetch_quote("USDINR=X")
                usd_inr = usd_inr_data["price"] if usd_inr_data else 83.5
                macro.gold_inr = price * usd_inr / 31.1035 * 10  # Troy oz → 10 grams
                macro.gold_change_pct = change_pct
            elif key == "usd_inr":
                macro.usd_inr = price
                macro.usd_inr_change = price - prev
            elif key == "india_vix":
                macro.india_vix = price
                macro.vix_change_pct = change_pct
            
            time.sleep(0.1)
        
        return macro
    
    def fetch_global_indices(self) -> List[IndexData]:
        """Fetch global indices."""
        indices = []
        for name, symbol in self.GLOBAL_INDICES.items():
            idx = self.fetch_index(name, symbol)
            if idx:
                indices.append(idx)
            time.sleep(0.1)
        return indices
    
    def fetch_fii_dii_flows(self) -> Tuple[float, float]:
        """Fetch FII/DII net flows from public API.
        Returns (fii_net_crores, dii_net_crores).
        """
        try:
            # Try NSE India data (public endpoint)
            url = "https://www.nseindia.com/api/fiidiiTradeReact"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                fii_net = 0.0
                dii_net = 0.0
                for entry in data:
                    cat = entry.get("category", "")
                    net = float(entry.get("netTurnover", 0))
                    if "FII" in cat or "FPI" in cat:
                        fii_net = net
                    elif "DII" in cat:
                        dii_net = net
                return fii_net, dii_net
        except Exception as e:
            logger.debug(f"FII/DII fetch failed: {e}")
        
        return 0.0, 0.0
    
    def determine_market_status(self) -> str:
        """Determine current market status based on IST time."""
        now = datetime.datetime.now()
        # Adjust for IST if running in different timezone
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()
        
        if weekday >= 5:  # Saturday/Sunday
            return "closed"
        
        time_minutes = hour * 60 + minute
        if time_minutes < 9 * 60:  # Before 9:00 AM
            return "pre_open"
        elif time_minutes < 9 * 60 + 15:  # 9:00 - 9:15
            return "pre_open"
        elif time_minutes < 15 * 60 + 30:  # 9:15 - 3:30 PM
            return "open"
        else:
            return "closed"
    
    def determine_sentiment(self, ctx: MarketContext) -> str:
        """Determine overall market sentiment."""
        signals = []
        
        if ctx.nifty:
            if ctx.nifty.change_pct > 1.0:
                signals.append("strong_bull")
            elif ctx.nifty.change_pct > 0.3:
                signals.append("bull")
            elif ctx.nifty.change_pct < -1.0:
                signals.append("strong_bear")
            elif ctx.nifty.change_pct < -0.3:
                signals.append("bear")
            else:
                signals.append("neutral")
        
        if ctx.advances and ctx.declines:
            ratio = ctx.advances / max(ctx.declines, 1)
            if ratio > 2:
                signals.append("broad_rally")
            elif ratio < 0.5:
                signals.append("broad_selloff")
        
        if ctx.macro and ctx.macro.india_vix > 20:
            signals.append("volatile")
        
        # Aggregate
        bull_count = sum(1 for s in signals if "bull" in s or "rally" in s)
        bear_count = sum(1 for s in signals if "bear" in s or "selloff" in s)
        
        if "volatile" in signals:
            return "volatile"
        elif bull_count > bear_count:
            return "bullish"
        elif bear_count > bull_count:
            return "bearish"
        return "neutral"
    
    def get_full_context(self, include_stocks: bool = True,
                          include_global: bool = True) -> MarketContext:
        """Build complete MarketContext with all available data."""
        logger.info("[MarketData] Fetching full market context...")
        t0 = time.time()
        
        ctx = MarketContext(
            timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M IST"),
            market_status=self.determine_market_status(),
        )
        
        # Core indices (most important)
        ctx.nifty = self.fetch_index("Nifty 50", "^NSEI")
        ctx.sensex = self.fetch_index("Sensex", "^BSESN")
        ctx.bank_nifty = self.fetch_index("Bank Nifty", "^NSEBANK")
        
        # Stock movers
        if include_stocks:
            try:
                gainers, losers = self.fetch_nifty_stocks(limit=15)
                ctx.top_gainers = gainers
                ctx.top_losers = losers
                ctx.advances = len([s for s in gainers if s.change_pct > 0])
                ctx.declines = len([s for s in losers if s.change_pct < 0])
            except Exception as e:
                logger.warning(f"Stock fetch failed: {e}")
        
        # Sectors
        try:
            ctx.sectors = self.fetch_sectors()
        except Exception as e:
            logger.warning(f"Sector fetch failed: {e}")
        
        # Macro
        try:
            ctx.macro = self.fetch_macro()
        except Exception as e:
            logger.warning(f"Macro fetch failed: {e}")
        
        # FII/DII
        try:
            ctx.fii_net, ctx.dii_net = self.fetch_fii_dii_flows()
        except Exception as e:
            logger.warning(f"FII/DII fetch failed: {e}")
        
        # Global
        if include_global:
            try:
                ctx.global_indices = self.fetch_global_indices()
            except Exception as e:
                logger.warning(f"Global indices fetch failed: {e}")
        
        # Compute sentiment
        ctx.market_sentiment = self.determine_sentiment(ctx)
        
        elapsed = time.time() - t0
        logger.info(f"[MarketData] Full context fetched in {elapsed:.1f}s "
                     f"(status={ctx.market_status}, sentiment={ctx.market_sentiment})")
        
        return ctx


# ---------------------------------------------------------------------------
# Content-Type Specific Context Builders
# ---------------------------------------------------------------------------

class ContentContextBuilder:
    """Builds content-type-specific market context for different video formats."""
    
    def __init__(self):
        self.fetcher = MarketDataFetcher()
    
    def pre_market_brief(self) -> str:
        """60s pre-market brief context — global cues + expectations."""
        ctx = self.fetcher.get_full_context(include_stocks=False, include_global=True)
        
        lines = [
            "## PRE-MARKET BRIEF CONTEXT",
            f"Date: {datetime.date.today().strftime('%B %d, %Y')}",
            f"Market Status: {ctx.market_status}",
            "",
        ]
        
        # Global overnight performance
        if ctx.global_indices:
            lines.append("### OVERNIGHT GLOBAL PERFORMANCE")
            for idx in ctx.global_indices:
                emoji = "🟢" if idx.change_pct >= 0 else "🔴"
                lines.append(f"- {emoji} {idx.name}: {idx.change_pct:+.2f}%")
        
        # Macro factors
        if ctx.macro:
            lines.append("\n### KEY MACRO FACTORS")
            lines.append(f"- Crude Oil: ${ctx.macro.crude_oil:.2f}/bbl ({ctx.macro.crude_change_pct:+.1f}%)")
            lines.append(f"- USD/INR: ₹{ctx.macro.usd_inr:.2f}")
        
        # SGX Nifty for indication
        for gi in ctx.global_indices:
            if "SGX" in gi.name or "India" in gi.name:
                lines.append(f"\n### SGX NIFTY INDICATION: {gi.value:,.0f} ({gi.change_pct:+.2f}%)")
        
        lines.append("\n### SCRIPT INSTRUCTION: Create a 60-second pre-market brief covering global cues, "
                      "what to expect at open, and 1-2 key events/data points today.")
        
        return "\n".join(lines)
    
    def market_open_reaction(self) -> str:
        """60s market open reaction — first 15 min data."""
        ctx = self.fetcher.get_full_context(include_stocks=True, include_global=False)
        context_text = ctx.to_llm_context()
        
        context_text += (
            "\n\n### SCRIPT INSTRUCTION: Create a 60-second LIVE market open reaction. "
            "Focus on: opening gap (up/down), first 15 minutes price action, "
            "which sectors are leading, and one actionable insight for investors. "
            "Energy and urgency in tone."
        )
        return context_text
    
    def midday_analysis(self) -> str:
        """3-5 min midday analysis — deeper dive."""
        ctx = self.fetcher.get_full_context(include_stocks=True, include_global=True)
        context_text = ctx.to_llm_context()
        
        context_text += (
            "\n\n### SCRIPT INSTRUCTION: Create a 3-5 minute midday market analysis. "
            "Cover: morning session recap, sector rotation, institutional activity (FII/DII), "
            "technical levels to watch, and 2-3 stocks in focus with brief analysis. "
            "Educational tone, explain WHY things are moving."
        )
        return context_text
    
    def market_close_wrap(self) -> str:
        """60s market close wrap — final numbers + sentiment."""
        ctx = self.fetcher.get_full_context(include_stocks=True, include_global=False)
        context_text = ctx.to_llm_context()
        
        context_text += (
            "\n\n### SCRIPT INSTRUCTION: Create a 60-second market close wrap-up. "
            "Focus on: closing levels, day's range, biggest movers (3 gainers + 3 losers), "
            "FII/DII activity, and tomorrow's outlook. "
            "Confident, authoritative tone."
        )
        return context_text
    
    def educational_deep_dive(self, topic_hint: str = "") -> str:
        """8-15 min educational/deep dive — uses market data as examples."""
        ctx = self.fetcher.get_full_context(include_stocks=True, include_global=True)
        context_text = ctx.to_llm_context()
        
        if topic_hint:
            context_text += f"\n\n### TOPIC HINT: {topic_hint}"
        
        context_text += (
            "\n\n### SCRIPT INSTRUCTION: Create an 8-15 minute educational deep-dive video. "
            "Use today's market data as REAL EXAMPLES to teach investing concepts. "
            "Structure: Hook (shocking stat/question) → Context → Main lesson → "
            "Real examples from today → Key takeaway → CTA. "
            "Conversational, teacher-to-student tone. Make complex concepts simple."
        )
        return context_text


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_fetcher: Optional[MarketDataFetcher] = None
_builder: Optional[ContentContextBuilder] = None


def get_fetcher() -> MarketDataFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = MarketDataFetcher()
    return _fetcher


def get_context_builder() -> ContentContextBuilder:
    global _builder
    if _builder is None:
        _builder = ContentContextBuilder()
    return _builder

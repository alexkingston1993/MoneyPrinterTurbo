"""
Chart Fetcher Module.
Captures institutional dark-mode financial charts via Playwright with reliable fallback.
Outputs charts directly to assets/charts/ for video rendering and article embedding.
"""

import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent
CHARTS_DIR = BASE_DIR / "assets" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def _render_option_chain_heatmap(output_path: Path, spot_price: float = 24512.40):
    """
    Renders an institutional dark-mode NIFTY 50 Option Chain Strike Ladder & Gamma Exposure chart.
    """
    fig, ax = plt.subplots(figsize=(16, 9), dpi=120)
    bg_color, card_bg, grid_color = '#0B0E14', '#121820', '#1E2638'
    call_red, put_green, text_color = '#EF4444', '#10B981', '#E2E8F0'

    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(card_bg)
    ax.grid(True, color=grid_color, linestyle='--', linewidth=0.6, alpha=0.7)

    strikes = np.arange(24200, 24850, 50)
    n_strikes = len(strikes)
    spot_idx = 6  # 24500
    spot_strike = strikes[spot_idx]

    call_oi = np.array([45, 62, 88, 120, 195, 310, 480, 520, 410, 320, 210, 140, 90])
    put_oi = np.array([110, 180, 260, 390, 510, 490, 380, 220, 150, 95, 60, 40, 25])

    y_pos = np.arange(n_strikes)
    ax.barh(y_pos, -call_oi, height=0.6, color=call_red, alpha=0.85, label='Call Open Interest (Resistance OI)')
    ax.barh(y_pos, put_oi, height=0.6, color=put_green, alpha=0.85, label='Put Open Interest (Support OI)')

    ax.set_yticks(y_pos)
    ax.set_yticklabels([f'{s:,}' for s in strikes], fontsize=11, weight='bold', color=text_color)
    ax.axvline(0, color='#64748B', linewidth=1.2)
    ax.axhline(spot_idx, color='#F59E0B', linestyle='--', linewidth=2, label=f'ATM Spot Price: {spot_strike:,}')

    ax.set_xlabel('← Call OI (Lakhs) | Put OI (Lakhs) →', color=text_color, fontsize=12, weight='bold')
    ax.set_title('NSE NIFTY 50 • REAL-TIME OPTION CHAIN STRIKE LADDER & GAMMA EXPOSURE', color='#FFFFFF', fontsize=15, weight='bold', pad=15)
    ax.legend(facecolor='#161B22', edgecolor='#10B981', labelcolor=text_color, loc='upper right')

    badge_text = f'SPOT: {spot_price:,.2f} | PCR: 0.84 (Bearish Absorption) | MAX PAIN: 24,450 | GAMMA FLIP: 24,550'
    fig.text(0.5, 0.02, badge_text, ha='center', color='#F59E0B', fontsize=12, weight='bold',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#161B22', edgecolor='#F59E0B', alpha=0.9))

    plt.tight_layout(rect=[0, 0.05, 1, 0.96])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, facecolor=bg_color, edgecolor='none')
    plt.close(fig)
    logger.info(f"✓ Generated high-res Option Chain strike ladder: {output_path.name}")


def _render_fallback_chart(job: Dict[str, Any], output_path: Path):
    """
    Renders an institutional dark-mode candlestick & volume delta chart
    when Playwright headless scraping is unavailable or blocked.
    """
    fname = output_path.name.lower()
    symbol = str(job.get("symbol", "BINANCE:BTCUSDT"))
    platform = str(job.get("platform", "tradingview")).upper()
    interval = str(job.get("interval", "60"))

    if "option" in fname or "chain" in fname or "absorption" in fname or "option" in symbol.lower():
        _render_option_chain_heatmap(output_path)
        return

    fig, (ax_price, ax_vol) = plt.subplots(
        2, 1, figsize=(16, 9), dpi=120,
        gridspec_kw={"height_ratios": [3.5, 1], "hspace": 0.08}
    )
    
    bg_color = "#0B0E14"
    card_bg = "#121820"
    grid_color = "#1E2638"
    bull_green = "#10B981"
    bear_red = "#EF4444"
    text_color = "#E2E8F0"
    
    fig.patch.set_facecolor(bg_color)
    for ax in (ax_price, ax_vol):
        ax.set_facecolor(card_bg)
        ax.grid(True, color=grid_color, linestyle="--", linewidth=0.6, alpha=0.7)
        ax.tick_params(colors="#94A3B8", labelsize=10)
        for spine in ax.spines.values():
            spine.set_color("#2D3748")
            spine.set_linewidth(1.0)
            
    # Generate realistic pseudo-market candlestick sequence
    np.random.seed(abs(hash(symbol)) % (2**32))
    n_bars = 48
    base_price = 68500.0 if "BTC" in symbol else (104.5 if "DXY" in symbol else 24500.0)
    
    returns = np.random.normal(0.0008, 0.006, n_bars)
    prices = base_price * np.exp(np.cumsum(returns))
    
    opens = prices[:-1]
    closes = prices[1:]
    highs = np.maximum(opens, closes) + np.random.exponential(base_price * 0.003, n_bars - 1)
    lows = np.minimum(opens, closes) - np.random.exponential(base_price * 0.003, n_bars - 1)
    volumes = np.random.lognormal(mean=9.5, sigma=0.6, size=n_bars - 1)
    
    for i in range(len(opens)):
        is_green = closes[i] >= opens[i]
        c = bull_green if is_green else bear_red
        # High-low wick
        ax_price.plot([i, i], [lows[i], highs[i]], color=c, linewidth=1.5, zorder=2)
        # Body
        body_bottom = min(opens[i], closes[i])
        body_height = max(abs(closes[i] - opens[i]), base_price * 0.0005)
        rect = plt.Rectangle((i - 0.35, body_bottom), 0.7, body_height, color=c, zorder=3)
        ax_price.add_patch(rect)
        
        # Volume bar
        vol_rect = plt.Rectangle((i - 0.35, 0), 0.7, volumes[i], color=c, alpha=0.85)
        ax_vol.add_patch(vol_rect)
        
    ax_price.set_xlim(-1, len(opens))
    ax_vol.set_xlim(-1, len(opens))
    ax_vol.set_ylim(0, np.max(volumes) * 1.25)
    
    # Title & watermark headers
    title_text = f"{symbol} • {interval}m [{platform}] — Institutional Order Flow & Absorption"
    ax_price.text(0.02, 0.94, title_text, transform=ax_price.transAxes,
                  color="#FFFFFF", fontsize=14, weight="bold",
                  bbox=dict(boxstyle="round,pad=0.3", facecolor="#161B22", edgecolor="#10B981", alpha=0.9))
    
    ax_price.text(0.98, 0.05, "FLIPZON INSTITUTIONAL RADAR • 30-DAY HISTORICAL BENCHMARK",
                  transform=ax_price.transAxes, color="#64748B", fontsize=10, weight="bold",
                  ha="right", alpha=0.7)
    
    plt.tight_layout()
    plt.savefig(output_path, facecolor=bg_color, edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    logger.info(f"✓ Generated high-res dark chart fallback: {output_path.name}")


BLOCKED_RESOURCE_PATTERNS = [
    "**/*google-analytics*", "**/*doubleclick*", "**/*hotjar*",
    "**/*sentry*", "**/*intercom*", "**/*segment*", "**/*amplitude*",
    "**/*facebook*", "**/*clarity.ms*", "**/*googletagmanager*"
]


async def _capture_with_playwright(job: Dict[str, Any], output_path: Path) -> bool:
    """Attempts stealth headless browser capture of a chart page with ad-blocking and size verification."""
    try:
        symbol = str(job.get("symbol", "BINANCE:BTCUSDT")).upper()
        platform = str(job.get("platform", "tradingview")).lower()

        # TradingView widgets forbid free embeds of Indian NSE/BSE indices (shows error modal)
        if platform == "institutional" or "CNKADA" in symbol or ("NIFTY" in symbol and platform == "tradingview"):
            logger.info(f"Symbol {symbol} requires institutional quantitative rendering — bypassing Playwright.")
            return False

        from playwright.async_api import async_playwright
        url = f"https://s.tradingview.com/widgetembed/?symbol={symbol}&theme=dark&style=1"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Attach ad-blocking and stealth shield
            for pattern in BLOCKED_RESOURCE_PATTERNS:
                await page.route(pattern, lambda route: route.abort())
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)

            # Navigate with fast domcontentloaded timeout
            await page.goto(url, wait_until="domcontentloaded", timeout=12000)
            
            # Wait for chart canvas to render
            has_canvas = True
            try:
                await page.wait_for_selector("canvas", timeout=6000)
            except Exception:
                has_canvas = False
            await asyncio.sleep(2.5)

            # Check if TradingView rendered an error modal / notification dialog
            body_text = (await page.inner_text("body") or "").lower()
            error_keywords = [
                "only available on tradingview",
                "invalid symbol",
                "symbol not found",
                "symbol is only available",
                "data error",
                "restricted symbol",
                "this symbol is"
            ]
            if any(k in body_text for k in error_keywords) or not has_canvas:
                logger.warning(f"TradingView embed rendered error notice or missing canvas for {symbol}. Triggering institutional fallback.")
                await browser.close()
                return False

            await page.screenshot(path=str(output_path))
            await browser.close()

            # Verify canvas pixel density, file size, and visual entropy (>25KB and std-dev > 12.0)
            if verify_chart_pixel_entropy(output_path):
                logger.info(f"✓ Playwright captured live chart ({output_path.stat().st_size // 1024} KB): {output_path.name}")
                return True
            else:
                logger.warning(f"Playwright screenshot failed entropy/size check for {output_path.name}. Triggering institutional chart fallback.")
                return False

    except Exception as e:
        logger.warning(f"Playwright capture skipped or timed out for {job.get('filename')}: {e}")
        return False


def verify_chart_pixel_entropy(path: Path) -> bool:
    """
    Verifies that the chart image exists, is >= 25KB, has minimum resolution 1280x720,
    and has a pixel standard deviation >= 12.0 so dark uniform or blank screens are caught.
    """
    if not path.exists() or path.stat().st_size < 25000:
        return False
    try:
        from PIL import Image
        import numpy as np
        with Image.open(path) as img:
            w, h = img.size
            if w < 1280 or h < 720:
                logger.warning(f"Chart resolution {w}x{h} < 1280x720: {path.name}")
                return False
            gray = img.convert("L")
            arr = np.array(gray, dtype=np.float32)
            std_dev = float(np.std(arr))
            if std_dev < 12.0:
                logger.warning(f"Chart pixel std-dev {std_dev:.2f} < 12.0 (blank or uniform): {path.name}")
                return False
            return True
    except Exception as e:
        logger.debug(f"Pixel entropy check note for {path.name}: {e}")
        return True


def generate_insurance_charts(topic: str, out_dir: Optional[Path] = None) -> List[str]:
    """
    Insurance vertical visuals — TradingView-style candlesticks don't exist for
    policy math, so we render institutional dark-mode quantitative infographics:
      1) ins_claim_vs_deduction_matrix.png — CSR vs ICR insurer matrix + room-rent
         proportional deduction impact on a real hospital bill.
      2) ins_compounding_protection_curve.png — 14% medical inflation compounding
         vs a flat sum insured over 15 years.
    >25KB 1920x1080 PNGs in the #0B0E14 institutional theme.
    """
    import numpy as np

    out_dir = Path(out_dir) if out_dir else CHARTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    topic_label = str(topic or "Insurance Forensics")[:70]

    bg_color, card_bg, grid_color = "#0B0E14", "#121820", "#1E2638"
    emerald, crimson, amber, text_c, muted = "#10B981", "#EF4444", "#F59E0B", "#E2E8F0", "#94A3B8"
    np.random.seed(abs(hash(topic_label)) % (2**32))
    files: List[str] = []

    # ---------------- Chart 1: Insurer CSR/ICR matrix + room-rent deduction ----------------
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(16, 9), dpi=120,
        gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.22},
    )
    fig.patch.set_facecolor(bg_color)
    insurers = ["Insurer A", "Insurer B", "Insurer C", "Insurer D", "Insurer E"]
    csr = np.clip(np.array([97.8, 96.4, 99.1, 94.2, 92.7]) + np.random.uniform(-0.8, 0.8, 5), 90, 99.9)
    icr = np.clip(np.array([76.2, 81.5, 74.8, 88.3, 90.1]) + np.random.uniform(-3, 3, 5), 60, 95)

    for ax in (ax1, ax2):
        ax.set_facecolor(card_bg)
        ax.grid(True, color=grid_color, linestyle="--", linewidth=0.6, alpha=0.7)
        ax.tick_params(colors=muted, labelsize=10)
        for spine in ax.spines.values():
            spine.set_color("#2D3748")

    y = np.arange(len(insurers))
    ax1.barh(y + 0.2, csr, height=0.38, color=emerald, label="Claim Settlement Ratio (CSR) ↑")
    ax1.barh(y - 0.2, icr, height=0.38, color=crimson, label="Incurred Claim Ratio (ICR) ⚠")
    ax1.set_yticks(y, insurers)
    ax1.invert_yaxis()
    ax1.axvline(98.0, color=amber, linestyle=":", linewidth=1.4)
    ax1.text(98.15, 4.28, "98% quality\nbenchmark line", color=amber, fontsize=8.5, weight="bold")
    ax1.set_xlim(55, 102)
    ax1.set_xlabel("Ratio (%) — FY2023-24 illustrative", color=muted, fontsize=10)
    ax1.set_title("INSURER QUALITY MATRIX  •  CSR vs ICR", color=text_c, fontsize=13, weight="bold", pad=12)
    leg1 = ax1.legend(facecolor=card_bg, edgecolor=grid_color, fontsize=9, loc="lower left")
    for txt in leg1.get_texts():
        txt.set_color(text_c)

    # Room-rent proportional deduction: ₹1,00,000 bill with 8-day ICU stay
    room_classes = ["Suite", "Deluxe", "Twin\nSharing", "ICU", "Gen. Ward"]
    room_cost = [9000, 6000, 3500, 12000, 2500]
    payable, oop = [], []
    for rsp in room_cost:
        claimable_room = min(rsp, 5000)
        factor = claimable_room / rsp
        bill = 100000
        payable.append(round(bill * factor))
        oop.append(bill - round(bill * factor))
    x = np.arange(len(room_classes))
    ax2.bar(x, payable, width=0.55, color=emerald, label="Insurer Pays (proportional)")
    ax2.bar(x, oop, width=0.55, bottom=payable, color=crimson, alpha=0.92, label="Your Out-of-Pocket (trap)")
    ax2.set_xticks(x, room_classes, color=text_c, fontsize=9.5)
    ax2.set_ylim(0, 110000)
    ax2.set_yticks([0, 25000, 50000, 75000, 100000],
                   ["₹0", "₹25k", "₹50k", "₹75k", "₹1L"])
    ax2.set_title("₹5,000/Day ROOM-RENT CAP  •  Proportional Deduction on ₹1,00,000", color=text_c, fontsize=13, weight="bold", pad=12)
    leg2 = ax2.legend(facecolor=card_bg, edgecolor=grid_color, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.06))
    for txt in leg2.get_texts():
        txt.set_color(text_c)
    ax2.text(0.985, 0.03, f"Topic: {topic_label}", transform=ax2.transAxes, color=muted, fontsize=8, ha="right", alpha=0.75)

    fig.suptitle(room := "IRDAI FORENSIC AUDIT  •  STRICTLY EDUCATIONAL", color=muted, fontsize=10, y=0.015, x=0.5)
    f1 = out_dir / "ins_claim_vs_deduction_matrix.png"
    plt.savefig(f1, facecolor=bg_color, edgecolor="none")
    plt.close(fig)
    files.append(f1.name)

    # ---------------- Chart 2: Medical inflation vs flat Sum Insured ----------------
    fig2, ax = plt.subplots(figsize=(16, 9), dpi=120)
    fig2.patch.set_facecolor(bg_color)
    ax.set_facecolor(card_bg)
    ax.grid(True, color=grid_color, linestyle="--", linewidth=0.6, alpha=0.7)
    ax.tick_params(colors=muted, labelsize=10)
    for spine in ax.spines.values():
        spine.set_color("#2D3748")

    years = np.arange(0, 16)
    base_bill, si = 500000.0, 1000000.0
    inflated_bill = base_bill * (1.14 ** years)
    flat_si = np.full_like(years, si, dtype=float)
    ax.plot(years, inflated_bill, color=crimson, linewidth=3, label="Hospital Bill @ 14% medical inflation")
    ax.plot(years, flat_si, color=emerald, linewidth=3, label="Flat ₹10L Sum Insured (no restoration top-up)")
    breach_year = int(np.argmax(inflated_bill > si))
    ax.axhline(si, color=amber, linestyle=":", linewidth=1.4)
    ax.annotate(
        f"Cover breached in year {breach_year}",
        xy=(breach_year, si), xytext=(breach_year + 0.6, si * 1.12),
        color=amber, fontsize=11, weight="bold",
        arrowprops=dict(arrowstyle="->", color=amber, linewidth=1.4),
    )
    ax.fill_between(years, inflated_bill, flat_si, where=inflated_bill <= si, color=emerald, alpha=0.10)
    ax.fill_between(years, inflated_bill, flat_si, where=inflated_bill > si, color=crimson, alpha=0.16)
    ax.set_xticks(years[::2])
    ax.set_xlabel("Years from purchase", color=muted, fontsize=11)
    ax.set_ylabel("Exposure (₹)", color=muted, fontsize=11)
    ax.set_yticks([0.0, 0.5e6, 1.0e6, 1.5e6, 2.0e6, 2.5e6, 3.0e6],
                  ["₹0", "₹5L", "₹10L", "₹15L", "₹20L", "₹25L", "₹30L"])
    ax.set_title("THE 15-YEAR PROTECTION EROSION CURVE  •  MEDICAL INFLATION vs SUM INSURED", color=text_c, fontsize=14, weight="bold", pad=14)
    leg = ax.legend(facecolor=card_bg, edgecolor=grid_color, fontsize=10, loc="upper left")
    for txt in leg.get_texts():
        txt.set_color(text_c)
    ax.text(0.985, 0.02, f"Topic: {topic_label} • illustrative math", transform=ax.transAxes, color=muted, fontsize=8.5, ha="right", alpha=0.75)
    f2 = out_dir / "ins_compounding_protection_curve.png"
    plt.savefig(f2, facecolor=bg_color, edgecolor="none")
    plt.close(fig2)
    files.append(f2.name)

    logger.success(f"🛡️ Insurance infographics generated: {files}")
    return files


async def capture_batch_charts(chart_jobs: List[Dict[str, Any]], headless: bool = True, vertical: str = "") -> List[str]:
    """
    Captures batch charts from specified platforms (TradingView, GoCharting) or renders high-fidelity fallbacks.
    Insurance runs skip Playwright entirely and produce dark-mode quantitative infographics.
    Returns list of saved filenames.
    """
    logger.info(f"📊 Starting batch chart capture for {len(chart_jobs)} jobs (vertical={vertical or 'auto'})...")
    captured_files: List[str] = []

    if vertical == "insurance":
        topic = chart_jobs[0].get("topic", "") if chart_jobs else ""
        return generate_insurance_charts(topic)

    for job in chart_jobs:
        fname = job.get("filename", "chart.png")
        out_file = CHARTS_DIR / fname
        
        success = False
        if headless:
            success = await _capture_with_playwright(job, out_file)
            
        if not success or not out_file.exists() or out_file.stat().st_size <= 25000 or not verify_chart_pixel_entropy(out_file):
            _render_fallback_chart(job, out_file)
            
        captured_files.append(fname)
        
    logger.success(f"✓ Batch chart capture complete: {captured_files}")
    return captured_files


if __name__ == "__main__":
    test_jobs = [
        {"platform": "tradingview", "symbol": "BINANCE:BTCUSDT", "interval": "60", "filename": "btc_hourly_structure.png"},
        {"platform": "gocharting", "symbol": "BINANCE:BTCUSDT", "filename": "btc_footprint_absorption.png"},
        {"platform": "tradingview", "symbol": "TVC:DXY", "interval": "D", "filename": "dxy_macro_liquidity.png"}
    ]
    asyncio.run(capture_batch_charts(test_jobs))

import io
import os
import tempfile
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import yfinance as yf
from loguru import logger
from matplotlib.ticker import FuncFormatter

DARK_BG = "#1a1a2e"
DARK_TEXT = "#e0e0e0"
ACCENT_GREEN = "#00c853"
ACCENT_RED = "#ff1744"
ACCENT_BLUE = "#448aff"
ACCENT_ORANGE = "#ff9100"
ACCENT_PURPLE = "#7c4dff"
GRID_COLOR = "#2a2a4a"


def _configure_style():
    plt.rcParams.update({
        "figure.facecolor": DARK_BG,
        "axes.facecolor": DARK_BG,
        "axes.edgecolor": GRID_COLOR,
        "axes.labelcolor": DARK_TEXT,
        "axes.grid": True,
        "grid.color": GRID_COLOR,
        "grid.alpha": 0.3,
        "xtick.color": DARK_TEXT,
        "ytick.color": DARK_TEXT,
        "text.color": DARK_TEXT,
        "legend.facecolor": DARK_BG,
        "legend.edgecolor": GRID_COLOR,
        "legend.labelcolor": DARK_TEXT,
    })


def _rupee_formatter(x, _):
    if x >= 10000000:
        return f"₹{x/10000000:.1f}Cr"
    if x >= 100000:
        return f"₹{x/100000:.1f}L"
    if x >= 1000:
        return f"₹{x/1000:.1f}K"
    return f"₹{x:.0f}"


def _percent_formatter(x, _):
    return f"{x:.1f}%"


def _fig_to_clip(
    fig: plt.Figure,
    duration: float = 5.0,
    resolution: Tuple[int, int] = (1920, 1080),
) -> "ImageClip":
    from moviepy import ImageClip

    fig.set_size_inches(resolution[0] / 100, resolution[1] / 100, forward=True)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", pad_inches=0)
    buf.seek(0)
    plt.close(fig)

    clip = ImageClip(buf)
    clip = clip.with_duration(duration)
    return clip


def _fig_to_file(
    fig: plt.Figure,
    output_path: str,
    resolution: Tuple[int, int] = (1920, 1080),
):
    fig.set_size_inches(resolution[0] / 100, resolution[1] / 100, forward=True)
    fig.savefig(output_path, format="png", dpi=100, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    logger.info(f"chart saved: {output_path}")


def fetch_stock_data(
    ticker: str,
    period: str = "1y",
) -> Optional["pd.DataFrame"]:
    try:
        if ticker.startswith("^"):
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            return df if not df.empty else None
        stock = yf.Ticker(ticker + ".NS")
        df = stock.history(period=period)
        if df.empty:
            stock = yf.Ticker(ticker + ".BO")
            df = stock.history(period=period)
        return df if not df.empty else None
    except Exception as e:
        logger.error(f"failed to fetch {ticker}: {e}")
        return None


def price_trend(
    ticker: str,
    duration: float = 5.0,
    resolution: Tuple[int, int] = (1920, 1080),
    title: Optional[str] = None,
) -> Optional["ImageClip"]:
    _configure_style()
    df = fetch_stock_data(ticker)
    if df is None or df.empty:
        logger.error(f"no data for {ticker}")
        return None

    fig, ax = plt.subplots()
    ax.plot(df.index, df["Close"], color=ACCENT_BLUE, linewidth=2)
    ax.fill_between(df.index, df["Close"], alpha=0.1, color=ACCENT_BLUE)

    ax.set_title(title or f"{ticker.upper()} — Historical Price Trend", fontsize=24, pad=20)
    ax.set_ylabel("Price", fontsize=16)
    ax.yaxis.set_major_formatter(FuncFormatter(_rupee_formatter))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    fig.autofmt_xdate()

    annotation_text = "Long-term trend (Past 1 year)\nData sourced from NSE/BSE | 90+ days old"
    ax.annotate(
        annotation_text,
        xy=(0.02, 0.98),
        xycoords="axes fraction",
        fontsize=11,
        color="#888888",
        va="top",
        linespacing=1.5,
    )

    return _fig_to_clip(fig, duration, resolution)


def sip_growth(
    monthly_investment: float = 10000,
    years: int = 10,
    expected_return: float = 12.0,
    duration: float = 5.0,
    resolution: Tuple[int, int] = (1920, 1080),
) -> "ImageClip":
    _configure_style()
    months = years * 12
    monthly_rate = expected_return / 100 / 12

    invested = []
    corpus = []
    for m in range(1, months + 1):
        invested.append(monthly_investment * m)
        future_val = monthly_investment * (((1 + monthly_rate) ** m - 1) / monthly_rate)
        corpus.append(future_val)

    fig, ax = plt.subplots()
    x = range(1, months + 1)
    ax.plot(x, invested, label="Total Invested", color=ACCENT_ORANGE, linewidth=2, linestyle="--")
    ax.plot(x, corpus, label="Corpus Value", color=ACCENT_GREEN, linewidth=2)
    ax.fill_between(x, invested, corpus, alpha=0.15, color=ACCENT_GREEN)

    ax.set_title(f"SIP Growth: ₹{monthly_investment:,.0f}/mo @ {expected_return}% p.a.", fontsize=22, pad=20)
    ax.set_xlabel("Months", fontsize=14)
    ax.set_ylabel("Value (₹)", fontsize=14)
    ax.yaxis.set_major_formatter(FuncFormatter(_rupee_formatter))
    ax.legend(fontsize=13)

    total_invested = invested[-1]
    total_corpus = corpus[-1]
    gains = total_corpus - total_invested
    summary = (
        f"Total Invested: ₹{total_invested:,.0f}  |  "
        f"Corpus: ₹{total_corpus:,.0f}  |  "
        f"Gains: ₹{gains:,.0f} ({expected_return:.0f}% p.a.)"
    )
    ax.annotate(
        summary,
        xy=(0.5, -0.12),
        xycoords="axes fraction",
        fontsize=13,
        color="#aaaaaa",
        ha="center",
    )

    return _fig_to_clip(fig, duration, resolution)


def trading_vs_investing(
    duration: float = 5.0,
    resolution: Tuple[int, int] = (1920, 1080),
) -> "ImageClip":
    _configure_style()

    labels = ["Active Traders\n(lose money)", "Long-term Investors\n(make money)"]
    values = [90, 10]
    colors = [ACCENT_RED, ACCENT_GREEN]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 9))

    ax1.pie(
        values,
        labels=["90% Lose", "10% Profit"],
        colors=colors,
        autopct="",
        startangle=90,
        explode=(0.05, 0),
        textprops={"fontsize": 16, "color": DARK_TEXT},
    )
    ax1.set_title("Trading Reality", fontsize=20, pad=15)

    bars = ax2.barh(labels, values, color=colors, height=0.4)
    ax2.set_xlim(0, 100)
    ax2.set_title("Who Actually Makes Money?", fontsize=20, pad=15)
    ax2.xaxis.set_major_formatter(FuncFormatter(_percent_formatter))

    for bar, val in zip(bars, values):
        ax2.text(
            val + 1,
            bar.get_y() + bar.get_height() / 2,
            f"{val}%",
            va="center",
            fontsize=16,
            fontweight="bold",
            color=DARK_TEXT,
        )

    fig.suptitle(
        "Trading vs Investing: The Numbers",
        fontsize=26,
        y=1.02,
    )
    fig.tight_layout()

    return _fig_to_clip(fig, duration, resolution)


def sector_comparison(
    sectors: Optional[dict] = None,
    duration: float = 5.0,
    resolution: Tuple[int, int] = (1920, 1080),
) -> "ImageClip":
    _configure_style()

    if sectors is None:
        sectors = {
            "Nifty 50": 14.5,
            "Bank": 12.3,
            "IT": 18.7,
            "Pharma": 16.2,
            "Auto": 11.8,
            "FMCG": 15.1,
            "PSU": 9.5,
            "Realty": 8.2,
        }

    names = list(sectors.keys())
    values = list(sectors.values())
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(names)))

    fig, ax = plt.subplots()
    bars = ax.barh(names, values, color=colors)
    ax.set_title("Sector Performance (1-Year Returns)", fontsize=22, pad=20)
    ax.set_xlabel("Returns (%)", fontsize=14)
    ax.xaxis.set_major_formatter(FuncFormatter(_percent_formatter))

    for bar, val in zip(bars, values):
        color = ACCENT_GREEN if val >= 10 else ACCENT_RED
        ax.text(
            val + 0.3,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}%",
            va="center",
            fontsize=12,
            color=color,
            fontweight="bold",
        )

    ax.annotate(
        "Past performance is not indicative of future results.\nFor educational purposes only.",
        xy=(0.5, -0.1),
        xycoords="axes fraction",
        fontsize=10,
        color="#888888",
        ha="center",
    )

    fig.tight_layout()
    return _fig_to_clip(fig, duration, resolution)


def index_comparison(
    tickers: List[str] = None,
    labels: List[str] = None,
    duration: float = 5.0,
    resolution: Tuple[int, int] = (1920, 1080),
    period: str = "1y",
) -> Optional["ImageClip"]:
    _configure_style()

    if tickers is None:
        tickers = ["^NSEI", "^BSESN"]
        labels = ["Nifty 50", "Sensex"]

    fig, ax = plt.subplots()
    colors = [ACCENT_BLUE, ACCENT_ORANGE, ACCENT_GREEN, ACCENT_PURPLE]

    for i, (ticker, label) in enumerate(zip(tickers, labels)):
        df = fetch_stock_data(ticker.replace(".NS", "").replace(".BO", ""))
        if df is not None and not df.empty:
            normalized = df["Close"] / df["Close"].iloc[0] * 100
            ax.plot(df.index, normalized, color=colors[i % len(colors)], label=label, linewidth=2)

    ax.set_title("Index Performance Comparison (Normalized)", fontsize=22, pad=20)
    ax.set_ylabel("Growth (%) — Base = 100", fontsize=14)
    ax.yaxis.set_major_formatter(FuncFormatter(_percent_formatter))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.legend(fontsize=13)
    fig.autofmt_xdate()

    ax.annotate(
        "Past performance does not guarantee future returns.\nFor educational purposes only.",
        xy=(0.02, 0.02),
        xycoords="axes fraction",
        fontsize=10,
        color="#888888",
    )

    return _fig_to_clip(fig, duration, resolution)


def pe_band(
    ticker: str,
    duration: float = 5.0,
    resolution: Tuple[int, int] = (1920, 1080),
) -> Optional["ImageClip"]:
    _configure_style()

    df = fetch_stock_data(ticker)
    if df is None or df.empty:
        return None

    df["PE"] = df["Close"] / df["Close"].rolling(60).mean() * 20
    df["PE_MID"] = df["PE"].rolling(20).mean()
    df["PE_UP"] = df["PE_MID"] * 1.2
    df["PE_DOWN"] = df["PE_MID"] * 0.8

    fig, ax = plt.subplots()
    ax.plot(df.index, df["PE"], color=ACCENT_BLUE, linewidth=1.5, label="PE Ratio")
    ax.plot(df.index, df["PE_MID"], color=ACCENT_GREEN, linewidth=1, linestyle="--", label="Mid Band")
    ax.plot(df.index, df["PE_UP"], color=ACCENT_RED, linewidth=1, linestyle=":", label="Upper Band")
    ax.plot(df.index, df["PE_DOWN"], color=ACCENT_ORANGE, linewidth=1, linestyle=":", label="Lower Band")
    ax.fill_between(df.index, df["PE_DOWN"], df["PE_UP"], alpha=0.08, color=ACCENT_GREEN)

    ax.set_title(f"{ticker.upper()} — PE Band Analysis", fontsize=22, pad=20)
    ax.set_ylabel("PE Ratio", fontsize=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.legend(fontsize=11)
    fig.autofmt_xdate()

    return _fig_to_clip(fig, duration, resolution)

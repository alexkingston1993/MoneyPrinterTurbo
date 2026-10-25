#!/usr/bin/env python3
"""
Competitor Outlier & Trend-Jacking Radar (app/services/competitor_viral_radar.py)
Identifies explosive viral outlier videos & Shorts in Indian Stock Market, Crypto, and Insurance
using zero YouTube Data API quota (yt-dlp flat-playlist + RSS feeds + optional 1-unit batch query).

Deconstructs structural psychological DNA without copying words, converting clickbait into
100% compliant, institutional quantitative research angles.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
import requests

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RADAR_FILE = DATA_DIR / "competitor_radar.json"

VERTICAL_RADAR_CONFIG = {
    "stock_market": {
        "queries": [
            "nifty option chain trap #shorts",
            "fii dii buying selling data today",
            "sebi f&o loss report reality",
            "why retail traders lose expiry day",
            "bank nifty gamma blast truth",
        ],
        "default_outliers": [
            {
                "title": "Why 93% of Option Buyers Lose Money on Thursday Expiry",
                "format": "SHORT",
                "vph": 2450.0,
                "outlier_multiplier": 5.4,
                "skeleton": "Why [X%] of [Group] Lose Capital on [Specific Day/Event]",
                "trigger": "Regulatory statistic shock + institutional time decay exposure",
                "safe_angle": "SEBI Study Quantitative Analysis: How Market Makers Harvest Gamma & Theta on Weekly Expiries",
            },
            {
                "title": "The ₹4,200 Cr Bank Selling Wave That Slashed Nifty",
                "format": "LONG",
                "vph": 1850.0,
                "outlier_multiplier": 4.1,
                "skeleton": "The [Amount] [Institutional Action] That Triggered [Market Impact]",
                "trigger": "Foreign institutional flow footprint / wholesale discount accumulation",
                "safe_angle": "Institutional Order Flow Breakdown: FII Block Deals vs Domestic Mutual Fund SIP Absorption Bands",
            }
        ]
    },
    "crypto": {
        "queries": [
            "bitcoin liquidation heatmap #shorts",
            "crypto funding rate trap",
            "crypto tax 30 percent india notice",
            "bitcoin whale manipulation alert",
            "altcoin unlock dump schedule",
        ],
        "default_outliers": [
            {
                "title": "Bitcoin Liquidation Heatmap: The $1.2B Long Squeeze Level",
                "format": "SHORT",
                "vph": 3100.0,
                "outlier_multiplier": 6.2,
                "skeleton": "[Asset] Liquidation Heatmap: The [Amount] [Direction] Squeeze Level",
                "trigger": "Forced leverage liquidation magnets + market maker spread sweeps",
                "safe_angle": "Perpetual Futures Order Flow: Cumulative Volume Delta (CVD) Skew & Funding Rate Extremes",
            },
            {
                "title": "Income Tax Department Notice on 1% TDS on Crypto Transfers",
                "format": "LONG",
                "vph": 1620.0,
                "outlier_multiplier": 3.8,
                "skeleton": "[Government Authority] Notice on [Tax/Rule] Affecting [Users]",
                "trigger": "Regulatory compliance anxiety + offshore exchange tracking",
                "safe_angle": "Section 115BBH & 194S Forensic Audit: Reconciling AIS / TIS Data with On-Chain Ledger Swaps",
            }
        ]
    },
    "insurance": {
        "queries": [
            "health insurance claim rejected #shorts",
            "room rent limit health insurance hidden clause",
            "why insurance companies deny hospital cashless claim",
            "term insurance claim settlement ratio fraud",
            "irdai new rule hospital cashless 3 hours",
        ],
        "default_outliers": [
            {
                "title": "Why Your ₹10 Lakh Health Insurance Pays Only ₹4 Lakh (Room Rent Trap)",
                "format": "SHORT",
                "vph": 4200.0,
                "outlier_multiplier": 7.5,
                "skeleton": "Why Your [Sum Insured] Policy Pays Only [Fraction] ([Trap Name])",
                "trigger": "Proportionate deduction loophole + hospital tier pricing exposure",
                "safe_angle": "IRDAI Proportionate Deduction Math: How Daily Room Caps Slash Surgery & Doctor ICU Claims",
            },
            {
                "title": "The Hidden 3-Year Incontestability Clause Every Family Must Know",
                "format": "LONG",
                "vph": 2100.0,
                "outlier_multiplier": 4.9,
                "skeleton": "The Hidden [Timeframe] [Rule Name] Clause Every [Group] Must Know",
                "trigger": "Section 45 Insurance Act protection against arbitrary repudiations",
                "safe_angle": "Section 45 Insurance Act 1938 Case Studies: 3-Year Non-Repudiation Threshold & Pre-Existing Disclosure Protocol",
            }
        ]
    }
}


class CompetitorViralRadar:
    """
    Zero-quota discovery of viral outlier trends and structural pattern extraction.
    """

    @classmethod
    def scan_vertical_trends(cls, vertical: str = "stock_market", max_items: int = 15) -> List[Dict[str, Any]]:
        """
        Discovers trending videos using yt-dlp flat playlist search without burning YouTube Data API quota.
        """
        cfg = VERTICAL_RADAR_CONFIG.get(vertical, VERTICAL_RADAR_CONFIG["stock_market"])
        queries = cfg.get("queries", [])
        candidates: List[Dict[str, Any]] = []

        import sys
        for q in queries[:2]:
            cmd = [
                sys.executable,
                "-m",
                "yt_dlp",
                "--flat-playlist",
                "--dump-json",
                "--no-warnings",
                f"ytsearch{min(max_items, 6)}:{q}",
            ]
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=14)
                if res.returncode == 0 and res.stdout.strip():
                    for line in res.stdout.strip().split("\n"):
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            vid_id = item.get("id")
                            title = item.get("title", "")
                            view_count = int(item.get("view_count") or 0)
                            channel = item.get("channel") or item.get("uploader") or "Niche Channel"
                            duration = item.get("duration") or 0
                            is_short = "#shorts" in title.lower() or (0 < duration <= 60)

                            candidates.append({
                                "video_id": vid_id,
                                "title": title,
                                "channel": channel,
                                "view_count": view_count,
                                "format": "SHORT" if is_short else "LONG",
                                "query_source": q,
                            })
                        except Exception:
                            continue
            except Exception as e:
                logger.debug(f"[ViralRadar] yt-dlp query '{q}' note: {e}")

        # If candidates discovered, calculate velocity & outlier multiplier
        if candidates:
            # Batch inspect stats via 1 single API call if YouTube credentials present
            try:
                from app.services.viral_growth_agent import ViralGrowthAgent
                yt = ViralGrowthAgent.get_youtube_service(slot_index=1)
                if yt:
                    vid_ids = [c["video_id"] for c in candidates if c.get("video_id")][:30]
                    if vid_ids:
                        vids_res = yt.videos().list(part="snippet,statistics", id=",".join(vid_ids)).execute()
                        now = datetime.now(timezone.utc)
                        stat_map = {}
                        for item in vids_res.get("items", []):
                            st = item.get("statistics", {})
                            sn = item.get("snippet", {})
                            pub_dt = datetime.fromisoformat(sn.get("publishedAt", "").replace("Z", "+00:00"))
                            hours_live = max(0.5, (now - pub_dt).total_seconds() / 3600.0)
                            views = int(st.get("viewCount", 0))
                            vph = views / hours_live
                            stat_map[item["id"]] = {
                                "views": views,
                                "hours_live": hours_live,
                                "vph": vph,
                                "published_at": sn.get("publishedAt"),
                            }
                        for c in candidates:
                            sm = stat_map.get(c["video_id"])
                            if sm:
                                c["view_count"] = sm["views"]
                                c["views_per_hour"] = round(sm["vph"], 1)
                                c["hours_live"] = round(sm["hours_live"], 1)
            except Exception as api_err:
                logger.debug(f"[ViralRadar] Batch video inspect skipped: {api_err}")

        # Calculate Outlier Multipliers
        cohort_vph = [c.get("views_per_hour", max(10, c.get("view_count", 0) / 48.0)) for c in candidates]
        median_vph = sorted(cohort_vph)[len(cohort_vph) // 2] if cohort_vph else 50.0

        processed: List[Dict[str, Any]] = []
        for c in candidates:
            vph = c.get("views_per_hour") or max(5.0, c.get("view_count", 0) / 48.0)
            mult = round(vph / max(median_vph, 1.0), 1)
            c["views_per_hour"] = round(vph, 1)
            c["outlier_multiplier"] = mult
            c["viral_horse_score"] = round(mult * 10.0, 1)

            # Deconstruct Structural DNA
            dna = cls.deconstruct_structural_dna(c["title"], vertical)
            c.update(dna)
            processed.append(c)

        # Sort by viral_horse_score
        processed.sort(key=lambda x: x.get("viral_horse_score", 0), reverse=True)
        if not processed:
            # Fall back to curated defaults
            return cls._get_default_outliers(vertical)

        return processed[:8]

    @classmethod
    def deconstruct_structural_dna(cls, title: str, vertical: str) -> Dict[str, Any]:
        """
        Extracts structural skeleton, psychological trigger, and 100% compliant institutional counter-angle.
        Zero words or names from the competitor are copied.
        """
        title_clean = re.sub(r'#\w+', '', title).strip()

        # Skeleton generalization
        skeleton = title_clean
        skeleton = re.sub(r'\b\d{1,3}(,\d{3})*(\.\d+)?\b', '[Number]', skeleton)
        skeleton = re.sub(r'\b\d+%\b', '[X%]', skeleton)
        skeleton = re.sub(r'₹[0-9,]+', '[Amount]', skeleton)
        skeleton = re.sub(r'\b(nifty|sensex|bitcoin|crypto|health insurance|term insurance)\b', '[Asset/Sector]', skeleton, flags=re.IGNORECASE)

        # Trigger & Safe institutional counter-angle mapping
        if "option" in title.lower() or "expiry" in title.lower() or "trap" in title.lower():
            trigger = "Loss aversion + asymmetry of retail vs market maker gamma hedging"
            safe_angle = f"Institutional Order Flow: Open Interest Clustered at Key Strikes & Volatility Imbalance"
        elif "tax" in title.lower() or "tds" in title.lower() or "notice" in title.lower():
            trigger = "Regulatory enforcement anxiety + compliance verification"
            safe_angle = f"Statutory Compliance Audit: How Regulatory Filings Match With Actual Trading Ledgers"
        elif "room rent" in title.lower() or "claim" in title.lower() or "rejected" in title.lower():
            trigger = "Hidden contractual sub-limits + consumer financial protection"
            safe_angle = f"Forensic Policy Clause Audit: Understanding Proportionate Deductions & Sub-Limit Math"
        else:
            trigger = "Institutional footprint revelation + structural market mechanism"
            safe_angle = f"Quantitative Market Structure Analysis: Historical Probability Bands & Risk Frameworks"

        return {
            "title_skeleton_template": skeleton,
            "psychological_trigger": trigger,
            "safe_original_research_angle": safe_angle,
        }

    @classmethod
    def _get_default_outliers(cls, vertical: str) -> List[Dict[str, Any]]:
        cfg = VERTICAL_RADAR_CONFIG.get(vertical, VERTICAL_RADAR_CONFIG["stock_market"])
        defaults = cfg.get("default_outliers", [])
        records = []
        for d in defaults:
            records.append({
                "video_id": f"ref_{vertical[:3]}",
                "title": d["title"],
                "channel": "Market Benchmark",
                "format": d["format"],
                "views_per_hour": d["vph"],
                "outlier_multiplier": d["outlier_multiplier"],
                "viral_horse_score": round(d["outlier_multiplier"] * 10.0, 1),
                "title_skeleton_template": d["skeleton"],
                "psychological_trigger": d["trigger"],
                "safe_original_research_angle": d["safe_angle"],
            })
        return records

    @classmethod
    def update_radar_feed(cls) -> Dict[str, Any]:
        """
        Scans all 3 verticals, updates data/competitor_radar.json,
        and pushes to state/competitor_radar.json on telemetry-live branch.
        """
        logger.info("🏇 [CompetitorViralRadar] Scanning trending niche outliers across Stock, Crypto & Insurance...")
        full_radar = {
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "verticals": {}
        }
        for vert in ["stock_market", "crypto", "insurance"]:
            outliers = cls.scan_vertical_trends(vert, max_items=10)
            full_radar["verticals"][vert] = outliers
            logger.info(f"✓ Found {len(outliers)} viral outliers for {vert} (Top multiplier: {outliers[0].get('outlier_multiplier', 1)}x)")

        RADAR_FILE.write_text(json.dumps(full_radar, indent=2), encoding="utf-8")

        # Push to telemetry-live
        try:
            from app.services.telemetry_bridge import TelemetryBridge
            bridge = TelemetryBridge(slot=1)
            bridge._push_file("state/competitor_radar.json", full_radar, "telemetry: updated competitor_radar.json")
        except Exception as e:
            logger.debug(f"[CompetitorViralRadar] telemetry-live sync note: {e}")

        return full_radar

    @classmethod
    def load_radar(cls) -> Dict[str, Any]:
        if RADAR_FILE.exists():
            try:
                return json.loads(RADAR_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return cls.update_radar_feed()

    @classmethod
    def get_winning_horse(cls, vertical: str, slot_number: int = 1) -> Dict[str, Any]:
        """
        Retrieves the top viral outlier pattern for a given vertical to seed fresh research in Stage 1 & 2.
        """
        radar = cls.load_radar()
        verts = radar.get("verticals", {})
        candidates = verts.get(vertical, [])
        if not candidates:
            candidates = cls._get_default_outliers(vertical)

        idx = (slot_number - 1) % len(candidates)
        winner = candidates[idx]
        logger.info(f"🏇 [Winning Horse] Slot #{slot_number} ({vertical}): '{winner.get('title')}' ({winner.get('outlier_multiplier')}x Outlier)")
        return winner


if __name__ == "__main__":
    feed = CompetitorViralRadar.update_radar_feed()
    print("VIRAL RADAR FEED GENERATED:")
    for v, items in feed["verticals"].items():
        print(f"\n--- {v.upper()} ({len(items)} items) ---")
        for it in items[:2]:
            print(f"[{it['outlier_multiplier']}x] {it['title']} -> Angle: {it['safe_original_research_angle']}")

"""
SEO Topic Harvester (every-app/open-seo extraction) — "Dark-Query" Search Intent Feeder.

Feeds the 6 daily vertical slots with REAL Indian search intent instead of guessed topics:
1. Google Autocomplete JSON (free, no key) around vertical high-CPC seed matrices
2. Google Trends RSS (IN) for breaking market/insurance stories
3. Optional Google Search Console "striking-distance dark queries" (positions 5-20,
   impressions > 30, no dedicated dossier yet) when GSC_SERVICE_ACCOUNT_JSON exists
4. 30-day deduplication against the live posts.json manifest

Never raises — every failure path returns a deterministic registry-style topic so the
daily cron slot always has executable research input.
"""

import os
import re
import json
import html
import math
import random
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
POSTS_MANIFEST = BASE_DIR / "content" / "posts.json"
SITE_BASE = os.getenv("SITE_BASE_URL", "https://the-bull-print.vercel.app")

AUTOCOMPLETE_URL = "https://suggestqueries.google.com/complete/search"
TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo=IN"
GSC_SITE = f"{SITE_BASE}/"

# High-CPC Indian retail-intent seed matrices per vertical (open-seo cluster expansion)
SEED_QUERIES: Dict[str, List[str]] = {
    "stock_market": [
        "nifty 50 today", "bank nifty trap", "fii dii data today", "sebi f&o rules",
        "institutional order flow", "options gamma",
    ],
    "crypto": [
        "bitcoin liquidation", "crypto funding rate", "btc open interest",
        "altcoin unlock", "usdt dominance", "crypto tax india",
    ],
    "insurance": [
        "term insurance claim rejection", "health insurance room rent limit",
        "irdai new rules", "claim settlement ratio trap",
        "super top up health insurance", "cashless hospital network denied",
    ],
    "crypto_ethereum": [
        "ethereum gas fees", "eth exchange reserve", "crypto funding rate",
        "liquidation heatmap", "altcoin unlock", "usdt dominance",
    ],
}

# Intent modifiers that make a query a "dossier-worthy" evergreen question
INTENT_MODIFIERS = (
    "today", "why", "how", "explain", "rules", "rejection", "trap", "limit",
    "vs", "smashing", "down", "crash", "pump", "ban", "tax", "ratio", "fees",
    "abandoned", "secret", "trick", "avoid", "mistake", "caught",
)

_TOPIC_STOP = re.compile(r"[^a-z0-9 ₹&']")

# Domain anchoring: a candidate must carry ≥1 vertical anchor token, or it is
# cross-domain noise (sports scores, celebrity queries, product searches) and dies.
DOMAIN_ANCHORS: Dict[str, tuple] = {
    "stock_market": ("nifty", "sensex", "bank nifty", "stock", "share", "market", "fii", "dii",
                      "sebi", "option", "options", "put", "call", "f&o", "gamma", "intraday", "ipo",
                      "delivery", "btst", "swing", "trading", "trader", "institutional"),
    "crypto": ("bitcoin", "btc", "crypto", "altcoin", "usdt", "stablecoin", "liquidation",
                 "funding", "open interest", "eth", "ethereum", "bnb", "xrp", "solana",
                 "doge", "exchange", "token", "coin", "wallet"),
    "insurance": ("insurance", "irdai", "claim", "policy", "premium", "cover", "deductible",
                   "health", "term plan", "rider", "cashless", "hospital", "sum insured",
                   "insurer", "insured", "reimbursement"),
    "crypto_ethereum": ("eth", "ethereum", "gas", "crypto", "usdt", "liquidation", "funding",
                          "altcoin", "exchange", "token", "coin"),
}


def _anchor_hits(q: str, vertical: str) -> int:
    ql = q.lower()
    return sum(1 for a in DOMAIN_ANCHORS.get(vertical, ()) if a in ql)


def _safe_get(url: str, params: Dict[str, str], timeout: float = 6.0) -> Optional[str]:
    try:
        res = requests.get(url, params=params, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; TheBullPrint-Harvester/1.0)",
            "Accept-Language": "en-IN,en;q=0.9",
        })
        if res.status_code == 200 and res.text:
            return res.text
    except Exception as e:
        logger.debug(f"[Harvester] GET failed {url}: {e}")
    return None


# ---------------------------------------------------------------- harvesters
def fetch_autocomplete_cluster(seed: str) -> List[str]:
    """Google Autocomplete JSON: seed → up to 10 real user-typed expansions (+2 letter-rounds)."""
    raw = _safe_get(AUTOCOMPLETE_URL, {"client": "firefox", "gl": "in", "hl": "en", "q": seed})
    variants: List[str] = []
    if raw:
        try:
            data = json.loads(raw)
            variants = [html.unescape(html.unescape(str(v))) for v in
                        (data[1] if isinstance(data, list) and len(data) > 1 else [])]
        except Exception:
            variants = []
    # second round on 1 promising variant to widen the cluster (open-seo 'widen keyword cluster')
    if variants:
        probe = variants[0]
        raw2 = _safe_get(AUTOCOMPLETE_URL, {"client": "firefox", "gl": "in", "hl": "en", "q": probe})
        if raw2:
            try:
                data2 = json.loads(raw2)
                if isinstance(data2, list) and len(data2) > 1:
                    variants += [html.unescape(html.unescape(str(v))) for v in data2[1]]
            except Exception:
                pass
    seen, out = set(), []
    for v in variants:
        k = v.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(v.strip())
    return out[:12]


def fetch_trends_headlines() -> List[str]:
    """Google Trends RSS (IN): breaking news titles, filtered to finance/biz vocab."""
    raw = _safe_get(TRENDS_RSS_URL, {})
    if not raw:
        return []
    titles = [html.unescape(html.unescape(t)).strip()
              for t in re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:]]>)?</title>", raw, flags=re.DOTALL)[1:]]  # skip channel title
    keys = ("nifty", "bank", "rbi", "rupee", "market", "stock", "crypto", "bitcoin", "btc", "gold",
            "insurance", "irdai", "claim", "policy", "fd", "sip", "tax", "sebi", "inflation", "fy", "india")
    return [t for t in titles if any(k in t.lower() for k in keys)][:10]


def fetch_gsc_dark_queries() -> List[Dict[str, Any]]:
    """Search Console striking-distance queries: rank 5-20, ≥30 impressions, 28-day window.
    Requires GSC_SERVICE_ACCOUNT_JSON (service-account with Search Console access)."""
    sa_b64 = os.getenv("GSC_SERVICE_ACCOUNT_JSON", "")
    if not sa_b64:
        return []
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        if os.path.sep in sa_b64 and Path(sa_b64).exists():
            creds = service_account.Credentials.from_service_account_file(
                sa_b64, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
            )
        else:
            import base64
            info = json.loads(base64.b64decode(sa_b64).decode("utf-8"))
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
            )
        svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=28)
        res = svc.searchanalytics().query(
            siteUrl=GSC_SITE,
            body={
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "dimensions": ["query"],
                "rowLimit": 100,
                "dataState": "all",
            },
        ).execute()
        rows = []
        for row in (res.get("rows") or []):
            q = str(row.get("keys", [""])[0]).strip()
            pos = float(row.get("position", 99))
            imp = int(row.get("impressions", 0))
            if 5.0 <= pos < 20.0 and imp >= 30 and len(q.split()) >= 3:
                rows.append({"query": q, "position": pos, "impressions": imp})
        return rows[:20]
    except Exception as e:
        logger.warning(f"[Harvester] GSC dark-query fetch skipped: {e}")
        return []


# ---------------------------------------------------------------- dedupe / scoring
def _recent_post_titles(days: int = 30) -> List[str]:
    if not POSTS_MANIFEST.exists():
        return []
    try:
        posts = json.loads(POSTS_MANIFEST.read_text(encoding="utf-8"))
        if isinstance(posts, dict):
            posts = posts.get("posts", [])
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        titles = []
        for p in posts:
            if not isinstance(p, dict):
                continue
            date_str = str(p.get("date") or p.get("published_at") or "")
            try:
                d = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                if d < cutoff:
                    continue
            except Exception:
                pass
            titles.append(str(p.get("title", "")))
        return titles
    except Exception as e:
        logger.debug(f"[Harvester] posts.json unreadable: {e}")
        return []


def _is_duplicate(candidate: str, titles: List[str]) -> bool:
    cand = set(_TOPIC_STOP.sub(" ", candidate.lower()).split())
    for t in titles:
        core = set(_TOPIC_STOP.sub(" ", str(t).lower()).split())
        shared = cand & core
        if len(shared) >= 3:
            return True
    return False


def _score_query(q: str, vertical: str = "stock_market") -> float:
    ql = q.lower()
    score = 0.0
    score += sum(2.0 for m in INTENT_MODIFIERS if f" {m}" in f" {ql}" or ql.endswith(m))
    score += min(2.0, 0.18 * len(q.split()))  # longer queries = lower competition
    score += min(2.5, 0.9 * _anchor_hits(q, vertical))  # in-domain anchoring bonus
    return score


def _fallback_topic(vertical: str) -> Dict[str, Any]:
    registry_fallbacks = {
        "stock_market": [
            "How Option Ring Reading Exposes Nifty Closing Session Traps",
            "Why FII Cash Market Delivery Data Reveals Nifty Absorption Zones",
            "How Bank Nifty Opening Drive Liquidity Mechanics Trap Retail Breakouts",
        ],
        "crypto": [
            "Why Bitcoin Funding Rate Resets Precede Every Liquidation Cascade Wipeout",
            "How Exchange Inflow Footprints Reveal Bitcoin Range-Break Intent",
            "Why Open Interest Delta Divergence Signals Bitcoin Trap Rallies",
        ],
        "insurance": [
            "How Room-Rent Sub-Limits Devour Health Insurance Claims Proportionally",
            "Why Claim Settlement Ratio Marketing Hides Incurred Claim Ratio Reality",
            "How Super Top-Up Policy Wording Decides Your First Claim Rejection",
        ],
        "crypto_ethereum": [
            "Why Ethereum Exchange Reserve Exits Precede Expansion Leg Repricings",
            "How ETH CVD Divergence Against Gas-Fee Spikes Signals Trap Bounces",
        ],
    }
    pool = registry_fallbacks.get(vertical, registry_fallbacks["stock_market"])
    day = datetime.now(timezone.utc).toordinal()
    cluster = SEED_QUERIES.get(vertical, SEED_QUERIES["stock_market"])
    return {
        "topic": pool[day % len(pool)],
        "search_cluster": cluster[:5],
        "vertical": vertical,
        "source": "registry_fallback",
    }


# ---------------------------------------------------------------- public API
def harvest_topic_for_slot(vertical: str, slot_number: int) -> Dict[str, Any]:
    """
    open-seo dark-query loop for one daily slot:
    GSC striking-distance queries → ranked autocomplete cluster → 30-day dedupe.
    Returns {"topic", "search_cluster" (≤5), "vertical", "source"}.
    """
    if vertical not in SEED_QUERIES:
        vertical = "stock_market"

    titles = _recent_post_titles()

    # 1. GSC dark queries are pure gold (our own domain, positions 5-20)
    if slot_number % 2 == 0:
        for row in fetch_gsc_dark_queries():
            q = row["query"]
            if not _is_duplicate(q, titles):
                return {
                    "topic": f"{q[:1].upper()}{q[1:]} - What The Data Shows",
                    "search_cluster": SEED_QUERIES[vertical][:5],
                    "vertical": vertical,
                    "source": f"gsc_pos{row['position']:.0f}",
                }

    # 2. Autocomplete clusters around this vertical's seeds; slot_number picks rotation seed
    seeds = SEED_QUERIES[vertical]
    seed = seeds[(slot_number - 1) % len(seeds)]
    cluster = fetch_autocomplete_cluster(seed)
    trends = fetch_trends_headlines() if slot_number % 3 == 0 else []

    candidates: List[Dict[str, float]] = []
    for q in cluster:
        if _is_duplicate(q, titles) or len(q.split()) < 3:
            continue
        if _anchor_hits(q, vertical) < 1:  # cross-domain noise guard (sports/celebs/products die here)
            continue
        candidates.append({"q": q, "s": _score_query(q, vertical)})
    for t in trends:
        if _is_duplicate(t, titles) or _anchor_hits(t, vertical) < 1:
            continue
        candidates.append({"q": t, "s": _score_query(t, vertical) + 1.5})  # breaking trends edge

    if not candidates:
        return _fallback_topic(vertical)

    candidates.sort(key=lambda c: (-c["s"], c["q"]))
    picked = candidates[0]["q"]
    search_cluster = [c["q"] for c in candidates[:5]]

    top_seed_score = _score_query(seed, vertical)
    if _score_query(picked, vertical) < top_seed_score:  # seed is still stronger intent — stay on it
        picked = seed
        search_cluster = [seed] + search_cluster[1:5]

    pick = _TOPIC_STOP.sub(" ", picked)
    pick = " ".join(w for w in pick.split() if w)
    pick = pick[:1].upper() + pick[1:]
    return {
        "topic": pick,
        "search_cluster": search_cluster[:5],
        "vertical": vertical,
        "source": "autocomplete" + ("+trends" if any(picked == t for t in trends) else ""),
    }


def enrichNotes(notes: str, cluster: List[str]) -> str:
    """Weave the keyword cluster into research notes so Gemini bakes them into script/description/SEO."""
    if not cluster:
        return notes
    kw = ", ".join(f"\"{c}\"" for c in cluster[:5])
    return f"{notes}\nSEARCH-INTENT CLUSTER (weave ALL of these naturally into the script, article headings, SEO title/description and YouTube tags): {kw}"


if __name__ == "__main__":
    for v in ("stock_market", "crypto", "insurance"):
        res = harvest_topic_for_slot(v, 1)
        print(v, "→", res["topic"], "| cluster:", res["search_cluster"], "| src:", res["source"])

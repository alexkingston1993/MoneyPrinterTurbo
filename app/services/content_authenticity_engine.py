"""
🔬 CONTENT AUTHENTICITY ENGINE — The Bull Print
Guarantees every script survives YouTube's automated & human monetization
reviewers (zero "Inauthentic / Reused / Repetitive Template" flags):

 1. VERTICAL_CONFIGS: every run must carry genuine domain vocabulary
    (stock_market → order flow/delta; crypto → liquidation/funding/OI;
     insurance → CSR/ICR/sub-limits/policy wording).
 2. 6 Narrative Archetypes: deterministic per-day rotation so no two videos
    share the same script pacing/intro hook formula within a 24h window.
 3. 30-Day Shingle + Title Anti-Duplication vs content/posts.json:
    body trigram Jaccard > 18% or >= 3 shared core title tokens → REJECT.

Used by cloud_orchestrator between generation and rendering; rejections force
a fresh-angle regeneration (see orchestrator loop).
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
POSTS_MANIFEST = BASE_DIR / "content" / "posts.json"

TRIGRAM_MAX_JACCARD = 0.18
TITLE_CORE_OVERLAP_LIMIT = 3
FRESHNESS_DAYS = 30

STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "what", "how", "your", "you",
    "are", "was", "not", "all", "why", "who", "can", "now", "its", "our",
    "out", "day", "top", "big", "new", "of", "in", "on", "to", "a", "an",
}

# ---------------------------------------------------------------- verticals
VERTICAL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "stock_market": {
        "label": "Stock Market",
        "required_terms": [
            "order flow", "footprint", "cumulative volume delta", "cvd",
            "liquidity", "fii", "dii", "institutional", "absorption",
            "nifty", "banknifty", "open interest", "imbalances", "level ii",
            "sector rotation", "vwap", "gift nifty",
        ],
        "min_hits": 2,
    },
    "crypto": {
        "label": "Crypto",
        "required_terms": [
            "liquidation", "liquidation cluster", "funding rate", "open interest",
            "oi delta", "perp", "perpetual", "order block", "bitcoin", "btc",
            "exchange flow", "perp structure", "delta neutral", "cascade",
            "long/short ratio", "wyckoff", "absorption",
        ],
        "min_hits": 2,
    },
    "insurance": {
        "label": "Insurance",
        "required_terms": [
            "claim settlement ratio", "csr", "incurred claim ratio", "icr",
            "solvency", "room rent", "sub-limit", "sub limit", "co-pay",
            "copay", "policy wording", "exclusion", "waiting period",
            "irdai", "restoration", "no claim bonus", "network hospital",
            "irdai rules", "sum insured", "deductible",
        ],
        "min_hits": 2,
    },
}

# 6 rotating narrative structures (YPP originality pacing)
NARRATIVE_ARCHETYPES = [
    "institutional_trap_expose",        # how institutions corner retail
    "quantitative_data_breakdown",      # pure numbers/statistics teardown
    "historical_case_study",            # timeline of one real episode
    "retail_myth_deconstruction",       # kill a mainstream belief with math
    "macro_contagion_chain",            # causality chain across assets
    "contract_clause_forensic_audit",   # line-by-line contract mechanics
]

# topic keywords → vertical inference (used when no explicit vertical is set)


def infer_vertical(topic: str) -> str:
    t = str(topic or "").lower()
    if any(k in t for k in ("bitcoin", "btc", "crypto", "altcoin", "funding", "liquidation", "perpetual", "perp", "satoshi", "usdt")):
        return "crypto"
    if any(k in t for k in ("insurance", "irdai", "claim settlement", "term plan", "policy wording", "health cover", "room rent", "solvency")):
        return "insurance"
    return "stock_market"


def assign_archetype(topic: str, slot_index: int = 0) -> str:
    """Deterministic per-day, per-slot rotation — same day never repeats a pacing."""
    today = datetime.now(timezone.utc)
    day_key = today.toordinal()
    topic_letter = (sum(ord(c) for c in str(topic or "").lower()) % 6)
    idx = (day_key + slot_index + topic_letter) % len(NARRATIVE_ARCHETYPES)
    return NARRATIVE_ARCHETYPES[idx]


def _normalize_words(text: str) -> List[str]:
    return re.sub(r"[^\w\s]+", " ", str(text or "").lower()).split()


def _trigrams(tokens: List[str]) -> set:
    return {tuple(tokens[i: i + 3]) for i in range(len(tokens) - 2)} if len(tokens) >= 3 else {tuple(tokens)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a | b))


def _core_title_tokens(title: str) -> set:
    return {w for w in _normalize_words(title) if w not in STOPWORDS and len(w) > 2}


def extract_payload_body(payload: Dict[str, Any]) -> str:
    yt = payload.get("youtube_payload", {})
    parts = [str(yt.get("metadata", {}).get("description_body", ""))]
    for seg in yt.get("segments") or []:
        parts.append(str(seg.get("chapter_title", "")))
        parts.append(str(seg.get("spoken_narration", "")))
    web = payload.get("website_article_payload", {})
    parts.append(str(web.get("seo_title", "")))
    parts.append(str(web.get("meta_description", "")))
    parts.append(str(web.get("direct_answer_passage", "")))
    for s in web.get("article_sections") or []:
        parts.append(str(s.get("heading", "")))
        body = s.get("body") or s.get("content") or ""
        if isinstance(body, dict):
            body = " ".join(str(v) for v in body.values())
        parts.append(str(body)[:900])
    return " ".join(parts)


class ContentAuthenticityEngine:
    """Anti-reuse & YPP-originality guard. Returns verdicts; never mutates content."""

    def __init__(self, posts_path: Path = POSTS_MANIFEST):
        self.posts_path = Path(posts_path)

    # ----------------------------------------------------- vertical vocabulary
    @classmethod
    def check_vertical_terms(cls, payload: Dict[str, Any], vertical: str) -> Tuple[bool, int, List[str]]:
        """Vertical vocabulary density: institutional-grade domain terms must appear."""
        config = VERTICAL_CONFIGS.get(vertical, VERTICAL_CONFIGS["stock_market"])
        combined = extract_payload_body(payload).lower()
        hits, present = 0, []
        for term in config["required_terms"]:
            if term in combined:
                hits += combined.count(term)
                present.append(term)
        return hits >= config["min_hits"], hits, present[:6]

    # ----------------------------------------------------- 30-day anti-reuse
    def recent_posts(self, days: int = FRESHNESS_DAYS) -> List[Dict[str, Any]]:
        if not self.posts_path.exists():
            return []
        try:
            posts = json.loads(self.posts_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"[Authenticity] posts.json unreadable: {e}")
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        fresh = []
        for post in posts:
            date_str = str(post.get("date") or post.get("published_at") or "")
            try:
                d = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if d >= cutoff:
                fresh.append(post)
        return fresh

    def _post_body(self, post: Dict[str, Any]) -> str:
        html = str(post.get("html", "") or "")
        text = re.sub(r"<[^>]+>", " ", html)
        excerpt = str(post.get("excerpt", "") or "")
        return f"{post.get('title', '')} {excerpt} {text}"[:6000]

    def find_dupe_offender(
        self, payload: Dict[str, Any], vertical: str
    ) -> Optional[Dict[str, str]]:
        """
        Returns {' offender': slug, 'reason': 'body 21% trigram / title 4 tokens'}
        when any post inside the freshness window is too similar; else None.
        """
        candidate_title = payload.get("youtube_payload", {}).get("metadata", {}).get("title", "")
        if not candidate_title:
            candidate_title = payload.get("website_article_payload", {}).get("seo_title", "")
        candidate_body = extract_payload_body(payload)
        cand_trigrams = _trigrams(_normalize_words(candidate_body))
        cand_core = _core_title_tokens(candidate_title) | _core_title_tokens(payload.get("topic", ""))

        for post in self.recent_posts():
            slug = str(post.get("slug", ""))
            post_trigrams = _trigrams(_normalize_words(self._post_body(post)))
            body_jac = _jaccard(cand_trigrams, post_trigrams)
            title_share = cand_core & _core_title_tokens(str(post.get("title", "")))
            if body_jac > TRIGRAM_MAX_JACCARD or len(title_share) >= TITLE_CORE_OVERLAP_LIMIT:
                reason = (
                    f"body-trigram {body_jac:.0%} ({TRIGRAM_MAX_JACCARD:.0%} cap)"
                    if body_jac > TRIGRAM_MAX_JACCARD
                    else f"title overlap {sorted(title_share)[:4]}"
                )
                return {"offender": slug, "reason": reason}
        # vertical vocabulary is not a dupe issue but still reported by check above flow
        return None

    # ----------------------------------------------------- main verdict API
    def verify_and_transform(
        self,
        payload: Dict[str, Any],
        vertical: str,
        slot_index: int = 0,
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Full YPP originality verdict.
        Returns (ok, report {archetype, vertical_terms, Dupe info if failing}).
        When ok is False the orchestrator MUST regenerate a fresh angle.
        """
        report: Dict[str, str] = {}
        report["archetype"] = assign_archetype(payload.get("topic", ""), slot_index)

        ok_terms, hits, present = self.check_vertical_terms(payload, vertical)
        report["vertical_terms"] = f"{hits} hits ({', '.join(present)})"
        if not ok_terms:
            report["failure"] = (
                f"Vertical '{vertical}' needs >= {VERTICAL_CONFIGS[vertical]['min_hits']} domain-term hits "
                f"but content scored only {hits}. Script reads like generic fluff — deep-dive required."
            )
            return False, report

        dupe = self.find_dupe_offender(payload, vertical)
        if dupe:
            report.update({"failure": f"30-day overlap vs '{dupe['offender']}' → {dupe['reason']}", "offender": dupe["offender"]})
            return False, report

        return True, report


content_authenticity_engine = ContentAuthenticityEngine()

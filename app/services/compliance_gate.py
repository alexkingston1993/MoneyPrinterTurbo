"""
🛡️ AUTOMATED COMPLIANCE & QUALITY GATE — The Bull Print
Sits between Gemini payload generation and the video/article rendering steps.
Acts as a ruthless SEBI Regulatory Officer + YouTube Monetization Auditor:

 1. Deterministic regex shield  → intercepts accidental "Buy Nifty 24500 CE",
    target prices, stop-losses and tip-expressing language BEFORE anything
    reaches YouTube or the website.
 2. 30-day anti-repetition      → cross-references content/posts.json; too-similar
    recent topics are rejected and force a fresh macro angle.
 3. LLM auditor + self-correct  → a strict Gemini pass judges the payload; on
    rejection the gate feeds the violation reason back to Gemini (higher
    temperature) and forces a brand-new, clean educational draft.

If the payload still fails after max_retries → ComplianceGateError aborts the
run (workflow fails) rather than letting non-compliant content publish.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
POSTS_MANIFEST = BASE_DIR / "content" / "posts.json"
SCHEMA_PATH = BASE_DIR / "master_schema.json"
SYSTEM_PROMPT_PATH = BASE_DIR / "master_system_prompt.txt"

# Live Gemini model alias ('gemini-flash-latest' always resolves to the currently served GA Flash model).
_raw_model = os.getenv("GEMINI_MODEL_NAME", "gemini-flash-latest")
LIVE_GEMINI_MODEL = "gemini-flash-latest" if (not _raw_model or "gemini-2.5-flash" in _raw_model or "gemini-pro" in _raw_model) else _raw_model

# Deterministic Regex Patterns for Illegal Financial Advisory Triggers
_BANNED_RAW = [
    r"\bbuy\s+(?:now|at|ce|pe|calls|puts|shares|stocks)\b",
    r"\bsell\s+(?:now|at|ce|pe|calls|puts|shares|stocks)\b",
    r"\bshort\s+(?:now|at|this)\b",
    r"\benter\s+(?:now|at)\b",
    r"\bexit\s+(?:now|at)\b",
    r"\btarget\s+(?:price|of|at)?\s*₹?\d+",
    r"\bstop\s*loss\s*(?:at)?\s*₹?\d+",
    r"\b\d+\s*(?:CE|PE)\b",  # e.g., "24500 CE" or "50000 PE"
    r"\bguaranteed\s+returns?\b",
    r"\b100\s*%\s+profit\b",
    r"\bpositional\s+call\b",
    r"\bintraday\s+(?:tip|call|trade)\b",
    r"\bsure\s*[- ]?shot\b",
    r"\boption\s+buying\s+(?:call|tip)\b",
    # IRDAI insurance solicitation bans (educational policy-wording forensics stay allowed)
    r"\bbuy\s+(?:this|the|a|that)\s+(?:policy|plan|cover)\b",
    r"\bpurchase\s+(?:this|the|a|that)\s+(?:policy|plan)\b",
    r"\bbest\s+(?:policy|plan)\s+(?:to\s+buy|buy\s+now|now)\b",
    r"\bown\s+(?:this|the)\s+(?:policy|plan)\b",
    r"\bapply\s+(?:now|today)\b",
    r"\bcover\s+yourself\s+(?:now|today|with\s+this)\b",
    r"\bclick\s+here\s+to\s+(?:buy|purchase)\b",
    r"\b₹\s?\d+\s+(?:policy|premium)\s+only\b",
    r"\bsave\s+tax\s+with\s+(?:this|our)\b",
    r"\bsold?\s+(?:in|within)\s+\d+\s*(?:minutes|hours)\b",
]
BANNED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _BANNED_RAW]


class ComplianceGateError(Exception):
    """Raised when a payload violates SEBI regulations or YouTube policies."""


class ComplianceGate:
    """Zero-tolerance SEBI + YouTube compliance audit with automated regeneration."""

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(re.sub(r"[^\w\s]+", " ", str(text or "").lower()).split())

    @classmethod
    def _check_deterministic_triggers(cls, text: str) -> List[str]:
        """Scans raw serialized payload for explicit banned regulatory triggers."""
        violations = []
        for pattern in BANNED_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                violations.append(f"banned pattern '{pattern.pattern}' → {matches[:3]}")
        return violations

    @classmethod
    def _check_30_day_freshness(cls, topic: str, title: Optional[str] = None) -> bool:
        """True when topic/title overlaps NO post published within the last 30 days."""
        if not POSTS_MANIFEST.exists():
            return True

        probe = cls._normalize(topic)[:60]
        alt_probe = cls._normalize(title)[:60] if title else ""
        try:
            posts = json.loads(POSTS_MANIFEST.read_text(encoding="utf-8"))
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            for post in posts:
                date_str = post.get("date") or post.get("published_at") or ""
                try:
                    pub_date = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                    if pub_date <= cutoff:
                        continue
                except Exception:
                    continue
                existing = post.get("title", "")
                norm_existing = cls._normalize(existing)
                # structural overlap: ≥3 shared words OR shared 60-char prefix
                shared = len(set(cls._normalize(topic).split()) & set(norm_existing.split()))
                if shared >= 3 or (alt_probe and norm_existing[:60] == alt_probe) or norm_existing[:60] == probe:
                    logger.warning(
                        f"[Compliance Gate] freshness overlap: '{existing[:60]}' ({shared} shared words)"
                    )
                    return False
        except Exception as e:
            logger.warning(f"[Compliance Gate] posts manifest check skipped: {e}")
        return True

    @classmethod
    def _gemini_client(cls):
        """Lazy google-genai client; never import at module scope (dry-run environments)."""
        import os

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            try:
                from app.config import config as app_config  # local config.toml fallback

                api_key = app_config.app.get("gemini_api_key")
            except Exception:
                api_key = None
        if not api_key:
            return None
        try:
            from google import genai

            return genai.Client(api_key=api_key)
        except Exception as e:
            logger.warning(f"[Compliance Gate] genai client unavailable: {e}")
            return None

    @classmethod
    def _llm_audit(cls, payload: Dict, client) -> Dict[str, Any]:
        """LLM auditor verdict: strict SEBI + YouTube policy JSON review, plus
        graceful deterministic-only degradation if the model is unreachable."""
        if client is None:
            return {"pass": True, "violation_reason": "auditor offline — deterministic checks only"}

        audit_prompt = f"""
        You are a strict SEBI Regulatory Officer and YouTube Monetization Auditor.
        Evaluate this financial media payload for strict educational compliance.

        CRITERIA FOR IMMEDIATE FAILURE:
        1. Contains any specific directional buy/sell recommendation, target price,
           stop-loss, or option strike (e.g., CE/PE).
        2. Sounds like an unlicensed investment advisor giving tips rather than an
           educator explaining market mechanics.
        3. Violates YouTube's Reused Content or Misleading Metadata policies.

        Payload to Audit:
        {json.dumps(payload, indent=2)}

        Respond ONLY with a JSON object:
        {{"pass": true, "violation_reason": ""}}
        or
        {{"pass": false, "violation_reason": "explain the violation here"}}
        """
        try:
            from google.genai import types

            res = client.models.generate_content(
                model=LIVE_GEMINI_MODEL,
                contents=audit_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
            )
            return json.loads(res.text)
        except Exception as e:
            logger.warning(f"[Compliance Gate] Auditor API error: {e} — deterministic verdict stands")
            return {"pass": True, "violation_reason": f"auditor offline ({e.__class__.__name__})"}

    @classmethod
    def _regenerate_fresh_payload(cls, client, reason: str, fallback_payload: Optional[Dict] = None) -> Dict:
        """Forces Gemini to produce a completely fresh, compliant master payload with failover protection."""
        if not client:
            return fallback_payload or {}
        try:
            from google.genai import types

            system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8") if SYSTEM_PROMPT_PATH.exists() else "Financial Educator"
            schema_dict = json.loads(SCHEMA_PATH.read_text(encoding="utf-8")) if SCHEMA_PATH.exists() else {}

            correction_prompt = f"""
            PREVIOUS GENERATION REJECTED BY COMPLIANCE GATE.

            Rejection Reason: {reason}

            INSTRUCTIONS FOR REGENERATION:
            - Shift to a completely fresh macro topic or order-flow angle unrelated to the rejected terms.
            - Strictly enforce educational-only market structure analysis.
            - Zero buy/sell calls, zero strike prices, zero target numbers, zero advisory language.
            - Keep the SEBI educational disclaimer structure intact.
            """
            res = client.models.generate_content(
                model=LIVE_GEMINI_MODEL,
                contents=correction_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=schema_dict,
                    temperature=0.9,  # frontier temperature for genuinely fresh ideas
                    max_output_tokens=8192,
                ),
            )
            return json.loads(res.text)
        except Exception as e:
            logger.warning(f"[Compliance Gate] Fresh payload regeneration failed ({e}) — falling back to current payload")
            return fallback_payload or {}

    @classmethod
    def audit_and_enforce(cls, payload: Dict, max_retries: int = 3) -> Dict:
        """
        Full gate: deterministic regex → 30-day freshness → LLM auditor.
        Any failure regenerates the payload with a fresh angle (up to max_retries).
        Raises ComplianceGateError when the channel-safety bar still is not met.
        """
        client = cls._gemini_client()
        current_payload = payload

        for attempt in range(1, max_retries + 1):
            logger.info(f"🛡️ [Compliance Gate] Running audit (Attempt {attempt}/{max_retries})...")

            # 1. Deterministic regex shield
            try:
                serialized = json.dumps(current_payload)
            except Exception as e:
                raise ComplianceGateError(f"Payload is not JSON-serializable: {e}")

            regex_violations = cls._check_deterministic_triggers(serialized)
            if regex_violations:
                reason = f"Deterministic rejection: {regex_violations}"
                logger.error(f"❌ [Compliance Gate] {reason}")
                fresh = cls._regenerate_fresh_payload(
                    client,
                    reason + " — Eliminate ALL specific trade calls, strike prices, or action verbs.",
                    fallback_payload=current_payload
                )
                if fresh:
                    current_payload = fresh
                continue

            # 2. 30-day freshness (topic + title)
            topic = str(current_payload.get("topic", "") or "")
            title = str(
                current_payload.get("youtube_payload", {}).get("metadata", {}).get("title", "") or ""
            )
            if not cls._check_30_day_freshness(topic, title=title):
                reason = f"Topic '{topic[:60]}' overlaps content published in the last 30 days."
                logger.warning(f"⚠️ [Compliance Gate] {reason} Forcing a fresh angle.")
                fresh = cls._regenerate_fresh_payload(
                    client,
                    reason + " Generate a completely fresh market-structure angle or asset class.",
                    fallback_payload=current_payload
                )
                if fresh:
                    current_payload = fresh
                continue

            # 3. LLM auditor (SEBI + YouTube)
            verdict = cls._llm_audit(current_payload, client)
            if verdict.get("pass", False):
                logger.success("✅ [Compliance Gate] Audit PASSED. Payload approved for production rendering.")
                return current_payload

            reason = verdict.get("violation_reason", "LLM auditor flagged compliance risk.")
            logger.error(f"❌ [Compliance Gate] LLM Auditor rejection: {reason}")
            if attempt < max_retries:
                current_payload = cls._regenerate_fresh_payload(
                    client,
                    f"LLM Audit Failed: {reason} — Rewrite with strict educational focus, "
                    "zero recommendations, and a fresh macro angle.",
                )

        raise ComplianceGateError(
            "❌ [Compliance Gate] CRITICAL: Payload failed compliance audit after "
            f"{max_retries} attempts. Aborting run to protect the channel."
        )

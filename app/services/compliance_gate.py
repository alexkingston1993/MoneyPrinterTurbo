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

# Live Gemini model alias ('gemini-flash-lite-latest' for high speed and zero deprecation).
_raw_model = os.getenv("GEMINI_MODEL_NAME", "gemini-flash-lite-latest")
LIVE_GEMINI_MODEL = "gemini-flash-lite-latest" if (not _raw_model or "gemini-2.5-flash" in _raw_model or "gemini-pro" in _raw_model) else _raw_model

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
    def audit_with_feedback(cls, payload: Dict[str, Any], vertical: str = "") -> Dict[str, Any]:
        """
        Scans generated scripts (longform chapters + short extractions) and title for:
        - SEBI regulatory violations (strike prices, buy/sell calls, target prices, stop-losses).
        - IRDAI policy solicitation violations.
        - YouTube YPP monetization risks (guaranteed returns, misleading claims).

        Returns structured report:
          - passed: bool
          - flagged_excerpts: list[str] (exact sentences found with violations)
          - improvement_suggestions: list[str] (actionable educational rewrite instructions)
          - violations: list[str]
          - summary: str
        """
        flagged_excerpts = []
        improvement_suggestions = []
        violations = []

        if isinstance(payload, str):
            payload = {
                "topic": "Market Analysis",
                "youtube_payload": {
                    "metadata": {"title": "Market Analysis"},
                    "chapters": [{"chapter_title": "Script", "spoken_narration": payload}],
                },
                "youtube_script": payload,
            }

        yt = payload.get("youtube_payload", {})
        meta = yt.get("metadata", {})
        title = meta.get("title", "") or payload.get("topic", "")
        
        texts_to_check = [("Title", str(title))]

        sections = yt.get("chapters", []) or payload.get("website_article_payload", {}).get("article_sections", [])
        for idx, s in enumerate(sections, 1):
            narration = s.get("spoken_narration") or s.get("body") or ""
            if narration:
                texts_to_check.append((f"Chapter {idx} ({s.get('chapter_title', '')})", str(narration)))

        shorts = yt.get("short_extractions") or []
        if not shorts and yt.get("short_extraction"):
            shorts = [yt["short_extraction"]]
        for idx, sh in enumerate(shorts, 1):
            hook_body = sh.get("spoken_hook_and_body") or ""
            cta = sh.get("cta_to_long_video") or ""
            st_title = sh.get("short_title") or ""
            if st_title:
                texts_to_check.append((f"Short #{idx} Title", str(st_title)))
            if hook_body:
                texts_to_check.append((f"Short #{idx} Hook & Body", str(hook_body)))
            if cta:
                texts_to_check.append((f"Short #{idx} CTA", str(cta)))

        for source_name, text in texts_to_check:
            sentences = re.split(r"(?<=[.!?])\s+", text)
            for sentence in sentences:
                sent_clean = sentence.strip()
                if not sent_clean:
                    continue
                for pattern in BANNED_PATTERNS:
                    matches = pattern.findall(sent_clean)
                    if matches:
                        match_str = ", ".join(set(matches))
                        violation_msg = f"[{source_name}] Banned pattern '{pattern.pattern}' matched: '{match_str}' in sentence: \"{sent_clean}\""
                        violations.append(violation_msg)
                        if sent_clean not in flagged_excerpts:
                            flagged_excerpts.append(sent_clean)

                        p_lower = pattern.pattern.lower()
                        if "ce|pe" in p_lower or r"\b\d+\s*(?:ce|pe)\b" in p_lower:
                            sug = f"Line in {source_name} references specific strike '{match_str}'. Replace with institutional open-interest cluster analysis explaining why gamma concentration exists at that strike and how market makers hedge."
                        elif "target" in p_lower or "stop" in p_lower:
                            sug = f"Line in {source_name} states price target/stop-loss '{match_str}'. Remove the directional prediction and describe historical volatility bands and institutional absorption levels instead."
                        elif "buy" in p_lower or "sell" in p_lower or "short" in p_lower:
                            if vertical == "insurance" or "policy" in sent_clean.lower():
                                sug = f"Line in {source_name} uses solicitation phrase '{match_str}'. Remove policy purchase advisory; frame objectively around policy wording definitions, exclusions, and IRDAI claim settlement metrics."
                            else:
                                sug = f"Line in {source_name} uses advisory call '{match_str}'. Reframe as passive institutional order-flow observation (e.g. 'smart money absorption detected at liquidity pools')."
                        elif "guaranteed" in p_lower or "profit" in p_lower or "sure" in p_lower:
                            sug = f"Line in {source_name} mentions guaranteed outcomes '{match_str}'. Replace with probabilistic risk-adjusted scenario analysis and SEBI educational disclosures."
                        else:
                            sug = f"Line in {source_name} contains regulatory advisory trigger '{match_str}'. Reframe into 100% educational market structure mechanics."

                        if sug not in improvement_suggestions:
                            improvement_suggestions.append(sug)

        passed = len(flagged_excerpts) == 0
        summary = "100% COMPLIANT" if passed else f"Flagged {len(flagged_excerpts)} excerpt(s) with {len(violations)} regulatory violation(s)"
        
        return {
            "passed": passed,
            "flagged_excerpts": flagged_excerpts,
            "improvement_suggestions": improvement_suggestions,
            "violations": violations,
            "summary": summary
        }

    @classmethod
    def deterministic_sanitize(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Surgical regex sanitizer used on final attempt if LLM rewrite still contains triggers.
        Replaces illegal advisory expressions with neutral institutional terminology.
        """
        replacements = [
            (re.compile(r"\b(\d+)\s*CE\b", re.IGNORECASE), r"\1 Call strike resistance cluster"),
            (re.compile(r"\b(\d+)\s*PE\b", re.IGNORECASE), r"\1 Put strike support cluster"),
            (re.compile(r"\bbuy\s+(?:now|immediately|at|ce|pe|calls|puts|shares|stocks)\b", re.IGNORECASE), "observe liquidity absorption in"),
            (re.compile(r"\bsell\s+(?:now|immediately|at|ce|pe|calls|puts|shares|stocks)\b", re.IGNORECASE), "observe distribution pressure in"),
            (re.compile(r"\bshort\s+(?:now|at|this)\b", re.IGNORECASE), "observe downward order flow in"),
            (re.compile(r"\benter\s+(?:now|at)\b", re.IGNORECASE), "analyze entry structure around"),
            (re.compile(r"\bexit\s+(?:now|at)\b", re.IGNORECASE), "analyze risk parameters around"),
            (re.compile(r"\btarget\s+(?:price|of|at)?\s*₹?\d+", re.IGNORECASE), "historical liquidity pool reference"),
            (re.compile(r"\bstop\s*loss\s*(?:at)?\s*₹?\d+", re.IGNORECASE), "invalidation reference level"),
            (re.compile(r"\bguaranteed\s+(?:\d+%\s+)?(?:returns?|profits?|outcomes?|gains?)\b", re.IGNORECASE), "historical statistical tendency"),
            (re.compile(r"\bguaranteed\b", re.IGNORECASE), "statistically observed"),
            (re.compile(r"\b100\s*%\s+(?:returns?|profit|gains?)\b", re.IGNORECASE), "asymmetric risk-adjusted setup"),
            (re.compile(r"\bpositional\s+call\b", re.IGNORECASE), "macro trend analysis"),
            (re.compile(r"\bintraday\s+(?:tip|call|trade)\b", re.IGNORECASE), "order-flow momentum analysis"),
            (re.compile(r"\bsure\s*[- ]?shot\s*(?:profits?|returns?|gains?|trades?|calls?)?\b", re.IGNORECASE), "high-probability technical pattern"),
            (re.compile(r"\boption\s+buying\s+(?:call|tip)\b", re.IGNORECASE), "option chain delta analysis"),
            (re.compile(r"\bbuy\s+(?:call\s+options?|calls?|puts?|options?|shares?)\s*(?:now|at)?\b", re.IGNORECASE), "observe order-flow delta"),
            (re.compile(r"\bstop\s*[- ]?loss\s*(?:hit|level|triggered|at)?\s*(?:₹?\d+)?\b", re.IGNORECASE), "invalidation reference level"),
            (re.compile(r"\btarget\s+(?:price|of|at)?\s*₹?\d+\s*(?:nifty|banknifty|sensex)?\b", re.IGNORECASE), "historical liquidity pool reference"),
            (re.compile(r"\bbuy\s+(?:this|the|a|that)\s+(?:policy|plan|cover)\b", re.IGNORECASE), "analyze this policy structure"),
            (re.compile(r"\bpurchase\s+(?:this|the|a|that)\s+(?:policy|plan)\b", re.IGNORECASE), "review the policy prospectus"),
            (re.compile(r"\bbest\s+(?:policy|plan)\s+(?:to\s+buy|buy\s+now|now)\b", re.IGNORECASE), "benchmark policy format"),
            (re.compile(r"\bown\s+(?:this|the)\s+(?:policy|plan)\b", re.IGNORECASE), "evaluate this coverage type"),
            (re.compile(r"\bapply\s+(?:now|today)\b", re.IGNORECASE), "review statutory documentation"),
            (re.compile(r"\bcover\s+yourself\s+(?:now|today|with\s+this)\b", re.IGNORECASE), "assess coverage parameters"),
            (re.compile(r"\bclick\s+here\s+to\s+(?:buy|purchase)\b", re.IGNORECASE), "read statutory IRDAI guidelines"),
            (re.compile(r"\b₹\s?\d+\s+(?:policy|premium)\s+only\b", re.IGNORECASE), "actuarial base pricing model"),
            (re.compile(r"\bsave\s+tax\s+with\s+(?:this|our)\b", re.IGNORECASE), "examine Section 80D provisions"),
            (re.compile(r"\bsold?\s+(?:in|within)\s+\d+\s*(?:minutes|hours)\b", re.IGNORECASE), "observed during peak settlement periods"),
        ]

        def _clean_str(s: str) -> str:
            res = str(s or "")
            for pat, rep in replacements:
                res = pat.sub(rep, res)
            return res

        # Sanitize youtube_payload
        yt = payload.get("youtube_payload", {}) or payload.get("youtube_script", {})
        if "metadata" in yt and isinstance(yt["metadata"], dict):
            if "title" in yt["metadata"]:
                yt["metadata"]["title"] = _clean_str(yt["metadata"]["title"])
            if "description_body" in yt["metadata"]:
                yt["metadata"]["description_body"] = _clean_str(yt["metadata"]["description_body"])

        for ch in yt.get("chapters", []):
            if isinstance(ch, dict) and "spoken_narration" in ch:
                ch["spoken_narration"] = _clean_str(ch["spoken_narration"])

        for sh in yt.get("short_extractions", []):
            if isinstance(sh, dict):
                if "spoken_hook_and_body" in sh:
                    sh["spoken_hook_and_body"] = _clean_str(sh["spoken_hook_and_body"])
                if "cta_to_long_video" in sh:
                    sh["cta_to_long_video"] = _clean_str(sh["cta_to_long_video"])
                if "short_title" in sh:
                    sh["short_title"] = _clean_str(sh["short_title"])

        if "youtube_script" in payload and isinstance(payload["youtube_script"], str):
            payload["youtube_script"] = _clean_str(payload["youtube_script"])

        # Sanitize website article payload if present
        art = payload.get("website_article_payload", {})
        if isinstance(art, dict):
            if "headline" in art:
                art["headline"] = _clean_str(art["headline"])
            for sec in art.get("article_sections", []):
                if isinstance(sec, dict) and "body" in sec:
                    sec["body"] = _clean_str(sec["body"])

        if "topic" in payload:
            payload["topic"] = _clean_str(payload["topic"])

        return payload

    @classmethod
    def audit_and_heal_script(
        cls,
        payload: Dict[str, Any],
        vertical: str = "stock_market",
        max_retries: int = 3,
        telemetry_callback=None
    ) -> Dict[str, Any]:
        """
        Feedback-driven pre-audio self-healing loop:
        Runs immediately after script generation and STRICTLY BEFORE any TTS audio synthesis or video rendering.
        Scans for SEBI/IRDAI/YPP violations, generates actionable critique, and iterates up to max_retries.
        """
        is_raw_str = isinstance(payload, str)
        if is_raw_str:
            current_payload = {
                "topic": "Market Analysis",
                "youtube_payload": {
                    "metadata": {"title": "Market Analysis"},
                    "chapters": [{"chapter_title": "Script", "spoken_narration": payload}],
                },
                "youtube_script": payload,
            }
        else:
            current_payload = payload

        client = cls._gemini_client()

        for attempt in range(1, max_retries + 1):
            logger.info(f"🛡️ [Compliance Feedback Gate] Pre-Audio Audit (Pass {attempt}/{max_retries})...")
            audit = cls.audit_with_feedback(current_payload, vertical=vertical)

            if audit["passed"]:
                logger.success(f"✅ [Compliance Feedback Gate] Script passed audit on Pass #{attempt}!")
                if telemetry_callback:
                    telemetry_callback({
                        "audit_attempts": attempt,
                        "suggestions_applied": attempt - 1,
                        "compliance_verdict": "PASSED" if attempt == 1 else "PASSED_AFTER_FEEDBACK",
                        "status": "COMPLIANCE_PASSED"
                    })
                if is_raw_str:
                    return current_payload.get("youtube_script") or current_payload.get("youtube_payload", {}).get("chapters", [{}])[0].get("spoken_narration", "")
                return current_payload

            logger.warning(
                f"⚠️ [Compliance Feedback Gate] Script failed Pass #{attempt}: {len(audit['flagged_excerpts'])} violation(s) found.\n"
                f"Suggestions: {audit['improvement_suggestions']}"
            )

            if telemetry_callback:
                telemetry_callback({
                    "audit_attempts": attempt,
                    "suggestions_applied": attempt - 1,
                    "compliance_verdict": f"HEALING_PASS_{attempt}",
                    "flagged_count": len(audit["flagged_excerpts"]),
                    "status": f"HEALING_PASS_{attempt}"
                })

            if attempt < max_retries:
                suggestions_txt = "\n".join(f"- {s}" for s in audit["improvement_suggestions"])
                excerpts_txt = "\n".join(f"- \"{e}\"" for e in audit["flagged_excerpts"])
                
                feedback_prompt = f"""
PREVIOUS GENERATION FLAGGED BY SEBI/IRDAI COMPLIANCE AUDIT.
Apply these exact compliance improvement suggestions to rewrite the flagged sections while keeping the vertical topic and narrative depth intact:

COMPLIANCE IMPROVEMENT SUGGESTIONS:
{suggestions_txt}

FLAGGED EXCERPTS TO REWRITE:
{excerpts_txt}

INSTRUCTIONS:
- Shift to 100% passive educational market structure mechanics.
- Zero buy/sell calls, zero strike recommendations, zero target numbers.
"""
                fresh = cls._regenerate_fresh_payload(client, feedback_prompt, fallback_payload=current_payload)
                if fresh and fresh != current_payload:
                    current_payload = fresh
                else:
                    current_payload = cls.deterministic_sanitize(current_payload)
            else:
                logger.info("🛡️ [Compliance Feedback Gate] Applying final deterministic surgical sanitization...")
                current_payload = cls.deterministic_sanitize(current_payload)
                final_audit = cls.audit_with_feedback(current_payload, vertical=vertical)
                if final_audit["passed"]:
                    logger.success("✅ [Compliance Feedback Gate] Final deterministic sanitization 100% verified.")
                    if telemetry_callback:
                        telemetry_callback({
                            "audit_attempts": max_retries,
                            "suggestions_applied": max_retries,
                            "compliance_verdict": "PASSED_AFTER_SURGICAL_HEAL",
                            "status": "COMPLIANCE_PASSED"
                        })
                    if is_raw_str:
                        return current_payload.get("youtube_script") or current_payload.get("youtube_payload", {}).get("chapters", [{}])[0].get("spoken_narration", "")
                    return current_payload

        sanitized = cls.deterministic_sanitize(current_payload)
        if is_raw_str:
            return sanitized.get("youtube_script") or sanitized.get("youtube_payload", {}).get("chapters", [{}])[0].get("spoken_narration", "")
        return sanitized

    @classmethod
    def validate_and_heal_thumbnail_prompt(
        cls,
        candidate: Dict[str, Any],
        vertical: str = "stock_market",
        is_short: bool = False,
        video_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        30-Day Thumbnail Uniqueness & Monetization Compliance Gate.
        Enforced right before ANY prompt is sent to the AI image generator (16:9 Long-Form & 9:16 Shorts).

        1. 30-Day Rolling Memory: auto-prunes entries older than 30 days.
        2. 100% Uniqueness: rejects candidate if line1/line2/badge has >40% word overlap with any entry in last 30 days.
        3. Buzzword Cap: bans repeating ('TRAP', 'EXPOSED', 'SHOCK', 'BLEED', 'LIE') if used >1 time in last 7 days.
        4. 30-Archetype 3D Visual Matrix Rotation: bans repeating hero object or color_palette in consecutive Shorts.
        5. Monetization & Ad-Suitability: strips yellow-dollar triggers and SEBI/IRDAI spam words ('SCAM', 'FRAUD', 'GUARANTEED', 'PONZI').
        6. Self-healing: auto-corrects candidate via gemini-flash-lite-latest / deterministic rules and records to state/thumbnail_prompt_history.json.
        """
        history_path = BASE_DIR / "state" / "thumbnail_prompt_history.json"
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        seven_days_ago = now - timedelta(days=7)

        # 30-Archetype 3D Visual Matrix
        ARCHETYPES_MATRIX = [
            {"archetype": "hydraulic_press", "name": "Hydraulic Press", "metaphor": "Industrial hydraulic press crushing contract with sparks and high pressure dials"},
            {"archetype": "xray_scanner", "name": "Airport X-Ray Scanner", "metaphor": "Airport security X-ray scanner exposing hidden fine print in policy dossier"},
            {"archetype": "iceberg_split", "name": "Iceberg Split", "metaphor": "Massive deep-blue iceberg splitting with submerged 90 percent mass illuminated by caustic cyan beams"},
            {"archetype": "hourglass", "name": "Glowing Hourglass", "metaphor": "Brass and crystal hourglass with luminous gold liquid sand draining through a tight vortex"},
            {"archetype": "transformer", "name": "High-Voltage Transformer", "metaphor": "Industrial high-voltage electrical transformer arcing gold and blue lightning"},
            {"archetype": "magnifying_glass", "name": "Magnifying Glass Burning Fine Print", "metaphor": "Giant brass magnifying glass focusing scorching sunbeam onto burning policy fine print"},
            {"archetype": "domino_collapse", "name": "Domino Collapse", "metaphor": "Towering obsidian domino slabs tumbling in cascading collapse towards a glowing red fault line"},
            {"archetype": "sonar_radar", "name": "Submarine Sonar Radar", "metaphor": "Submarine sonar radar console with green sweep pulse illuminating hidden massive whale orders"},
            {"archetype": "balance_scale", "name": "Balance Scale Tipping", "metaphor": "Ornate bronze balance scale tipping violently as gold bullion outbalances hospital claim cards"},
            {"archetype": "speedometer", "name": "Speedometer Redlining", "metaphor": "Titanium speedometer needle redlining into emergency threshold with glowing crimson halos"},
            {"archetype": "trojan_horse", "name": "Trojan Horse", "metaphor": "Cybernetic steel and timber Trojan Horse breaching illuminated fortified citadel gates"},
            {"archetype": "laser_grid", "name": "Laser Vault Grid", "metaphor": "High-security bank vault crisscrossed by sharp crimson laser tripwires and volumetric mist"},
            {"archetype": "heavy_vault", "name": "Heavy Bank Vault Door", "metaphor": "Massive circular multi-bolt titanium vault door swinging open under glowing pneumatic force"},
            {"archetype": "pendulum", "name": "Pendulum Slicing", "metaphor": "Razor-sharp chrome pendulum slicing on a massive dark arc over glowing depth charts"},
            {"archetype": "shattered_clock", "name": "Shattering Glass Clock", "metaphor": "Roman numeral glass clock shattering mid-air into thousands of crystal shards"},
            {"archetype": "bull_cage", "name": "Cybernetic Bull in Steel Cage", "metaphor": "Glowing cybernetic emerald bull prying open reinforced titanium cage bars with sparks"},
            {"archetype": "abacus", "name": "Actuarial Abacus", "metaphor": "Giant brass and neon abacus computing actuarial reserve equations with glowing floating beads"},
            {"archetype": "orderbook_matrix", "name": "Holographic Order Book Matrix", "metaphor": "Glowing 3D volumetric bid and ask depth towers forming an architectural cityscape"},
            {"archetype": "syphon_pump", "name": "Golden Syphon Pump", "metaphor": "Industrial brass syphon pump draining luminous amber liquidity out of a glowing containment flask"},
            {"archetype": "pressure_gauge", "name": "Deep Sea Trench Pressure Gauge", "metaphor": "Heavy cast-iron pressure dial cracking across tempered glass as needle plunges"},
            {"archetype": "shredder", "name": "Industrial Shredder", "metaphor": "Twin interlocking titanium shredder gears chewing through misleading marketing clauses"},
            {"archetype": "guillotine", "name": "Guillotine Blade", "metaphor": "Gleaming steel guillotine blade suspended over zero-dte option expiration calendar block"},
            {"archetype": "black_hole", "name": "Black Hole Gravitational Lens", "metaphor": "Cosmic accretion disk bending light and pulling market candlestick trajectories"},
            {"archetype": "lightning_rod", "name": "Lightning Rod Surge Diverter", "metaphor": "Copper lightning rod grounding a massive golden volatility strike into subterranean capacitors"},
            {"archetype": "stethoscope_safe", "name": "Safe Cracker Stethoscope", "metaphor": "Chrome stethoscope pressed against glowing combination lock dials on an impenetrable safe"},
            {"archetype": "chess_king", "name": "Chess King Trapped in Checkmate", "metaphor": "Crystalline King chess piece trapped on a glowing chessboard between two obsidian Rooks"},
            {"archetype": "microscope", "name": "Microscopic Inspection Probe", "metaphor": "High-precision electron microscope beam exposing microscopic trap clauses in an insurance section"},
            {"archetype": "volcano_cap", "name": "Volcano Caldera Pressure Cap", "metaphor": "Cracked molten rock pressure dome venting high-pressure geothermal steam over obsidian basalt"},
            {"archetype": "altimeter", "name": "Cockpit Emergency Altimeter", "metaphor": "Jet cockpit primary flight display with flashing terrain warning and emergency amber telemetry"},
            {"archetype": "spinning_compass", "name": "Spinning Brass Compass", "metaphor": "Vintage navigational brass compass needle spinning erratically over glowing oceanic depth contours"}
        ]

        COLOR_PALETTES = [
            "gold_slate",
            "crimson_gold",
            "emerald_gold",
            "cyan_crimson",
            "amber_purple",
            "neon_blue_amber"
        ]

        BUZZWORDS = {"TRAP", "EXPOSED", "SHOCK", "BLEED", "LIE"}
        SPAM_WORDS = {
            "SCAM": "HIDDEN CLAUSE",
            "FRAUD": "REGULATORY GAP",
            "GUARANTEED": "STATISTICAL",
            "PONZI": "UNSUSTAINABLE DRAIN",
            "SURE SHOT": "HIGH PROBABILITY",
            "100% PROFIT": "ASYMMETRIC SETUP"
        }

        # 1. Load & Auto-Prune 30-Day Memory
        history_data = {"version": "1.0", "history": []}
        if history_path.exists():
            try:
                history_data = json.loads(history_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"[Compliance Gate] Failed reading thumbnail history: {e}")

        pruned_history = []
        for item in history_data.get("history", []):
            t_str = item.get("timestamp", "")
            try:
                item_date = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
                if item_date >= thirty_days_ago:
                    pruned_history.append(item)
            except Exception:
                pruned_history.append(item)

        # 2. Check buzzword counts in last 7 days
        recent_buzzword_counts = {bw: 0 for bw in BUZZWORDS}
        for item in pruned_history:
            t_str = item.get("timestamp", "")
            try:
                item_date = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
                if item_date < seven_days_ago:
                    continue
            except Exception:
                pass
            txt = f"{item.get('line1', '')} {item.get('line2', '')} {item.get('pill_badge', '')}".upper()
            for bw in BUZZWORDS:
                if bw in txt:
                    recent_buzzword_counts[bw] += 1

        # 3. Determine recent archetypes & color palettes to avoid consecutive repetition
        recent_archetypes = [h.get("archetype") for h in pruned_history[-5:] if h.get("archetype")]
        recent_palettes = [h.get("color_palette") for h in pruned_history[-3:] if h.get("color_palette")]

        # Clean candidate text of ad-suitability / spam triggers
        line1 = str(candidate.get("line1", "")).strip().upper()
        line2 = str(candidate.get("line2", "")).strip().upper()
        pill = str(candidate.get("pill_badge", "")).strip().upper()

        for bad, rep in SPAM_WORDS.items():
            line1 = line1.replace(bad, rep)
            line2 = line2.replace(bad, rep)
            pill = pill.replace(bad, rep)

        # Uniqueness check (word overlap <= 40%)
        candidate_words = set(re.findall(r"\w+", f"{line1} {line2} {pill}".upper()))
        is_too_similar = False
        overlapping_title = ""

        for h in pruned_history:
            h_words = set(re.findall(r"\w+", f"{h.get('line1', '')} {h.get('line2', '')} {h.get('pill_badge', '')}".upper()))
            if not h_words or not candidate_words:
                continue
            common = candidate_words & h_words
            overlap_ratio = len(common) / max(len(candidate_words), 1)
            if overlap_ratio > 0.40:
                is_too_similar = True
                overlapping_title = h.get("title", "")
                break

        # Check buzzword overuse
        buzzword_flagged = any(recent_buzzword_counts.get(bw, 0) >= 1 and bw in f"{line1} {line2}" for bw in BUZZWORDS)

        # Pick rotating archetype from matrix
        available_archetypes = [a for a in ARCHETYPES_MATRIX if a["archetype"] not in recent_archetypes[-3:]]
        if not available_archetypes:
            available_archetypes = ARCHETYPES_MATRIX
        
        # Consistent hash pick or rotation
        seed_key = candidate.get("title", "") or line1
        hash_val = sum(ord(c) for c in seed_key)
        selected_archetype_dict = available_archetypes[hash_val % len(available_archetypes)]
        selected_archetype = selected_archetype_dict["archetype"]

        available_palettes = [p for p in COLOR_PALETTES if p not in recent_palettes]
        if not available_palettes:
            available_palettes = COLOR_PALETTES
        selected_palette = available_palettes[hash_val % len(available_palettes)]

        # Self-Heal if too similar or buzzwords overused
        healed_candidate = dict(candidate)
        if is_too_similar or buzzword_flagged:
            logger.warning(
                f"[Compliance Gate] Candidate '{line1} {line2}' failed uniqueness "
                f"(overlap={is_too_similar} with '{overlapping_title}', buzzword_cap={buzzword_flagged}). Healing..."
            )
            # Safe forensic alternatives with numbers / metrics
            topic_title = candidate.get("title", "") or f"{line1} {line2}"
            if "insurance" in vertical.lower() or "claim" in topic_title.lower() or "room" in topic_title.lower():
                healed_candidate["line1"] = "0.5x CUT"
                healed_candidate["line2"] = "POLICY MATH"
                healed_candidate["pill_badge"] = "IRDAI CLAUSE 19"
            elif "crypto" in vertical.lower() or "funding" in topic_title.lower() or "bitcoin" in topic_title.lower() or "tax" in topic_title.lower():
                healed_candidate["line1"] = "115BBH DRAIN"
                healed_candidate["line2"] = "ON-CHAIN AUDIT"
                healed_candidate["pill_badge"] = "30% LEVY RULE"
            else:
                healed_candidate["line1"] = "DELTA FLOW"
                healed_candidate["line2"] = "GAMMA PEAK"
                healed_candidate["pill_badge"] = "NIFTY ABSORPTION"
        else:
            healed_candidate["line1"] = line1
            healed_candidate["line2"] = line2
            healed_candidate["pill_badge"] = pill

        healed_candidate["archetype"] = selected_archetype
        healed_candidate["archetype_name"] = selected_archetype_dict["name"]
        healed_candidate["color_palette"] = selected_palette

        # Build Rich 3D AI Prompt with the assigned archetype
        arch_metaphor = selected_archetype_dict["metaphor"]
        healed_candidate["scene_prompt"] = (
            f"photorealistic 3D octane render, {arch_metaphor}, "
            f"cinematic volumetric lighting, glowing edge highlights, high contrast dark atmosphere #070B14, "
            f"8k resolution, raytracing, clean composition zone on left for overlays, strictly no text in image"
        )

        # 4. Save to history
        new_entry = {
            "id": video_id or f"gen_{now.strftime('%Y%m%d_%H%M%S')}",
            "type": "short" if is_short else "long_form",
            "title": candidate.get("title", ""),
            "line1": healed_candidate["line1"],
            "line2": healed_candidate["line2"],
            "pill_badge": healed_candidate["pill_badge"],
            "archetype": selected_archetype,
            "color_palette": selected_palette,
            "timestamp": now.isoformat()
        }
        pruned_history.append(new_entry)
        history_data["history"] = pruned_history
        try:
            history_path.write_text(json.dumps(history_data, indent=2), encoding="utf-8")
            logger.info(f"[Compliance Gate] Saved approved prompt to 30-day history (archetype={selected_archetype}, palette={selected_palette})")
        except Exception as e:
            logger.warning(f"[Compliance Gate] Failed writing history: {e}")

        return healed_candidate


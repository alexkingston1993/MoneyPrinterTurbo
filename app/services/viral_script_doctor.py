#!/usr/bin/env python3
"""
Viral Script Doctor (app/services/viral_script_doctor.py)
Audits and self-heals video scripts for maximum audience retention, dopamine pacing,
and high-CTR curiosity gaps strictly BEFORE audio synthesis or video rendering.

Integrates with ComplianceGate for single-pass unified virality + compliance optimization.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class ViralScriptDoctor:
    """
    Audits hooks, dopamine pacing, curiosity gaps, and retention anchors.
    Ensures scripts trigger algorithmic velocity without crossing into clickbait or compliance violations.
    """

    GENERIC_GREETINGS = [
        "welcome back", "hello everyone", "in this video", "today we will",
        "hey guys", "welcome to", "let's dive in", "let's get started",
        "today i am going to", "in today's video"
    ]

    PATTERN_INTERRUPT_MARKERS = [
        "here is the catch", "but look at this", "the reality is", "what they won't tell you",
        "here is where retail gets trapped", "notice this divergence", "institutions do the exact opposite",
        "the math proves", "this changes everything", "look closely at", "the numbers reveal"
    ]

    @classmethod
    def audit_retention_and_pacing(
        cls,
        payload: Dict[str, Any],
        vertical: str = "stock_market",
        viral_memory: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Runs comprehensive virality & retention audit on long script and companion shorts.
        Returns:
            passed: bool
            virality_score: int (0..100)
            flagged_issues: list[str]
            viral_suggestions: list[str]
        """
        flagged: List[str] = []
        suggestions: List[str] = []
        score = 100

        # Load viral memory directives if not passed
        if not viral_memory:
            from app.services.viral_growth_agent import ViralGrowthAgent
            viral_memory = ViralGrowthAgent.load_memory()
        
        directives = viral_memory.get("next_run_directives", {})
        mandatory_terms = directives.get("mandatory_vocabulary", ["order flow", "gamma cluster", "sub-limit"])

        # 1. Title Audit (45–75 chars, high-stakes curiosity gap)
        title = payload.get("title") or payload.get("topic") or ""
        if len(title) < 40:
            score -= 10
            flagged.append(f"Title too short ({len(title)} chars): '{title}'")
            suggestions.append("Expand title to 45–68 characters with a high-stakes institutional or financial conflict.")
        elif len(title) > 85:
            score -= 5
            flagged.append(f"Title exceeds 85 chars ({len(title)} chars): '{title}'")
            suggestions.append("Tighten title to under 75 characters so it doesn't truncate on mobile feeds.")

        # 2. 3-Second Hook Shock (First 35 words)
        script_body = ""
        yt_script = payload.get("youtube_script", {})
        if isinstance(yt_script, dict):
            chapters = yt_script.get("chapters", [])
            if chapters and isinstance(chapters, list):
                script_body = chapters[0].get("spoken_narration", "")
        if not script_body and "script_body" in payload:
            script_body = str(payload["script_body"])

        words = script_body.split()
        first_35 = " ".join(words[:35]).lower()

        # Check for generic greeting violations
        for greet in cls.GENERIC_GREETINGS:
            if greet in first_35:
                score -= 15
                flagged.append(f"Hook starts with generic greeting: '{greet}'")
                suggestions.append("Delete opening pleasantries; start immediately with a hard quantitative fact or institutional shock in word 1–7.")
                break

        # Check for hard numbers in first 35 words
        has_number = bool(re.search(r'\b(\d+|₹[\d,]+|%|\$\d+)\b', first_35))
        if not has_number and len(words) > 10:
            score -= 10
            flagged.append("Hook lacks a concrete numerical figure in the first 35 words.")
            suggestions.append("Inject a specific quantified figure (e.g., '₹4,200 Cr', '93%', or '40% cut') into the opening 15 words.")

        # 3. Dopamine Pacing & Pattern Interrupts (every ~60 words)
        total_words = len(words)
        if total_words > 120:
            interrupts_found = sum(1 for m in cls.PATTERN_INTERRUPT_MARKERS if m in script_body.lower())
            expected_interrupts = max(1, total_words // 120)
            if interrupts_found < expected_interrupts:
                score -= 10
                flagged.append(f"Insufficient pattern interrupts ({interrupts_found} found, expected {expected_interrupts}).")
                suggestions.append("Insert high-engagement narrative pivots (e.g., 'Here is where retail gets trapped', 'Institutions do the opposite') every 60–80 words to prevent viewer drop-off.")

        # 4. Companion Shorts Hook Audit
        shorts_list = payload.get("short_extractions", [])
        for idx, s in enumerate(shorts_list[:2], 1):
            hook = s.get("hook") or s.get("title") or ""
            hook_words = hook.split()
            hook_lower = hook.lower()
            if any(g in hook_lower for g in cls.GENERIC_GREETINGS):
                score -= 10
                flagged.append(f"Short #{idx} hook contains generic intro.")
                suggestions.append(f"Rewrite Short #{idx} hook to immediately state an institutional paradox or trap.")
            if not bool(re.search(r'\b(\d+|%|₹|\$)\b', hook)):
                score -= 5
                flagged.append(f"Short #{idx} hook lacks a punchy number.")
                suggestions.append(f"Add a concrete percentage or monetary metric to Short #{idx} hook.")

        # 5. Thumbnail Punchline Length (<= 4 words)
        thumb_payload = payload.get("thumbnail_prompt_payload", {})
        punchline = thumb_payload.get("punchline", "")
        if punchline and len(punchline.split()) > 5:
            score -= 5
            flagged.append(f"Thumbnail text too wordy ({len(punchline.split())} words): '{punchline}'")
            suggestions.append("Compress thumbnail punchline to 3–4 high-contrast words for mobile readability.")

        passed = score >= 75 and len(flagged) <= 1
        return {
            "passed": passed,
            "virality_score": max(0, min(100, score)),
            "flagged_issues": flagged,
            "viral_improvement_suggestions": suggestions,
        }

    @classmethod
    def unified_audit_and_heal(
        cls,
        payload: Dict[str, Any],
        vertical: str = "stock_market",
        max_retries: int = 3,
        telemetry_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Unified single-pass loop:
        Merges ViralScriptDoctor retention audit with ComplianceGate regulatory audit
        so the script generator solves both virality and compliance simultaneously
        strictly BEFORE TTS audio or GPU video rendering starts!
        """
        from app.services.compliance_gate import ComplianceGate, ComplianceGateError
        from app.services.viral_growth_agent import ViralGrowthAgent

        viral_memory = ViralGrowthAgent.load_memory()

        for attempt in range(1, max_retries + 1):
            # 1. Audit Compliance
            comp_res = ComplianceGate.audit_with_feedback(payload, vertical=vertical)
            
            # 2. Audit Virality
            viral_res = cls.audit_retention_and_pacing(payload, vertical=vertical, viral_memory=viral_memory)

            comp_passed = comp_res.get("passed", False)
            viral_passed = viral_res.get("passed", False)

            if comp_passed and viral_passed:
                logger.success(f"✅ [Unified Doctor] Script passed Virality ({viral_res['virality_score']}/100) & Compliance Gate on Pass #{attempt}!")
                if telemetry_callback:
                    telemetry_callback(attempt, max_retries, f"100% Pass: Virality {viral_res['virality_score']}/100 + SEBI/IRDAI Approved")
                return payload

            # Merge suggestions into a cohesive prompt
            combined_suggestions = []
            if not comp_passed:
                combined_suggestions.extend(comp_res.get("improvement_suggestions", []))
            if not viral_passed:
                combined_suggestions.extend(viral_res.get("viral_improvement_suggestions", []))

            msg = f"Pass #{attempt}/{max_retries}: {len(combined_suggestions)} suggestion(s) applied (Virality: {viral_res['virality_score']}/100, Compliance: {'PASS' if comp_passed else 'FLAGGED'})"
            logger.warning(f"⚠️ [Unified Doctor] {msg}")
            if telemetry_callback:
                telemetry_callback(attempt, max_retries, msg)

            if attempt < max_retries:
                # Ask LLM to rewrite script solving both constraints simultaneously
                try:
                    payload = ComplianceGate._regenerate_fresh_payload(
                        payload,
                        improvement_suggestions=combined_suggestions,
                        attempt=attempt
                    )
                except Exception as err:
                    logger.warning(f"[Unified Doctor] LLM rewrite fallback on attempt {attempt}: {err}")
                    payload = ComplianceGate.deterministic_sanitize(payload)
            else:
                # Final attempt fail-safe: surgical deterministic sanitize
                logger.info("[Unified Doctor] Final pass deterministic sanitization engaged.")
                payload = ComplianceGate.deterministic_sanitize(payload)
                # Ensure generic greetings are pruned deterministically from hook
                try:
                    chaps = payload.get("youtube_script", {}).get("chapters", [])
                    if chaps:
                        h = chaps[0].get("spoken_narration", "")
                        for g in cls.GENERIC_GREETINGS:
                            h = re.sub(re.escape(g), "", h, flags=re.IGNORECASE).strip()
                        chaps[0]["spoken_narration"] = h
                except Exception:
                    pass

        return payload


if __name__ == "__main__":
    test_payload = {
        "title": "Nifty Update",
        "topic": "Nifty 50 Option Flow",
        "youtube_script": {
            "chapters": [
                {"spoken_narration": "Welcome back guys! Today we will look at Nifty and buy 24500 CE for target 25000."}
            ]
        },
        "short_extractions": [
            {"hook": "Hey guys welcome to my short on option trading."}
        ]
    }
    healed = ViralScriptDoctor.unified_audit_and_heal(test_payload, vertical="stock_market")
    print("HEALED PAYLOAD CHAPTER 1:")
    print(healed["youtube_script"]["chapters"][0]["spoken_narration"])

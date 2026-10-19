"""
Autonomous QA Critic & Content Optimization Engine.

Gating and evaluation agent positioned:
1. Immediately after video script generation (before TTS and rendering)
2. Immediately before web article publishing (before commit to GitHub/Vercel)

Evaluates 5 critical vectors:
1. Regulatory Compliance & SEBI Safeguards (100% mandatory gating)
2. Algorithmic Virality & Audience Retention (Hook, curiosity gap, pacing, CTA)
3. Search Engine Optimization (SEO - title CTR, keyword targeting, search intent)
4. AI Engine Optimization (GEO / AEO - Perplexity & Google AI Overviews quotability)
5. Platform Ban Protection (YouTube TOS, Community Guidelines, Zero-Spam)

Includes a Closed Feedback Loop:
If overall score < 85 or any compliance violation is detected, generates surgical
feedback and returns the script/article to the LLM generator for iterative refinement.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
from loguru import logger

from app.services.compliance import (
    validate_script,
    auto_sanitize_script,
    check_banned_phrases,
    check_required_disclaimers,
    check_personal_opinion_follow_up,
    check_price_targets,
)
from app.services.llm import _generate_response


@dataclass
class QAEvaluationResult:
    passed: bool
    overall_score: int  # 0 to 100
    compliance_score: int  # 0 to 100 (Must be 100 to pass)
    virality_score: int  # 0 to 100
    seo_score: int  # 0 to 100
    geo_aeo_score: int  # 0 to 100
    ban_risk_score: int  # 0 to 100 (100 = 0% risk of ban)
    violations: List[str] = field(default_factory=list)
    critiques: List[str] = field(default_factory=list)
    actionable_fixes: List[str] = field(default_factory=list)
    iteration_count: int = 1


class QACriticAgent:
    """Autonomous evaluator and quality gate for high-velocity financial media."""

    PASSING_THRESHOLD = 85

    def __init__(self):
        logger.info("[QACritic] Initialized Autonomous QA Critic Agent")

    def _deterministic_evaluation(
        self,
        content_type: str,
        title: str,
        text: str,
    ) -> Dict:
        """
        Instant, deterministic rule-based evaluation.
        Runs with zero API token consumption and zero rate limits.
        """
        full_text = f"{title}\n{text}"
        violations = []
        critiques = []
        actionable_fixes = []

        # 1. Compliance Vector (SEBI)
        is_clean, comp_violations = validate_script(full_text)
        compliance_score = 100
        if not is_clean:
            compliance_score = max(0, 100 - (len(comp_violations) * 35))
            violations.extend(comp_violations)
            for v in comp_violations:
                critiques.append(f"SEBI Compliance Failure: {v}")
                if "Banned phrase" in v:
                    actionable_fixes.append("Rephrase direct command to personal viewpoint ('I would hold...', 'In my view...').")
                elif "Missing required disclaimer" in v:
                    actionable_fixes.append("Append mandatory SEBI educational disclaimer and research reminder.")

        # 2. Virality & Retention Vector
        virality_score = 85
        # Hook check (first 120 chars or first line)
        first_line = text.strip().split("\n")[0] if text.strip() else ""
        has_question_or_intrigue = any(q in first_line for q in ["?", "Why", "How", "Cracks", "Squeeze", "Hidden", "Reveals", "Shock", "Surge", "Dump"])
        if not has_question_or_intrigue:
            virality_score -= 15
            critiques.append("Opening hook lacks an intrigue trigger or tension question.")
            actionable_fixes.append("Start with an irresistible hook question (e.g., 'Why did FIIs dump ₹3,000 Cr in Nifty today?').")

        # Call to Action / Engagement check
        has_debate_cta = any(w in full_text.lower() for w in ["comment", "what do you think", "drop your view", "let me know", "share your thought", "agree or disagree"])
        if not has_debate_cta:
            virality_score -= 10
            critiques.append("Ending lacks a conversational debate CTA to stimulate algorithmic engagement.")
            actionable_fixes.append("Add a question prompting viewer debate in comments.")

        # 3. SEO Vector
        seo_score = 90
        has_primary_keyword = any(k in title.lower() for k in ["nifty", "sensex", "bank nifty", "stock", "market", "fii", "reliance", "tcs", "hdfc"])
        if not has_primary_keyword:
            seo_score -= 25
            critiques.append("Title lacks high-volume primary financial keywords.")
            actionable_fixes.append("Include target keyword ('Nifty 50', 'Sensex', or active stock symbol) in title.")

        # 4. GEO / AEO Vector (Perplexity & Google AI Overviews)
        geo_score = 90
        # Check for factual numeric density (e.g. percentages, rupee levels)
        numeric_count = len(re.findall(r"\b\d+([.,]\d+)?%?|\b₹\s*\d+", full_text))
        if numeric_count < 3:
            geo_score -= 20
            critiques.append("Low factual data density. AI engines require concrete numbers for answer cards.")
            actionable_fixes.append("Add specific index points, percentage changes, or institutional flow numbers.")

        # 5. Ban Risk Vector
        ban_risk_score = 100
        hyperbolic_terms = re.findall(r"\b(100% guaranteed|get rich quick|multibagger alert|secret jackpot)\b", full_text, re.IGNORECASE)
        if hyperbolic_terms:
            ban_risk_score = 40
            critiques.append(f"Hyperbolic clickbait detected: {hyperbolic_terms}. High risk of platform strike.")
            actionable_fixes.append("Remove guaranteed return claims and sensationalist financial clickbait.")

        return {
            "compliance_score": compliance_score,
            "virality_score": max(0, min(100, virality_score)),
            "seo_score": max(0, min(100, seo_score)),
            "geo_aeo_score": max(0, min(100, geo_score)),
            "ban_risk_score": ban_risk_score,
            "violations": violations,
            "critiques": critiques,
            "actionable_fixes": actionable_fixes,
        }

    def _ai_deep_critique(
        self,
        content_type: str,
        title: str,
        text: str,
    ) -> Optional[Dict]:
        """
        Executes advanced AI evaluation with Gemini when quota permits.
        Returns parsed scores and qualitative recommendations.
        """
        prompt = f"""
You are the Chief Quality Officer & Algorithmic Growth Specialist for an institutional financial media platform.
Critique the following {content_type} based on:
1. SEBI Regulatory Compliance: Zero direct imperative investment advice. Personal opinion only.
2. Algorithmic Retention: Is the hook irresistible? Is there a strong curiosity gap?
3. SEO & GEO Optimization: Will it rank on Google and be quoted in Perplexity / Google AI Overviews?
4. Viral Potential: High retention pacing, punchy lines, debate-inducing CTA.

CONTENT TITLE: {title}
CONTENT BODY:
{text[:2500]}

Respond ONLY in strict JSON format:
{{
  "compliance_score": 100,
  "virality_score": 88,
  "seo_score": 90,
  "geo_aeo_score": 85,
  "ban_risk_score": 100,
  "critique": "Short constructive critique",
  "recommended_revision": "Specific revision suggestions"
}}
"""
        try:
            raw = _generate_response(prompt)
            # Strip markdown code blocks
            clean_raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
            clean_raw = re.sub(r"```$", "", clean_raw.strip(), flags=re.MULTILINE)
            match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", clean_raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return data
        except Exception as e:
            logger.debug(f"[QACritic] AI critique skipped/deferred (quota/network): {e}")
        return None

    def evaluate_content(
        self,
        content_type: str,
        title: str,
        text: str,
        meta: Optional[Dict] = None,
    ) -> QAEvaluationResult:
        """
        Evaluates a video script or web article.
        Combines deterministic rules with AI critique.
        """
        logger.info(f"[QACritic] Auditing {content_type}: '{title[:45]}...'")

        # 1. Deterministic baseline evaluation
        det = self._deterministic_evaluation(content_type, title, text)

        # 2. AI Nuance evaluation (if feasible)
        ai_data = self._ai_deep_critique(content_type, title, text)
        if ai_data:
            # Blend deterministic and AI scores (deterministic compliance is always absolute veto)
            det["virality_score"] = int((det["virality_score"] * 0.4) + (ai_data.get("virality_score", 85) * 0.6))
            det["seo_score"] = int((det["seo_score"] * 0.4) + (ai_data.get("seo_score", 85) * 0.6))
            det["geo_aeo_score"] = int((det["geo_aeo_score"] * 0.4) + (ai_data.get("geo_aeo_score", 85) * 0.6))
            if ai_data.get("critique"):
                det["critiques"].append(f"AI Review: {ai_data['critique']}")
            if ai_data.get("recommended_revision"):
                det["actionable_fixes"].append(f"AI Directive: {ai_data['recommended_revision']}")

        # Composite score weighting:
        # Compliance 35%, Virality 25%, SEO 20%, GEO/AEO 20%
        overall = int(
            (det["compliance_score"] * 0.35)
            + (det["virality_score"] * 0.25)
            + (det["seo_score"] * 0.20)
            + (det["geo_aeo_score"] * 0.20)
        )

        # Gating condition: Compliance must be 100, BanRisk 100, and overall >= 85
        passed = (
            det["compliance_score"] >= 100
            and det["ban_risk_score"] >= 100
            and overall >= self.PASSING_THRESHOLD
        )

        logger.info(
            f"[QACritic] Evaluated: Overall={overall}/100, Compliance={det['compliance_score']}, "
            f"Virality={det['virality_score']}, SEO={det['seo_score']}, GEO={det['geo_aeo_score']}, Passed={passed}"
        )

        return QAEvaluationResult(
            passed=passed,
            overall_score=overall,
            compliance_score=det["compliance_score"],
            virality_score=det["virality_score"],
            seo_score=det["seo_score"],
            geo_aeo_score=det["geo_aeo_score"],
            ban_risk_score=det["ban_risk_score"],
            violations=det["violations"],
            critiques=det["critiques"],
            actionable_fixes=det["actionable_fixes"],
        )

    def evaluate_and_refine(
        self,
        content_type: str,
        title: str,
        body: str,
        generator_fn: Optional[Callable[[str, str, List[str]], Tuple[str, str]]] = None,
        max_iterations: int = 3,
    ) -> Tuple[str, str, QAEvaluationResult]:
        """
        Closed-loop audit & refinement.
        If QA fails, auto-sanitizes and, if a generator_fn is supplied,
        re-prompts the generator with surgical feedback up to max_iterations.
        """
        current_title = title
        current_body = body

        for iteration in range(1, max_iterations + 1):
            eval_res = self.evaluate_content(content_type, current_title, current_body)
            eval_res.iteration_count = iteration

            if eval_res.passed:
                logger.info(f"[QACritic] Content PASSED on iteration #{iteration} (Score: {eval_res.overall_score}/100)")
                return current_title, current_body, eval_res

            logger.warning(
                f"[QACritic] Content REJECTED on iteration #{iteration}. "
                f"Issues: {len(eval_res.violations)} violations, {len(eval_res.critiques)} critiques. Triggering refinement..."
            )

            # Auto-sanitize compliance issues directly
            current_body = auto_sanitize_script(current_body)
            current_title = auto_sanitize_script(current_title)

            # If generator function provided, re-invoke with feedback
            if generator_fn and iteration < max_iterations:
                try:
                    logger.info(f"[QACritic] Calling generator for feedback rewrite (Round {iteration + 1})...")
                    feedback_prompt = " | ".join(eval_res.actionable_fixes)
                    new_title, new_body = generator_fn(current_title, current_body, eval_res.actionable_fixes)
                    if new_body:
                        current_title, current_body = new_title, new_body
                except Exception as e:
                    logger.warning(f"[QACritic] Generator re-invocation failed: {e}. Relying on deterministic auto-sanitization.")

        # Final pass validation
        final_eval = self.evaluate_content(content_type, current_title, current_body)
        final_eval.iteration_count = max_iterations
        return current_title, current_body, final_eval


# Global QA Critic Singleton
qa_critic = QACriticAgent()

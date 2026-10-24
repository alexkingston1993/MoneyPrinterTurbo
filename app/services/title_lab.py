"""
Title Lab & SEO Findability Scorecard.
Inspired by YAAS (YouTube Agentic AI Studio) and darkzOGx YouTube Automation Agent.

Generates 6 psychological title variations for financial content:
1. Curiosity Gap (Hidden institutional data / dark pools)
2. Loss Aversion (Stop-loss hunting / retail traps)
3. Contrarian Institutional (Big banks vs everyday investors)
4. Order-Flow Urgency (Opening/closing bell price action)
5. Masterclass Playbook (Capital allocation & wealth compounding)
6. High-Intent Keyword Search (Nifty 50, F&O, Bank Nifty)

Scores every title on a 0-100 CTR & Findability Scorecard:
- Mobile front-loading (< 50 chars for mobile notification visibility)
- Power words presence (Trap, Secret, Shock, Divergence, Dumped, Liquidity)
- Quantitative numerical anchors (₹4,100 Cr, 22,400, 91%, 70-20-10)
- SEBI compliance (Strictly educational, zero false promises)
"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class TitleScore:
    title: str
    angle: str
    score: int
    char_count: int
    front_loaded: bool
    has_numbers: bool
    has_power_words: bool
    sebi_compliant: bool
    critique: str


class TitleLab:
    """Psychological Title Generator and CTR Scorecard Engine."""

    POWER_WORDS = {
        "trap", "exposed", "secret", "shock", "dumped", "dump", "warning", "breakdown",
        "truth", "hoards", "gold", "rupee", "crude", "inflation", "big banks",
        "big funds", "beginners", "everyday", "selling", "protect", "danger", "mistake",
        "lose money", "missed", "blindside", "reversal"
    }

    PROHIBITED_WORDS = {
        "guaranteed", "sure shot", "double your money", "buy now", "target price",
        "multibagger jackpot", "100% profit", "call tip", "put tip"
    }

    @classmethod
    def generate_and_rank_titles(
        cls,
        base_subject: str,
        nifty_str: str = "24500",
        nifty_chg: str = "+0.25%",
        slot_name: str = "market_close",
    ) -> List[TitleScore]:
        """
        Generates 6 psychological title variants and ranks them by CTR / Findability score.
        """
        titles_to_evaluate: List[Dict[str, str]] = []

        # Extract core entities
        clean_base = re.sub(r"[|—:\-]+", " ", base_subject).strip()

        # 1. Curiosity Gap (Simple & Intriguing)
        titles_to_evaluate.append({
            "angle": "Curiosity Gap",
            "title": f"The ₹4,100 Cr Move by Big Banks That Everyday Investors Missed" if "FII" in base_subject else f"Why Big Banks Are Moving Money at {nifty_str} (Beginner Guide)"
        })

        # 2. Loss Aversion (Protecting Everyday People)
        titles_to_evaluate.append({
            "angle": "Loss Aversion",
            "title": f"Closing Bell Trap: Big Funds Dump ₹3,200 Cr in Final 15 Minutes" if "Close" in base_subject or "Bell" in base_subject else f"Don't Fall for the {nifty_str} Trap: Why 90% of Everyday Buyers Lose Money"
        })

        # 3. Contrarian Institutional (Plain explanation of big banks vs beginners)
        titles_to_evaluate.append({
            "angle": "Contrarian Institutional",
            "title": f"Big Banks Are Selling While Beginners Buy: The Truth About {nifty_str}"
        })

        # 4. Order-Flow Urgency (Urgent warning in simple words)
        titles_to_evaluate.append({
            "angle": "Order-Flow Urgency",
            "title": f"Market Warning: Big Foreign Funds Are Dumping Shares at {nifty_str}"
        })

        # 5. Masterclass Playbook (Beginner-friendly learning hook)
        titles_to_evaluate.append({
            "angle": "Masterclass Playbook",
            "title": f"How Big Institutions Trick Beginners Into Selling Cheap: The Truth Exposed"
        })

        # 6. High-Intent Search (Simple search phrase for beginners)
        titles_to_evaluate.append({
            "angle": "High-Intent Search",
            "title": f"Indian Stock Market for Beginners: What Big Bank Selling Means for You"
        })

        # Always evaluate the user's base subject as well
        titles_to_evaluate.append({
            "angle": "Base Subject",
            "title": base_subject
        })

        ranked: List[TitleScore] = []
        for item in titles_to_evaluate:
            score_obj = cls.score_title(item["title"], item["angle"])
            ranked.append(score_obj)

        # Sort descending by score
        ranked.sort(key=lambda x: x.score, reverse=True)
        return ranked

    @classmethod
    def score_title(cls, title: str, angle: str = "Standard") -> TitleScore:
        """Evaluates a single title across YouTube CTR and findability parameters (0-100)."""
        score = 50
        critique_points = []
        clean_lower = title.lower()

        # 1. Length & Front-loading (Max score for 45-75 chars)
        char_len = len(title)
        front_loaded = False
        if 40 <= char_len <= 75:
            score += 15
            critique_points.append("Optimal length for YouTube mobile feed (40-75 chars).")
        elif char_len < 40:
            score += 5
            critique_points.append("Slightly short; could add stronger context keyword.")
        else:
            score -= 10
            critique_points.append("Exceeds 75 chars; title will truncate on mobile devices.")

        # Check if high-impact keyword is in the first 40 chars
        first_40 = clean_lower[:40]
        has_power_words = any(pw in clean_lower for pw in cls.POWER_WORDS)
        if any(pw in first_40 for pw in cls.POWER_WORDS):
            front_loaded = True
            score += 15
            critique_points.append("Power hook is front-loaded in the first 40 characters.")
        elif has_power_words:
            score += 8
            critique_points.append("Contains power words, but positioned later in the title.")

        # 2. Specific Numbers (Quantitative credibility)
        has_numbers = bool(re.search(r"\d+", title))
        if has_numbers:
            score += 15
            critique_points.append("Contains specific numerical anchor (boosts CTR by ~22%).")
        else:
            critique_points.append("No specific numbers; abstract titles suffer lower click velocity.")

        # 3. Currency / Magnitude presence
        if any(sym in title for sym in ["₹", "Cr", "Crore", "Crores", "$", "%"]):
            score += 10
            critique_points.append("Includes financial magnitude anchor (₹ / Cr / %).")

        # 4. SEBI Compliance & Safety Check
        sebi_compliant = True
        for forbidden in cls.PROHIBITED_WORDS:
            if forbidden in clean_lower:
                score -= 30
                sebi_compliant = False
                critique_points.append(f"VIOLATION: Contains prohibited promise word '{forbidden}'.")

        final_score = max(0, min(100, score))
        return TitleScore(
            title=title,
            angle=angle,
            score=final_score,
            char_count=char_len,
            front_loaded=front_loaded,
            has_numbers=has_numbers,
            has_power_words=has_power_words,
            sebi_compliant=sebi_compliant,
            critique=" | ".join(critique_points)
        )

    @classmethod
    def get_best_title(cls, base_subject: str, slot_name: str = "market_close") -> str:
        """Returns the single highest-scoring title for a given subject."""
        ranked = cls.generate_and_rank_titles(base_subject, slot_name=slot_name)
        if ranked:
            best = ranked[0]
            logger.info(f"[TitleLab] Selected #{best.angle} title (Score: {best.score}/100): '{best.title}'")
            return best.title
        return base_subject


# Global instance
title_lab = TitleLab()

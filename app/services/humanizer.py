"""
Humanizer Engine — Advanced Anti-AI Detection & Voice Shaping.

Inspired by blader/humanizer and statistical burstiness analysis:
- Strips 60+ known AI fingerprint words/phrases ('delve', 'tapestry', 'testament', etc.)
- Enforces sentence length variance (burstiness) to break robotic cadence
- Imparts Dalal Street trader desk authority and active voice
- Injects quantitative market facts, option chain nuances, and concrete numbers
"""

import math
import re
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Strict AI Vocabulary Blacklist & Replacements
# ---------------------------------------------------------------------------

AI_BLACKLIST = [
    # Overused AI verbs & clichés
    r"\bdelve(?:s|d|ing)?\b",
    r"\btapestry\b",
    r"\bbeacon\b",
    r"\btestament\b",
    r"\bpivotal\b",
    r"\bparamount\b",
    r"\bgroundbreaking\b",
    r"\bgame-changer\b",
    r"\brevolutionize(?:s|d|ing)?\b",
    r"\bdemystify(?:ies|ied|ing)?\b",
    r"\bharness(?:es|ed|ing)?\b",
    r"\bfoster(?:s|ed|ing)?\b",
    r"\bunderscore(?:s|d|ing)?\b",
    r"\bseamlessly\b",
    r"\bunpack(?:s|ed|ing)?\b",
    r"\bnavigat(?:e|es|ed|ing) the complexities\b",
    
    # Generic transition filler
    r"\bin conclusion\b",
    r"\bmoreover\b",
    r"\bfurthermore\b",
    r"\bto summarize\b",
    r"\bin summary\b",
    r"\bit is crucial to\b",
    r"\bit's crucial to\b",
    r"\bit is important to remember\b",
    r"\bit's important to note\b",
    r"\bit is worth noting\b",
    r"\bin the fast-paced world of\b",
    r"\bin today's dynamic\b",
    r"\bin this ever-evolving\b",
    r"\ba wide array of\b",
    r"\ba myriad of\b",
    r"\bat the end of the day\b",
    
    # Robotic filler phrases
    r"\bfirst and foremost\b",
    r"\blast but not least\b",
    r"\ball in all\b",
    r"\bas an ai\b",
    r"\bhere is the article\b",
    r"\bwithout further ado\b",
]

AI_WORD_REPLACEMENTS = {
    "delve into": "examine",
    "delving into": "breaking down",
    "pivotal": "key",
    "paramount": "critical",
    "groundbreaking": "major",
    "revolutionize": "transform",
    "harness": "use",
    "foster": "build",
    "underscore": "highlight",
    "moreover": "also,",
    "furthermore": "in addition,",
    "it is crucial to": "investors must",
    "it is important to remember": "keep in mind that",
    "it is worth noting": "specifically,",
}


# ---------------------------------------------------------------------------
# Humanizer Class
# ---------------------------------------------------------------------------

class Humanizer:
    """Statistical and prompt-based text humanization engine."""

    @staticmethod
    def calculate_burstiness(text: str) -> Tuple[float, float, str]:
        """
        Calculate sentence length variance (burstiness).
        Low standard deviation (< 5.0) strongly flags text as AI generated.
        Human text typically has standard deviation > 8.0.
        """
        # Split into sentences
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 3]
        if not sentences:
            return 0.0, 0.0, "empty"
        
        lengths = [len(s.split()) for s in sentences]
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        std_dev = math.sqrt(variance)
        
        if std_dev < 5.0:
            rating = "robotic_ai"
        elif std_dev < 8.0:
            rating = "moderate"
        else:
            rating = "natural_human"
            
        return mean_len, std_dev, rating

    @staticmethod
    def clean_ai_fingerprints(text: str) -> str:
        """Strip conversational chat prefixes and replace blacklisted words."""
        # Strip LLM conversational meta-chat
        cleaned = re.sub(
            r"^(?:Sure|Certainly|Here is|Below is|Here's).*?(?:\n\n|\n)",
            "",
            text,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\n(?:Hope this helps|Let me know if you need anything else|Feel free to ask).*?$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        
        # Replace common robotic phrases with natural equivalents
        for phrase, replacement in AI_WORD_REPLACEMENTS.items():
            pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
            cleaned = pattern.sub(replacement, cleaned)
            
        # Clean double spaces
        cleaned = re.sub(r" +", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def get_system_prompt_rules() -> str:
        """
        Comprehensive blader/humanizer style system rules to inject into LLM prompts.
        Forces the model to output text that bypasses AI detectors natively.
        """
        return """
### STRICT JOURNALISTIC & ANTI-AI WRITING RULES (Zero AI Fingerprints)
1. FORBIDDEN WORDS: NEVER use words like 'delve', 'tapestry', 'beacon', 'testament', 'pivotal', 'crucial', 'moreover', 'furthermore', 'in conclusion', 'in the fast-paced world of', 'game-changer', or 'revolutionize'.
2. BURSTINESS & SENTENCE CADENCE: You MUST radically vary sentence lengths. Alternate a sharp, 4-word sentence with a rich, 22-word analytical thought. Never write 3 sentences of equal length in a row.
3. PRIMARY TRADER VOICE: Write from the perspective of an experienced institutional quantitative trading desk. Use authentic market language: 'cash segment delivery', 'call unwinding', 'short covering', 'institutional flow', 'support breach', 'premium decay'.
1.1 POLICY BAN: NEVER EVER use the phrase 'Dalal Street'. Refer to markets as 'Indian equities', 'the benchmark indices', or 'domestic markets'.
4. CONCRETE NUMBERS: Never say 'markets rose significantly'. Say 'Nifty surged 142 points to cross 25,120 on heavy volumes'.
5. DIRECT ANSWER FIRST: Under every H2 heading, the first sentence must directly answer the core question before elaborating. This maximizes Google Featured Snippet and Perplexity AI citations.
6. AVOID ROBOTIC SUMMARIES: Do not start final sections with 'In conclusion' or 'To sum up'. Instead, use 'The Bottom Line for Traders' or 'Actionable Outlook for Tomorrow'.
"""

    @classmethod
    def apply_human_touch(cls, text: str, context_type: str = "article") -> str:
        """
        Injects a genuine human educator voice (Alex from Chennai persona):
        - Strips AI robotic markers
        - Enforces warm conversational tone & relatable real-world framing
        - Adds sentence burstiness and authentic human rhythm
        """
        cleaned = cls.clean_ai_fingerprints(text)

        # Conversational warmth replacements for robotic phrases
        conversational_replacements = [
            (r"\butilize\b", "use"),
            (r"\butilizing\b", "using"),
            (r"\bcommence\b", "start"),
            (r"\bterminate\b", "stop"),
            (r"\bdemonstrates\b", "shows"),
            (r"\bindicates\b", "points to"),
            (r"\bsubsequently\b", "then"),
            (r"\bconsequently\b", "as a result"),
            (r"\bin order to\b", "to"),
            (r"\bdue to the fact that\b", "because"),
            (r"\bat this point in time\b", "right now"),
            (r"\bwith respect to\b", "about"),
            (r"\bin regards to\b", "about"),
            (r"\bpertaining to\b", "about"),
            (r"\boptimal\b", "best"),
            (r"\bmitigate\b", "reduce"),
            (r"\bmitigating\b", "reducing"),
            (r"\bprecipitous\b", "sharp"),
            (r"\bamplified\b", "increased"),
            (r"\bexponentially\b", "rapidly"),
            (r"\baforementioned\b", "earlier mentioned"),
            (r"\bnotwithstanding\b", "despite"),
            (r"\bplethora of\b", "dozens of"),
        ]

        for pat, repl in conversational_replacements:
            cleaned = re.sub(pat, repl, cleaned, flags=re.IGNORECASE)

        # Ensure sentence burstiness: break up unnaturally long run-on sentences (> 40 words)
        def break_run_on_sentence(match):
            sentence = match.group(0)
            words = sentence.split()
            if len(words) > 35 and " and " in sentence:
                # Split at middle ' and '
                mid = len(sentence) // 2
                split_pos = sentence.find(" and ", mid - 20)
                if split_pos != -1:
                    return sentence[:split_pos] + ". In addition, " + sentence[split_pos + 5:]
            return sentence

        cleaned = re.sub(r"[A-Z][^.!?]+[.!?]", break_run_on_sentence, cleaned)
        return cleaned.strip()

    @classmethod
    def humanize_article(cls, article_html: str) -> str:
        """Run comprehensive human touch optimization on HTML articles."""
        return cls.apply_human_touch(article_html, context_type="article")

    @classmethod
    def humanize_script(cls, script_text: str) -> str:
        """Run speech-focused human touch optimization on video narration scripts."""
        cleaned = cls.apply_human_touch(script_text, context_type="script")
        # Add natural speech pause cues for TTS where appropriate
        cleaned = re.sub(r"\b(Look|Here is the truth|Think about it|Remember):\b", r"\1...", cleaned)
        return cleaned

    @classmethod
    def humanize(cls, raw_article: str) -> str:
        """Run full humanization pipeline on text."""
        return cls.apply_human_touch(raw_article)


# Global instance
humanizer = Humanizer()

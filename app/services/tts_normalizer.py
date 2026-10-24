"""
TTS Normalizer Service for The Bull Print & Autonomous Media Engine.

Regulates text scripts for Text-to-Speech (TTS) models (Coqui XTTS-v2, Kokoro, Edge-TTS, Whisper).
Ensures:
1. No raw symbols remain in the text:
   - '$' converted to 'dollars' / 'dollar'
   - '₹' / 'Rs.' converted to 'rupees' / 'rupee'
   - '€' converted to 'euros', '£' converted to 'pounds'
   - '%' converted to 'percent'
   - '&' converted to 'and' (or expanded e.g. F&O -> Futures and Options)
   - '+' / '-' converted to 'plus' / 'minus' when denoting values
2. Punctuation is never converted into spoken text:
   - Colons ':', semicolons ';', em-dashes '—', hyphens '-' are converted into natural prosody pauses (commas/periods)
     so the TTS engine never literally pronounces 'colon', 'dash', 'slash', etc.
   - Parentheses '()', brackets '[]', and quotation marks '\"' are stripped/re-spaced so engines never voice 'open parenthesis' or 'quote'.
3. Comma-separated numbers (e.g. 22,400 or 1,00,000) are cleaned to digits (22400, 100000)
   so the TTS engine does not pause awkwardly or voice the word 'comma'.
4. Common financial acronyms are expanded or phonetically spaced for perfect prosody.
"""

import re
from typing import Optional
from loguru import logger


class TTSNormalizer:
    """Comprehensive Text-To-Speech Normalization and Script Regulator."""

    # Acronym mappings for financial and quantitative speech
    ACRONYMS = {
        r"\bF&O\b": "Futures and Options",
        r"\bP&L\b": "Profit and Loss",
        r"\bFII/DII\b": "FII and DII",
        r"\bATM\b": "at the money",
        r"\bOTM\b": "out of the money",
        r"\bITM\b": "in the money",
        r"\bVWAP\b": "V-WAP",
        r"\bPOC\b": "Point of Control",
        r"\bEMA\b": "E M A",
        r"\bSMA\b": "S M A",
        r"\bATH\b": "All Time High",
        r"\bOI\b": "Open Interest",
        r"\bPCR\b": "P C R",
        r"\bNifty 50\b": "Nifty Fifty",
        r"\bNIFTY 50\b": "Nifty Fifty",
        r"\bBSE\b": "B S E",
        r"\bNSE\b": "N S E",
        r"\bSEBI\b": "SEBI",
        r"\bGift Nifty\b": "Gift Nifty",
        r"\bRBI\b": "R B I",
        r"\bFed\b": "Federal Reserve",
    }

    @classmethod
    def normalize_for_tts(cls, text: str, language: str = "en") -> str:
        """
        Normalizes a script into clean, natural, symbol-free text for TTS engines.
        Guarantees punctuation is used strictly for pacing pauses without verbalized punctuation words.
        """
        if not text or not isinstance(text, str):
            return ""

        s = text

        # ── 1. Clean Markdown, HTML, and URLs ──
        s = re.sub(r"https?://\S+|www\.\S+", "", s)
        s = re.sub(r"<[^>]+>", "", s)
        s = re.sub(r"[*_#`~^]", "", s)

        # ── 2. Standardize Unicode Punctuation & Quotes ──
        s = s.replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", ", ")
        s = s.replace("\u2014", ", ").replace("\u2015", ", ")  # Em-dashes to pauses
        s = s.replace("\u2212", "-")  # Minus sign
        s = s.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
        s = s.replace("\u2018", "'").replace("\u2019", "'")
        s = s.replace("\u201c", '"').replace("\u201d", '"')
        s = s.replace("…", ", ").replace("...", ", ")

        # ── 3. Financial Acronyms & Spoken Expansions ──
        for pattern, replacement in cls.ACRONYMS.items():
            s = re.sub(pattern, replacement, s, flags=re.IGNORECASE)

        # ── 4. Remove Commas from Numbers (e.g. 24,500 -> 24500, 1,00,000 -> 100000) ──
        # Repeat replacement to handle Indian format like 1,00,000
        while re.search(r"(?<=\d),(?=\d)", s):
            s = re.sub(r"(?<=\d),(?=\d)", "", s)

        # ── 5. Time Formatting (e.g. 9:00 AM -> 9 AM, 9:30 AM -> 9:30 AM) ──
        s = re.sub(r"\b(\d{1,2}):00\s*(AM|PM|am|pm)\b", r"\1 \2", s)

        # ── 6. Currency Normalization (₹, $, €, £, ¥, Rs) ──
        # Rupee with Crore / Lakh
        s = re.sub(r"[₹\u20B9]\s*(\d+(?:\.\d+)?)\s*(?:Cr|Crores?|cr|crores?)\b", r"\1 crore rupees", s)
        s = re.sub(r"[₹\u20B9]\s*(\d+(?:\.\d+)?)\s*(?:L|Lakhs?|l|lakhs?)\b", r"\1 lakh rupees", s)
        s = re.sub(r"\b(?:Rs\.?|INR)\s*(\d+(?:\.\d+)?)\s*(?:Cr|Crores?|cr|crores?)\b", r"\1 crore rupees", s)
        s = re.sub(r"\b(?:Rs\.?|INR)\s*(\d+(?:\.\d+)?)\s*(?:L|Lakhs?|l|lakhs?)\b", r"\1 lakh rupees", s)

        # Rupee standalone amounts
        s = re.sub(r"[₹\u20B9]\s*1(?!\d)", "1 rupee", s)
        s = re.sub(r"[₹\u20B9]\s*(\d+(?:\.\d+)?)", r"\1 rupees", s)
        s = re.sub(r"\b(?:Rs\.?|INR)\s*1(?!\d)", "1 rupee", s)
        s = re.sub(r"\b(?:Rs\.?|INR)\s*(\d+(?:\.\d+)?)", r"\1 rupees", s)
        s = re.sub(r"[₹\u20B9]", " rupees ", s)

        # Dollars with Magnitudes (Billion, Million, Thousand)
        s = re.sub(r"\$\s*(\d+(?:\.\d+)?)\s*[Bb](?:illion)?\b", r"\1 billion dollars", s)
        s = re.sub(r"\$\s*(\d+(?:\.\d+)?)\s*[Mm](?:illion)?\b", r"\1 million dollars", s)
        s = re.sub(r"\$\s*(\d+(?:\.\d+)?)\s*[Kk]\b", r"\1 thousand dollars", s)
        s = re.sub(r"\$\s*1(?!\d)", "1 dollar", s)
        s = re.sub(r"\$\s*(\d+(?:\.\d+)?)", r"\1 dollars", s)
        s = re.sub(r"\$", " dollars ", s)

        # Euros
        s = re.sub(r"€\s*1(?!\d)", "1 euro", s)
        s = re.sub(r"€\s*(\d+(?:\.\d+)?)", r"\1 euros", s)
        s = re.sub(r"€", " euros ", s)

        # Pounds
        s = re.sub(r"£\s*1(?!\d)", "1 pound", s)
        s = re.sub(r"£\s*(\d+(?:\.\d+)?)", r"\1 pounds", s)
        s = re.sub(r"£", " pounds ", s)

        # Yen
        s = re.sub(r"¥\s*(\d+(?:\.\d+)?)", r"\1 yen", s)
        s = re.sub(r"¥", " yen ", s)

        # ── 7. Percentages & Math Signs ──
        # Percent symbol
        s = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1 percent", s)
        s = s.replace("%", " percent")

        # Plus sign (e.g. +0.25 percent -> plus 0.25 percent, +50 points -> plus 50 points)
        s = re.sub(r"\+([0-9]+(?:\.[0-9]+)?)", r"plus \1", s)
        s = re.sub(r"\s\+\s", " plus ", s)

        # Minus sign before numbers (e.g. -1.5 percent -> minus 1.5 percent)
        s = re.sub(r"(?<=\s)-([0-9]+(?:\.[0-9]+)?)", r"minus \1", s)
        s = re.sub(r"(?<=^\()-([0-9]+(?:\.[0-9]+)?)", r"minus \1", s)
        s = re.sub(r"(?<=\()-([0-9]+(?:\.[0-9]+)?)", r"minus \1", s)

        # Common symbols
        s = s.replace("&", " and ")
        s = s.replace("@", " at ")
        s = s.replace("=", " equals ")
        s = s.replace(">", " greater than ")
        s = s.replace("<", " less than ")

        # Slashes
        s = re.sub(r"\band/or\b", "and or", s, flags=re.IGNORECASE)
        s = re.sub(r"(\w+)/(\w+)", r"\1 or \2", s)
        s = s.replace("/", " or ")

        # ── 8. Punctuation Regulation (Eliminating Spoken Punctuation) ──
        # Colons ':' in sentences make TTS literally say "colon"
        # Convert non-time colons to natural breath pauses (commas)
        s = re.sub(r"(?<!\d):(?!\d)", ", ", s)
        s = re.sub(r":", ", ", s)  # Remaining colons become pauses

        # Semicolons ';' to pauses
        s = s.replace(";", ", ")

        # Parentheses, Brackets, and Braces
        # Convert outer brackets to pauses and strip inner to prevent 'open parenthesis'
        s = re.sub(r"\s*\(([^)]+)\)\s*", r", \1, ", s)
        s = re.sub(r"\s*\[([^\]]+)\]\s*", r", \1, ", s)
        s = re.sub(r"\s*\{([^}]+)\}\s*", r", \1, ", s)
        # Any stray bracket characters
        s = re.sub(r"[()[\]{}]", " ", s)

        # Quotation marks (both single and double) to prevent 'quote' / 'unquote'
        s = re.sub(r'["\']', "", s)

        # Vertical pipes '|' used in headlines to pause or period
        s = re.sub(r"\s*\|\s*", ". ", s)

        # Hyphens and compound dashes:
        # e.g. 'stop-loss' -> 'stop loss', 'dark-pool' -> 'dark pool', '70-20-10' -> '70 20 10'
        # Standalone ' - ' becomes comma pause
        s = re.sub(r"\s+-\s+", ", ", s)
        s = re.sub(r"(\w+)-(\w+)", r"\1 \2", s)
        s = s.replace("-", " ")

        # ── 9. Prosody Cleaning & Deduplication ──
        # Retain ONLY natural sentence terminators and pauses: . , ? !
        # Remove any remaining unwanted symbols
        s = re.sub(r"[^\w\s.,?!]", " ", s)

        # Clean consecutive punctuation marks (e.g. ',,' or '.,' or ',.')
        s = re.sub(r",\s*,+", ", ", s)
        s = re.sub(r"\.\s*\.+", ". ", s)
        s = re.sub(r",\s*\.", ". ", s)
        s = re.sub(r"\.\s*,", ". ", s)
        s = re.sub(r"\s+,", ",", s)
        s = re.sub(r"\s+\.", ".", s)

        # Deduplicate whitespace
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\n\s*\n+", "\n\n", s)

        # If ending with a comma, change to period
        s = re.sub(r",\s*$", ".", s)
        s = re.sub(r",\s*\n", ".\n", s)

        # Clean up leading commas or punctuation at start of sentences
        s = re.sub(r"(?<=\n)[,\s]+", "", s)
        s = re.sub(r"^[,\s]+", "", s)

        return s.strip()


# Global convenient function
def normalize_script_for_tts(text: str, language: str = "en") -> str:
    """Convenience helper for pipeline modules."""
    return TTSNormalizer.normalize_for_tts(text, language=language)

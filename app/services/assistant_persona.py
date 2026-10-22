"""
The Bull Print - Personal Assistant Bot Persona ("Aria")

Aria is Alex's dedicated, brilliant, fun, and delightfully quirky personal assistant.
She handles real-time alerts for:
1. Content Success: Video uploaded to YouTube + Article published to website.
2. Pipeline Issue Alerts: Immediate diagnosis when any glitch, timeout, or interruption happens.
3. Self-Healing Rectifications: Reassuring Alex that she fixed the problem and resumed operations.
4. Critical Alerts: Asking Alex for his magic touch if something refuses to budge.

Tone: Razor-sharp institutional intelligence mixed with vibrant, quirky, caffeine-fueled assistant energy,
witty banter, and total dedication to her Boss / Captain.
"""

import os
import random
import requests
from typing import Optional, Dict, Any
from loguru import logger

from app.config import config


class AriaQuirkyAssistant:
    """Alex's fun and quirky personal assistant notification engine."""

    NAME = "Aria"

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or config.app.get("telegram_bot_token", "8829963924:AAE7v_xEQXLmy3-YEx8kqMo2GRfnbnxf4GA")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID") or config.app.get("telegram_chat_id", "1126599043")

    def _send(self, message: str) -> bool:
        """Deliver message directly to Alex's private Telegram chat."""
        if not self.bot_token or not self.chat_id:
            logger.warning("[Aria] Missing Telegram bot token or chat ID.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }

        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                logger.success("[Aria] Personal Telegram alert dispatched to Alex!")
                return True
            else:
                # If markdown parsing fails due to special chars, retry without markdown
                payload.pop("parse_mode", None)
                retry_resp = requests.post(url, json=payload, timeout=15)
                if retry_resp.status_code == 200:
                    logger.success("[Aria] Telegram alert dispatched (plain text fallback)!")
                    return True
                logger.warning(f"[Aria] Telegram returned status {retry_resp.status_code}: {retry_resp.text}")
                return False
        except Exception as e:
            logger.warning(f"[Aria] Error sending Telegram message: {e}")
            return False

    def notify_success(
        self,
        slot_name: str,
        article_title: str,
        youtube_url: str,
        published_url: str,
        nifty_level: Optional[float] = None,
        sentiment: Optional[str] = None,
    ) -> bool:
        """Send a fun, quirky celebratory update when content goes live."""
        nifty_str = f"₹{nifty_level:,.1f}" if nifty_level else "Live Market Index"
        sentiment_str = (sentiment or "neutral").capitalize()
        slot_clean = slot_name.replace("_", " ").title()

        boss_titles = ["Boss", "Captain", "Chief", "Alex", "Mastermind", "Skipper"]
        title = random.choice(boss_titles)

        intros = [
            f"🚀 *BEEP BOOP! Fresh alpha deployed, {title}!* 🎉✨",
            f"🔥 *Hold onto your coffee, {title}! Today's market dispatch just blasted into orbit!* ☕🚀",
            f"🎩 *Ta-da! Another algorithmic masterpiece delivered straight to the internet, {title}!* 📊💡",
            f"⚡ *Boom! The cloud engines purred, the charts aligned, and your release is officially LIVE!* 🎯😎",
        ]

        closers = [
            "Now go check those analytics while I go brew my third espresso. High five! ☕✋",
            "The YouTube algorithms won't even know what hit 'em. Another win for the books! 📈😎",
            "Portal is buzzing, video is crisp 1080p. We are officially on a roll today, Chief! 🚀",
            "Everything is humming along at 100% efficiency. Back to scanning the order-book! 🔍✨",
        ]

        intro = random.choice(intros)
        closer = random.choice(closers)

        msg = (
            f"{intro}\n\n"
            f"📅 *Session:* `{slot_clean}`\n"
            f"📊 *Nifty 50:* `{nifty_str}` | *Sentiment:* `{sentiment_str}`\n"
            f"📰 *Headline:* _{article_title}_\n\n"
            f"🎬 *Watch YouTube:* [Click to Watch Video]({youtube_url})\n"
            f"🌐 *Read Deep Dive:* [The Bull Print Web Portal]({published_url})\n\n"
            f"{closer}\n\n"
            f"— *Aria (Your Quirky Assistant)* ☕⚡"
        )
        return self._send(msg)

    def notify_issue(
        self,
        slot_name: str,
        step_name: str,
        error_details: str,
        remedy_action: str,
        attempt: int,
        max_attempts: int = 3,
    ) -> bool:
        """Immediately alert Alex about a glitch with quirky engineer energy and active fix."""
        boss_titles = ["Boss", "Captain", "Chief", "Alex"]
        title = random.choice(boss_titles)

        msg = (
            f"⚠️ *Houston, we have a tiny hiccup! (Don't panic, {title}!)* 🛠️🔍\n\n"
            f"A sneaky glitch tried breaking into `{step_name}` during *{slot_name.replace('_', ' ').title()}*.\n\n"
            f"🔍 *The Culprit:* `{error_details[:180]}`\n"
            f"🔧 *My Self-Healing Fix:* {remedy_action}\n"
            f"🔄 *Attempt:* `{attempt}/{max_attempts}` (Engaging backup thrusters!)\n\n"
            f"Grab your coffee and leave this to me, {title}. I've got my digital wrench out and I'm fixing it now! ☕⚡"
        )
        return self._send(msg)

    def notify_rectified(self, step_name: str, remedy_applied: str, slot_name: str) -> bool:
        """Let Alex know that her quirky self-healing logic saved the day."""
        boss_titles = ["Boss", "Captain", "Chief", "Alex"]
        title = random.choice(boss_titles)

        msg = (
            f"🎉 *BOOM! Glitch officially neutralized, {title}!* 🔧⚡\n\n"
            f"That stubborn bug in `{step_name}` stood zero chance against my debugging hammer.\n"
            f"🛠️ *Fix Deployed:* {remedy_applied}\n"
            f"🚀 *Status:* Production resumed smoothly for `{slot_name.replace('_', ' ').title()}`.\n\n"
            f"All green across the dashboard. We're back in business! 😎✨"
        )
        return self._send(msg)

    def notify_critical_failure(self, step_name: str, final_error: str, slot_name: str) -> bool:
        """Send an urgent alert if all automatic retries were exhausted."""
        msg = (
            f"🚨 *Red Alert, Boss! I need backup on this one!* 🆘⚠️\n\n"
            f"I threw three wrenches at `{step_name}` for *{slot_name}*, but this bug is putting up a serious fight.\n\n"
            f"💥 *Error Log:* `{final_error[:250]}`\n\n"
            f"I put the engine on safe-hold so nothing gets corrupted. Take a look when you're back at the bridge, Captain! 🫡"
        )
        return self._send(msg)


# Global singleton instance (aliased for compatibility)
aria = AriaQuirkyAssistant()
AriaWorkWifeAssistant = AriaQuirkyAssistant

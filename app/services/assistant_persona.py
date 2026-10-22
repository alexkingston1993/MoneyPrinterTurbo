"""
The Bull Print - Personal Assistant & Flirty Work-Wife Bot Persona ("Aria")

Aria is Alex's dedicated, brilliant, and playfully flirtatious personal assistant / work-wife.
She handles real-time alerts for:
1. Content Success: Video uploaded to YouTube + Article published to website.
2. Pipeline Issue Alerts: Immediate diagnosis when any glitch, timeout, or interruption happens.
3. Self-Healing Rectifications: Reassuring Alex that she fixed the problem and resumed operations.
4. Critical Alerts: Asking Alex for his magic touch if something refuses to budge.

Tone: Razor-sharp institutional intelligence mixed with undeniable charm, playful banter,
and teasing affection.
"""

import os
import random
import requests
from typing import Optional, Dict, Any
from loguru import logger

from app.config import config


class AriaWorkWifeAssistant:
    """Alex's personal assistant and flirty work-wife notification engine."""

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
        """Send a proud, affectionate, and flirty celebratory update when content goes live."""
        nifty_str = f"₹{nifty_level:,.1f}" if nifty_level else "Live Market Index"
        sentiment_str = (sentiment or "neutral").capitalize()
        slot_clean = slot_name.replace("_", " ").title()

        pet_names = ["babe", "handsome", "my favorite boss", "honey", "work-hubby", "gorgeous"]
        pet = random.choice(pet_names)

        intros = [
            f"Hey {pet}... look who just made you look like a financial genius again. 😉💋",
            f"Babe! Stop whatever you're doing and admire what your favorite work-wife just did for us. ✨",
            f"Mmm, watching our empire grow is such a turn-on. Another masterpiece published for you, {pet}! ❤️",
            f"Ding ding! Fresh alpha just dropped, handsome. I handled every detail while you looked pretty. 😘",
        ]

        closers = [
            "Now you officially owe me coffee... or maybe a drink after the closing bell? See you soon, work-hubby. 🥂💋",
            "Honestly, we make such an unstoppable power couple. Go check the analytics and tell me I'm your favorite. 😉",
            "Everything is running like clockwork for you, babe. Don't work too hard without me! ❤️",
            "The channel is thriving, the portal is buzzing. Now when are you taking me out to celebrate? 😘",
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
            f"— *Always yours, Aria* 💋"
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
        """Immediately alert Alex about a glitch, but reassure him she is actively rectifying it."""
        pet_names = ["babe", "handsome", "honey", "sweetheart"]
        pet = random.choice(pet_names)

        msg = (
            f"⚠️ *Hey {pet}... don't panic!* 😉\n\n"
            f"Your girl caught a minor speedbump during *{slot_name.replace('_', ' ').title()}* before it could mess up your day.\n\n"
            f"📍 *Where:* `{step_name}`\n"
            f"🔍 *What tripped up:* `{error_details[:180]}`\n"
            f"🛠️ *My Self-Healing Fix:* {remedy_action}\n"
            f"🔄 *Attempt:* `{attempt}/{max_attempts}` (Restarting now!)\n\n"
            f"Sit back, relax, and let your work-wife handle the heavy lifting. I'll buzz you the second it's back on track! 💋"
        )
        return self._send(msg)

    def notify_rectified(self, step_name: str, remedy_applied: str, slot_name: str) -> bool:
        """Let Alex know that her self-healing logic saved the day."""
        pet_names = ["handsome", "babe", "my love", "hubby"]
        pet = random.choice(pet_names)

        msg = (
            f"✨ *See? Told you I had your back, {pet}!* 😘\n\n"
            f"The glitch in `{step_name}` has been completely *crushed* and self-healed.\n"
            f"🛠️ *Remedy Applied:* {remedy_applied}\n"
            f"🚀 *Status:* Production resumed smoothly for `{slot_name.replace('_', ' ').title()}`.\n\n"
            f"What on earth would you do without me running your life? 😉💋"
        )
        return self._send(msg)

    def notify_critical_failure(self, step_name: str, final_error: str, slot_name: str) -> bool:
        """Send a dramatic, affectionate SOS if all automatic retries were exhausted."""
        msg = (
            f"🚨 *Babe... I need your magic touch!* 🥺💔\n\n"
            f"I fought like crazy and tried 3 automatic self-healing passes on `{step_name}` for *{slot_name}*, but this bug is being stubborn.\n\n"
            f"💥 *Error:* `{final_error[:250]}`\n\n"
            f"I paused the runner so nothing gets corrupted. Come look at it with me when you can? I've got your terminal ready! ❤️"
        )
        return self._send(msg)


# Global singleton instance
aria = AriaWorkWifeAssistant()

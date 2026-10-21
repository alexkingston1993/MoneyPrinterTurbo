"""
The Bull Print - Autonomous Broadcast Notifier
Sends real-time broadcast alerts (YouTube Short link + Published Website Article link)
directly to your personal WhatsApp without needing a dedicated phone number or server.
Uses CallMeBot Gateway API.
"""

import os
import urllib.parse
from typing import Optional
from loguru import logger
import requests

from app.config import config


def send_whatsapp_alert(
    message: str,
    phone: Optional[str] = None,
    api_key: Optional[str] = None,
) -> bool:
    """
    Sends an alert message to WhatsApp via CallMeBot.
    No dedicated phone number or server required.
    """
    target_phone = phone or os.getenv("WHATSAPP_PHONE") or config.app.get("whatsapp_phone")
    target_key = api_key or os.getenv("WHATSAPP_APIKEY") or config.app.get("whatsapp_apikey")

    if not target_phone or not target_key:
        logger.info("[Notifier] WhatsApp notification skipped (WHATSAPP_PHONE or WHATSAPP_APIKEY not configured).")
        return False

    # Clean phone number (ensure no spaces or hyphens)
    clean_phone = str(target_phone).strip().replace(" ", "").replace("-", "")
    if not clean_phone.startswith("+"):
        clean_phone = f"+{clean_phone}"

    encoded_msg = urllib.parse.quote(message)
    api_url = f"https://api.callmebot.com/whatsapp.php?phone={clean_phone}&text={encoded_msg}&apikey={target_key}"

    try:
        resp = requests.get(api_url, timeout=15)
        if resp.status_code == 200:
            logger.success(f"[Notifier] WhatsApp notification dispatched successfully to {clean_phone}!")
            return True
        else:
            logger.warning(f"[Notifier] CallMeBot API returned status {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.warning(f"[Notifier] Failed to send WhatsApp notification: {e}")
        return False


def send_market_release_alert(
    slot_name: str,
    article_title: str,
    youtube_url: Optional[str],
    published_url: Optional[str],
    nifty_level: Optional[float] = None,
    sentiment: Optional[str] = None,
) -> bool:
    """
    Formats and delivers a high-impact release alert to your WhatsApp
    immediately after a video & article go live.
    """
    slot_display = {
        "pre_market": "Opening Bell Setup (09:00 AM IST)",
        "morning_momentum": "Morning Momentum Radar (11:00 AM IST)",
        "midday_update": "Mid-Day European Cues (01:30 PM IST)",
        "market_close": "Closing Bell Settlement (04:00 PM IST)",
        "evening_wrap": "Evening Institutional Deep Dive (07:30 PM IST)",
        "weekend_masterclass": "Weekend Wealth Masterclass (11:00 AM IST)",
    }.get(slot_name, slot_name.replace("_", " ").title())

    nifty_str = f"{nifty_level:,.1f}" if nifty_level else "Live Market Index"
    sentiment_str = (sentiment or "Neutral").capitalize()

    lines = [
        "🔔 *The Bull Print: New Content Live!* 🚀",
        "",
        f"📅 *Slot:* {slot_display}",
        f"📊 *Nifty 50:* {nifty_str} | *Sentiment:* {sentiment_str}",
        f"📰 *Topic:* {article_title}",
        "",
    ]

    if youtube_url:
        lines.append(f"🎥 *YouTube Short:* {youtube_url}")
    if published_url:
        lines.append(f"🌐 *Full Research Article:* {published_url}")

    lines.extend([
        "",
        "✅ Generated & Published 100% autonomously in the cloud.",
        "👉 https://dalal-street-alpha.vercel.app",
    ])

    formatted_message = "\n".join(lines)
    return send_whatsapp_alert(formatted_message)

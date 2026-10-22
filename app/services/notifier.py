"""
The Bull Print - Autonomous Broadcast Notifier
Sends real-time broadcast alerts (YouTube Short link + Published Website Article link)
directly to your personal phone without needing a dedicated server or phone number.
Supports:
1. Twilio WhatsApp Sandbox (Official, high-reliability WhatsApp)
2. CallMeBot WhatsApp (Free community gateway)
3. Telegram Bot (Instant, 100% free, zero limitations)
"""

import os
import urllib.parse
from typing import Optional
from loguru import logger
import requests
from requests.auth import HTTPBasicAuth

from app.config import config


def send_twilio_whatsapp(message: str) -> bool:
    """
    Sends WhatsApp alert via Twilio WhatsApp Sandbox.
    Uses Twilio's shared business number (+1 415 523 8886) - zero phone number needed from user.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    to_phone = os.getenv("TWILIO_TO_PHONE") or os.getenv("WHATSAPP_PHONE")
    from_phone = os.getenv("TWILIO_FROM_PHONE", "+14155238886")

    if not account_sid or not auth_token or not to_phone:
        return False

    clean_to = str(to_phone).strip().replace(" ", "").replace("-", "")
    if not clean_to.startswith("+"):
        clean_to = f"+{clean_to}"
    if not clean_to.startswith("whatsapp:"):
        clean_to = f"whatsapp:{clean_to}"

    clean_from = from_phone if from_phone.startswith("whatsapp:") else f"whatsapp:{from_phone}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    payload = {
        "From": clean_from,
        "To": clean_to,
        "Body": message,
    }

    try:
        resp = requests.post(url, data=payload, auth=HTTPBasicAuth(account_sid, auth_token), timeout=15)
        if resp.status_code in (200, 201):
            logger.success(f"[Notifier] Twilio WhatsApp notification delivered to {clean_to}!")
            return True
        else:
            logger.warning(f"[Notifier] Twilio WhatsApp API returned {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.warning(f"[Notifier] Twilio WhatsApp error: {e}")
        return False


def send_callmebot_whatsapp(
    message: str,
    phone: Optional[str] = None,
    api_key: Optional[str] = None,
) -> bool:
    """
    Sends WhatsApp alert via CallMeBot gateway.
    """
    target_phone = phone or os.getenv("WHATSAPP_PHONE") or config.app.get("whatsapp_phone")
    target_key = api_key or os.getenv("WHATSAPP_APIKEY") or config.app.get("whatsapp_apikey")

    if not target_phone or not target_key:
        return False

    clean_phone = str(target_phone).strip().replace(" ", "").replace("-", "")
    if not clean_phone.startswith("+"):
        clean_phone = f"+{clean_phone}"

    encoded_msg = urllib.parse.quote(message)
    api_url = f"https://api.callmebot.com/whatsapp.php?phone={clean_phone}&text={encoded_msg}&apikey={target_key}"

    try:
        resp = requests.get(api_url, timeout=15)
        if resp.status_code == 200:
            logger.success(f"[Notifier] CallMeBot WhatsApp notification dispatched to {clean_phone}!")
            return True
        else:
            logger.warning(f"[Notifier] CallMeBot returned status {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.warning(f"[Notifier] CallMeBot error: {e}")
        return False


def send_telegram_alert(message: str) -> bool:
    """
    Sends instant push alert via Telegram Bot.
    Takes 30 seconds to set up via @BotFather. 100% free forever with rich embeds.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or config.app.get("telegram_bot_token")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or config.app.get("telegram_chat_id")

    if not bot_token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": False,
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            logger.success("[Notifier] Telegram notification dispatched successfully!")
            return True
        else:
            logger.warning(f"[Notifier] Telegram returned status {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.warning(f"[Notifier] Telegram error: {e}")
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
    Formats and delivers release alerts across all configured channels
    (Twilio WhatsApp, CallMeBot, and/or Telegram).
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
        lines.append(f"🎥 *YouTube Video:* {youtube_url}")
    if published_url:
        clean_pub_url = published_url if "github.com" not in published_url else "https://the-bull-print.vercel.app"
        lines.append(f"🌐 *Full Research Article:* {clean_pub_url}")

    lines.extend([
        "",
        "✅ Generated & Published 100% autonomously in the cloud.",
        "👉 https://the-bull-print.vercel.app",
    ])

    formatted_message = "\n".join(lines)

    delivered = False
    # 1. Try Twilio WhatsApp Sandbox
    if send_twilio_whatsapp(formatted_message):
        delivered = True

    # 2. Try CallMeBot WhatsApp
    if send_callmebot_whatsapp(formatted_message):
        delivered = True

    # 3. Try Telegram Bot
    if send_telegram_alert(formatted_message):
        delivered = True

    if not delivered:
        logger.info("[Notifier] No notification services configured (Twilio, CallMeBot, or Telegram).")

    return delivered

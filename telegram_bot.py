"""
Telegram Bot & Real-Time Alert Engine (telegram_bot.py).
1. Sends live status alerts at key pipeline milestones:
   - 📈 Playwright charts captured
   - 🎬 FFmpeg video rendered & stitched
   - 🚀 YouTube uploaded with containsSyntheticMedia=True
   - 🌐 Vercel deployment live & IndexNow pinged
2. Listens for remote /run commands to trigger automated cloud runs.
"""

import os
import sys
import asyncio
import subprocess
from pathlib import Path
import requests
from loguru import logger

BASE_DIR = Path(__file__).parent
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_telegram_alert(message: str) -> bool:
    """Sends a formatted markdown notification to your private Telegram channel/chat."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    chat_id = os.getenv("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)

    if not token or not chat_id:
        logger.info(f"[Telegram Alert Preview]:\n{message}")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as e:
        logger.warning(f"Telegram alert ping failed: {e}")
        return False


def run_telegram_bot():
    """Starts polling listener for Telegram /run commands."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured. Bot listener not started.")
        print("To activate the bot listener, set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
        return

    try:
        from telegram import Update
        from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

        async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = str(update.effective_chat.id)
            target_chat_id = os.getenv("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
            
            if target_chat_id and user_id != target_chat_id:
                await update.message.reply_text("⛔ Unauthorized user.")
                return

            topic = " ".join(context.args) if context.args else "Institutional Order Flow Absorption & Macro Liquidity"
            await update.message.reply_text(f"🚀 Master publishing pipeline initiated for: '{topic}'...")

            # Run master_engine
            cmd = [
                str(BASE_DIR / ".venv" / "bin" / "python") if (BASE_DIR / ".venv").exists() else "python3",
                str(BASE_DIR / "master_engine.py")
            ]
            
            send_telegram_alert(f"🚀 *Mobile Run Triggered:*\nTopic: `{topic}`")
            proc = subprocess.Popen(cmd, cwd=str(BASE_DIR))
            await update.message.reply_text("⚙️ Pipeline execution dispatched to background runner!")

        app = ApplicationBuilder().token(token).build()
        app.add_handler(CommandHandler("run", run_command))
        print("🤖 Telegram Bot listener active. Send /run <topic> to start...")
        app.run_polling()
    except ImportError:
        logger.warning("python-telegram-bot not installed. You can trigger via Vercel serverless webhook.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        send_telegram_alert("🔔 *The Bull Print Media Engine:* Test alert successfully connected!")
    else:
        run_telegram_bot()

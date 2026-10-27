"""
Master 12-Video Autonomous Publisher (publish_all_12_videos.py).
Sequentially executes 4 market slots to generate and publish exactly 12 videos to YouTube:
- Slot 1: Stock Market Pre-Open (1 Long-Form 1080p + 2 Shorts 9:16 = 3 videos)
- Slot 2: Crypto Macro Morning (1 Long-Form 1080p + 2 Shorts 9:16 = 3 videos)
- Slot 3: Insurance Room-Rent Forensics (1 Long-Form 1080p + 2 Shorts 9:16 = 3 videos)
- Slot 4: Stock Market Closing Auction (1 Long-Form 1080p + 2 Shorts 9:16 = 3 videos)

Total: 4 Masterclasses + 8 Shorts = 12 Videos Published to YouTube.
If Kaggle GPU times out or errors, automatic CPU fallback finishes the render on the GHA runner.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from loguru import logger

SLOTS = [
    {
        "slot": 1,
        "vertical": "stock_market",
        "name": "Stock Pre-Open Institutional Flow",
        "shorts": 2,
    },
    {
        "slot": 2,
        "vertical": "crypto",
        "name": "Crypto Liquidation & Funding Stress",
        "shorts": 2,
    },
    {
        "slot": 3,
        "vertical": "insurance",
        "name": "Insurance Room-Rent & CSR Forensics",
        "shorts": 2,
    },
    {
        "slot": 4,
        "vertical": "stock_market",
        "name": "Stock Closing Session & Option Chain",
        "shorts": 2,
    },
]

def send_telegram_alert(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        import urllib.request
        import urllib.parse
        body = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }).encode()
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", body
        ), timeout=10)
    except Exception as e:
        logger.warning(f"Telegram alert error: {e}")

def main():
    total_slots = len(SLOTS)
    expected_videos = sum(1 + s["shorts"] for s in SLOTS)
    logger.info("=" * 75)
    logger.info(f"🐂 [The Bull Print] MASTER 12-VIDEO PRODUCTION RUN INITIALIZING")
    logger.info(f"Target: {expected_videos} Videos across {total_slots} Slots (4 Long-Form + 8 Shorts)")
    logger.info("=" * 75)

    send_telegram_alert(
        f"🚀 *Agent Aria:* Initiating Master 12-Video Production Run! 🎬✨\n\n"
        f"📊 *Target:* `4 Long-Form Masterclasses + 8 Shorts = 12 Videos`\n"
        f"🛡️ *Safety Net:* Automatic CPU FFmpeg fallback armed for zero-dropped uploads.\n\n"
        f"Grab a coffee, Captain! The engines are spinning up. ☕⚡"
    )

    completed_slots = 0
    slot_results = []

    for idx, s in enumerate(SLOTS, 1):
        slot_num = s["slot"]
        vertical = s["vertical"]
        name = s["name"]
        shorts_count = s["shorts"]

        logger.info(f"\n{'='*75}")
        logger.info(f"▶️ [Slot #{slot_num} - {idx}/{total_slots}] {name.upper()} ({vertical})")
        logger.info(f"Expected: 1 Long-Form (1080p) + {shorts_count} Shorts (9:16)")
        logger.info(f"{'='*75}\n")

        cmd = [
            sys.executable,
            "cloud_orchestrator.py",
            "--slot", str(slot_num),
            "--vertical", vertical,
            "--shorts-count", str(shorts_count),
        ]

        # Check if force cpu fallback is globally active
        if os.getenv("FORCE_CPU_FALLBACK", "").lower() in ("true", "1", "yes"):
            cmd.append("--force-cpu-fallback")

        start_t = time.time()
        success = False

        # Attempt 1: Standard orchestrator (Kaggle GPU with automatic CPU fallback)
        try:
            res = subprocess.run(cmd, check=True)
            success = True
            logger.success(f"✓ Slot #{slot_num} finished successfully!")
        except Exception as e:
            logger.warning(f"⚠️ Slot #{slot_num} primary attempt encountered an issue: {e}")
            logger.info(f"🔄 Retrying Slot #{slot_num} with explicit --force-cpu-fallback...")
            # Attempt 2: Explicit CPU Fallback
            retry_cmd = list(cmd)
            if "--force-cpu-fallback" not in retry_cmd:
                retry_cmd.append("--force-cpu-fallback")
            try:
                subprocess.run(retry_cmd, check=True)
                success = True
                logger.success(f"✓ Slot #{slot_num} recovered and completed via CPU fallback!")
            except Exception as e2:
                logger.error(f"❌ Slot #{slot_num} retry failed: {e2}")

        elapsed_m = int((time.time() - start_t) // 60)
        elapsed_s = int((time.time() - start_t) % 60)

        if success:
            completed_slots += 1
            slot_results.append(f"✅ Slot #{slot_num} ({name}): 3 Videos Uploaded ({elapsed_m}m {elapsed_s}s)")
        else:
            slot_results.append(f"⚠️ Slot #{slot_num} ({name}): Glitch encountered")

        # Telegram progress checkpoint
        send_telegram_alert(
            f"🎬 *Batch Progress [{idx}/{total_slots}]:* Slot #{slot_num} ({name})\n"
            f"Status: {'✅ Completed' if success else '⚠️ Check logs'}\n"
            f"Elapsed: `{elapsed_m}m {elapsed_s:02d}s`\n"
            f"Total Completed: `{completed_slots}/{total_slots}` slots."
        )

    # Final summary
    total_videos_produced = completed_slots * 3
    logger.info("\n" + "=" * 75)
    logger.info(f"🎉 MASTER 12-VIDEO PRODUCTION FINISHED!")
    logger.info(f"Results: {completed_slots}/{total_slots} Slots Completed (~{total_videos_produced} Videos)")
    for r in slot_results:
        logger.info(f"  {r}")
    logger.info("=" * 75)

    summary_text = (
        f"🏁 *Master 12-Video Run Complete, Captain!* 🎉✨\n\n"
        f"📊 *Summary:*\n"
        + "\n".join(slot_results) + "\n\n"
        f"🚀 *Total Videos Generated:* ~`{total_videos_produced}` Videos live on YouTube!\n"
        f"🌐 *Portal Synced:* https://thebullprint.in\n\n"
        f"— *Aria (Operations Manager)* ☕🕶️"
    )
    send_telegram_alert(summary_text)

if __name__ == "__main__":
    main()

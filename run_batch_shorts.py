"""
Master 10-Shorts Batch Generator (run_batch_shorts.py).
Sequentially executes 5 market slots with --shorts-only.
In each slot, generates 2 shorts sequentially directly on the GitHub Actions runner (CPU FFmpeg + YouTube Upload):
Resulting in 10 Short videos uploaded to YouTube today without touching Kaggle GPU.
"""

import sys
import subprocess
from loguru import logger

SLOTS = [
    {"slot": 1, "vertical": "stock_market"},
    {"slot": 2, "vertical": "crypto"},
    {"slot": 3, "vertical": "insurance"},
    {"slot": 4, "vertical": "stock_market"},
    {"slot": 5, "vertical": "crypto"},
]

def main():
    target_shorts = 10
    total_slots = len(SLOTS)
    logger.info(f"🚀 [The Bull Print] Launching Master 10-Shorts Sequential Production Run!")
    logger.info(f"Target: {target_shorts} Shorts across {total_slots} slots (100% GHA Sequential CPU FFmpeg + Headless Upload).")

    successful_slots = 0
    for idx, s in enumerate(SLOTS, 1):
        slot_num = s["slot"]
        vertical = s["vertical"]
        logger.info(f"\n{'='*65}\n🎬 BATCH #{idx}/{total_slots}: Slot #{slot_num} ({vertical.upper()})\n{'='*65}\n")
        cmd = [
            sys.executable,
            "cloud_orchestrator.py",
            "--slot", str(slot_num),
            "--vertical", vertical,
            "--shorts-only",
            "--shorts-count", "2",
        ]
        try:
            res = subprocess.run(cmd, check=True)
            successful_slots += 1
            logger.info(f"✅ Slot #{slot_num} finished successfully! (2 Shorts created & uploaded)")
        except subprocess.CalledProcessError as err:
            logger.error(f"⚠️ Slot #{slot_num} encountered an issue (exit code {err.returncode}) — continuing next slot...")

    logger.info(f"\n🎉 [The Bull Print] Batch run finished: {successful_slots}/{total_slots} slots completed.")

if __name__ == "__main__":
    main()

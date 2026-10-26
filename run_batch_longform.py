"""
Master Long-Format Batch Generator (run_batch_longform.py).
Sequentially executes all 6 daily market slots on Kaggle's Dual Tesla T4 GPU:
- Slot 1: Stock Market Pre-Open
- Slot 2: Crypto Macro Morning
- Slot 3: Insurance Forensic Lunch
- Slot 4: Stock Market Closing Auction
- Slot 5: Crypto Evening CVD Breakdown
- Slot 6: Insurance Night Claim Settlement Forensics

Each slot:
1. Harvests charts & order flow via Playwright
2. Generates institutional breakdown via Gemini AI Studio
3. Passes SEBI/IRDAI Zero-Quota Compliance Gate
4. Dispatches to Kaggle Dual-T4 GPU (Faster-Whisper + NVENC FFmpeg)
5. Uploads 1080p Masterclass directly to YouTube Data API
6. Generates companion research dossier on the website
"""

import sys
import subprocess
import time
from loguru import logger

LONG_SLOTS = [
    {"slot": 1, "vertical": "stock_market", "name": "Stock Pre-Open Institutional Flow"},
    {"slot": 2, "vertical": "crypto", "name": "Crypto Liquidation & Funding Stress"},
    {"slot": 3, "vertical": "insurance", "name": "Insurance Room-Rent & CSR Forensics"},
    {"slot": 4, "vertical": "stock_market", "name": "Stock Closing Session Flows & Option Ring"},
    {"slot": 5, "vertical": "crypto", "name": "Crypto CVD Divergence & Exchange Reserves"},
    {"slot": 6, "vertical": "insurance", "name": "Insurance CSR vs ICR Reality Check"},
]

def main():
    total_slots = len(LONG_SLOTS)
    logger.info("🐂 [The Bull Print] Launching Master Long-Format Sequential GPU Production Run!")
    logger.info(f"Target: {total_slots} Long-Format Masterclass Videos on Kaggle Dual-T4 GPU (in sequence).")

    successful_slots = 0
    for idx, s in enumerate(LONG_SLOTS, 1):
        slot_num = s["slot"]
        vertical = s["vertical"]
        name = s["name"]

        logger.info(f"\n{'='*70}\n🎬 LONG-FORM SLOT #{idx}/{total_slots}: Slot #{slot_num} ({name})\n{'='*70}\n")
        cmd = [
            sys.executable,
            "cloud_orchestrator.py",
            "--slot", str(slot_num),
            "--vertical", vertical,
        ]

        slot_start = time.time()
        try:
            subprocess.run(cmd, check=True)
            successful_slots += 1
            elapsed_m = int((time.time() - slot_start) // 60)
            elapsed_s = int((time.time() - slot_start) % 60)
            logger.info(f"✅ Slot #{slot_num} finished successfully in {elapsed_m}m {elapsed_s}s! (Long-form video live on YouTube & dossier published)")
        except subprocess.CalledProcessError as err:
            logger.error(f"⚠️ Slot #{slot_num} encountered an issue (exit code {err.returncode}) — continuing next slot in sequence...")
        except Exception as e:
            logger.error(f"⚠️ Unexpected error on Slot #{slot_num}: {e} — continuing next slot...")

    logger.info(f"\n🎉 [The Bull Print] Long-form batch run complete: {successful_slots}/{total_slots} slots finished.")

if __name__ == "__main__":
    main()

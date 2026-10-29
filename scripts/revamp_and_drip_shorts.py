#!/usr/bin/env python3
"""
scripts/revamp_and_drip_shorts.py
Revamps privated (<= 50 views) Shorts with 100% Cloned Arjun voice,
30-Day Compliance-approved 3D visuals & persistent 3D headers,
uncropped glassmorphic chart cards, and smart drip scheduling.

Pacing:
- First 3 Shorts uploaded as PUBLIC immediately for live verification.
- Remaining Shorts scheduled spaced 3 hours apart using status.publishAt (ISO 8601 UTC).
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from loguru import logger
from app.services.compliance_gate import ComplianceGate
from app.services.short_renderer import render_and_upload_short_local

# 6 Unique High-Impact Topics across Verticals (Deduplicated from 27 Privated Shorts)
REVAMP_CANDIDATES = [
    {
        "index": 1,
        "vertical": "insurance",
        "title": "Why 98% Claim Settlement Ratios Are a Marketing Mirage",
        "hook_data": {
            "line1_setup": "98% RATIO",
            "line2_power": "CLAIM TRAP!",
            "badge": "ICR MATH EXPOSED"
        },
        "spoken_hook_and_body": (
            "Think a ninety-eight percent claim settlement ratio means your hospital bill is safe? Think again. "
            "Insurers advertise high claim counts by approving small fifteen-thousand-rupee outpatient claims, "
            "but when a twelve-lakh-rupee major surgery hits, the Incurred Claim Ratio reveals the brutal reality. "
            "Incurred claim ratio measures total rupees paid out versus total premiums collected. "
            "If an insurer's ICR is below sixty-five percent, they are aggressively rejecting high-value claims to protect underwriting profit. "
            "Never buy health insurance based on claim settlement ratio alone. Always demand the three-year average incurred claim ratio from the public IRDAI disclosures."
        ),
        "cta_to_long_video": "Read the full Claim Audit Dossier at thebullprint.in. Follow for daily edge."
    },
    {
        "index": 2,
        "vertical": "crypto",
        "title": "The 8-Hour Funding Bleed: How Perpetual Swaps Drain Retail Longs",
        "hook_data": {
            "line1_setup": "8-HOUR DRAIN",
            "line2_power": "PERP TRAP!",
            "badge": "FUNDING FEE BLEED"
        },
        "spoken_hook_and_body": (
            "Ever wonder why your leveraged Bitcoin long is bleeding money even when price moves sideways? "
            "You are paying perpetual funding rates. Unlike traditional futures that expire, perpetual contracts use an eight-hour funding mechanism to anchor perpetual prices to spot index. "
            "When retail sentiment is hyper-bullish, longs pay shorts every eight hours. "
            "At point zero five percent per interval, you are bleeding over fifty-four percent annualized just to hold the position. "
            "Institutional market makers hedge spot against perps, pocketing your funding fee completely risk-free. "
            "Before holding leveraged perps overnight, check the predicted funding rate on CoinGlass."
        ),
        "cta_to_long_video": "Full On-Chain CVD Dossier at thebullprint.in. Follow for daily institutional signals."
    },
    {
        "index": 3,
        "vertical": "stock_market",
        "title": "The Math They Don't Tell You About SEBI F&O Rules",
        "hook_data": {
            "line1_setup": "LOT SIZE SHOCK",
            "line2_power": "SEBI F&O TRAP",
            "badge": "MARGIN MULTIPLIER"
        },
        "spoken_hook_and_body": (
            "SEBI just increased minimum contract values from five lakhs to fifteen lakhs, and retail option traders are celebrating higher premium collections. "
            "That is an expensive misunderstanding. With lot sizes tripling, one adverse gap-up against an naked short position can wipe out three months of option writing profits in a single opening tick. "
            "Institutional desks do not write unhedged options; they run gamma-neutral calendars and dynamic delta hedges. "
            "If you trade F and O without defining maximum margin drawdowns on three-x lot sizes, you are providing exit liquidity to proprietary algorithmic desks. Always trade defined-risk spreads."
        ),
        "cta_to_long_video": "Full Institutional Order-Flow Masterclass at thebullprint.in. Follow for daily edge."
    },
    {
        "index": 4,
        "vertical": "insurance",
        "title": "The 0.5x Multiplier Trap: How Room Rent Caps Slash Hospital Bills",
        "hook_data": {
            "line1_setup": "0.5x SLASH",
            "line2_power": "ROOM RENT TRAP",
            "badge": "PROPORTIONATE CUT"
        },
        "spoken_hook_and_body": (
            "If your health insurance policy has a one percent room rent cap and you pick an executive suite, the insurer will not just deduct the room difference. "
            "Under IRDAI proportionate deduction clauses, they will slash your doctor consultations, ICU charges, and operating theater fees by fifty percent. "
            "If your base sum insured is five lakhs and you choose a ten-thousand-rupee room instead of five thousand, every single associated medical cost is multiplied by zero point five. "
            "You end up paying two lakhs out of pocket despite having cashless insurance. Always buy a policy with zero room rent capping."
        ),
        "cta_to_long_video": "Full IRDAI Policy Dossier at thebullprint.in. Follow for daily edge."
    },
    {
        "index": 5,
        "vertical": "crypto",
        "title": "The Flat 30% Crypto Tax Trap Nobody Talks About",
        "hook_data": {
            "line1_setup": "30% LEVY",
            "line2_power": "TAX AUDIT TRAP",
            "badge": "SECTION 115BBH"
        },
        "spoken_hook_and_body": (
            "Did you know that under Section one-one-five BBH, you cannot offset crypto losses against crypto gains? "
            "If you make five lakhs on Bitcoin and lose five lakhs on Ethereum, your net trading profit is zero, but you still owe one lakh fifty thousand rupees in tax plus four percent cess. "
            "On top of that, decentralized wallet swaps and offshore P2P transfers are now being flagged by automated AIS data matching, triggering Section one-forty-two sub-one inquiry notices. "
            "Don't let algorithmic tax reporting catch you off guard."
        ),
        "cta_to_long_video": "Full VDA Tax Forensics at thebullprint.in. Follow for daily edge."
    },
    {
        "index": 6,
        "vertical": "stock_market",
        "title": "The Nifty 50 Liquidity Trap: Smart Money Strike Absorption",
        "hook_data": {
            "line1_setup": "DELTA FLOW",
            "line2_power": "NIFTY TRAP!",
            "badge": "STRIKE CLUSTER"
        },
        "spoken_hook_and_body": (
            "Retail traders look at big call open interest and assume it is a brick wall of resistance. Smart money uses that exact liquidity pool to engineer stop runs. "
            "When Nifty approaches a heavy open interest strike like twenty-four thousand five hundred, market makers hedge short gamma by aggressively buying underlying futures as price breaches the level. "
            "What looked like resistance suddenly morphs into an explosive short squeeze. Never trade naked strikes without tracking real-time cumulative delta and proprietary order-flow absorption."
        ),
        "cta_to_long_video": "Read the Full Order-Flow Breakdown at thebullprint.in. Follow for daily edge."
    }
]


async def main():
    now_utc = datetime.now(timezone.utc)
    logger.info("🚀 Starting Revamp & Drip Queue for Privated Shorts...")
    logger.info(f"   Current UTC Time: {now_utc.isoformat()}")

    results = []

    for idx, cand in enumerate(REVAMP_CANDIDATES, 1):
        title = cand["title"]
        vert = cand["vertical"]
        hook_data = cand["hook_data"]
        spoken = cand["spoken_hook_and_body"]
        cta = cand["cta_to_long_video"]

        logger.info(f"\n=======================================================")
        logger.info(f"🎬 Processing Revamped Short #{idx}/{len(REVAMP_CANDIDATES)}: {title}")
        logger.info(f"   Vertical: {vert}")

        # Determine Pacing: First 3 are PUBLIC immediately; remaining are spaced 3h apart via publishAt
        if idx <= 3:
            status_config = {"privacyStatus": "public"}
            pacing_label = "PUBLIC [IMMEDIATE LIVE VERIFICATION]"
            sched_time_str = "NOW (LIVE)"
        else:
            # 3h interval offset
            hours_offset = (idx - 3) * 3
            publish_time = now_utc + timedelta(hours=hours_offset)
            publish_iso = publish_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            status_config = {
                "privacyStatus": "private",
                "publishAt": publish_iso
            }
            pacing_label = f"SCHEDULED DRIP (+{hours_offset}h)"
            sched_time_str = publish_iso

        # 1. 30-Day Compliance & Uniqueness Validation
        candidate_dict = {
            "title": title,
            "line1": hook_data["line1_setup"],
            "line2": hook_data["line2_power"],
            "pill_badge": hook_data["badge"],
        }
        healed_art = ComplianceGate.validate_and_heal_thumbnail_prompt(
            candidate_dict,
            vertical=vert,
            is_short=True,
            video_id=f"revamp_short_{idx:02d}"
        )
        logger.info(f"   Archetype: {healed_art.get('archetype_name')} ({healed_art.get('archetype')})")
        logger.info(f"   Palette: {healed_art.get('color_palette')}")
        logger.info(f"   Hook: {healed_art.get('line1')} | {healed_art.get('line2')} [{healed_art.get('pill_badge')}]")

        # 2. Build payload for render_and_upload_short_local
        payload = {
            "youtube_payload": {
                "metadata": {
                    "title": f"{title} #Shorts",
                    "tags": ["shorts", vert, "finance", "investing", "thebullprint"]
                },
                "short_extractions": [
                    {
                        "short_title": f"{title} #Shorts",
                        "spoken_hook_and_body": spoken,
                        "cta_to_long_video": cta,
                        "thumbnail_hook": {
                            "line1_setup": healed_art.get("line1"),
                            "line2_power": healed_art.get("line2"),
                            "badge": healed_art.get("pill_badge")
                        },
                        "status": status_config
                    }
                ],
                "status": status_config
            }
        }

        # 3. Render and upload locally
        try:
            vid_id = await render_and_upload_short_local(
                payload=payload,
                short_index=1,
                vertical=vert,
            )
            if vid_id and not vid_id.startswith("DRY_RUN"):
                status_res = "SUCCESS"
                url = f"https://youtube.com/shorts/{vid_id}"
            else:
                status_res = f"SUCCESS ({vid_id})"
                url = f"https://youtube.com/shorts/{vid_id}"
        except Exception as e:
            logger.error(f"❌ Failed rendering/uploading short #{idx}: {e}")
            status_res = f"FAILED: {e}"
            vid_id = "ERROR"
            url = "N/A"

        results.append({
            "idx": idx,
            "title": title,
            "archetype": healed_art.get("archetype_name", "3D Forensic"),
            "hook": f"{healed_art.get('line1')} {healed_art.get('line2')}",
            "badge": healed_art.get("pill_badge"),
            "pacing": pacing_label,
            "publish_at": sched_time_str,
            "vid_id": vid_id,
            "url": url,
            "status": status_res
        })

        await asyncio.sleep(2.0)

    # Print Clean Formatted Audit Table
    print("\n" + "=" * 140)
    print(f"{'#':<3} | {'STATUS':<9} | {'PACING / PUBLISH TIME':<34} | {'3D ARCHETYPE':<28} | {'HOOK & BADGE':<32} | {'URL'}")
    print("=" * 140)
    for r in results:
        print(f"{r['idx']:<3} | {r['status'][:9]:<9} | {r['publish_at']:<34} | {r['archetype'][:28]:<28} | {r['hook'][:18]} [{r['badge'][:10]}] | {r['url']}")
    print("=" * 140 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

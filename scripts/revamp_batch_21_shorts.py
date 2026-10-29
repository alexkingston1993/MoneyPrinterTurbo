#!/usr/bin/env python3
"""
scripts/revamp_batch_21_shorts.py
Revamps remaining 21 privated Shorts (completing 1-to-1 replacement of all 27 privated videos)
with 100% Cloned Arjun voice, 30-Day Compliance-approved 3D visuals & persistent 3D headers,
uncropped glassmorphic chart cards, and automated 3-hour drip scheduling.

Pacing continues from Short #6 (+9h):
- Short #7: +12h UTC
- Short #8: +15h UTC
...
- Short #27: +72h UTC
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

# 21 Unique Institutional Topics (7 Stock Market, 7 Crypto, 7 Insurance)
BATCH_21_CANDIDATES = [
    # 7. Crypto: Blockchain Transparency & Whale Tracking
    {
        "index": 7,
        "vertical": "crypto",
        "title": "On-Chain Whale Alert: How Exchange Inflows Signal Dumps",
        "hook_data": {
            "line1_setup": "WHALE INFLOW",
            "line2_power": "ON-CHAIN ALERT",
            "badge": "WALLET FORENSICS"
        },
        "spoken_hook_and_body": (
            "When retail traders look at price candles, whales look at on-chain wallet movements. "
            "Large holders do not keep trading inventory on centralized exchanges; they store assets in multi-signature cold storage. "
            "When twenty thousand Bitcoin suddenly moves from an unlabelled whale wallet onto Binance or Coinbase, that is not an investment—that is collateral positioning for a spot market dump. "
            "By monitoring mempool transactions and exchange reserve balances on Glassnode, proprietary desks exit longs before retail order books get slammed. Always monitor exchange net flows."
        ),
        "cta_to_long_video": "Full On-Chain Whale Dossier at thebullprint.in. Follow for daily edge."
    },
    # 8. Insurance: Cashless Rejections & Network Hospital Rules
    {
        "index": 8,
        "vertical": "insurance",
        "title": "Why Cashless Hospitalization Claims Get Rejected at Admission",
        "hook_data": {
            "line1_setup": "TPA REJECTION",
            "line2_power": "CASHLESS DENIED",
            "badge": "NETWORK HOSPITAL RULES"
        },
        "spoken_hook_and_body": (
            "Arriving at a network hospital does not guarantee cashless admission. Third-Party Administrators reject cashless pre-authorization in twenty percent of cases during the first six hours. "
            "Why? Because hospitals submit provisional codes with incomplete clinical summaries. "
            "Insurers invoke policy clause six, demanding primary treatment records before committing funds. "
            "A cashless denial is not a claim repudiation; it simply converts your claim into reimbursement mode. "
            "Always retain every single pharmacy bill, diagnostic film, and discharge summary to ensure total reimbursement recovery from the insurer."
        ),
        "cta_to_long_video": "Read the Hospital TPA Audit Dossier at thebullprint.in. Follow for daily edge."
    },
    # 9. Stock Market: Naked Short Strangles & Margin Spikes
    {
        "index": 9,
        "vertical": "stock_market",
        "title": "Naked Short Strangles: The Hidden Margin Multiplier",
        "hook_data": {
            "line1_setup": "MARGIN SURGE",
            "line2_power": "STRANGLE MATH",
            "badge": "GAMMA DRAWDOWN"
        },
        "spoken_hook_and_body": (
            "Option sellers love selling out-of-the-money strangles for theta decay, until a volatility event strikes. "
            "Under exchange SPAN margin systems, margin requirements are not fixed. "
            "When India VIX surges from twelve to eighteen, overnight margin on naked option positions can jump by seventy percent within minutes. "
            "If your account has insufficient free cash collateral, broker risk management systems automatically square off your positions at market price at the absolute worst possible moment. "
            "Never sell unhedged strangles; always buy deep out-of-the-money wings to cap peak portfolio margin expansion."
        ),
        "cta_to_long_video": "Full Institutional Options Greek Masterclass at thebullprint.in. Follow for daily edge."
    },
    # 10. Crypto: Spot vs Perpetual CVD Divergence
    {
        "index": 10,
        "vertical": "crypto",
        "title": "CVD Divergence: How Smart Money Spots Fake Breakouts",
        "hook_data": {
            "line1_setup": "DELTA DIVERGENCE",
            "line2_power": "CVD SIGNALS",
            "badge": "SPOT VS PERP"
        },
        "spoken_hook_and_body": (
            "When Bitcoin breaks out to new highs, do not trust price action alone. Check Cumulative Volume Delta across spot and perpetual markets. "
            "If perpetual futures delta is aggressively positive but spot delta is declining, retail leverage is chasing the pump while institutional spot desks are distributing inventory into retail bids. "
            "This spot-perp CVD divergence is the single most reliable precursor to a violent long squeeze. "
            "Real structural rallies require aggressive market orders on underlying spot exchanges. "
            "Track spot versus perp delta before entering breakout trades."
        ),
        "cta_to_long_video": "Full CVD Order-Flow Breakdown at thebullprint.in. Follow for daily edge."
    },
    # 11. Insurance: Pre-Existing Disease Waiting Periods
    {
        "index": 11,
        "vertical": "insurance",
        "title": "The 36-Month Pre-Existing Disease Rule Under New IRDAI Norms",
        "hook_data": {
            "line1_setup": "36-MONTH NORM",
            "line2_power": "WAITING PERIOD",
            "badge": "IRDAI REFORM 2024"
        },
        "spoken_hook_and_body": (
            "Under landmark IRDAI regulatory updates, maximum pre-existing disease waiting periods have been reduced from forty-eight months down to thirty-six months across all retail health policies. "
            "Furthermore, any medical condition diagnosed more than thirty-six months before policy inception cannot be used by insurers to reject genuine hospitalization claims. "
            "If your insurer attempts to cite five-year-old medical history that was never disclosed, quote the revised IRDAI Master Circular on health insurance underwriting. "
            "Always verify your waiting period transition schedule."
        ),
        "cta_to_long_video": "Read the Full IRDAI Policy Dossier at thebullprint.in. Follow for daily edge."
    },
    # 12. Stock Market: Smart Money Order Flow & Delta Absorption
    {
        "index": 12,
        "vertical": "stock_market",
        "title": "Order-Flow Footprints: How Institutions Absorb Liquidity",
        "hook_data": {
            "line1_setup": "DELTA ABSORPTION",
            "line2_power": "ORDER FLOW",
            "badge": "POC ACCUMULATION"
        },
        "spoken_hook_and_body": (
            "Traditional candlestick charts only show you where price traveled; footprint charts show you who won the battle at every bid and ask. "
            "When aggressive retail selling fails to push price lower at key support, that is passive institutional limit buying absorbing every single market sell order. "
            "You will see extreme negative delta coupled with zero downward price progress. "
            "Once retail liquidity runs completely dry, the market maker turns price around with explosive upward velocity. "
            "Learn to trade liquidity absorption, not lagging chart indicators."
        ),
        "cta_to_long_video": "Full Order-Flow Masterclass at thebullprint.in. Follow for daily edge."
    },
    # 13. Stock Market: Gamma Scalping vs Directional Risk
    {
        "index": 13,
        "vertical": "stock_market",
        "title": "The Gamma Playbook: How Market Makers Hedge Zero-DTE Expiries",
        "hook_data": {
            "line1_setup": "GAMMA SPIKE",
            "line2_power": "ZERO-DTE MATH",
            "badge": "OPTION DELTA RUN"
        },
        "spoken_hook_and_body": (
            "On expiry days, option gamma approaches infinity for strikes near the money. "
            "A tiny five-point move in Nifty can double an option delta from zero point two to zero point four in seconds. "
            "Market makers who sold those options are forced to rapidly buy or sell underlying futures to remain delta-neutral. "
            "This mandatory hedging creates an algorithmic feedback loop, accelerating intraday momentum and producing outsized zero-hero price surges. "
            "Never trade zero-DTE options without understanding dealer gamma exposure."
        ),
        "cta_to_long_video": "Read the Full Market Maker Greek Guide at thebullprint.in. Follow for daily edge."
    },
    # 14. Insurance: Co-Payment Clauses
    {
        "index": 14,
        "vertical": "insurance",
        "title": "The 20% Co-Payment Clause: How Insurers Cut Big Claim Payouts",
        "hook_data": {
            "line1_setup": "20% DEDUCTION",
            "line2_power": "CO-PAY MATH",
            "badge": "POLICY CLAUSE AUDIT"
        },
        "spoken_hook_and_body": (
            "Cheap health insurance premiums often hide a devastating twenty percent mandatory co-payment clause. "
            "If your hospital bill reaches ten lakh rupees, a twenty percent co-pay means you must pay two lakh rupees completely out of pocket before the insurer releases a single rupee. "
            "Worse, co-pay applies after non-payable medical deductions and room rent prorations are already slashed from your claim. "
            "Never compromise on lifetime savings just to save five thousand rupees on annual premium. Always demand zero co-pay policies."
        ),
        "cta_to_long_video": "Full Policy Forensic Dossier at thebullprint.in. Follow for daily edge."
    },
    # 15. Crypto: Liquidation Heatmap Clusters
    {
        "index": 15,
        "vertical": "crypto",
        "title": "Liquidation Heatmaps: The Magnet Pulling Crypto Prices",
        "hook_data": {
            "line1_setup": "LIQUIDATION CLUSTERS",
            "line2_power": "HEATMAP AUDIT",
            "badge": "STOP RUN MAGNET"
        },
        "spoken_hook_and_body": (
            "Crypto market makers do not guess where price is going; they hunt resting liquidation pools. "
            "When high-leverage traders cluster twenty-x and fifty-x long positions around fifty-eight thousand dollars, liquidation heatmaps glow bright yellow. "
            "That concentrated cluster represents guaranteed market sell orders waiting to be triggered. "
            "Price is naturally drawn to these liquidity pockets like a magnet to clear open interest before the real trend resumes. "
            "Before entering swing trades, check high-density liquidation zones on CoinGlass."
        ),
        "cta_to_long_video": "Full Liquidation Analysis at thebullprint.in. Follow for daily edge."
    },
    # 16. Stock Market: Institutional Block Deals & Dark Pools
    {
        "index": 16,
        "vertical": "stock_market",
        "title": "Block Deals Decoded: Tracking FII Institutional Accumulation",
        "hook_data": {
            "line1_setup": "BLOCK WINDOW",
            "line2_power": "INSTITUTIONAL FLOW",
            "badge": "FII ACCUMULATION"
        },
        "spoken_hook_and_body": (
            "Did you know institutional funds trade billions of rupees without moving retail stock charts by a single paise? "
            "Between eight forty-five and nine AM, institutional desks utilize exchange block deal windows to execute matched cross-orders at negotiated benchmark prices. "
            "When Foreign Institutional Investors execute substantial block purchases in frontline banking or IT stocks, it indicates multi-quarter structural accumulation. "
            "Tracking end-of-day block deal disclosures reveals where smart money is deploying institutional capital long before retail breakout patterns form."
        ),
        "cta_to_long_video": "Full Institutional Flow Dossier at thebullprint.in. Follow for daily edge."
    },
    # 17. Insurance: Consumables & Non-Payable Hospital Deductions
    {
        "index": 17,
        "vertical": "insurance",
        "title": "The Consumables Trap: Why Cashless Policies Leave You Paying 15%",
        "hook_data": {
            "line1_setup": "15% UNPAID",
            "line2_power": "CONSUMABLES CUT",
            "badge": "NON-PAYABLE ITEMS"
        },
        "spoken_hook_and_body": (
            "You have full cashless health insurance, yet the hospital demands seventy thousand rupees upon discharge. "
            "Under standard health policies, over sixty common hospital items—including surgical gloves, PPE kits, nebulizer masks, and administrative registration charges—are classified as non-payable consumables. "
            "On a five-lakh-rupee surgery, consumables easily account for ten to fifteen percent of the total bill. "
            "To achieve true zero out-of-pocket cashless coverage, always add an inexpensive Consumables Protection Rider to your health policy."
        ),
        "cta_to_long_video": "Full Health Insurance Rider Audit at thebullprint.in. Follow for daily edge."
    },
    # 18. Crypto: CME Futures Gaps & Weekend Arbitrage
    {
        "index": 18,
        "vertical": "crypto",
        "title": "CME Futures Gaps: Why Bitcoin Rallies Return to Weekend Levels",
        "hook_data": {
            "line1_setup": "CME GAP",
            "line2_power": "FUTURES ARBITRAGE",
            "badge": "ALGO REBALANCE"
        },
        "spoken_hook_and_body": (
            "Crypto spot trades twenty-four seven, but the Chicago Mercantile Exchange Bitcoin futures market closes on Friday evening and reopens on Sunday night. "
            "When Bitcoin moves violently over the weekend, a substantial price gap forms on the CME charts. "
            "Historically, over eighty percent of these CME gaps eventually fill as institutional market makers arbitrage spot basis against futures contracts during regular Chicago trading hours. "
            "Never assume weekend pumps are definitive without monitoring Sunday night CME gap fills."
        ),
        "cta_to_long_video": "Full CME Basis Dossier at thebullprint.in. Follow for daily edge."
    },
    # 19. Stock Market: Expiry Day Zero-Hero Option Decay
    {
        "index": 19,
        "vertical": "stock_market",
        "title": "The Zero-Hero Option Trap: The Mathematics of Theta Decay",
        "hook_data": {
            "line1_setup": "THETA CRUSH",
            "line2_power": "ZERO-HERO MATH",
            "badge": "EXPIRY VOLATILITY"
        },
        "spoken_hook_and_body": (
            "Every Thursday afternoon, retail traders buy five-rupee out-of-the-money options hoping for a ten-x zero-hero jackpot. "
            "Statistically, over ninety-four percent of those cheap options expire completely worthless at three-thirty PM. "
            "On expiry afternoon, extrinsic time value decays non-linearly. Unless underlying index velocity is exceptionally explosive, theta decay silently consumes option premiums within twenty minutes. "
            "Proprietary algorithmic desks collect those retail lottery tickets every single week. "
            "Trade high-probability credit spreads instead of buying hopeless expiry lottery tickets."
        ),
        "cta_to_long_video": "Full Expiry Theta Strategy at thebullprint.in. Follow for daily edge."
    },
    # 20. Insurance: Critical Illness vs Mediclaim
    {
        "index": 20,
        "vertical": "insurance",
        "title": "Critical Illness vs Mediclaim: The Thirty-Day Survival Clause",
        "hook_data": {
            "line1_setup": "30-DAY CLAUSE",
            "line2_power": "POLICY AUDIT",
            "badge": "CRITICAL ILLNESS"
        },
        "spoken_hook_and_body": (
            "Mediclaim pays your actual hospital bills upon submission of medical invoices, but Critical Illness insurance pays a fixed lump-sum cash benefit upon diagnosis of major covered diseases like cancer or stroke. "
            "However, critical illness policies carry a strict thirty-day survival clause. "
            "If the insured does not survive thirty days post-formal medical diagnosis, the critical illness claim is denied. "
            "Understanding the distinct legal definitions between indemnity hospital policies and fixed-benefit critical illness plans is essential for family protection."
        ),
        "cta_to_long_video": "Full Critical Illness Audit at thebullprint.in. Follow for daily edge."
    },
    # 21. Crypto: Negative Funding Rate Inversions
    {
        "index": 21,
        "vertical": "crypto",
        "title": "Negative Funding Rates: Why Extreme Bearish Sentiment Sparks Squeezes",
        "hook_data": {
            "line1_setup": "NEGATIVE RATES",
            "line2_power": "SHORT SQUEEZE",
            "badge": "PERP INVERSION"
        },
        "spoken_hook_and_body": (
            "When perpetual swap funding rates flip deeply negative, shorts pay longs every eight hours just to maintain their bearish bets. "
            "This indicates retail traders are aggressively panic-shorting at market lows. "
            "For institutional market makers, deeply negative funding is an invitation to engineer a violent short squeeze. "
            "By buying spot inventory and forcing price above key resistance, market makers trigger stop-losses and forced liquidations, igniting explosive cascading rallies. "
            "Never short when funding rates are deeply inverted."
        ),
        "cta_to_long_video": "Full Perp Dynamics at thebullprint.in. Follow for daily edge."
    },
    # 22. Stock Market: FII Index Long-Short Ratio
    {
        "index": 22,
        "vertical": "stock_market",
        "title": "FII Long-Short Ratio: The Ultimate Institutional Macro Indicator",
        "hook_data": {
            "line1_setup": "FII RATIO",
            "line2_power": "INDEX SIGNALS",
            "badge": "DERIVATIVE MACRO"
        },
        "spoken_hook_and_body": (
            "Every evening after market close, the exchange publishes detailed participant-wise open interest data. "
            "By tracking the Foreign Institutional Investors' Long-Short Ratio in index futures, you get a clear look at global hedge fund positioning. "
            "When the FII long-short ratio drops below twenty percent, market positioning is oversold and ripe for a violent short squeeze rally. "
            "When the ratio surges above eighty percent, markets are euphoric and vulnerable to aggressive profit booking. "
            "Always track participant open interest before placing swing trades."
        ),
        "cta_to_long_video": "Full FII Positioning Breakdown at thebullprint.in. Follow for daily edge."
    },
    # 23. Insurance: Policy Portability Rules
    {
        "index": 23,
        "vertical": "insurance",
        "title": "Health Insurance Portability: How to Switch Without Losing Credits",
        "hook_data": {
            "line1_setup": "PORTABILITY NORM",
            "line2_power": "CREDIT SHIELD",
            "badge": "IRDAI CLAUSE 14"
        },
        "spoken_hook_and_body": (
            "Unsatisfied with your health insurance provider? Under IRDAI portability regulations, you can switch insurers while retaining one hundred percent of your accrued waiting period credits. "
            "If you completed thirty-six months with your previous insurer, your new insurer cannot restart pre-existing disease waiting periods. "
            "However, you must submit your portability application at least forty-five days prior to your policy renewal date. "
            "Missing that regulatory window forces you into standard renewal. Protect your accumulated waiting period credits when upgrading coverage."
        ),
        "cta_to_long_video": "Full Portability Checklist at thebullprint.in. Follow for daily edge."
    },
    # 24. Crypto: Cold Storage vs Proof-of-Reserves
    {
        "index": 24,
        "vertical": "crypto",
        "title": "Proof of Reserves vs Real Audits: What Exchanges Won't Tell You",
        "hook_data": {
            "line1_setup": "MERKLE TREE",
            "line2_power": "RESERVE AUDIT",
            "badge": "LIABILITY GAP"
        },
        "spoken_hook_and_body": (
            "Crypto exchanges publish cryptographic Merkle Tree Proof of Reserves and claim customer deposits are one hundred percent safe. "
            "That is only half the financial equation. "
            "Proof of Reserves only shows on-chain assets; it reveals absolutely nothing about corporate off-chain liabilities, outstanding corporate debt, or undocumented re-hypothecation. "
            "Unless an exchange provides a comprehensive liabilities audit conducted by an independent forensic accounting firm, your funds are exposed to institutional counterparty risk. "
            "Not your keys, not your crypto."
        ),
        "cta_to_long_video": "Full Exchange Solvency Dossier at thebullprint.in. Follow for daily edge."
    },
    # 25. Stock Market: Implied Volatility Crush
    {
        "index": 25,
        "vertical": "stock_market",
        "title": "The IV Crush Trap: Why Options Lose Value Even When You Are Right",
        "hook_data": {
            "line1_setup": "IV CRUSH",
            "line2_power": "VOLATILITY MATH",
            "badge": "VEGA EXPIRY"
        },
        "spoken_hook_and_body": (
            "You predicted strong earnings, the stock gapped up three percent, and your call option still lost forty percent of its value. "
            "Welcome to the Implied Volatility crush. "
            "Leading into high-stakes binary events like earnings or budget announcements, option demand inflates implied volatility to extreme levels. "
            "The moment the news is announced, event uncertainty evaporates and implied volatility collapses immediately. "
            "That rapid drop in vega completely destroys option premium regardless of stock direction. Always trade volatility, not just price."
        ),
        "cta_to_long_video": "Full Vega Volatility Guide at thebullprint.in. Follow for daily edge."
    },
    # 26. Insurance: AYUSH & Alternative Medicine Limits
    {
        "index": 26,
        "vertical": "insurance",
        "title": "The AYUSH Sub-Limit Trap: Ayurveda Hospital Bill Reductions",
        "hook_data": {
            "line1_setup": "AYUSH LIMIT",
            "line2_power": "POLICY SUB-CAP",
            "badge": "ALTERNATIVE CLAIMS"
        },
        "spoken_hook_and_body": (
            "IRDAI mandates coverage for alternative medicine including Ayurveda, Yoga, Unani, Siddha, and Homeopathy. "
            "However, many policies embed severe sub-limits, capping AYUSH treatments at ten to twenty percent of your base sum insured. "
            "Additionally, treatment is only covered if performed at a government-recognized healthcare institute with minimum bed capacities. "
            "A two-lakh-rupee Ayurvedic hospitalization can result in an unexpected eighty percent out-of-pocket shortfall if your policy carries an AYUSH sub-cap. Always inspect your policy schedule."
        ),
        "cta_to_long_video": "Read the Policy Sub-Limit Guide at thebullprint.in. Follow for daily edge."
    },
    # 27. Stock Market: Volume Profile Point of Control
    {
        "index": 27,
        "vertical": "stock_market",
        "title": "Point of Control: How Smart Money Uses Volume Profiles",
        "hook_data": {
            "line1_setup": "VOLUME POC",
            "line2_power": "VALUE AREA",
            "badge": "AUCTION THEORY"
        },
        "spoken_hook_and_body": (
            "Standard volume bars tell you how much volume traded across time. Volume Profile tells you where volume traded across price. "
            "The Point of Control is the exact price level where the highest volume of shares changed hands during the session. "
            "It represents fair institutional value. When price deviates outside the Value Area, responsive smart money buyers step in, driving price right back to the Point of Control. "
            "Stop looking at basic horizontal lines; use volume profile auction market theory to trade alongside institutional capital."
        ),
        "cta_to_long_video": "Read the Full Volume Profile Masterclass at thebullprint.in. Follow for daily edge."
    }
]


async def main():
    now_utc = datetime.now(timezone.utc)
    logger.info("🚀 Starting 21-Short Batch Revamp (Shorts #7 to #27)...")
    logger.info(f"   Current UTC Time: {now_utc.isoformat()}")

    results = []

    for idx_offset, cand in enumerate(BATCH_21_CANDIDATES, 1):
        global_short_num = cand["index"]  # 7 through 27
        title = cand["title"]
        vert = cand["vertical"]
        hook_data = cand["hook_data"]
        spoken = cand["spoken_hook_and_body"]
        cta = cand["cta_to_long_video"]

        logger.info(f"\n==========================================================================")
        logger.info(f"🎬 Processing Revamped Short #{global_short_num}/27: {title}")
        logger.info(f"   Vertical: {vert}")

        # Pacing: Spaced 3 hours apart continuing from Short #6 (+9h -> +12h, +15h, ..., +72h)
        hours_offset = 9 + (idx_offset * 3)
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
            video_id=f"revamp_short_{global_short_num:02d}"
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
            logger.error(f"❌ Failed rendering/uploading short #{global_short_num}: {e}")
            status_res = f"FAILED: {e}"
            vid_id = "ERROR"
            url = "N/A"

        results.append({
            "idx": global_short_num,
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

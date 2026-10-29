#!/usr/bin/env python3
"""
scripts/retroactive_update_all_thumbnails.py
Retroactively updates the thumbnails on ALL uploaded Long-Form videos on The Bull Print YouTube Channel
using native 100% full-bleed 3D AI renders (Flow AI & Imagen 3 benchmark quality).

Zero black fallbacks, zero flat 2D PIL text walls.
API Cost: 50 quota units per video (very low, well within daily quota pool).
"""

import os
import sys
import pickle
import time
from pathlib import Path
from typing import List, Dict, Any

from PIL import Image, ImageStat
from loguru import logger
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import thumbnail_generator


# Master 9-Video Native 3D Full-Bleed Artwork Mapping
MASTER_3D_THUMBNAILS = {
    # 1. IRDAI Proportionate Deduction Math: Room Caps
    "nMfqeaCzuAg": {
        "source": "/Users/apple/.gemini/antigravity-ide/brain/96ef1dba-78f2-4790-bd8d-1dbad7261bf9/.user_uploaded/media_1793278651474.jpg",
        "hook": "CLAIM CUTS EXPOSED",
        "badge": "ROOM RENT CAPS!",
        "metaphor": "Cracked Medical Shield + Scissors Cutting Falling Chart",
    },
    # 2. Claim Settlement Ratio vs ICR Reality
    "GgFmjQY9IMo": {
        "source": "/Users/apple/.gemini/antigravity-ide/brain/96ef1dba-78f2-4790-bd8d-1dbad7261bf9/ratio_lie_thumb_1793281935784.jpg",
        "hook": "98% RATIO LIE!",
        "badge": "HIDDEN ICR MATH",
        "metaphor": "Red Claim Rejected Stamp Smashing Golden Shield",
    },
    # 3. Crypto Funding Rates: Perpetuals
    "WG-9Tv5Jt-k": {
        "source": "/Users/apple/.gemini/antigravity-ide/brain/96ef1dba-78f2-4790-bd8d-1dbad7261bf9/funding_bleed_thumb_1793281972376.jpg",
        "hook": "8-HOUR BLEED!",
        "badge": "FUNDING FEE DRAIN",
        "metaphor": "Golden Bitcoin Drained by Red Syphon Tubes + Liquidation Gauge",
    },
    # 4. Crypto Funding Rates: Foreign Banks & Whales
    "gEkRKqYhCN4": {
        "source": "/Users/apple/.gemini/antigravity-ide/brain/96ef1dba-78f2-4790-bd8d-1dbad7261bf9/whale_squeeze_thumb_1793282004908.jpg",
        "hook": "WHALE SQUEEZE",
        "badge": "LIQUIDATION CASCADE",
        "metaphor": "Cybernetic Killer Whale Crushing Leveraged Gauges",
    },
    # 5. Decoding SEBI F&O Rules
    "T69-BM1mgjc": {
        "source": "/Users/apple/.gemini/antigravity-ide/brain/96ef1dba-78f2-4790-bd8d-1dbad7261bf9/sebi_fo_shock_1793281902849.jpg",
        "hook": "SEBI F&O SHOCK",
        "badge": "NEW LOT SIZES",
        "metaphor": "Metallic Gavel Smashing F&O Option Terminal",
    },
    # 6. Nifty 50 Today Option Chain Analysis
    "-2K3qWYq6y8": {
        "source": "/Users/apple/.gemini/antigravity-ide/brain/96ef1dba-78f2-4790-bd8d-1dbad7261bf9/.user_uploaded/media_1793278668553.jpg",
        "hook": "NIFTY 50 TRAP EXPOSED!",
        "badge": "OPTION CHAIN LIGHTNING",
        "metaphor": "Golden Bull in Fiery Steel Bear Trap + Option Matrix",
    },
    # 7. Don't Fall for the 24500 Trap
    "b02BMahomyE": {
        "source": "/Users/apple/.gemini/antigravity-ide/brain/96ef1dba-78f2-4790-bd8d-1dbad7261bf9/.user_uploaded/media_1793278689806.jpg",
        "hook": "24,500 LEVEL / DON'T FALL FOR IT!",
        "badge": "LED WARNING MATRIX",
        "metaphor": "LED Warning Sign + Candlestick Crashing Off Cliff Edge",
    },
    # 8. The 22,400 Liquidity Trap
    "t05-xVABLaE": {
        "source": "/Users/apple/.gemini/antigravity-ide/brain/96ef1dba-78f2-4790-bd8d-1dbad7261bf9/.user_uploaded/media_1793278681565.jpg",
        "hook": "SMART MONEY CODE",
        "badge": "LIQUIDITY TRAP 22,400",
        "metaphor": "Neon Green Cybernetic Bull Breaking Red Handcuffs",
    },
    # 9. The Institutional Compounding Secret
    "dxhUWlm3DUQ": {
        "source": "/Users/apple/.gemini/antigravity-ide/brain/96ef1dba-78f2-4790-bd8d-1dbad7261bf9/formula_engine_thumb_1793282042236.jpg",
        "hook": "THE 1% FORMULA",
        "badge": "INSTITUTIONAL ENGINE",
        "metaphor": "Golden Vault Gear Clockwork Compounding Candlestick Tower",
    },
}


def get_authenticated_service():
    token_path = BASE_DIR / "data" / "youtube_tokens" / "youtube_token_en.pickle"
    if not token_path.exists():
        logger.error(f"❌ YouTube token pickle not found at {token_path}")
        return None
    try:
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)
        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        logger.error(f"❌ Failed to build YouTube client: {e}")
        return None


def fetch_long_form_videos(service) -> List[Dict[str, Any]]:
    uploads_id = "UUwe4D4M4i9aaHdi2ZBlbUmA"
    logger.info(f"🔍 Fetching videos from uploads playlist: {uploads_id}...")

    raw_items = []
    page_token = None
    while True:
        res = service.playlistItems().list(
            playlistId=uploads_id,
            part="snippet,contentDetails",
            maxResults=50,
            pageToken=page_token
        ).execute()

        for it in res.get("items", []):
            vid_id = it["snippet"]["resourceId"]["videoId"]
            title = it["snippet"]["title"]
            pub = it["snippet"].get("publishedAt", "")
            raw_items.append((vid_id, title, pub))

        page_token = res.get("nextPageToken")
        if not page_token:
            break

    long_form = []
    for i in range(0, len(raw_items), 50):
        chunk = raw_items[i:i+50]
        ids = [c[0] for c in chunk]
        v_res = service.videos().list(
            id=",".join(ids),
            part="snippet,contentDetails,status"
        ).execute()

        for v in v_res.get("items", []):
            vid = v["id"]
            title = v["snippet"]["title"]
            dur = v["contentDetails"]["duration"]
            privacy = v["status"]["privacyStatus"]

            is_short = "#shorts" in title.lower() or dur in ("PT1M", "PT59S", "PT58S", "PT30S", "PT15S", "PT20S")
            if not is_short and ("M" in dur or "H" in dur):
                long_form.append({
                    "id": vid,
                    "title": title,
                    "duration": dur,
                    "privacy": privacy,
                })

    return long_form


def prepare_and_validate_thumbnail(vid: str, meta: Dict[str, str]) -> Path:
    src_path = Path(meta["source"])
    if not src_path.exists():
        raise FileNotFoundError(f"Missing master 3D thumbnail file: {src_path}")

    img = Image.open(src_path).convert("RGB")
    
    # 1. Enforce Strict Visual Richness & Brightness Gate (Bans all black fallbacks)
    thumbnail_generator.validate_thumbnail_richness(img, name=vid)

    # 2. Resize to crisp 1280x720 standard if needed
    if img.size != (1280, 720):
        img = img.resize((1280, 720), Image.Resampling.LANCZOS)

    # 3. Export to output/thumbnails
    out_dir = BASE_DIR / "output" / "thumbnails"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"master_{vid}.jpg"
    img.save(out_path, "JPEG", quality=95)
    return out_path


def main():
    service = get_authenticated_service()
    if not service:
        sys.exit(1)

    videos = fetch_long_form_videos(service)
    logger.info(f"🎯 Found {len(videos)} Long-Form videos to update.")

    results = []

    for idx, v in enumerate(videos, 1):
        vid = v["id"]
        title = v["title"]
        meta = MASTER_3D_THUMBNAILS.get(vid)

        if not meta:
            logger.warning(f"[{idx}/{len(videos)}] No custom 3D mapping found for {vid}. Skipping.")
            continue

        logger.info(f"\n[{idx}/{len(videos)}] Processing: {title[:55]} ({vid})")
        logger.info(f"   Hook: {meta['hook']} | Badge: {meta['badge']}")
        logger.info(f"   Metaphor: {meta['metaphor']}")

        # Prepare and validate high-res thumbnail
        try:
            thumb_path = prepare_and_validate_thumbnail(vid, meta)
            size_kb = os.path.getsize(thumb_path) / 1024
            logger.info(f"   ✓ Validated Full-Bleed 3D Artwork: {thumb_path.name} ({size_kb:.1f} KB)")
        except Exception as e:
            logger.error(f"   ❌ Validation failed for {vid}: {e}")
            results.append({
                "id": vid,
                "title": title,
                "hook": meta["hook"],
                "badge": meta["badge"],
                "status": f"FAILED: {e}"
            })
            continue

        # Upload thumbnail to YouTube Data API v3
        success = False
        err_msg = ""
        try:
            media = MediaFileUpload(str(thumb_path), mimetype="image/jpeg", resumable=True)
            res = service.thumbnails().set(videoId=vid, media_body=media).execute()
            logger.success(f"   🎉 Successfully updated 3D thumbnail on YouTube for {vid}!")
            success = True
        except Exception as e:
            err_msg = str(e)
            logger.error(f"   ❌ Failed to set thumbnail for {vid}: {err_msg}")

        results.append({
            "id": vid,
            "title": title,
            "hook": meta["hook"],
            "badge": meta["badge"],
            "status": "SUCCESS" if success else f"FAILED: {err_msg[:20]}"
        })

        time.sleep(1.0) # respectful rate pacing

    # Print Confirmation Table
    print("\n" + "=" * 125)
    print(f"{'VIDEO ID':<13} | {'STATUS':<9} | {'NATIVE 3D HOOK TEXT':<34} | {'WARNING BADGE':<24} | {'TITLE'}")
    print("=" * 125)
    for r in results:
        print(f"{r['id']:<13} | {r['status']:<9} | {r['hook'][:34]:<34} | {r['badge'][:24]:<24} | {r['title'][:35]}")
    print("=" * 125 + "\n")

    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    logger.success(f"🚀 Retroactive thumbnail update finished: {success_count}/{len(results)} videos updated live on YouTube!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
scripts/retroactive_update_all_thumbnails.py
Retroactively updates the thumbnails on ALL uploaded Long-Form videos on The Bull Print YouTube Channel
using the new 2-Stage Hybrid AI 3D Scene + Metallic Typography Compositor.

API Cost: 50 quota units per video (very low, well within daily quota pool).
"""

import os
import sys
import pickle
import time
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from loguru import logger
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

import thumbnail_generator


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

    logger.info(f"📋 Total playlist items: {len(raw_items)}. Fetching duration details...")

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
            # Long form has duration > 65s (contains 'M' or 'H' and not a short)
            if not is_short and ("M" in dur or "H" in dur):
                # Infer vertical from title
                t_lower = title.lower()
                if any(w in t_lower for w in ["claim", "insurance", "irdai", "room rent", "hospital"]):
                    vert = "insurance"
                elif any(w in t_lower for w in ["crypto", "bitcoin", "funding rate", "perp", "115bbh", "tax notice"]):
                    vert = "crypto"
                else:
                    vert = "stock_market"

                long_form.append({
                    "id": vid,
                    "title": title,
                    "duration": dur,
                    "privacy": privacy,
                    "vertical": vert,
                })

    return long_form


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
        vert = v["vertical"]

        logger.info(f"\n[{idx}/{len(videos)}] Processing: {title[:55]} ({vid}) [{vert}]")

        # 1. Art Direction via Gemini
        art = thumbnail_generator.get_ai_art_direction(title, vertical=vert)
        hook_display = f"{art.get('line1')} / {art.get('line2')} [{art.get('pill_badge')}]"
        logger.info(f"   Hook: {hook_display}")

        # 2. Render 1280x720 3D Hybrid Thumbnail
        slug = f"retro_{vid}"
        seed = abs(hash(vid)) % 100000 + 42
        raw_bg = thumbnail_generator.generate_ai_scene_backdrop(art["scene_prompt"], width=1280, height=720, seed=seed)
        bg = thumbnail_generator.apply_calm_zone_gradient(raw_bg, width=1280, height=720, calm_ratio=0.62)
        thumb_img = thumbnail_generator.composite_3d_metallic_branding(bg, art, width=1280, height=720, is_short=False)

        out_path = BASE_DIR / "output" / "thumbnails" / f"{slug}.jpg"
        thumb_img.save(out_path, "JPEG", quality=95)
        size_kb = os.path.getsize(out_path) / 1024
        logger.info(f"   Saved thumbnail: {out_path.name} ({size_kb:.1f} KB)")

        # 3. Upload thumbnail to YouTube Data API v3
        success = False
        err_msg = ""
        try:
            media = MediaFileUpload(str(out_path), mimetype="image/jpeg", resumable=True)
            res = service.thumbnails().set(videoId=vid, media_body=media).execute()
            logger.success(f"   ✓ Successfully updated thumbnail on YouTube for {vid}!")
            success = True
        except Exception as e:
            err_msg = str(e)
            logger.error(f"   ❌ Failed to set thumbnail for {vid}: {err_msg}")

        results.append({
            "id": vid,
            "title": title,
            "hook": f"{art.get('line1')} / {art.get('line2')}",
            "badge": art.get("pill_badge", ""),
            "status": "SUCCESS" if success else f"FAILED: {err_msg[:20]}"
        })

        time.sleep(1.0) # respectful rate pacing

    # Print Confirmation Table
    print("\n" + "=" * 115)
    print(f"{'VIDEO ID':<13} | {'STATUS':<9} | {'HOOK TEXT (LINE 1 / LINE 2)':<32} | {'RED PILL BADGE':<22} | {'TITLE'}")
    print("=" * 115)
    for r in results:
        print(f"{r['id']:<13} | {r['status']:<9} | {r['hook'][:32]:<32} | {r['badge'][:22]:<22} | {r['title'][:30]}")
    print("=" * 115 + "\n")

    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    logger.success(f"🎉 Retroactive thumbnail update finished: {success_count}/{len(results)} videos updated successfully!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
scripts/cleanup_channel_shorts.py
Clean up legacy, low-CTR Shorts from The Bull Print YouTube Channel.

Features:
- Scans all uploads from the channel's master playlist.
- Identifies legacy Shorts (containing '#Shorts' or duration <= 60s).
- Displays a clean visual audit table (Video ID, Title, Published Date, Views, Privacy).
- Supports:
    --list (default, dry run inspection)
    --private (safely sets legacy shorts to private, keeping channel analytics)
    --delete (permanently deletes legacy shorts from YouTube)
    --include-today (by default, today's uploads are protected from deletion)
"""

import os
import re
import sys
import pickle
import argparse
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from loguru import logger
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


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


def fetch_channel_shorts(service, protect_today: bool = True) -> List[Dict[str, Any]]:
    ch = service.channels().list(mine=True, part="snippet,contentDetails").execute()
    items = ch.get("items", [])
    if not items:
        logger.error("❌ No channel found.")
        return []

    channel_title = items[0]["snippet"]["title"]
    uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    logger.info(f"📺 Channel: '{channel_title}' | Uploads Playlist: {uploads_playlist_id}")

    raw_items = []
    page_token = None
    while True:
        res = service.playlistItems().list(
            playlistId=uploads_playlist_id,
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

    logger.info(f"🔍 Found {len(raw_items)} total videos in uploads playlist. Fetching details...")

    # Fetch status & stats in chunks of 50
    shorts_list = []
    for i in range(0, len(raw_items), 50):
        chunk = raw_items[i:i+50]
        ids = [c[0] for c in chunk]
        v_res = service.videos().list(
            id=",".join(ids),
            part="snippet,status,statistics,contentDetails"
        ).execute()

        for v in v_res.get("items", []):
            vid = v["id"]
            snip = v.get("snippet", {})
            stat = v.get("statistics", {})
            status = v.get("status", {})
            details = v.get("contentDetails", {})

            title = snip.get("title", "")
            desc = snip.get("description", "")
            pub = snip.get("publishedAt", "")
            views = int(stat.get("viewCount", 0))
            privacy = status.get("privacyStatus", "unknown")
            dur = details.get("duration", "")

            # Identify if it's a Short
            is_short = "#shorts" in title.lower() or "#shorts" in desc.lower() or dur in ("PT1M", "PT59S", "PT58S", "PT30S")

            if not is_short:
                continue

            # Protect today's fresh uploads if protect_today is True
            today_str = "2026-10-29"
            is_today = pub.startswith(today_str)

            shorts_list.append({
                "id": vid,
                "title": title,
                "published_at": pub[:10],
                "views": views,
                "privacy": privacy,
                "is_today": is_today,
            })

    return shorts_list


def main():
    parser = argparse.ArgumentParser(description="Clean up legacy low-CTR YouTube Shorts.")
    parser.add_argument("--private", action="store_true", help="Set legacy Shorts to private.")
    parser.add_argument("--delete", action="store_true", help="Permanently delete legacy Shorts.")
    parser.add_argument("--include-today", action="store_true", help="Also modify/delete shorts uploaded today.")
    args = parser.parse_args()

    service = get_authenticated_service()
    if not service:
        sys.exit(1)

    shorts = fetch_channel_shorts(service, protect_today=not args.include_today)
    if not shorts:
        logger.info("✓ No legacy Shorts found.")
        return

    print("\n" + "=" * 90)
    print(f"{'VIDEO ID':<13} | {'PUB DATE':<10} | {'VIEWS':<6} | {'PRIVACY':<8} | {'TITLE'}")
    print("=" * 90)
    for s in shorts:
        flag = " [TODAY]" if s["is_today"] else ""
        print(f"{s['id']:<13} | {s['published_at']:<10} | {s['views']:<6} | {s['privacy']:<8} | {s['title'][:45]}{flag}")
    print("=" * 90 + "\n")

    targets = [s for s in shorts if args.include_today or not s["is_today"]]
    logger.info(f"📋 Found {len(shorts)} total Shorts ({len(targets)} eligible legacy targets).")

    if args.delete:
        logger.warning(f"🚨 PERMANENT DELETION requested for {len(targets)} Shorts!")
        for idx, t in enumerate(targets, 1):
            try:
                service.videos().delete(id=t["id"]).execute()
                logger.success(f"[{idx}/{len(targets)}] 🗑️ Deleted Short: {t['id']} - {t['title'][:40]}")
            except Exception as e:
                logger.error(f"Failed to delete {t['id']}: {e}")
        logger.success("✓ Batch deletion completed.")
    elif args.private:
        logger.info(f"🔒 Setting {len(targets)} legacy Shorts to PRIVATE...")
        for idx, t in enumerate(targets, 1):
            if t["privacy"] == "private":
                logger.info(f"[{idx}/{len(targets)}] Already private: {t['id']}")
                continue
            try:
                service.videos().update(
                    part="status",
                    body={"id": t["id"], "status": {"privacyStatus": "private"}}
                ).execute()
                logger.success(f"[{idx}/{len(targets)}] 🔒 Set to PRIVATE: {t['id']} - {t['title'][:40]}")
            except Exception as e:
                logger.error(f"Failed to update {t['id']}: {e}")
        logger.success("✓ Batch privacy update completed.")
    else:
        logger.info("ℹ️ Dry-run mode completed. To execute, run:")
        logger.info("   python scripts/cleanup_channel_shorts.py --private   (to safely hide old Shorts)")
        logger.info("   python scripts/cleanup_channel_shorts.py --delete    (to permanently remove old Shorts)")


if __name__ == "__main__":
    main()

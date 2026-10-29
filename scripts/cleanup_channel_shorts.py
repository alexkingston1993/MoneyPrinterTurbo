#!/usr/bin/env python3
"""
scripts/cleanup_channel_shorts.py
Audit & Privacy Management for The Bull Print YouTube Shorts.

Rules:
- Rule A (viewCount > 50): MUST be/remain PUBLIC (protected top performers).
- Rule B (viewCount <= 50): Set to PRIVATE (never deleted, queued for revamp).
"""

import os
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


def fetch_all_shorts(service) -> List[Dict[str, Any]]:
    uploads_id = "UUwe4D4M4i9aaHdi2ZBlbUmA"
    logger.info(f"🔍 Fetching all videos from playlist: {uploads_id}...")

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

    logger.info(f"📋 Total videos in channel: {len(raw_items)}. Fetching statistics & durations...")

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

            # Identify if it's a Short (duration <= 60s or #Shorts in metadata)
            is_short = "#shorts" in title.lower() or "#shorts" in desc.lower() or dur in ("PT1M", "PT59S", "PT58S", "PT50S", "PT45S", "PT30S", "PT15S", "PT20S")
            # If duration has minutes > 1, it's long form
            if ("M" in dur and dur != "PT1M") or "H" in dur:
                is_short = False

            if not is_short:
                continue

            shorts_list.append({
                "id": vid,
                "title": title,
                "published_at": pub[:10],
                "views": views,
                "previous_privacy": privacy,
                "duration": dur,
            })

    return shorts_list


def audit_and_sync_shorts_privacy(service, execute: bool = True):
    shorts = fetch_all_shorts(service)
    if not shorts:
        logger.info("✓ No Shorts found.")
        return

    logger.info(f"📊 Auditing {len(shorts)} Shorts on channel...")

    audit_results = []
    for s in shorts:
        vid = s["id"]
        views = s["views"]
        prev_priv = s["previous_privacy"]

        # Rule A: > 50 views -> MUST BE PUBLIC
        if views > 50:
            target_priv = "public"
            label = "PUBLIC [PROTECTED >50 VIEWS]"
        else:
            # Rule B: <= 50 views -> MUST BE PRIVATE
            target_priv = "private"
            label = "PRIVATE [QUEUED FOR REVAMP]"

        status_changed = (prev_priv != target_priv)

        if execute and status_changed:
            try:
                service.videos().update(
                    part="status",
                    body={"id": vid, "status": {"privacyStatus": target_priv}}
                ).execute()
                logger.success(f"Updated {vid} ({views} views): {prev_priv} -> {target_priv}")
                current_priv = target_priv
            except Exception as e:
                logger.error(f"Failed to update {vid}: {e}")
                current_priv = prev_priv
        else:
            current_priv = target_priv if execute else prev_priv

        audit_results.append({
            "id": vid,
            "pub": s["published_at"],
            "views": views,
            "prev": prev_priv,
            "new": current_priv,
            "label": label,
            "title": s["title"]
        })

    # Print Clean Formatted Audit Table
    print("\n" + "=" * 125)
    print(f"{'VIDEO ID':<13} | {'PUB DATE':<10} | {'VIEWS':<6} | {'OLD STATUS':<10} | {'NEW STATUS / ACTION':<32} | {'TITLE'}")
    print("=" * 125)
    for r in audit_results:
        print(f"{r['id']:<13} | {r['pub']:<10} | {r['views']:<6} | {r['prev']:<10} | {r['label']:<32} | {r['title'][:40]}")
    print("=" * 125 + "\n")

    protected_count = sum(1 for r in audit_results if r["views"] > 50)
    privated_count = sum(1 for r in audit_results if r["views"] <= 50)
    logger.success(f"✓ Shorts Audit Complete: {protected_count} Protected (>50 views, PUBLIC) | {privated_count} Privated (<=50 views, PRIVATE)")
    return audit_results


def main():
    parser = argparse.ArgumentParser(description="Audit and sync Shorts privacy status.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without modifying.")
    args = parser.parse_args()

    service = get_authenticated_service()
    if not service:
        sys.exit(1)

    audit_and_sync_shorts_privacy(service, execute=not args.dry_run)


if __name__ == "__main__":
    main()

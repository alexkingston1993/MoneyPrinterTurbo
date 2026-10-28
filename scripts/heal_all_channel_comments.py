#!/usr/bin/env python3
"""
scripts/heal_all_channel_comments.py
All-Channel Comment & Metadata Healer.

Scans EVERY video and Short ever uploaded to The Bull Print YouTube channel:
1. Paginates through the channel's master 'uploads' playlist.
2. Detects each video's true vertical (insurance, crypto, stock_market).
3. Strips debug slot tags like '(27 Oct 2026 Slot #1)' and fixes mismatched '#Nifty50' hashtags.
4. Identifies all comments authored by our channel.
5. Deletes all duplicate creator comments (keeping strictly 1).
6. In-place edits (youtube.comments().update) any generic or mismatched comments so they are custom-tailored to that specific video's title and topic.
7. Inserts a custom comment if none existed.
"""

import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add workspace root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load .env if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# Also load from config.toml
try:
    import toml
    config_file = BASE_DIR / "config.toml"
    if config_file.exists():
        cfg = toml.load(str(config_file))
        if "gemini_api_key" in cfg and not os.getenv("GEMINI_API_KEY"):
            os.environ["GEMINI_API_KEY"] = cfg["gemini_api_key"]
except Exception:
    pass

from loguru import logger
from app.services.youtube_uploader import get_uploader, sanitize_clean_title, detect_vertical_from_content

# Vertical-specific custom comments
FALLBACK_COMMENTS = {
    "insurance": (
        "Check your policy schedule tonight: does your health plan have a room-rent cap or proportional deduction clause hidden in the fine print? "
        "Drop your insurer name below 👇 Full forensic dossier: https://thebullprint.in"
    ),
    "crypto": (
        "Have you reconciled your Annual Information Statement (AIS) with your 1% TDS on-chain swap records yet, or are you waiting for tax season? "
        "Share your experience below 👇 Full dossier: https://thebullprint.in"
    ),
    "stock_market": (
        "Did you watch passive limit absorption at VWAP today, or did the opening gamma sweep catch you on the wrong side? "
        "Drop your view below 👇 Full institutional breakdown: https://thebullprint.in"
    ),
}

VERTICAL_HASHTAGS = {
    "insurance": "#TheBullPrint #HealthInsurance #TermInsurance #IRDAI #PersonalFinanceIndia #InsuranceClaims #ConsumerProtection",
    "crypto": "#TheBullPrint #Bitcoin #CryptoIndia #CryptoTaxIndia #Section115BBH #OnChainData #PerpetualFutures",
    "stock_market": "#TheBullPrint #Nifty50 #BankNifty #StockMarketIndia #OptionsTrading #FIIFlows #InstitutionalTrading",
}


def generate_custom_topic_comment(title: str, description: str, vertical: str) -> str:
    """Generates a sharp, human-sounding creator question tailored to the exact video title and topic."""
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = (
                f"You are the lead institutional editor of 'The Bull Print', an analytical finance and research publication. "
                f"Write a single, punchy, thought-provoking pinned YouTube comment for a video titled '{title}'. "
                f"Vertical: {vertical}. "
                f"Requirements:\n"
                f"1. Ask viewers a sharp, technical, or practical debate question directly about the specific concept in the title (e.g. room rent sub-limit, 1% crypto TDS, order flow VWAP absorption).\n"
                f"2. End with: 'Drop your experience below 👇 Full dossier: https://thebullprint.in'\n"
                f"3. Strictly under 280 characters. No hashtags. No generic fluff like 'Did you spot this pattern'."
            )
            resp = client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt,
            )
            text = (resp.text or "").strip().replace('"', '')
            if text and len(text) > 20 and "thebullprint.in" in text:
                return text
        except Exception as e:
            logger.debug(f"Gemini comment generation notice: {e}")

    # Deterministic topic-aware generator
    t_lower = title.lower()
    if vertical == "insurance":
        if "room rent" in t_lower or "sub-limit" in t_lower or "deduction" in t_lower:
            return (
                "Check your policy schedule tonight: does your health plan have a 1% room-rent cap triggering proportional deduction? "
                "Drop your insurer name below 👇 Full forensic dossier: https://thebullprint.in"
            )
        if "icr" in t_lower or "csr" in t_lower or "settlement" in t_lower:
            return (
                "Do you check your insurer's Incurred Claim Ratio (ICR) or only the marketing Claim Settlement Ratio (CSR)? "
                "Share your insurer experience below 👇 Full forensic dossier: https://thebullprint.in"
            )
        return FALLBACK_COMMENTS["insurance"]
    elif vertical == "crypto":
        if "tax" in t_lower or "115bbh" in t_lower or "tds" in t_lower or "194s" in t_lower:
            return (
                "Have you reconciled your Annual Information Statement (AIS) with your 1% TDS on-chain swap records yet? "
                "Share your tax filing experience below 👇 Full dossier: https://thebullprint.in"
            )
        if "liquidation" in t_lower or "funding" in t_lower or "futures" in t_lower:
            return (
                "Are you monitoring perpetual funding rate spikes before major liquidation cluster flushes? "
                "Drop your on-chain metric below 👇 Full dossier: https://thebullprint.in"
            )
        return FALLBACK_COMMENTS["crypto"]
    else:
        if "mutual fund" in t_lower or "sip" in t_lower or "trap" in t_lower:
            return (
                "Did you verify your active mutual fund's portfolio overlap with the Nifty 50 index before investing? "
                "Drop your fund name below 👇 Full breakdown: https://thebullprint.in"
            )
        return FALLBACK_COMMENTS["stock_market"]


def clean_description_hashtags(description: str, vertical: str) -> str:
    """Ensures description does not have mismatched vertical hashtags."""
    if not description:
        return ""
    # If insurance or crypto video, remove mismatched Nifty50 / BankNifty hashtags
    if vertical in ("insurance", "crypto"):
        desc_clean = re.sub(r"#Nifty50\s*", "", description, flags=re.IGNORECASE)
        desc_clean = re.sub(r"#BankNifty\s*", "", desc_clean, flags=re.IGNORECASE)
        desc_clean = re.sub(r"#OptionsTrading\s*", "", desc_clean, flags=re.IGNORECASE)
        desc_clean = re.sub(r"#FIIFlows\s*", "", desc_clean, flags=re.IGNORECASE)
        desc_clean = re.sub(r"#InstitutionalTrading\s*", "", desc_clean, flags=re.IGNORECASE)
        # Ensure proper footer hashtags are included
        correct_footer = VERTICAL_HASHTAGS[vertical]
        if correct_footer.split()[0] not in desc_clean:
            desc_clean = desc_clean.rstrip() + f"\n\n{correct_footer}"
        return desc_clean
    return description


def main():
    logger.info("🩺 [All-Channel Healer] Starting full-channel comment & metadata audit...")
    uploader = get_uploader()
    service = uploader._get_service("en")
    if not service:
        logger.error("❌ Failed to obtain authenticated YouTube service.")
        sys.exit(1)

    # 1. Fetch Channel Info & Master Uploads Playlist
    ch_res = service.channels().list(mine=True, part="id,snippet,contentDetails").execute()
    items = ch_res.get("items", [])
    if not items:
        logger.error("❌ No YouTube channel found for current credentials.")
        sys.exit(1)

    channel_id = items[0]["id"]
    channel_title = items[0]["snippet"]["title"]
    uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    logger.info(f"📺 Channel: '{channel_title}' (ID: {channel_id})")
    logger.info(f"📂 Master Uploads Playlist: {uploads_playlist_id}")

    # 2. Paginate Through ALL Videos in Uploads Playlist
    all_videos = []
    page_token = None
    while True:
        pl_resp = service.playlistItems().list(
            playlistId=uploads_playlist_id,
            part="snippet,contentDetails",
            maxResults=50,
            pageToken=page_token
        ).execute()

        for item in pl_resp.get("items", []):
            vid_id = item["snippet"]["resourceId"]["videoId"]
            vid_title = item["snippet"]["title"]
            vid_desc = item["snippet"].get("description", "")
            pub_at = item["snippet"].get("publishedAt", "")
            all_videos.append({
                "video_id": vid_id,
                "title": vid_title,
                "description": vid_desc,
                "published_at": pub_at,
            })

        page_token = pl_resp.get("nextPageToken")
        if not page_token:
            break

    logger.info(f"📊 Total videos found on channel: {len(all_videos)}")

    # 3. Heal Every Video & Short
    stats = {
        "scanned": len(all_videos),
        "titles_cleaned": 0,
        "descriptions_cleaned": 0,
        "duplicate_comments_deleted": 0,
        "comments_updated": 0,
        "comments_inserted": 0,
    }

    for idx, v in enumerate(all_videos, 1):
        vid_id = v["video_id"]
        title = v["title"]
        desc = v["description"]

        vertical = detect_vertical_from_content(title, desc)
        clean_title = sanitize_clean_title(title)
        clean_desc = clean_description_hashtags(desc, vertical)

        # Update video title/desc if needed
        needs_vid_update = (clean_title != title) or (clean_desc != desc)
        if needs_vid_update:
            try:
                # Fetch full current snippet for safe update
                v_full = service.videos().list(part="snippet", id=vid_id).execute()
                if v_full.get("items"):
                    snip = v_full["items"][0]["snippet"]
                    if clean_title != title:
                        snip["title"] = clean_title[:100]
                        stats["titles_cleaned"] += 1
                        logger.info(f"  ✏️ Cleaned Title [{vid_id}]: '{title}' -> '{clean_title}'")
                    if clean_desc != desc:
                        snip["description"] = clean_desc[:5000]
                        stats["descriptions_cleaned"] += 1
                        logger.info(f"  ✏️ Cleaned Description Hashtags [{vid_id}] for vertical: {vertical}")
                    service.videos().update(part="snippet", body={"id": vid_id, "snippet": snip}).execute()
            except Exception as vid_err:
                logger.warning(f"  ⚠️ Video metadata update notice for {vid_id}: {vid_err}")

        # 4. Audit & Heal Comments
        try:
            threads_resp = service.commentThreads().list(
                part="snippet", videoId=vid_id, maxResults=50
            ).execute()
            threads = threads_resp.get("items", [])
        except Exception as ct_err:
            logger.debug(f"  commentThreads list error for {vid_id}: {ct_err}")
            threads = []

        own_comments = []
        for t in threads:
            top = t.get("snippet", {}).get("topLevelComment", {})
            auth_id = top.get("snippet", {}).get("authorChannelId", {}).get("value")
            if auth_id == channel_id:
                own_comments.append(top)

        target_comment = generate_custom_topic_comment(clean_title, clean_desc, vertical)

        if len(own_comments) > 1:
            # Keep first, delete the rest
            first_c = own_comments[0]
            for dup in own_comments[1:]:
                dup_id = dup.get("id")
                if dup_id:
                    try:
                        service.comments().delete(id=dup_id).execute()
                        stats["duplicate_comments_deleted"] += 1
                        logger.info(f"  🗑️ Deleted duplicate creator comment {dup_id} on [{clean_title[:35]}]")
                    except Exception as del_err:
                        logger.warning(f"  ⚠️ Delete duplicate failed: {del_err}")

            # Update the remaining first comment in-place if generic or mismatched
            first_id = first_c.get("id")
            existing_text = first_c.get("snippet", {}).get("textOriginal", "")
            is_generic = (
                "spot this pattern in the market today" in existing_text.lower()
                or ("pattern" in existing_text.lower() and vertical in ("insurance", "crypto"))
                or existing_text.strip() != target_comment.strip()
            )
            if is_generic and first_id:
                try:
                    service.comments().update(
                        part="snippet",
                        body={"id": first_id, "snippet": {"textOriginal": target_comment}}
                    ).execute()
                    stats["comments_updated"] += 1
                    logger.success(f"  🔄 Updated in-place [{vid_id}]: {target_comment[:60]}...")
                except Exception as upd_err:
                    logger.warning(f"  ⚠️ Comment update failed: {upd_err}")

        elif len(own_comments) == 1:
            # Check if generic or mismatched
            first_c = own_comments[0]
            first_id = first_c.get("id")
            existing_text = first_c.get("snippet", {}).get("textOriginal", "")
            is_generic = (
                "spot this pattern in the market today" in existing_text.lower()
                or ("pattern" in existing_text.lower() and vertical in ("insurance", "crypto"))
            )
            if is_generic and first_id:
                try:
                    service.comments().update(
                        part="snippet",
                        body={"id": first_id, "snippet": {"textOriginal": target_comment}}
                    ).execute()
                    stats["comments_updated"] += 1
                    logger.success(f"  🔄 Updated in-place [{vid_id}]: {target_comment[:60]}...")
                except Exception as upd_err:
                    logger.warning(f"  ⚠️ Comment update failed: {upd_err}")

        else:
            # Zero comments: insert 1 custom topic-specific comment
            try:
                body = {
                    "snippet": {
                        "videoId": vid_id,
                        "topLevelComment": {
                            "snippet": {
                                "textOriginal": target_comment
                            }
                        }
                    }
                }
                service.commentThreads().insert(part="snippet", body=body).execute()
                stats["comments_inserted"] += 1
                logger.success(f"  ➕ Inserted custom comment [{vid_id}]: {target_comment[:60]}...")
            except Exception as ins_err:
                logger.warning(f"  ⚠️ Comment insert notice for {vid_id}: {ins_err}")

        time.sleep(0.2)  # courteous API rate pacing

    print("\n" + "=" * 70)
    print("✨ ALL-CHANNEL COMMENT & METADATA HEALING COMPLETE ✨")
    print("=" * 70)
    print(f"Total Channel Videos Scanned:        {stats['scanned']}")
    print(f"Titles Cleaned (Debug Slots Removed): {stats['titles_cleaned']}")
    print(f"Descriptions Cleaned (Hashtags):     {stats['descriptions_cleaned']}")
    print(f"Duplicate Creator Comments Deleted:  {stats['duplicate_comments_deleted']}")
    print(f"Mismatched Comments Updated In-Place: {stats['comments_updated']}")
    print(f"New Custom Pinned Comments Inserted:  {stats['comments_inserted']}")
    print("=" * 70)


if __name__ == "__main__":
    main()

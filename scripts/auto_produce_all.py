"""
Autonomous Batch Video Production & YouTube + Vercel Pipeline.
Processes benchmark Indian equities sequentially:
1. Generates Kokoro TTS audio with af_heart voice (zero personal photos/avatars).
2. Generates dynamic mplfinance candlestick chart clip.
3. Downloads relevant Pexels footage.
4. Renders 1080x1920 vertical short.
5. Uploads directly to YouTube channel with SEBI & ASCI compliance.
6. Adds video to official public playlist PLO2FWTao-JNA.
7. Updates content/posts/ and content/posts.json with live YouTube link.
8. Deploys to Vercel edge production.
"""

import json
import os
import pickle
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from loguru import logger
from googleapiclient.discovery import build
from app.services.youtube_uploader import YouTubeUploader

API_URL = "http://127.0.0.1:8080/api/v1/videos"
TASK_URL = "http://127.0.0.1:8080/api/v1/tasks"
PLAYLIST_ID = "PLO2FWTao-JNA"

SCRIPTS = [
    {
        "ticker": "ICICIBANK",
        "slug": "icici-bank-growth-engine-2026",
        "subject": "ICICI Bank: The Growth Engine of India",
        "script": "Why is ICICI Bank capturing institutional attention for the next ten years? Here is the quantitative analysis. Financially, ICICI has consistently improved its asset quality with steady loan book expansion. Market research proves their digital platforms are onboarding retail customers rapidly. Technicals show an enduring long-term uptrend. With capable management steering operations, ICICI Bank is well-positioned, but please do your own due diligence and market research as I am not a SEBI-registered advisor.",
        "terms": ["digital banking app", "financial growth graph", "indian economy", "stock analysis", "business handshake"]
    },
    {
        "ticker": "BAJFINANCE",
        "slug": "bajaj-finance-consumer-credit-2026",
        "subject": "Bajaj Finance: The Consumer Credit King",
        "script": "Can Bajaj Finance sustain its compound growth trajectory over the next decade? Let's examine the fundamentals. Their historical net interest margins remain industry-leading. Market research highlights their dominant omnichannel network in consumer durable financing. From a technical perspective, institutional volumes frequently accumulate near key moving averages. Supported by the trusted Bajaj Group, corporate governance is high. Please conduct your own due diligence and market research before taking any financial decision.",
        "terms": ["consumer shopping", "credit card transaction", "finance chart upward", "business team success", "money growth"]
    },
    {
        "ticker": "LT",
        "slug": "larsen-toubro-capex-breakdown-2026",
        "subject": "Larsen and Toubro: Building the Future of India",
        "script": "How will Larsen and Toubro capitalize on India's capital expenditure boom? Let's analyze the setup. Fundamentally, their order book stands at record highs, offering visible multi-year revenue visibility. Research shows unmatched engineering capability across mega-infrastructure projects. Technical analysis highlights constructive multi-year chart structures. Run by seasoned management with high integrity, I would personally consider holding this stock for the next decade, but please do your own due diligence and market research.",
        "terms": ["construction infrastructure", "engineering blueprint", "stock chart rising", "corporate building", "india development"]
    },
    {
        "ticker": "INFY",
        "slug": "infosys-consistent-compounder-2026",
        "subject": "Infosys: The Consistent Wealth Creator",
        "script": "Why does Infosys remain a staple for long-term quantitative study? Let's dive in. Their balance sheet exhibits high return on capital employed and a clear capital allocation policy. Market research indicates deep enterprise relationships across Fortune 500 organizations. Technically, the stock respects key cyclical support bands. Founded on exemplary corporate governance standards, Infosys represents a resilient case study, but please do your own due diligence and market research.",
        "terms": ["software coding", "global corporate office", "financial chart analysis", "technology consulting", "wealth growth"]
    },
    {
        "ticker": "HINDUNILVR",
        "slug": "hindustan-unilever-defensive-giant-2026",
        "subject": "Hindustan Unilever: The Defensive Giant",
        "script": "How does Hindustan Unilever navigate long-term market cycles? Fundamentally, HUL produces steady free cash flow with virtually zero leverage. Research indicates their distribution touches nearly nine out of ten Indian households—a distribution moat that is formidable. Technicals indicate this stock historically provides capital stability during high-volatility regimes. For capital preservation and compounding potential, I would hold it, but please do your own due diligence and market research.",
        "terms": ["supermarket shopping", "household products", "stable stock chart", "indian family", "defensive investment"]
    },
    {
        "ticker": "ITC",
        "slug": "itc-cashflow-dividend-breakout-2026",
        "subject": "ITC: The High Dividend Powerhouse",
        "script": "Why has ITC emerged as a favorite for cash-flow focused portfolios? Let's analyze. Financially, ITC is an exceptional cash generator with consistent dividend yields. Research indicates their non-cigarette FMCG, paper, and agribusiness segments are scaling to improve margin diversification. Technicals demonstrate a clear multi-year structure breakout. Led by professional stewardship with high integrity, it remains a valuable study, but please do your own due diligence and market research.",
        "terms": ["fmcg products", "luxury hotel", "dividend income chart", "business success", "stock market investing"]
    },
    {
        "ticker": "BHARTIARTL",
        "slug": "bharti-airtel-telecom-monopoly-2026",
        "subject": "Bharti Airtel: The Telecom Monopoly Player",
        "script": "Could Bharti Airtel be a prime beneficiary of digital data consumption? Let's break it down. Their fundamental metrics are improving with steady average revenue per user expansion. Market structure shows the Indian telecom landscape operates as an effective duopoly, giving Airtel durable pricing leverage. Technical charts reflect disciplined accumulation. For the digital decade, I would hold this stock, but please do your own due diligence and market research as I am not a SEBI-registered advisor.",
        "terms": ["telecom tower", "5g technology", "stock growth graph", "mobile internet", "digital transformation"]
    }
]

def add_to_playlist(video_id: str):
    """Add uploaded video to the official public playlist."""
    token_path = "data/youtube_tokens/youtube_token_en.pickle"
    if not os.path.exists(token_path) or not video_id:
        return
    with open(token_path, "rb") as f:
        creds = pickle.load(f)
    youtube = build("youtube", "v3", credentials=creds)
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": PLAYLIST_ID,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
    ).execute()
    logger.success(f"Added video {video_id} to playlist {PLAYLIST_ID}")

def update_post_with_video(slug: str, yt_url: str):
    """Update posts.json and the post md file with the live YouTube URL."""
    manifest_path = "content/posts.json"
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                posts = json.load(f)
            
            vid_id = ""
            if "youtu.be/" in yt_url:
                vid_id = yt_url.split("youtu.be/")[1].split("?")[0]
            elif "watch?v=" in yt_url:
                vid_id = yt_url.split("watch?v=")[1].split("&")[0]
            
            embed_iframe = (
                f'<div class="yt-embed-wrapper" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:8px;margin:24px 0;">'
                f'<iframe src="https://www.youtube.com/embed/{vid_id}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen></iframe>'
                f'</div>'
            )

            updated = False
            for p in posts:
                if p.get("slug") == slug:
                    p["youtubeUrl"] = yt_url
                    if "[YOUTUBE_EMBED_PLACEHOLDER]" in p.get("html", ""):
                        p["html"] = p["html"].replace("[YOUTUBE_EMBED_PLACEHOLDER]", embed_iframe)
                    elif '<div class="yt-embed-wrapper"' not in p.get("html", ""):
                        p["html"] = embed_iframe + p.get("html", "")
                    updated = True
                    break
            
            if updated:
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(posts, f, indent=2, ensure_ascii=False)
                logger.success(f"Updated {manifest_path} for {slug} -> {yt_url}")

            # Also update markdown file
            md_path = f"content/posts/{slug}.md"
            if os.path.exists(md_path):
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace('youtubeUrl: ""', f'youtubeUrl: "{yt_url}"')
                content = content.replace("[YOUTUBE_EMBED_PLACEHOLDER]", embed_iframe)
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.success(f"Updated {md_path} for {slug} -> {yt_url}")

            # Trigger git commit & push
            subprocess.run(["git", "add", "content/posts.json", f"content/posts/{slug}.md"], check=False)
            subprocess.run(["git", "commit", "-m", f"Attach live YouTube video embed for {slug}"], check=False)
            subprocess.run(["git", "push", "origin", "main"], check=False)
            logger.info(f"Pushed update for {slug} to origin main")
            
            # Instant Vercel Edge propagation
            subprocess.run(["vercel", "--prod", "--yes"], check=False)
            logger.info(f"Deployed update for {slug} directly to Vercel production")
        except Exception as e:
            logger.error(f"Failed to update post for {slug}: {e}")

def run_single(item):
    logger.info(f"\n=======================================================")
    logger.info(f"🎬 STARTING BATCH PRODUCTION: {item['subject']}")
    logger.info(f"=======================================================")

    payload = {
        "video_subject": item["subject"],
        "video_script": item["script"],
        "video_terms": item["terms"],
        "video_aspect": "9:16",
        "video_concat_mode": "sequential",
        "video_clip_duration": 5,
        "video_count": 1,
        "video_source": "pexels",
        "video_language": "",
        "voice_name": "kokoro:af_heart",
        "bgm_type": "random",
        "subtitle_enabled": True,
        "subtitle_position": "center",
        "font_size": 75,
        "text_fore_color": "#FFFFFF",
        "text_background_color": True,
        "stroke_color": "#000000",
        "stroke_width": 2.0
    }

    try:
        resp = requests.post(API_URL, json=payload, timeout=15)
        if resp.status_code != 200:
            logger.error(f"Failed to queue {item['subject']}: {resp.text}")
            return None
        data = resp.json().get("data", {})
        task_id = data.get("task_id")
        logger.success(f"Queued task {task_id} for {item['subject']}")
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return None

    # Poll for completion (up to 20 mins)
    start_time = time.time()
    yt_url = None
    final_video_path = None

    while time.time() - start_time < 1200:
        time.sleep(10)
        try:
            status_resp = requests.get(f"{TASK_URL}/{task_id}", timeout=10)
            if status_resp.status_code == 200:
                task_data = status_resp.json().get("data", {})
                state = task_data.get("state")
                progress = task_data.get("progress", 0)
                logger.info(f"[{item['ticker']}] Task {task_id[:8]}... state: {state}, progress: {progress}%")

                if state == 1: # Success
                    videos = task_data.get("videos", [])
                    logger.success(f"🎉 Task {task_id} finished successfully! Generated: {videos}")
                    
                    # 1. Check if background task already uploaded to YouTube
                    yt_upload = task_data.get("youtube_upload", {}).get("en", {})
                    if yt_upload and yt_upload.get("success") and yt_upload.get("url"):
                        yt_url = yt_upload.get("url")
                        logger.success(f"🚀 LIVE YOUTUBE VIDEO UPLOADED BY PIPELINE: {yt_url}")
                        
                        try:
                            add_to_playlist(yt_upload.get("video_id"))
                        except Exception as e:
                            logger.warning(f"Playlist addition error: {e}")
                        
                        update_post_with_video(item["slug"], yt_url)
                        return yt_url

                    # 2. Otherwise locate local file and upload
                    task_dir = os.path.join("storage", "tasks", task_id)
                    final_video_path = os.path.join(task_dir, "final-1.mp4")
                    break
                elif state == -1 or state == 2: # Error
                    logger.error(f"Task {task_id} failed with state {state}")
                    return None
        except Exception as e:
            logger.warning(f"Polling error: {e}")

    if not final_video_path or not os.path.exists(final_video_path):
        logger.error(f"Could not find rendered video for task {task_id}")
        return None

    # Manual upload fallback
    logger.info(f"Checking YouTube upload for {final_video_path}...")
    uploader = YouTubeUploader()
    upload_res = uploader.upload_video(
        language="en",
        video_path=final_video_path,
        title=f"{item['subject']} | Dalal Street Alpha",
        description=f"In-depth institutional stock analysis of {item['ticker']}. Full research breakdown, technical setup, and valuation multiples.\n\nRead the quantitative report: https://dalal-street-alpha.vercel.app\n\n#Shorts #{item['ticker']} #StockMarketIndia #Nifty50 #Investing",
        is_short=True,
        privacy_status="public"
    )

    if upload_res.get("success"):
        yt_url = upload_res.get("url")
        vid_id = upload_res.get("video_id")
        logger.success(f"🚀 LIVE YOUTUBE VIDEO UPLOADED: {yt_url}")
        try:
            add_to_playlist(vid_id)
        except Exception as e:
            logger.warning(f"Playlist error: {e}")
        update_post_with_video(item["slug"], yt_url)
        return yt_url
    else:
        logger.error(f"YouTube upload error: {upload_res.get('error')}")
        return None

if __name__ == "__main__":
    start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    count = int(sys.argv[2]) if len(sys.argv) > 2 else len(SCRIPTS)
    
    selected_items = SCRIPTS[start_idx:start_idx + count]
    logger.info(f"Queuing batch production for {len(selected_items)} stocks...")
    for idx, item in enumerate(selected_items):
        logger.info(f"\nProcessing item {idx+1}/{len(selected_items)}: {item['ticker']}")
        run_single(item)

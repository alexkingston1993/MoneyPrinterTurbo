"""
Master Orchestrator Engine (master_engine.py).
Coordinates the entire automated publishing pipeline from end to end:
1. Load LLM Master Payload & Verify Regulatory Compliance
2. Capture Fresh Dark-Mode Charts via Playwright / Matplotlib
3. Generate High-CTR YouTube Thumbnail & Google Discover Images
4. Synthesize Spoken Narration (Edge-TTS) & Render Video Scenes (FFmpeg)
5. Stitch All Segments into Long-Form MP4
6. Upload to YouTube Data API v3 (containsSyntheticMedia=True)
7. Generate In-Depth Website MDX Article (with Triple JSON-LD & Humanizer)
8. Publish to GitHub/Vercel & Ping Search Engine Indexers

Also exposes FastAPI Webhook endpoint for n8n/RSS real-time automated triggers.
"""

import sys
import json
import asyncio
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, BackgroundTasks, HTTPException

# Import custom core modules
from chart_fetcher import capture_batch_charts
from thumbnail_generator import create_marketing_images
from publisher import publish_and_index_article
from engine import (
    verify_compliance,
    generate_tts_audio,
    render_segment_mp4,
    stitch_all_segments,
    upload_to_youtube,
    generate_website_article_file
)

BASE_DIR = Path(__file__).parent
WEBHOOK_SECRET = "flipzon_secure_macro_webhook_2026"

app = FastAPI(title="Flipzon & The Bull Print Automated Media Engine")


class PipelineWebhookPayload(BaseModel):
    secret: str
    topic: str
    market_notes: str
    custom_headline_words: List[str] = ["INSTITUTIONAL", "DELTA", "TRAP"]


async def run_master_pipeline(payload_json_path: Path, upload_live: bool = False, custom_topic: Optional[str] = None):
    print("\n🚀 ========================================================")
    print("   INITIALIZING MASTER AUTOMATED PUBLISHING ENGINE...")
    print("========================================================\n")
    
    # 1. Load LLM Master Payload
    payload = json.loads(payload_json_path.read_text(encoding="utf-8"))
    if custom_topic:
        payload["topic"] = custom_topic
        
    slug = payload["campaign_id"]
    topic = payload.get("topic", "Market Structure & Order Flow")
    print(f"📌 Target Campaign: {slug} | Topic: {topic}")
    
    # Pre-flight SEBI Compliance Check
    verify_compliance(payload)
    
    # 2. STEP 1: CAPTURE FRESH CHARTS WITH PLAYWRIGHT
    print("\n--- STEP 1: CAPTURING CHART VISUALS ---")
    chart_jobs = [
        {"platform": "tradingview", "symbol": "BINANCE:BTCUSDT", "interval": "60", "filename": "btc_hourly_structure.png"},
        {"platform": "gocharting", "symbol": "BINANCE:BTCUSDT", "filename": "btc_footprint_absorption.png"},
        {"platform": "tradingview", "symbol": "TVC:DXY", "interval": "D", "filename": "dxy_macro_liquidity.png"}
    ]
    captured_charts = await capture_batch_charts(chart_jobs, headless=True)
    
    # 3. STEP 2: GENERATE HIGH-CTR THUMBNAIL & DISCOVER IMAGE
    print("\n--- STEP 2: GENERATING MARKETING IMAGES ---")
    primary_chart = BASE_DIR / "assets" / "charts" / (captured_charts[0] if captured_charts else "default.png")
    studio_avatar = BASE_DIR / "assets" / "avatars" / "avatar_1.png"
    headline_words = payload.get("youtube_payload", {}).get("metadata", {}).get("thumbnail_top_text", "INSTITUTIONAL DELTA TRAP").split()[:3]
    
    yt_thumb, discover_img = create_marketing_images(
        chart_bg_path=primary_chart,
        avatar_path=studio_avatar,
        headline_words=headline_words,
        output_slug=slug
    )

    # 4. STEP 3: RENDER AUDIO & STITCH VIDEO (FFMPEG)
    print("\n--- STEP 3: RENDERING VIDEO SCENES & STITCHING ---")
    segments = payload["youtube_payload"]["segments"]
    rendered_segment_files = []
    cumulative_sec = 0.0
    timestamps_log = []

    for seg in segments:
        idx = seg["segment_index"]
        mp3_path = BASE_DIR / "build" / f"{slug}_seg_{idx:02d}.mp3"
        mp4_path = BASE_DIR / "build" / f"{slug}_seg_{idx:02d}.mp4"

        mins, secs = divmod(int(cumulative_sec), 60)
        timestamp_entry = f"{mins:02d}:{secs:02d} - {seg['chapter_title']}"
        timestamps_log.append(timestamp_entry)
        print(f"   [Segment {idx:02d}]: {timestamp_entry}")

        duration = await generate_tts_audio(seg["spoken_narration"], mp3_path)
        render_segment_mp4(seg, mp3_path, duration, mp4_path)
        rendered_segment_files.append(mp4_path)
        cumulative_sec += duration

    final_video_path = BASE_DIR / "output" / f"{slug}_longform.mp4"
    stitch_all_segments(rendered_segment_files, final_video_path)

    # Append Chapter Timestamps to YouTube Description
    chapter_block = "\n\n⏱️ CHAPTER TIMESTAMPS:\n" + "\n".join(timestamps_log)
    payload["youtube_payload"]["metadata"]["description_body"] += chapter_block

    # 5. STEP 4: UPLOAD TO YOUTUBE (with containsSyntheticMedia=True)
    print("\n--- STEP 4: UPLOADING TO YOUTUBE ---")
    if upload_live:
        youtube_video_id = upload_to_youtube(final_video_path, payload["youtube_payload"])
    else:
        youtube_video_id = "DRY_RUN_VIDEO_ID_123"
        print("ℹ️ Dry-run mode: Mock YouTube ID assigned (DRY_RUN_VIDEO_ID_123).")

    # 6. STEP 5: GENERATE WEBSITE .MDX ARTICLE
    print("\n--- STEP 5: GENERATING WEBSITE MDX ARTICLE ---")
    out_article_path = generate_website_article_file(payload, youtube_video_id, timestamps_log)

    # 7. STEP 6: PUBLISH, DEPLOY (VERCEL), & PING INDEXERS
    print("\n--- STEP 6: PUBLISHING & PINGING SEARCH ENGINES ---")
    used_charts = [
        sec["chart_image_ref"]
        for sec in payload["website_article_payload"]["article_sections"]
        if sec.get("chart_image_ref") != "NONE"
    ]
    
    live_url = publish_and_index_article(out_article_path, used_charts, slug)
    print(f"\n🎉 PIPELINE RUN COMPLETE! Live Article URL: {live_url}")
    return live_url


# =====================================================================
# FASTAPI WEBHOOK TRIGGER ROUTE (For RSS Feeds, n8n, Make.com)
# =====================================================================
@app.post("/api/trigger-pipeline")
async def trigger_pipeline_endpoint(data: PipelineWebhookPayload, background_tasks: BackgroundTasks):
    if data.secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid webhook secret token.")
    
    sample_payload = BASE_DIR / "payload.json"
    background_tasks.add_task(
        run_master_pipeline,
        payload_json_path=sample_payload,
        upload_live=False,
        custom_topic=data.topic
    )
    return {
        "status": "accepted",
        "message": f"Pipeline successfully triggered for topic: '{data.topic}'. Running in background."
    }


@app.get("/health")
def health_check():
    return {"status": "online", "engine": "master_orchestrator", "sebi_compliant": True}


if __name__ == "__main__":
    sample_payload = BASE_DIR / "payload.json"
    if "--serve" in sys.argv:
        import uvicorn
        port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8000
        print(f"🌐 Launching FastAPI Webhook Server on port {port}...")
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        asyncio.run(run_master_pipeline(sample_payload, upload_live=False))

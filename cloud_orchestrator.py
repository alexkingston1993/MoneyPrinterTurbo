"""
Cloud Orchestrator Engine (cloud_orchestrator.py).
Zero-cost cloud architecture tying together:
1. GitHub Actions (Ubuntu runner - Playwright scraping & coordination)
2. Aria Mission Control (Single editable Telegram status card + 5-min human thumbnail gate)
3. Google AI Studio (Free Gemini API Structured Output generation)
4. Kaggle GPU Kernel (Dual T4 GPU - Faster-Whisper & NVENC FFmpeg video rendering)
5. YouTube Data API v3 (Headless synthetic media upload)
6. Vercel & Search Engine Indexers (Instant deployment & IndexNow ping)
"""

import os
import json
import time
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import requests
from loguru import logger

from chart_fetcher import capture_batch_charts
from thumbnail_generator import create_marketing_images
from engine import generate_website_article_file
from publisher import publish_and_index_article

BASE_DIR = Path(__file__).parent
KAGGLE_STAGE_DIR = BASE_DIR / "kaggle_stage"
KAGGLE_STAGE_DIR.mkdir(parents=True, exist_ok=True)

KAGGLE_USERNAME = os.getenv("KAGGLE_USERNAME", "")
DATASET_SLUG = "flipzon-daily-payload"
KERNEL_SLUG = "flipzon-gpu-video-renderer"


class AriaMissionControl:
    """
    Replaces multi-message spam with a single editable Telegram Mission Control card
    + a 5-minute Human-in-the-Loop Thumbnail Approval & Live Word-Edit Gate.
    """
    def __init__(self, topic: str):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.topic = topic
        self.start_ts = time.time()
        self.status_msg_id: Optional[int] = None
        self.stages = {
            "playwright": "⏳ Pending",
            "gemini": "⏳ Pending",
            "thumbnail": "⏳ Pending",
            "kaggle_gpu": "⏳ Pending",
            "vercel": "⏳ Pending",
        }

    def _elapsed(self) -> str:
        mins, secs = divmod(int(time.time() - self.start_ts), 60)
        return f"{mins:02d}m {secs:02d}s"

    def _render_card_text(self, footer_note: str = "") -> str:
        return (
            f"🐂 *THE BULL PRINT — CLOUD MISSION CONTROL* 🕶️☕\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Topic:* `{self.topic}`\n"
            f"⏱️ *Elapsed Time:* `{self._elapsed()}`\n\n"
            f"1️⃣ *Playwright Charts:* {self.stages['playwright']}\n"
            f"2️⃣ *Gemini 2.5 JSON:* {self.stages['gemini']}\n"
            f"3️⃣ *Pillow Thumbnail:* {self.stages['thumbnail']}\n"
            f"4️⃣ *Kaggle Dual-T4 GPU:* {self.stages['kaggle_gpu']}\n"
            f"5️⃣ *Vercel & IndexNow:* {self.stages['vercel']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            + (f"💡 _{footer_note}_\n" if footer_note else "🚀 _Agent Aria cloud engines running autonomously._\n")
        )

    def init_card(self):
        """Sends the initial pinned Mission Control card and stores message_id."""
        if not self.token or not self.chat_id:
            logger.info(f"[Mission Control Offline]:\n{self._render_card_text('Initializing runner...')}")
            return
        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": self._render_card_text("Initializing GitHub Actions runner..."),
                    "parse_mode": "Markdown",
                },
                timeout=10,
            ).json()
            self.status_msg_id = resp.get("result", {}).get("message_id")
            logger.success(f"✓ Initialized Telegram Mission Control card (msg_id: {self.status_msg_id})")
        except Exception as e:
            logger.warning(f"Failed to initialize Telegram Mission Control card: {e}")

    def update_stage(self, stage_key: str, status_text: str, footer_note: str = ""):
        """Edits the single Mission Control message in place."""
        self.stages[stage_key] = status_text
        if not self.token or not self.chat_id or not self.status_msg_id:
            logger.info(f"[{stage_key.upper()}]: {status_text} | {footer_note}")
            return
        try:
            requests.post(
                f"{self.base_url}/editMessageText",
                json={
                    "chat_id": self.chat_id,
                    "message_id": self.status_msg_id,
                    "text": self._render_card_text(footer_note),
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
        except Exception as e:
            logger.debug(f"Card update notice: {e}")

    def await_thumbnail_approval_or_edit(
        self,
        yt_thumb: Path,
        primary_chart: Path,
        avatar_path: Path,
        headline_words: List[str],
        slug: str,
        timeout_sec: int = 300,  # 5-minute review window before auto-approving
    ) -> Path:
        """
        Sends thumbnail preview to Telegram with inline buttons:
        [✅ Approve & Render GPU] [🛑 Abort Run]
        Or allows Alex to reply with 3 new words (e.g. 'DELTA TRAP EXPOSED') to re-render live!
        Temporarily pauses/restores any active Telegram webhook to prevent HTTP 409 getUpdates conflicts.
        """
        if not self.token or not self.chat_id:
            self.update_stage("thumbnail", f"✅ Rendered (`{' '.join(headline_words)}`)")
            return yt_thumb

        # Prevent HTTP 409 Conflict: check and temporarily pause webhook if active
        had_webhook = False
        saved_webhook_url = ""
        try:
            wh_info = requests.get(f"{self.base_url}/getWebhookInfo", timeout=6).json()
            saved_webhook_url = wh_info.get("result", {}).get("url", "")
            if saved_webhook_url:
                had_webhook = True
                requests.post(f"{self.base_url}/deleteWebhook", timeout=6)
                logger.info("Paused webhook temporarily for interactive thumbnail approval window.")
        except Exception as e:
            logger.debug(f"Webhook check notice: {e}")

        try:
            # Flush existing offset
            updates = requests.get(f"{self.base_url}/getUpdates", params={"timeout": 1}, timeout=6).json()
            last_offset = max([u["update_id"] for u in updates.get("result", [])], default=0) + 1

            def send_preview(thumb_path: Path, words: List[str]) -> int:
                caption = (
                    f"🎨 *HUMAN-IN-THE-LOOP THUMBNAIL GATE* ⏱️ ({timeout_sec // 60}m Auto-Approve)\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔤 *Current Words:* `{' '.join(words)}`\n\n"
                    f"• Tap *Approve* to launch Kaggle Dual-T4 GPU immediately.\n"
                    f"• Or *reply with 3 new words* (e.g. `DELTA TRAP EXPOSED`) to re-generate the thumbnail live!"
                )
                kb = {
                    "inline_keyboard": [[
                        {"text": "✅ Approve & Render GPU", "callback_data": "thumb_approve"},
                        {"text": "🛑 Abort Run", "callback_data": "thumb_abort"}
                    ]]
                }
                with open(thumb_path, "rb") as img_f:
                    r = requests.post(
                        f"{self.base_url}/sendPhoto",
                        data={"chat_id": self.chat_id, "caption": caption, "parse_mode": "Markdown", "reply_markup": json.dumps(kb)},
                        files={"photo": img_f},
                        timeout=20,
                    ).json()
                return r.get("result", {}).get("message_id", 0)

            send_preview(yt_thumb, headline_words)
            deadline = time.time() + timeout_sec
            logger.info(f"⏳ Waiting up to {timeout_sec}s for Alex's Telegram review / approval...")

            while time.time() < deadline:
                rem = int(deadline - time.time())
                try:
                    poll = requests.get(
                        f"{self.base_url}/getUpdates",
                        params={"offset": last_offset, "timeout": min(10, max(1, rem))},
                        timeout=15,
                    ).json()
                except Exception:
                    time.sleep(2)
                    continue

                for u in poll.get("result", []):
                    last_offset = u["update_id"] + 1

                    # Case A: Inline Button Tapped
                    cb = u.get("callback_query")
                    if cb and str(cb.get("message", {}).get("chat", {}).get("id")) == str(self.chat_id):
                        action = cb.get("data")
                        requests.post(f"{self.base_url}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
                        if action == "thumb_approve":
                            logger.success("Alex approved thumbnail via Telegram inline button!")
                            self.update_stage("thumbnail", f"✅ Approved by Alex (`{' '.join(headline_words)}`)")
                            return yt_thumb
                        elif action == "thumb_abort":
                            self.update_stage("thumbnail", "🛑 Aborted by Alex via Telegram")
                            raise SystemExit("Pipeline cleanly aborted by user via Telegram callback.")

                    # Case B: Alex replied with 3 new words
                    msg = u.get("message", {})
                    if str(msg.get("chat", {}).get("id")) == str(self.chat_id) and msg.get("text"):
                        raw_text = msg["text"].strip()
                        if not raw_text.startswith("/"):
                            new_words = raw_text.upper().split()[:3]
                            logger.info(f"Alex provided new thumbnail headline words: {new_words}")
                            yt_thumb, _ = create_marketing_images(primary_chart, avatar_path, new_words, slug)
                            headline_words = new_words
                            send_preview(yt_thumb, headline_words)
                            deadline = time.time() + timeout_sec  # Reset countdown after live edit

            logger.info("Auto-approval window elapsed. Proceeding to Kaggle GPU...")
            self.update_stage("thumbnail", f"⚡ Auto-Approved (`{' '.join(headline_words)}`)")
            return yt_thumb

        finally:
            # Restore webhook if it was previously active
            if had_webhook and saved_webhook_url:
                try:
                    requests.post(f"{self.base_url}/setWebhook", json={"url": saved_webhook_url}, timeout=6)
                    logger.info("Restored Telegram serverless webhook on Vercel.")
                except Exception as e:
                    logger.debug(f"Webhook restoration notice: {e}")


# =====================================================================
# STEP 1: GOOGLE AI STUDIO (FREE GEMINI API) MASTER JSON GENERATOR
# =====================================================================
def generate_master_json_via_ai_studio(topic: str, market_notes: str, chart_files: List[str]) -> Dict:
    """Calls Google AI Studio Free Tier with Structured Outputs to generate dual script + article."""
    api_key = os.getenv("GEMINI_API_KEY")
    prompt_file = BASE_DIR / "master_system_prompt.txt"
    schema_file = BASE_DIR / "master_schema.json"

    if api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            system_prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else "Financial Educator"
            schema_dict = json.loads(schema_file.read_text(encoding="utf-8")) if schema_file.exists() else {}

            user_input = json.dumps({
                "topic": topic,
                "market_data_notes": market_notes,
                "chart_screenshots": chart_files,
                "website_domain": "flipzon.work.gd"
            })

            logger.info("🧠 Calling Google AI Studio (Gemini 2.5 Flash / Pro)...")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_input,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=schema_dict,
                    temperature=0.4,
                    max_output_tokens=8192,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            logger.warning(f"Google AI Studio direct API call failed or timed out: {e}")

    # Fallback to local payload benchmark
    logger.info("ℹ️ Using local payload benchmark.")
    payload_file = BASE_DIR / "payload.json"
    data = json.loads(payload_file.read_text(encoding="utf-8"))
    data["topic"] = topic
    return data


# =====================================================================
# STEP 2: PUSH PAYLOAD TO KAGGLE & STATE-AWARE ADAPTIVE BACKOFF POLLER
# =====================================================================
def run_kaggle_gpu_renderer(
    payload: Dict,
    chart_files: List[str],
    yt_thumb: Path,
    mission: AriaMissionControl
) -> Tuple[str, List[str]]:
    """
    Pushes payload + charts to private Kaggle dataset, triggers T4 GPU kernel,
    and runs a 26-minute state-aware poller. Falls back to local engine if Kaggle is unconfigured.
    """
    import shutil
    kaggle_key = os.getenv("KAGGLE_KEY")
    if not (KAGGLE_USERNAME and kaggle_key):
        logger.info("ℹ️ Kaggle credentials not provided in environment. Running local video stitching...")
        mission.update_stage("kaggle_gpu", "⚙️ Local Fallback Render Active")
        from engine import generate_tts_audio, render_segment_mp4, stitch_all_segments, upload_to_youtube
        
        slug = payload["campaign_id"]
        segments = payload["youtube_payload"]["segments"]
        rendered_files = []
        cumulative = 0.0
        timestamps = []

        for seg in segments:
            idx = seg["segment_index"]
            mp3 = BASE_DIR / "build" / f"{slug}_seg_{idx:02d}.mp3"
            mp4 = BASE_DIR / "build" / f"{slug}_seg_{idx:02d}.mp4"
            m, s = divmod(int(cumulative), 60)
            timestamps.append(f"{m:02d}:{s:02d} - {seg['chapter_title']}")
            
            dur = asyncio.run(generate_tts_audio(seg["spoken_narration"], mp3))
            render_segment_mp4(seg, mp3, dur, mp4)
            rendered_files.append(mp4)
            cumulative += dur

        final_mp4 = BASE_DIR / "output" / f"{slug}_longform.mp4"
        stitch_all_segments(rendered_files, final_mp4)
        vid_id = upload_to_youtube(final_mp4, payload["youtube_payload"])
        mission.update_stage("kaggle_gpu", f"✅ Rendered Locally (`{vid_id}`)")
        return vid_id, timestamps

    # 1. Stage Kaggle Dataset
    (KAGGLE_STAGE_DIR / "payload.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if yt_thumb.exists():
        shutil.copy2(yt_thumb, KAGGLE_STAGE_DIR / "yt_thumb.jpg")
    for cf in chart_files:
        src = BASE_DIR / "assets" / "charts" / cf
        if src.exists():
            shutil.copy2(src, KAGGLE_STAGE_DIR / cf)

    dataset_meta = {
        "title": "Flipzon Daily Payload",
        "id": f"{KAGGLE_USERNAME}/{DATASET_SLUG}",
        "licenses": [{"name": "CC0-1.0"}]
    }
    (KAGGLE_STAGE_DIR / "dataset-metadata.json").write_text(json.dumps(dataset_meta), encoding="utf-8")

    logger.info("☁️ Pushing payload & chart PNGs to Private Kaggle Dataset...")
    mission.update_stage("kaggle_gpu", "☁️ Pushing Dataset to Kaggle...")
    subprocess.run(
        ["kaggle", "datasets", "version", "-p", str(KAGGLE_STAGE_DIR), "-m", "Auto daily run", "--dir-mode", "zip"],
        check=True
    )
    time.sleep(12)

    # 2. Push & Trigger Kaggle Dual-T4 GPU Kernel
    kernel_dir = BASE_DIR / "kaggle_kernel"
    logger.info("🔥 Triggering Kaggle Dual-T4 GPU Kernel for Whisper + NVENC Video Render...")
    mission.update_stage("kaggle_gpu", "🔥 Waking Dual-T4 GPU Kernel...")
    subprocess.run(["kaggle", "kernels", "push", "-p", str(kernel_dir)], check=True)

    # 3. State-Aware Kaggle Poller (Handles Peak US Queue Spikes Gracefully up to 26 mins)
    kernel_id = f"{KAGGLE_USERNAME}/{KERNEL_SLUG}"
    poll_start = time.time()
    max_wait_sec = 26 * 60  # 26 minutes (leaves 9 mins buffer inside 35-min GitHub Action timeout)

    while time.time() - poll_start < max_wait_sec:
        res = subprocess.run(
            ["kaggle", "kernels", "status", kernel_id],
            stdout=subprocess.PIPE, text=True, check=True
        )
        status_out = res.stdout.lower().strip()
        elapsed_m = int((time.time() - poll_start) // 60)
        elapsed_s = int((time.time() - poll_start) % 60)
        logger.info(f"   [Kaggle GPU Status ({elapsed_m}m {elapsed_s}s)]: {status_out}")

        if "complete" in status_out:
            mission.update_stage("kaggle_gpu", f"✅ Rendered & Uploaded ({elapsed_m}m {elapsed_s}s)")
            break
        elif "error" in status_out or "cancel" in status_out:
            mission.update_stage("kaggle_gpu", "❌ Kaggle Error — Fallback Engaged")
            raise RuntimeError(f"Kaggle GPU Kernel failed: {status_out}")
        elif "queued" in status_out:
            mission.update_stage("kaggle_gpu", f"⏳ Queued on Kaggle ({elapsed_m}m {elapsed_s}s)", "Waiting for free T4 node...")
            time.sleep(30)  # Slower poll while queued
        else:
            mission.update_stage("kaggle_gpu", f"🔥 Encoding NVENC + Whisper ({elapsed_m}m {elapsed_s}s)", "Generating 1080p MP4...")
            time.sleep(20)

    out_dir = BASE_DIR / "kaggle_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["kaggle", "kernels", "output", kernel_id, "-p", str(out_dir)], check=True)

    result_data = json.loads((out_dir / "render_result.json").read_text(encoding="utf-8"))
    return result_data["youtube_video_id"], result_data["timestamps_log"]


# =====================================================================
# MAIN CLOUD PIPELINE EXECUTION
# =====================================================================
async def main():
    topic = os.getenv("INPUT_TOPIC", "Bitcoin Order Flow Absorption & Global Macro Liquidity")
    notes = os.getenv("INPUT_NOTES", "Analyze BTC footprint delta absorption and 30-day+ historical Nifty macro structure.")

    # 1. Initialize Single Editable Mission Control Card
    mission = AriaMissionControl(topic=topic)
    mission.init_card()

    # 2. Capture Dark-Mode Charts via Playwright
    chart_jobs = [
        {"platform": "tradingview", "symbol": "BINANCE:BTCUSDT", "interval": "60", "filename": "btc_hourly_structure.png"},
        {"platform": "gocharting", "symbol": "BINANCE:BTCUSDT", "filename": "btc_footprint_absorption.png"},
        {"platform": "tradingview", "symbol": "TVC:DXY", "interval": "D", "filename": "dxy_macro_liquidity.png"}
    ]
    mission.update_stage("playwright", "🔄 Capturing 3 charts...")
    chart_files = await capture_batch_charts(chart_jobs, headless=True)
    mission.update_stage("playwright", f"✅ Captured ({len(chart_files)} charts)")

    # 3. Call Google AI Studio / Gemini
    mission.update_stage("gemini", "🧠 Synthesizing Dual Script + Article...")
    payload = generate_master_json_via_ai_studio(topic, notes, chart_files)
    slug = payload["campaign_id"]
    mission.update_stage("gemini", f"✅ Generated (`{slug}`)")

    # 4. Generate Thumbnail & Enter 5-Min Human-in-the-Loop Approval Gate
    mission.update_stage("thumbnail", "🎨 Rendering Pillow Graphics...")
    headline_words = payload["youtube_payload"]["metadata"]["thumbnail_top_text"].split()[:3]
    primary_chart = BASE_DIR / "assets" / "charts" / chart_files[0]
    avatar_1 = BASE_DIR / "assets" / "avatars" / "avatar_1.png"
    yt_thumb, discover_img = create_marketing_images(primary_chart, avatar_1, headline_words, slug)

    # Await approval or live 3-word edit from Alex via Telegram
    yt_thumb = mission.await_thumbnail_approval_or_edit(
        yt_thumb=yt_thumb,
        primary_chart=primary_chart,
        avatar_path=avatar_1,
        headline_words=headline_words,
        slug=slug,
        timeout_sec=300
    )

    # 5. Render Video via Kaggle GPU NVENC / Faster-Whisper
    mission.update_stage("kaggle_gpu", "🚀 Dispatching to Kaggle Dual-T4 GPU...")
    yt_video_id, timestamps_log = run_kaggle_gpu_renderer(payload, chart_files, yt_thumb, mission)

    # 6. Generate MDX Article + Deploy to Vercel + Ping Search Indexers
    mission.update_stage("vercel", "📝 Compiling MDX & IndexNow Ping...")
    mdx_path = generate_website_article_file(payload, yt_video_id, timestamps_log)
    live_url = publish_and_index_article(mdx_path, chart_files, slug)
    mission.update_stage("vercel", f"✅ Live & Indexed (`{live_url}`)", "Run complete! All systems operational.")

    print(f"\n🎉 Cloud pipeline completed successfully! Live URL: {live_url}")


if __name__ == "__main__":
    asyncio.run(main())

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
import re
import json
import time
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import requests
from loguru import logger

from chart_fetcher import capture_batch_charts
from thumbnail_generator import create_marketing_images, create_short_thumbnail
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


def _enforce_master_keys(data: Dict) -> Dict:
    """Guarantees the mandatory keys (short_extraction, tldr_summary, seo_meta.h1_title) exist,
    deriving defensive fallbacks from the rest of the payload so the Shorts / X / SEO renderers
    never hit a missing key even if a fallback LLM ignores the schema."""
    yt = data.setdefault("youtube_payload", {})
    web = data.setdefault("website_article_payload", {})
    meta = yt.setdefault("metadata", {})
    sections = web.get("article_sections") or []

    short_data = yt.get("short_extraction")
    if not isinstance(short_data, dict) or not short_data.get("spoken_hook_and_body"):
        seg0 = (yt.get("segments") or [{}])[0]
        first_chart = (sections[0].get("chart_image_ref") if sections else "") or ""
        yt["short_extraction"] = {
            "short_title": str(meta.get("title", data.get("topic", "")))[:60],
            "spoken_hook_and_body": str(seg0.get("spoken_narration", ""))[:400],
            "cta_to_long_video": "Watch the full masterclass on The Bull Print for every detail and chart.",
            "chart_image_ref": first_chart,
        }

    tldr = web.get("tldr_summary")
    if not isinstance(tldr, list) or len([t for t in tldr if str(t).strip()]) < 3:
        derived = [str(s.get("direct_answer_passage", "")).strip()[:70] for s in sections[:3]]
        meta_desc = str(web.get("meta_description", "")).replace(". ", ".|").split("|")
        derived += [m.strip()[:70] for m in meta_desc]
        derived = [d for d in derived if d][:3]
        while len(derived) < 3:
            derived.append(str(meta.get("title", data.get("topic", "The Bull Print daily insight")))[:70])
        web["tldr_summary"] = derived

    seo_meta = web.get("seo_meta")
    if not isinstance(seo_meta, dict) or not str(seo_meta.get("h1_title", "")).strip():
        web["seo_meta"] = {"h1_title": web.get("seo_title") or meta.get("title") or data.get("topic", "")}

    return data


# =====================================================================
# STEP 1: GOOGLE AI STUDIO (FREE GEMINI API) MASTER JSON GENERATOR
# =====================================================================
def _parse_llm_json(text: str) -> Optional[Dict]:
    """Strips markdown fences / AI chatter and parses a raw LLM response into a JSON dict."""
    clean = (text or "").strip()
    if "```" in clean:
        clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"```\s*$", "", clean).strip()
    match = re.search(r"(\{.*\})", clean, re.DOTALL)
    if match:
        clean = match.group(1)
    try:
        data = json.loads(clean)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _free_llm_json_fallback(system_prompt: str, user_input: str) -> Optional[Dict]:
    """
    Free LLM Quota Failover: fires when GEMINI_API_KEY is depleted (429 ResourceExhausted) or errors.
    Routes (first success wins, a depleted Google token never halts the cloud pipeline):
    1. OpenAI-compatible: OPENAI_API_KEY or OPENROUTER_API_KEY with JSON response_format
    2. Repo's own multi-provider fallback engine in app/services/llm.py (Pollinations openai-fast)
    3. Direct zero-dependency Pollinations POST (always free, no keys required)
    """
    messages = [
        {"role": "system", "content": system_prompt or "You are an expert financial educator producing institutional-grade research."},
        {"role": "user", "content": (
            f"{user_input}\n\nIMPORTANT: Respond with ONLY one valid JSON object matching the required "
            f"schema. No markdown fences and no commentary.\n"
            f"MANDATORY KEYS (must be present): youtube_payload.short_extraction "
            f"(short_title, spoken_hook_and_body, cta_to_long_video, chart_image_ref), "
            f"website_article_payload.tldr_summary (exactly 3 bullets), "
            f"website_article_payload.seo_meta.h1_title."
        )},
    ]

    compat_routes = []
    openai_key = os.getenv("OPENAI_API_KEY", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if openai_key:
        compat_routes.append(("https://api.openai.com/v1/chat/completions", openai_key, os.getenv("OPENAI_MODEL", "gpt-4o-mini")))
    if openrouter_key:
        compat_routes.append(("https://openrouter.ai/api/v1/chat/completions", openrouter_key, os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")))

    for url, key, model in compat_routes:
        try:
            resp = requests.post(
                url,
                timeout=90,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.4,
                    "response_format": {"type": "json_object"},
                },
            )
            if resp.status_code == 200:
                txt = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                data = _parse_llm_json(txt)
                if data:
                    logger.success(f"✓ Free LLM failover succeeded via {model}.")
                    return data
            else:
                logger.warning(f"Free LLM route {model} returned HTTP {resp.status_code}.")
        except Exception as e:
            logger.warning(f"Free LLM route {model} failed: {e}")

    try:
        from app.services.llm import _generate_via_openai_fast

        flat_prompt = f"{messages[0]['content']}\n\n---\n\n{messages[1]['content']}"
        data = _parse_llm_json(_generate_via_openai_fast(flat_prompt))
        if data:
            logger.success("✓ Free LLM failover succeeded via app.services.llm (Pollinations openai-fast).")
            return data
    except Exception as e:
        logger.warning(f"app.services.llm fallback unavailable: {e}")

    try:
        resp = requests.post(
            "https://text.pollinations.ai/openai",
            timeout=35,
            json={"model": "openai-fast", "messages": messages, "temperature": 0.4},
        )
        if resp.status_code == 200:
            txt = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            data = _parse_llm_json(txt)
            if data:
                logger.success("✓ Free LLM failover succeeded via Pollinations direct endpoint.")
                return data
    except Exception as e:
        logger.warning(f"Pollinations direct failover failed: {e}")

    return None


def generate_master_json_via_ai_studio(topic: str, market_notes: str, chart_files: List[str]) -> Dict:
    """Calls Google AI Studio Free Tier with Structured Outputs to generate dual script + article.
    If GEMINI_API_KEY is depleted (429 ResourceExhausted) or the call errors, engages _free_llm_json_fallback."""
    api_key = os.getenv("GEMINI_API_KEY")
    prompt_file = BASE_DIR / "master_system_prompt.txt"
    schema_file = BASE_DIR / "master_schema.json"

    system_prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else "Financial Educator"
    user_input = json.dumps({
        "topic": topic,
        "market_data_notes": market_notes,
        "chart_screenshots": chart_files,
        "website_domain": "flipzon.work.gd"
    })

    if api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            schema_dict = json.loads(schema_file.read_text(encoding="utf-8")) if schema_file.exists() else {}

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
            return _enforce_master_keys(json.loads(response.text))
        except Exception as e:
            logger.warning(f"GEMINI_API_KEY depleted or Google AI Studio call failed: {e}")
            logger.info("🔁 Engaging free LLM quota failover (OpenRouter / OpenAI / Pollinations)...")
            fallback_data = _free_llm_json_fallback(system_prompt, user_input)
            if fallback_data:
                return _enforce_master_keys(fallback_data)
            logger.warning("All free LLM providers exhausted — using local payload benchmark.")

    # Fallback to local payload benchmark
    logger.info("ℹ️ Using local payload benchmark.")
    payload_file = BASE_DIR / "payload.json"
    data = json.loads(payload_file.read_text(encoding="utf-8"))
    data["topic"] = topic
    return _enforce_master_keys(data)


# =====================================================================
# STEP 2: PUSH PAYLOAD TO KAGGLE & STATE-AWARE ADAPTIVE BACKOFF POLLER
# =====================================================================
def run_kaggle_gpu_renderer(
    payload: Dict,
    chart_files: List[str],
    yt_thumb: Path,
    mission: AriaMissionControl,
    short_thumb_path: Optional[Path] = None,
) -> Tuple[str, List[str], str, int]:
    """
    Pushes payload + charts to private Kaggle dataset, triggers T4 GPU kernel,
    and runs a 26-minute state-aware poller. Returns (long_video_id, timestamps,
    short_video_id, oauth_slot_used). Falls back to local engine if Kaggle is
    unconfigured.
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
        logger.info("ℹ️ No 9:16 Short generated in local fallback mode (Kaggle GPU required).")
        return vid_id, timestamps, "", 0

    # 1. Stage Kaggle Dataset — include the YT OAuth quota pool so the GPU kernel rotates slots
    if short_thumb_path and Path(short_thumb_path).exists():
        shutil.copy2(short_thumb_path, KAGGLE_STAGE_DIR / "yt_short_thumb.jpg")
        logger.info(f"🎬 Staged 9:16 Shorts shelf thumbnail into Kaggle dataset")
    pool_json = os.getenv("YT_OAUTH_POOL_JSON", "")
    if not pool_json:
        local_pool = BASE_DIR / "data" / "youtube_tokens" / "oauth_pool.json"
        if local_pool.exists():
            pool_json = local_pool.read_text(encoding="utf-8")
    if pool_json:
        try:
            (KAGGLE_STAGE_DIR / "yt_oauth_pool.json").write_text(pool_json, encoding="utf-8")
            logger.info(f"🔐 Staged YT OAuth quota pool ({len(json.loads(pool_json))} slot(s)) into Kaggle dataset")
        except Exception as e:
            logger.warning(f"Could not stage YT OAuth pool: {e}")

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

    # Surface which Google Cloud OAuth slot served the upload → Mission Control 🔑 line
    oauth_slot_used = int(result_data.get("oauth_slot_used") or 0)
    if oauth_slot_used > 0:
        mission.update_stage("kaggle_gpu", f"🔥 Encoding NVENC + Whisper (done)", f"🔑 YT Quota Slot #{oauth_slot_used}")
    return result_data["youtube_video_id"], result_data["timestamps_log"], result_data.get("short_video_id", ""), oauth_slot_used


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

    # 🛡️ THE COMPLIANCE GATE (zero-tolerance SEBI + YouTube audit & 30-day freshness)
    mission.update_stage("gemini", "🛡️ Auditing Compliance Gate...", "SEBI regex + freshness + LLM auditor")
    try:
        from app.services.compliance_gate import ComplianceGate, ComplianceGateError

        payload = ComplianceGate.audit_and_enforce(payload)
        mission.update_stage("gemini", f"✅ Generated + Compliance-Approved (`{payload['campaign_id']}`)")
    except ComplianceGateError as e:
        logger.error(str(e))
        mission.update_stage("gemini", "🚨 COMPLIANCE HALT", str(e)[:120])
        _alert = os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")
        if _alert:
            try:
                import urllib.request

                _body = urllib.parse.urlencode({
                    "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
                    "text": "🚨 *CRITICAL COMPLIANCE HALT*\n" + str(e)[:400],
                    "parse_mode": "Markdown",
                }).encode()
                urllib.request.urlopen(urllib.request.Request(
                    f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage", _body
                ))
            except Exception:
                pass
        raise SystemExit(1)
    slug = payload["campaign_id"]
    mission.update_stage("gemini", f"✅ Generated (`{slug}`)")

    # 4. Generate Thumbnail & Enter 5-Min Human-in-the-Loop Approval Gate
    mission.update_stage("thumbnail", "🎨 Rendering Pillow Graphics...")
    headline_words = payload["youtube_payload"]["metadata"]["thumbnail_top_text"].split()[:4]
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

    # High-CTR vertical shelf thumb for the 9:16 Short (Khaby-style top-chart/bottom-avatar)
    try:
        mission.update_stage("thumbnail", "🎨 Rendering 9:16 Shorts Shelf Thumbnail...")
        short_thumb_path = create_short_thumbnail(primary_chart, avatar_1, headline_words, slug)
        logger.info(f"🎬 Shorts shelf thumbnail staged: {short_thumb_path.name}")
    except Exception as s_err:
        short_thumb_path = None
        logger.warning(f"Shorts thumbnail generation failed (Short falls back to long thumb): {s_err}")

    # 5. Render Video via Kaggle GPU NVENC / Faster-Whisper
    mission.update_stage("kaggle_gpu", "🚀 Dispatching to Kaggle Dual-T4 GPU...")
    yt_video_id, timestamps_log, short_video_id, oauth_slot_used = run_kaggle_gpu_renderer(
        payload, chart_files, yt_thumb, mission, short_thumb_path=short_thumb_path
    )
    if short_video_id:
        logger.info(f"🎬 9:16 #Shorts published: https://youtube.com/shorts/{short_video_id}")

    # 6. Generate MDX Article + Deploy to Vercel + Ping Search Indexers
    mission.update_stage("vercel", "📝 Compiling MDX & IndexNow Ping...")
    mdx_path = generate_website_article_file(payload, yt_video_id, timestamps_log)
    live_url = publish_and_index_article(mdx_path, chart_files, slug)

    # 7. Distribute the 3-tweet X/Twitter thread (graceful skip without X credentials)
    try:
        from app.services.x_thread_publisher import publish_x_thread

        chart_paths = [str(BASE_DIR / "assets" / "charts" / cf) for cf in chart_files]
        x_thread_status = publish_x_thread(payload, chart_paths, yt_video_id, short_video_id, live_url)
    except Exception as x_err:
        x_thread_status = f"Error ({x_err.__class__.__name__})"
        logger.warning(f"X thread distribution failed: {x_err}")
    logger.info(f"🐦 X Thread status: {x_thread_status}")

    final_note = f"🐦 X Thread: {x_thread_status}"
    if short_video_id:
        final_note = f"🎬 Short: youtube.com/shorts/{short_video_id} · 🐦 X Thread: {x_thread_status}"
    if oauth_slot_used > 0:
        final_note = f"🔑 YT Quota Slot #{oauth_slot_used} · " + final_note
    mission.update_stage("vercel", f"✅ Live & Indexed (`{live_url}`)", final_note)

    print(f"\n🎉 Cloud pipeline completed successfully! Live URL: {live_url}")
    print(f"🎬 Short: {'youtube.com/shorts/' + short_video_id if short_video_id else 'skipped'} | 🐦 X Thread: {x_thread_status}")


if __name__ == "__main__":
    asyncio.run(main())
